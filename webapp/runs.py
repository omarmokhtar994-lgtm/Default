# © 2026 Omar Mokhtar. All rights reserved.
"""Run queue: check an uploaded workbook, queue it, run the production runner,
score the release gates, zip the results, and expire them after 30 days.

Statuses: CHECKING -> REJECTED | QUEUED -> GATE -> RUNNING -> SCORING ->
DONE | REVIEW | FAILED (REVIEW: validated, but the release verdict asks for a
person's review before publishing); a run can also end STOPPED (owner pressed Stop), INTERRUPTED
(the server restarted during it) or EXPIRED (files deleted after 30 days).
STOPPED, INTERRUPTED and FAILED runs can be resumed from their checkpoints.

The website never judges a schedule itself: DONE means the runner exited 0
(its independent validator approved the schedule); anything else is shown as
not approved, with the runner's exit code and the release verdict lines.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.utils import secure_filename

from . import gate
from . import outcome as engine_outcome
from .results import metrics, summarize
from .store import Store

KEEP_DAYS = 30  # run files, by default (SCHEDULER_RUN_FILES_DAYS: 30 to 60)
RECORD_DAYS = 395  # the record of actions: 13 months, like schedules and attendance
ACTIVE = ("GATE", "RUNNING", "SCORING")
RESUMABLE = ("STOPPED", "INTERRUPTED", "FAILED")
MODES = ("QUICK", "DEEP", "OVERNIGHT", "SMOKE")
# Same automatic seeds as the Colab notebooks (measured, evidence/seed_portfolio_ab):
# None = the runner's own default (DEEP: best of 4, OVERNIGHT: best of 6).
AUTO_SEEDS = {"QUICK": 2, "DEEP": None, "OVERNIGHT": None, "SMOKE": 1}
# The Colab notebooks' advanced settings. "workbook" (or nothing) = what the
# workbook's Instructions sheet says, and no flag is passed.
OPTIONS = {
    "language_window": ("--language-working-window", ("OFF", "MINIMUM_ROWS", "ALL_ROWS", "REQUIRED_LANGUAGE_ONLY")),
    "coverage_measure": ("--coverage-objective-weighting", ("INTERVAL_COUNT", "VOLUME_WEIGHTED")),
    "stage": ("--stage", ("FULL_SCHEDULE", "BEFORE_BREAKS_ONLY")),
}
OPTION_LABELS = {"OFF": "Off", "MINIMUM_ROWS": "Minimum rows", "ALL_ROWS": "All rows",
                 "REQUIRED_LANGUAGE_ONLY": "Required language only", "INTERVAL_COUNT": "Interval count",
                 "VOLUME_WEIGHTED": "Volume weighted", "FULL_SCHEDULE": "Full schedule",
                 "BEFORE_BREAKS_ONLY": "Before breaks only"}


def parse_options(form) -> Tuple[Dict[str, str], str]:
    """(options, problem) from the upload form; only listed values are accepted."""
    chosen: Dict[str, str] = {}
    for name, (_, allowed) in OPTIONS.items():
        value = (form.get(name) or "workbook").strip()
        if value == "workbook" or (name == "stage" and value == "FULL_SCHEDULE"):
            continue
        if value not in allowed:
            return {}, f"Choose one of the listed options for {name.replace('_', ' ')}."
        chosen[name] = value
    return chosen, ""
CHECK_TIMEOUT_SECONDS = 300
SCORE_TIMEOUT_SECONDS = 1800
STOP_GRACE_SECONDS = 30
FINAL_SCHEDULE_SUFFIX = "_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
SHORTFALL_SCHEDULE_SUFFIX = "_HARD_RULE_SHORTFALL_SCHEDULE.xlsx"
BEFORE_SCHEDULE_SUFFIX = "_BEST_BEFORE_BREAKS_SCHEDULE.xlsx"


class RunQueue:
    def __init__(self, store: Store, package_root: Path, runs_root: Path, runner_cmd: Optional[List[str]] = None,
                 parallel: int = 1, check_cmd: Optional[List[str]] = None, score_cmd: Optional[List[str]] = None,
                 gate_cmd: Optional[List[str]] = None, keep_days: int = KEEP_DAYS):
        self.store = store
        self.keep_days = keep_days  # run files (zips, results); the run's row and figures stay
        self.package_root = Path(package_root)
        self.runs_root = Path(runs_root)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.gate_dir = self.runs_root / "_gate"
        self.parallel = max(1, int(parallel))
        py = [sys.executable]
        self.runner_cmd = runner_cmd or py + ["-u", str(self.package_root / "runners" / "rc922_runner.py")]
        self.check_cmd = check_cmd or py + [str(self.package_root / "tools" / "check_input_workbook.py")]
        self.score_cmd = score_cmd or py + [str(self.package_root / "tools" / "release_gate_report.py")]
        self.gate_cmd = gate_cmd or ["bash", "run_tests.sh"]
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._procs: Dict[str, subprocess.Popen] = {}
        self._stopping: set = set()
        self._threads: List[threading.Thread] = []
        self.schedules = None  # the ScheduleBook (Phase N), set by the website
        self.days = None  # the DayBook (attendance and actual breaks), set by the website
        self.recover()

    # ------------------------------------------------------------ paths
    def run_dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def results_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "results"

    def log_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.log"

    def zip_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "results.zip"

    def input_path(self, run_id: str) -> Optional[Path]:
        found = sorted((self.run_dir(run_id) / "input").glob("*.xlsx"))
        return found[0] if found else None

    def final_schedule(self, run_id: str) -> Optional[Path]:
        results = self.results_dir(run_id)
        if not results.is_dir():
            return None
        found = [p for p in results.rglob(f"*{FINAL_SCHEDULE_SUFFIX}") if "debug" not in p.parts]
        return min(found, key=lambda p: (len(p.parts), str(p))) if found else None

    def before_schedule(self, run_id: str) -> Optional[Path]:
        results = self.results_dir(run_id)
        if not results.is_dir():
            return None
        found = [p for p in results.rglob(f"*{BEFORE_SCHEDULE_SUFFIX}") if "debug" not in p.parts]
        return min(found, key=lambda p: (len(p.parts), str(p))) if found else None

    def keep_schedules(self, run_id: str) -> None:
        """Copy the run's schedules in as versions (Phase N); a failure here never fails the run."""
        if self.schedules is None:
            return
        try:
            self.schedules.ensure(self.store.get_run(run_id), self.input_path(run_id), self.final_schedule(run_id),
                                  self.before_schedule(run_id))
        except Exception as exc:  # the run's own files stay authoritative; say why the copy failed
            with self.log_path(run_id).open("a", encoding="utf-8") as log:
                log.write(f"\n(website) could not keep this run's schedules as versions: {exc!r}\n")

    def shortfall_schedule(self, run_id: str) -> Optional[Path]:
        """The schedule the engine attaches when no schedule meets every hard rule."""
        results = self.results_dir(run_id)
        if not results.is_dir():
            return None
        found = [p for p in results.rglob(f"*{SHORTFALL_SCHEDULE_SUFFIX}") if "debug" not in p.parts]
        return min(found, key=lambda p: (len(p.parts), str(p))) if found else None

    def log_tail(self, run_id: str, lines: int = 80) -> str:
        path = self.log_path(run_id)
        if not path.is_file():
            return ""
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 64 * 1024))
            text = handle.read().decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])

    # ------------------------------------------------------------ lifecycle
    def recover(self) -> None:
        """After a restart: runs that were in flight are INTERRUPTED (resumable);
        QUEUED runs stay queued and are picked up by the worker."""
        for run in self.store.runs_with_status("CHECKING", *ACTIVE):
            self.store.update_run(run["id"], status="INTERRUPTED", finished=time.time(),
                                  message="The server restarted during this run. "
                                          "Press Resume to continue from its checkpoints.")

    def start(self) -> None:
        for n in range(self.parallel):
            thread = threading.Thread(target=self._worker, name=f"run-worker-{n}", daemon=True)
            thread.start()
            self._threads.append(thread)
        cleaner = threading.Thread(target=self._cleaner, name="run-cleaner", daemon=True)
        cleaner.start()
        self._threads.append(cleaner)
        self._wake.set()

    def submit(self, user_id: int, upload_path: Path, mode: str, workbook_name: str,
               options: Optional[Dict[str, str]] = None, program: str = "", week_start: str = "") -> str:
        """Check the uploaded workbook now (seconds) and queue it if accepted."""
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        run_id = secrets.token_hex(6)
        safe = secure_filename(workbook_name) or "workbook.xlsx"
        if not safe.lower().endswith(".xlsx"):
            safe += ".xlsx"
        target = self.run_dir(run_id) / "input" / safe
        target.parent.mkdir(parents=True)
        shutil.move(str(upload_path), target)
        self.store.add_run(run_id, user_id, workbook_name, mode, "CHECKING",
                           options=json.dumps(options) if options else "", program=program, week_start=week_start)
        try:
            proc = subprocess.run(self.check_cmd + [str(target)], cwd=str(self.package_root),
                                  capture_output=True, text=True, timeout=CHECK_TIMEOUT_SECONDS)
            output = ((proc.stdout or "") + (proc.stderr or "")).strip()
            accepted = proc.returncode == 0
        except subprocess.TimeoutExpired:
            output, accepted = f"The workbook check did not finish within {CHECK_TIMEOUT_SECONDS} s.", False
        except OSError as exc:
            output, accepted = f"The workbook check could not start: {exc}", False
        self.log_path(run_id).write_text(output + "\n", encoding="utf-8")
        if accepted:
            self.store.update_run(run_id, status="QUEUED", message="Workbook accepted; waiting for its turn.")
            self._wake.set()
        else:
            self.store.update_run(run_id, status="REJECTED", finished=time.time(),
                                  message=output[-4000:] or "The workbook check refused this file.")
        return run_id

    def resume(self, run_id: str) -> bool:
        run = self.store.get_run(run_id)
        if run is None or run["status"] not in RESUMABLE or self.input_path(run_id) is None:
            return False
        self.store.update_run(run_id, status="QUEUED", resume=1, exit_code=None, finished=None,
                              message="Resuming from checkpoints; waiting for its turn.")
        self._wake.set()
        return True

    def start_from(self, run_id: str, user_id: int, mode: str) -> Optional[str]:
        """A new run of the same workbook, program, week and settings (for
        example the real run after a readiness check). None if the workbook is
        no longer on the server or the mode is not a run mode."""
        run = self.store.get_run(run_id)
        source = self.input_path(run_id)
        if run is None or source is None or mode not in MODES:
            return None
        incoming = self.runs_root / "_incoming"
        incoming.mkdir(exist_ok=True)
        copy = incoming / f"{secrets.token_hex(8)}.upload"
        shutil.copyfile(source, copy)
        return self.submit(user_id, copy, mode, run["workbook"], run_options(run) or None,
                           program=run.get("program") or "", week_start=run.get("week_start") or "")

    def stop(self, run_id: str) -> bool:
        """Ask a running run to stop safely (SIGINT keeps its checkpoints),
        then end its whole process group if it has not stopped in 30 s."""
        run = self.store.get_run(run_id)
        if run is None:
            return False
        if run["status"] == "QUEUED":
            self.store.update_run(run_id, status="STOPPED", finished=time.time(),
                                  message="Stopped before it started. Press Resume to queue it again.")
            return True
        with self._lock:
            proc = self._procs.get(run_id)
            if run["status"] not in ACTIVE:
                return False
            self._stopping.add(run_id)
        if proc is not None and proc.poll() is None:
            _signal_group(proc, signal.SIGINT)
            threading.Thread(target=_escalate, args=(proc,), daemon=True).start()
        return True

    # ------------------------------------------------------------ the work
    def runner_command(self, run: Dict[str, Any], skip_guards: bool) -> List[str]:
        run_id = run["id"]
        cmd = list(self.runner_cmd) + [
            "--package-root", str(self.package_root),
            "--results-root", str(self.results_dir(run_id)),
            "--mode", run["mode"],
            "--num-workers", str(max(1, (os.cpu_count() or 1) // self.parallel)),
        ]
        options = run_options(run)
        cmd += ["--stage", options.get("stage", "FULL_SCHEDULE")]
        for name in ("language_window", "coverage_measure"):
            if name in options:
                cmd += [OPTIONS[name][0], options[name]]
        seeds = AUTO_SEEDS[run["mode"]]
        if seeds:
            cmd += ["--seeds", str(seeds)]
        cmd += ["--input", str(self.input_path(run_id))]
        if skip_guards:
            cmd += ["--skip-guards"]
        cmd += ["--resume"]  # as the notebooks: a rerun continues from checkpoints
        return cmd

    def _claim(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            queued = self.store.runs_with_status("QUEUED")
            if not queued:
                return None
            run = queued[0]
            self.store.update_run(run["id"], status="GATE", started=time.time(),
                                  message="Checking the installed package (safety gate).")
            return self.store.get_run(run["id"])

    def _worker(self) -> None:
        while True:
            run = self._claim()
            if run is None:
                self._wake.wait(5)
                self._wake.clear()
                continue
            try:
                self._execute(run)
            except Exception as exc:  # the worker must survive; the run shows why it failed
                self.store.update_run(run["id"], status="FAILED", finished=time.time(),
                                      message=f"The website hit an error running this: {exc!r}")
            finally:
                with self._lock:
                    self._procs.pop(run["id"], None)
                    self._stopping.discard(run["id"])

    def _execute(self, run: Dict[str, Any]) -> None:
        run_id = run["id"]
        try:
            stamp = gate.ensure(self.package_root, self.gate_dir, self.gate_cmd)
        except gate.GateFailed as exc:
            self.store.update_run(run_id, status="FAILED", finished=time.time(),
                                  message=f"Not started: {exc}\nNo run can start until the safety gate passes.")
            return
        if self._stopped(run_id):
            return
        cmd = self.runner_command(run, skip_guards=passed(stamp))
        results = self.results_dir(run_id)
        results.mkdir(parents=True, exist_ok=True)
        with self.log_path(run_id).open("a", encoding="utf-8") as log:
            log.write("\n$ " + " ".join(cmd) + "\n")
            log.flush()
            proc = subprocess.Popen(cmd, cwd=str(self.package_root), stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=(os.name == "posix"))
            with self._lock:
                self._procs[run_id] = proc
            self.store.update_run(run_id, status="RUNNING", message="Building the schedule.")
            code = proc.wait()
        if self._stopped(run_id, code):
            return
        self.store.update_run(run_id, status="SCORING", exit_code=code, message="Scoring the release gates.")
        # A readiness check builds no schedule, so release scoring has nothing to judge.
        verdict = "" if run["mode"] == "SMOKE" else self._score(run_id)
        self._save_summary(run_id)
        self._zip(run_id)
        found = engine_outcome.read(results)
        if found is not None:  # kept on the row: the files go after 30 days
            self.store.update_run(run_id, engine_outcome=json.dumps(engine_outcome.compact(found)))
        if run["mode"] == "SMOKE":
            status, message = readiness(found)
        elif code == 0:
            status, message = outcome(run["mode"], verdict)
        else:
            status = "FAILED"
            message = (str(found.get("headline") or "") if found else "") or (
                f"Not approved: the runner exited with code {code} and the engine wrote no outcome. "
                "The log below and the files in the download say why.")
        if status in ("DONE", "REVIEW") and run["mode"] != "SMOKE":
            # before the status says finished: a finished run's work is over (clean-up may follow at once)
            self.store.update_run(run_id, message="Keeping the schedules as versions.")
            self.keep_schedules(run_id)
        self.store.update_run(run_id, status=status, exit_code=code, verdict=verdict,
                              finished=time.time(), message=message)
        self._stamp_outcome(run_id, status)

    def _stopped(self, run_id: str, code: Optional[int] = None) -> bool:
        with self._lock:
            stopping = run_id in self._stopping
        if stopping:
            if self.results_dir(run_id).is_dir():
                self._zip(run_id)
            self.store.update_run(run_id, status="STOPPED", exit_code=code, finished=time.time(),
                                  message="Stopped. Its checkpoints are kept: press Resume to continue.")
        return stopping

    def _score(self, run_id: str) -> str:
        results = self.results_dir(run_id)
        cmd = self.score_cmd + [str(results), "--out-dir", str(results / "_gate_report")]
        try:
            proc = subprocess.run(cmd, cwd=str(self.package_root), capture_output=True, text=True,
                                  timeout=SCORE_TIMEOUT_SECONDS)
            output = (proc.stdout or "") + (proc.stderr or "")
        except (subprocess.TimeoutExpired, OSError) as exc:
            output = f"release gate scoring did not complete: {exc}\n"
        with self.log_path(run_id).open("a", encoding="utf-8") as log:
            log.write("\n" + output)
        lines = [line.strip() for line in output.splitlines() if line.startswith("RELEASE VERDICT")]
        return "\n".join(lines) or "No release verdict was produced (see the log)."

    def gate_pending(self) -> bool:
        """True while the installed package has no PASS stamp (the next run runs the gate)."""
        return gate.passed_stamp(self.gate_dir, self.package_root) is None

    def summary_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "summary.json"

    def _save_summary(self, run_id: str) -> None:
        try:
            summary = summarize(self.results_dir(run_id))
        except Exception as exc:  # a summary is a convenience; the run's own files stay authoritative
            with self.log_path(run_id).open("a", encoding="utf-8") as log:
                log.write(f"\n(website) could not read the run summary: {exc!r}\n")
            return
        if summary is not None:
            self.summary_path(run_id).write_text(json.dumps(summary), encoding="utf-8")
            # The compact figures live on the run row, so a program's history
            # outlives the run's files (deleted after 30 days).
            self.store.update_run(run_id, metrics=json.dumps(metrics(summary)))

    def _stamp_outcome(self, run_id: str, status: str) -> None:
        """Keep the run's outcome with its figures (the status becomes EXPIRED later)."""
        run = self.store.get_run(run_id) or {}
        try:
            figures = json.loads(run.get("metrics") or "")
        except ValueError:
            return
        figures["outcome"] = status
        self.store.update_run(run_id, metrics=json.dumps(figures))

    def summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(self.summary_path(run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _zip(self, run_id: str) -> None:
        target = self.zip_path(run_id)
        partial = target.with_suffix(".zip.part")
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.results_dir(run_id).rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(self.results_dir(run_id)))
            if self.log_path(run_id).is_file():
                archive.write(self.log_path(run_id), "run.log")
        partial.replace(target)

    # ------------------------------------------------------------ retention
    def cleanup(self, now: Optional[float] = None) -> int:
        """Delete the files of runs older than ``keep_days`` (30 to 60); the row stays as EXPIRED."""
        cutoff = (time.time() if now is None else now) - self.keep_days * 86400
        expired = 0
        for run in self.store.list_runs(limit=1_000_000):
            if run["status"] in ("EXPIRED", "QUEUED", "CHECKING") + ACTIVE or run["created"] >= cutoff:
                continue
            shutil.rmtree(self.run_dir(run["id"]), ignore_errors=True)
            self.store.update_run(run["id"], status="EXPIRED",
                                  message=f"Files deleted after {self.keep_days} days.")
            expired += 1
        return expired

    def backfill(self) -> int:
        """Runs that finished before program history (Phase K) or the week view
        (Phase M) existed get their figures from their files, while the files
        are still there."""
        filled = 0
        for run in self.store.list_runs(limit=1_000_000):
            if run["status"] not in ("DONE", "REVIEW") or not self.results_dir(run["id"]).is_dir():
                continue
            try:
                kept = json.loads(run.get("metrics") or "{}")
            except ValueError:
                kept = {}
            if isinstance(kept, dict) and kept.get("intervals"):  # already has the week view's figures
                continue
            self._save_summary(run["id"])
            self._stamp_outcome(run["id"], run["status"])
            filled += bool((self.store.get_run(run["id"]) or {}).get("metrics"))
        return filled

    def backfill_outcomes(self) -> int:
        """Runs finished before the engine's outcome was kept on the row get it
        from their files. A readiness check judged by the old rule (the
        runner's exit code, which is 2 for every readiness check) is judged
        again by the engine's own outcome."""
        filled = 0
        for run in self.store.list_runs(limit=1_000_000):
            if run.get("engine_outcome") or run["status"] in ACTIVE + ("QUEUED", "CHECKING", "EXPIRED"):
                continue
            found = engine_outcome.read(self.results_dir(run["id"]))
            if found is None:
                continue
            fields: Dict[str, Any] = {"engine_outcome": json.dumps(engine_outcome.compact(found))}
            if run["mode"] == "SMOKE" and run["status"] in ("DONE", "FAILED"):
                fields["status"], fields["message"] = readiness(found)
            self.store.update_run(run["id"], **fields)
            filled += 1
        return filled

    def backfill_schedules(self) -> int:
        """Finished runs from before Phase N keep their schedules as versions, while their files exist."""
        kept = 0
        if self.schedules is None:
            return kept
        for run in self.store.list_runs(limit=1_000_000):
            if run["status"] in ("DONE", "REVIEW") and run["mode"] != "SMOKE" and not self.schedules.versions(run["id"]) \
                    and self.final_schedule(run["id"]) is not None:
                self.keep_schedules(run["id"])
                kept += bool(self.schedules.versions(run["id"]))
        return kept

    def _cleaner(self) -> None:
        try:
            self.backfill_schedules()
        except Exception as exc:  # versions for older runs are a convenience; say why it failed
            print(f"schedule backfill failed: {exc!r}", file=sys.stderr, flush=True)
        try:
            self.backfill_outcomes()
        except Exception as exc:  # a convenience for older runs; say why it failed
            print(f"outcome backfill failed: {exc!r}", file=sys.stderr, flush=True)
        try:
            self.backfill()
        except Exception as exc:  # history for older runs is a convenience; say why it failed
            print(f"history backfill failed: {exc!r}", file=sys.stderr, flush=True)
        while True:
            try:
                self.cleanup()
                if self.schedules is not None:
                    self.schedules.cleanup()
                if self.days is not None:
                    self.days.cleanup()
                self.store.delete_events_before(time.time() - RECORD_DAYS * 86400)
            except Exception as exc:  # keep cleaning tomorrow; say why today failed
                print(f"run cleanup failed: {exc!r}", file=sys.stderr, flush=True)
            time.sleep(3600)


def run_options(run: Dict[str, Any]) -> Dict[str, str]:
    """The run's advanced settings; anything not listed is ignored (fail closed)."""
    try:
        raw = json.loads(run.get("options") or "{}")
    except ValueError:
        return {}
    return {k: v for k, v in raw.items() if k in OPTIONS and v in OPTIONS[k][1]}


def readiness(found: Optional[Dict[str, Any]]) -> tuple:
    """(status, message) for a readiness check, from the engine's own outcome.

    Not from the runner's exit code: the runner also scores release gates,
    which a run that builds no schedule always fails, so every readiness
    check used to read "Not approved". No outcome at all is "not ready"."""
    if found and found.get("outcome_code") == engine_outcome.READY:
        return "DONE", ("Ready to run: the workbook was read, every input check passed, and the hard rules "
                        "can all be met together. Nothing was scheduled yet.")
    if found:
        return "FAILED", str(found.get("headline") or "Not ready")
    return "FAILED", "Not ready: the engine wrote no outcome for this check. The log below says why."


def outcome(mode: str, verdict: str) -> tuple:
    """(status, message) for a run whose runner exited 0. The runner exits 0
    for RELEASABLE and for REVIEW_REQUIRED alike (only NOT_RELEASABLE fails
    it), so the label follows the run-level release verdict, never a guess."""
    run_line = next((line for line in verdict.splitlines() if line.startswith("RELEASE VERDICT (run):")), "")
    words = run_line.split(":", 1)[1].split() if run_line else []
    level = words[0] if words else ""  # the verdict word; a note may follow it
    if level == "RELEASABLE":
        return "DONE", "Approved: the independent validator passed this schedule and its release verdict is RELEASABLE."
    return "REVIEW", ("The independent validator passed this schedule, but its release verdict is "
                      f"{level or 'missing'}: a person must review it before it is published. "
                      "The verdict lines below and the schedule's Read Me First tab say what to check.")


def passed(stamp: Optional[dict]) -> bool:
    return bool(stamp) and stamp.get("status") == "PASS"


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), sig)
        else:
            proc.send_signal(sig)
    except (ProcessLookupError, PermissionError):
        pass


def _escalate(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        _signal_group(proc, signal.SIGTERM)
