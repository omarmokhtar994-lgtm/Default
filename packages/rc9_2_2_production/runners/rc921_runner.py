#!/usr/bin/env python3
"""RC9.2.2 scenario runner — shared core for every Colab variant.

Runs one or more scenarios from SCENARIOS.json at their configured budget, then
scores the release gates. Designed for SHARDED parallel execution: launch
several Colab instances and give each a different --only or --shard.

Every run is self-contained. Nothing here depends on Drive, on a notebook, or
on any earlier run, so a shard that dies can simply be re-run.

Usage
-----
    python rc921_runner.py --package-root . --results-root results
    python rc921_runner.py --only CRICUT_VOICE,NMG_SP
    python rc921_runner.py --shard 0 --shards 4          # instance 0 of 4
    python rc921_runner.py --time-limit 5400             # override the budget
    python rc921_runner.py --gate-only                   # just re-score results
    python rc921_runner.py --mode QUICK --seeds 2        # best of 2 seeds per scenario
    python rc921_runner.py --mode DEEP                   # best of 4 x 1 h seeds (measured default)
    python rc921_runner.py --mode DEEP --single-run      # one 4 h run instead

Seeds: the same workbook solved with a different solver seed gives a different
schedule. --seeds N runs N seeds per scenario through engine/RUN_PORTFOLIO.py
and keeps the best validated after-breaks schedule; the best before-breaks sheet
of any seed is kept alongside it. Measured (evidence/seed_portfolio_ab/): best of
2 x 3600 s beat a single 3600 s run by +8.5 target intervals summed over 7 cases,
with no before-breaks sheet lower. Seeds run side by side when there are at
least 2 cores per seed (2 workers each, as measured), otherwise one after another.

DEEP and OVERNIGHT: measured against one long run on the same engine
(evidence/seed_portfolio_ab/RESULT.txt, rule registered before the runs), the
best of four 1 h QUICK seeds tied one 4 h DEEP run where that run finished
(Voice 248, NMG_SP 122) and the single DEEP run produced no schedule at all on
Chat and on the 24x7 case (killed at 13-14 GB in joint refinement). So DEEP
now means best of 4 x 3600 s QUICK seeds and OVERNIGHT best of 6 x 3600 s.
--seeds N changes the count, --time-limit the per-seed budget, and
--single-run restores one long DEEP/OVERNIGHT run.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def load_manifest(root: Path) -> dict:
    path = root / "SCENARIOS.json"
    if not path.exists():
        raise SystemExit(f"SCENARIOS.json not found under {root}. "
                         "Pass --package-root pointing at the unzipped package.")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_inputs(root: Path, scenarios: list) -> list:
    """Refuse to run a scenario whose workbook does not match the manifest hash.

    A run against a silently different input produces evidence that cannot be
    compared with anything, which is worse than not running it.
    """
    import hashlib
    problems = []
    for row in scenarios:
        path = root / "inputs" / row["input"]
        if not path.exists():
            problems.append(f"{row['scenario_id']}: missing input {row['input']}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != row["input_sha256"]:
            problems.append(f"{row['scenario_id']}: input sha256 {actual[:16]} "
                            f"!= manifest {row['input_sha256'][:16]}")
    return problems


def verify_engine(root: Path, manifest: dict) -> list:
    """The engine that will run must be the engine the manifest names (RC5 F-17)."""
    import hashlib
    engine = root / "engine" / "_tools" / "l632_universal_scheduler.py"
    if not engine.is_file():
        return [f"missing engine: {engine}"]
    actual = hashlib.sha256(engine.read_bytes()).hexdigest()
    expected = str(manifest.get("engine_sha256") or "")
    return [] if expected and actual == expected else [
        f"engine sha256 {actual[:16]} != manifest {expected[:16] or 'missing'}"]


def run_runtime_check(root: Path) -> bool:
    """Reject a solver run before any optimization budget is consumed."""
    checker = root / "tools" / "runtime_environment_check.py"
    if not checker.is_file():
        print(f"RUNTIME CHECK FAILED: missing {checker}", file=sys.stderr)
        return False
    log("checking pinned runtime and CP-SAT compatibility")
    proc = subprocess.run([sys.executable, str(checker)], capture_output=True, text=True, timeout=120)
    if proc.returncode:
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        return False
    log("runtime check PASS")
    return True


def _terminate_process_tree(proc: subprocess.Popen, grace_seconds: float = 15.0) -> None:
    """Terminate a run and every descendant (portfolio seeds, engines, joint children)."""
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=grace_seconds)
        return
    except (ProcessLookupError, ChildProcessError):
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, ChildProcessError):
        pass
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass


def show_failure_logs(logfiles, lines: int = 25) -> None:
    """Print the end of each log of a failed run into the notebook.

    A failed run used to report only 'exit=1' and 'winner seed=None'; the reason
    sat in a log file the notebook never showed (first Colab production run).
    """
    for path in logfiles:
        path = Path(path)
        if not path.is_file():
            print(f"  (no log at {path})", flush=True)
            continue
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        print(f"---- last {len(tail)} lines of {path} ----", flush=True)
        for line in tail:
            print(f"  {line}", flush=True)


def _run_engine(command: list, logfile: Path, timeout: int) -> int:
    """Run in its own process group so a timeout or interrupt stops every descendant.

    subprocess.run(timeout=...) kills only the direct child: a timed-out
    portfolio left its seed runs and their engines running into the next
    scenario (audit F-05). RC5's runner had this; it is restored here.
    """
    with logfile.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT,
                                start_new_session=(os.name == "posix"))
        try:
            return int(proc.wait(timeout=timeout))
        except KeyboardInterrupt:
            _terminate_process_tree(proc)
            raise
        except subprocess.TimeoutExpired:
            _terminate_process_tree(proc)
            raise


def select(scenarios: list, only: str, shard: int, shards: int) -> list:
    if only:
        wanted = {s.strip().upper() for s in only.split(",") if s.strip()}
        unknown = wanted - {r["scenario_id"] for r in scenarios}
        if unknown:
            raise SystemExit(f"Unknown scenario id(s): {sorted(unknown)}")
        return [r for r in scenarios if r["scenario_id"] in wanted]
    if shards > 1:
        return [r for i, r in enumerate(scenarios) if i % shards == shard]
    return list(scenarios)


def mode_default_budget(args) -> int:
    return int(args.time_limit or {"SMOKE": 900, "QUICK": 3600,
                                   "DEEP": 14400, "OVERNIGHT": 21600}[args.mode or "DEEP"])


# DEEP / OVERNIGHT as seed portfolios of 1 h QUICK runs (see module docstring).
PORTFOLIO_DEPTH_SEEDS = {"DEEP": 4, "OVERNIGHT": 6}
PORTFOLIO_SEED_MODE = "QUICK"
PORTFOLIO_SEED_SECONDS = 3600


def depth_plan(args, row: dict) -> tuple:
    """(engine mode, budget per run in seconds, number of seeds) for one scenario."""
    mode = args.mode or row.get("mode", "DEEP")
    requested = int(getattr(args, "seeds", 0) or 0)
    if mode in PORTFOLIO_DEPTH_SEEDS and not getattr(args, "single_run", False):
        budget = int(args.time_limit) if args.time_limit else PORTFOLIO_SEED_SECONDS
        return PORTFOLIO_SEED_MODE, budget, requested or PORTFOLIO_DEPTH_SEEDS[mode]
    mode_budgets = {"SMOKE": 900, "QUICK": 3600, "DEEP": 14400, "OVERNIGHT": 21600}
    if args.time_limit:
        budget = int(args.time_limit)
    elif args.mode:
        budget = mode_budgets[args.mode]
    else:
        budget = int(row["time_limit_sec"])
    return mode, budget, requested or 1


def run_one(root: Path, results_root: Path, row: dict, args) -> dict:
    scenario = row["scenario_id"]
    # The wrapper creates <output-root>/<schedule-id>/ itself, so output-root is
    # the RESULTS root, not a per-scenario directory. Nesting it a second time
    # gives results/<id>/<id>/, which the gate report will not find - it looks
    # for case directories one level down.
    results_root.mkdir(parents=True, exist_ok=True)
    # A mode override without a matching budget is the trap this exists to
    # avoid: DEEP's 14400s budget under --mode QUICK, or QUICK's phase reserves
    # under a 14400s one. An explicit --time-limit still wins over both.
    engine_mode, budget, seeds = depth_plan(args, row)
    command = [
        sys.executable, "-u", str(root / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"),
        "--input", str(row.get("_input_path") or (root / "inputs" / row["input"])),
        "--output-root", str(results_root),
        "--schedule-id", scenario,
        "--mode", engine_mode,
        "--time-limit", str(budget),
        "--num-workers", str(args.num_workers or row.get("num_workers", 4)),
        "--solver-random-seed", str(row.get("solver_random_seed", 9000)),
    ]
    if getattr(args, "overwrite", False):
        # RC5 semantics: replacing an existing schedule-id is an explicit choice.
        command.append("--overwrite")
    if row.get("acknowledged_departed"):
        # Baseline-protected workbooks cannot be edited, so a scenario whose
        # previous-week sheet names people no longer on the roster lists them in
        # the manifest; the engine records the override in its run identity.
        command += ["--acknowledge-departed", ";".join(row["acknowledged_departed"])]
    if args.stage:
        command += ["--stage", args.stage]
    if args.language_working_window:
        command += ["--language-working-window", args.language_working_window]
    if args.resume:
        command.append("--resume")
    if seeds > 1:
        return run_portfolio(root, results_root, row, args, command, budget, seeds)
    log(f"START {scenario}  budget={budget}s  workers={command[command.index('--num-workers')+1]}")
    started = time.time()
    logfile = results_root / f"{scenario}.log"
    returncode = _run_engine(command, logfile, budget + 1800)
    if returncode != 0:
        show_failure_logs([logfile])
    elapsed = round(time.time() - started, 1)
    log(f"DONE  {scenario}  exit={returncode}  wall={elapsed}s  "
        f"({'within' if elapsed <= budget else 'OVER'} budget)")
    return {"scenario_id": scenario, "exit_code": returncode,
            "wall_sec": elapsed, "budget_sec": budget,
            "overran_budget": elapsed > budget, "log": str(logfile)}


def record_failed(record: dict) -> bool:
    """A scenario failed if its run exited nonzero, timed out, or (portfolio) produced no winner."""
    if record.get("exit_code") not in (0, "0"):
        return True
    return int(record.get("seeds") or 1) > 1 and record.get("after_breaks_winner_seed") is None


# Measured peak RSS of one QUICK engine run with joint refinement off is about
# 0.8-2 GB (evidence/NIGHT_03, BUDGET_SWEEP_AND_OOM.md); 3 GB per seed keeps a
# margin. Side-by-side seeds are limited by memory as well as by cores (M-09).
SEED_MEMORY_MB = 3072


def available_memory_mb():
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def seed_plan(seeds: int, parallel: int, cpus: int, memory_mb=None) -> tuple:
    """(seeds at once, workers per seed). Auto: 2+ cores per seed side by side."""
    seeds = max(1, int(seeds))
    if parallel <= 0:
        parallel = max(1, min(seeds, cpus // 2))
        if memory_mb:
            parallel = max(1, min(parallel, int(memory_mb) // SEED_MEMORY_MB))
    parallel = max(1, min(seeds, parallel))
    return parallel, max(1, cpus // parallel)


def run_portfolio(root: Path, results_root: Path, row: dict, args, command: list, budget: int,
                  seeds: int) -> dict:
    """Run N seeds via RUN_PORTFOLIO.py; publish the winning seed as the scenario."""
    scenario = row["scenario_id"]
    seeds = int(seeds)
    parallel, workers = seed_plan(seeds, int(getattr(args, "parallel", 0) or 0), os.cpu_count() or 2,
                                  available_memory_mb())
    base_seed = int(row.get("solver_random_seed", 9000))
    passthrough = [c for c in command[3:] if c not in ("--overwrite",)]
    # drop the arguments RUN_PORTFOLIO sets itself, and the worker count it is given here
    cleaned, skip = [], False
    for c in passthrough:
        if skip:
            skip = False
            continue
        if c in ("--output-root", "--schedule-id", "--solver-random-seed", "--num-workers"):
            skip = True
            continue
        cleaned.append(c)
    if "--resume" in cleaned:
        cleaned.remove("--resume")
        log("note: --resume is not supported with --seeds; seeds start fresh")
    seeds_root = results_root / "_seeds"
    cmd = [sys.executable, "-u", str(root / "engine" / "RUN_PORTFOLIO.py"),
           "--seeds", str(seeds), "--base-seed", str(base_seed), "--parallel", str(parallel),
           "--output-root", str(seeds_root), "--schedule-id", scenario,
           *cleaned, "--num-workers", str(workers)]
    log(f"START {scenario}  seeds={seeds} (base {base_seed})  side-by-side={parallel}  "
        f"workers/seed={workers}  budget/seed={budget}s")
    # A summary left by an earlier portfolio of the same scenario must never be
    # read as this run's result if this run dies before writing its own.
    stale = seeds_root / scenario / "PORTFOLIO_SUMMARY.json"
    if stale.exists():
        stale.unlink()
    started = time.time()
    logfile = results_root / f"{scenario}.log"
    rounds = math.ceil(seeds / parallel)
    returncode = _run_engine(cmd, logfile, budget * rounds + 1800 * rounds)
    if returncode != 0 or not (seeds_root / scenario / "PORTFOLIO_SUMMARY.json").exists():
        show_failure_logs([logfile, *sorted((seeds_root / scenario).glob(f"{scenario}_S*.log"))])
    elapsed = round(time.time() - started, 1)
    summary_path = seeds_root / scenario / "PORTFOLIO_SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    winner = summary.get("after_breaks_winner_seed")
    published = None
    if winner is not None:
        # The winning seed's complete run becomes results/<scenario>/, unchanged,
        # so the gate report and the reader see one self-consistent run.
        src = seeds_root / scenario / "seeds" / f"{scenario}_S{winner}"
        dst = results_root / scenario
        if dst.exists() and not getattr(args, "overwrite", False):
            log(f"REFUSED {scenario}: {dst} exists; pass --overwrite to replace it "
                f"(the portfolio's own seeds are kept under {seeds_root / scenario})")
            return {"scenario_id": scenario, "exit_code": "EXISTS_NOT_OVERWRITTEN", "wall_sec": elapsed,
                    "budget_sec": budget, "seeds": seeds, "after_breaks_winner_seed": winner,
                    "before_breaks_winner_seed": summary.get("before_breaks_winner_seed"),
                    "published_case": None, "log": str(logfile)}
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        portfolio_dir = dst / "PORTFOLIO"
        shutil.copytree(seeds_root / scenario / "PORTFOLIO_BEST", portfolio_dir)
        for name in ("PORTFOLIO_SUMMARY.json", "PORTFOLIO_SUMMARY.csv"):
            shutil.copy2(seeds_root / scenario / name, portfolio_dir / name)
        published = str(dst)
    log(f"DONE  {scenario}  exit={returncode}  wall={elapsed}s  "
        f"after-breaks winner seed={winner}  before-breaks winner seed={summary.get('before_breaks_winner_seed')}")
    return {"scenario_id": scenario, "exit_code": returncode, "wall_sec": elapsed,
            "budget_sec": budget, "seeds": seeds, "side_by_side": parallel, "workers_per_seed": workers,
            "after_breaks_winner_seed": winner,
            "before_breaks_winner_seed": summary.get("before_breaks_winner_seed"),
            "published_case": published, "overran_budget": elapsed > budget * rounds,
            "log": str(logfile)}


def score_gates(root: Path, results_root: Path) -> int:
    log("scoring release gates")
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "release_gate_report.py"),
         str(results_root), "--out-dir", str(results_root / "_gate_report")],
        capture_output=True, text=True, timeout=1800)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr[-4000:], file=sys.stderr)
    return proc.returncode


def run_guard_suite(root: Path) -> bool:
    """Run the package's full offline gate before any solver time is spent.

    This is the same gate the repository and the package builder run
    (run_tests.sh: tests/, tests_staged/, selfchecks, call-signature check),
    so the Colab guard and the release gate cannot drift apart. The previous
    runner globbed tests/test_rc9_2_1_*.py only and skipped every staged
    suite (audit F-17 / H-03).
    """
    log("running the offline gate (run_tests.sh)")
    gate = root / "run_tests.sh"
    if not gate.is_file():
        print(f"GUARD SUITE FAILED: missing {gate}", file=sys.stderr)
        return False
    proc = subprocess.run(["bash", str(gate)], cwd=str(root), capture_output=True,
                          text=True, timeout=3600)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    log(f"   {tail[0][:120]}")
    if proc.returncode != 0:
        print((proc.stdout or "")[-6000:], file=sys.stderr)
        print((proc.stderr or "")[-2000:], file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package-root", type=Path, default=Path("."))
    ap.add_argument("--results-root", type=Path, default=None)
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--time-limit", type=int, default=0, help="override budget seconds")
    ap.add_argument("--mode", choices=["SMOKE", "QUICK", "DEEP", "OVERNIGHT"], default=None,
                    help="override the manifest depth. Setting --time-limit alone is NOT "
                         "the same: mode also sets the phase reserves, and DEEP's joint "
                         "reserve is 5400s, which on its own exceeds a 3600s budget.")
    ap.add_argument("--stage", choices=["BEFORE_BREAKS_ONLY", "FULL_SCHEDULE"], default=None,
                    help="BEFORE_BREAKS_ONLY runs Stage 1 and exports the before-break "
                         "champion without placing breaks.")
    ap.add_argument("--language-working-window",
                    choices=["OFF", "MINIMUM_ROWS", "ALL_ROWS", "REQUIRED_LANGUAGE_ONLY"], default=None,
                    help="override the workbook's Language Working Window setting.")
    ap.add_argument("--input", type=Path, default=None,
                    help="run a workbook that is not in SCENARIOS.json - your own live "
                         "scenario. Skips the manifest hash check for that file only; "
                         "the manifest scenarios stay hash-verified.")
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=0,
                    help="solver seeds per scenario; the best validated result is kept "
                         "(default: 4 for DEEP, 6 for OVERNIGHT, 1 otherwise)")
    ap.add_argument("--single-run", action="store_true",
                    help="DEEP/OVERNIGHT as one long run instead of 1 h seeds")
    ap.add_argument("--parallel", type=int, default=0,
                    help="seeds to run side by side (default: automatic, 2+ cores per seed)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--overwrite", action="store_true",
                    help="explicitly replace an existing schedule-id; off by default")
    ap.add_argument("--skip-guards", action="store_true")
    ap.add_argument("--skip-gates", action="store_true",
                    help="defer release-gate scoring; used by parallel shards")
    ap.add_argument("--gate-only", action="store_true", help="re-score existing results")
    args = ap.parse_args()

    root = args.package_root.resolve()
    results_root = (args.results_root or root / "results").resolve()
    results_root.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(root)
    log(f"package : {manifest['package']}")
    log(f"engine  : {manifest['engine_release']}")
    log(f"sha256  : {manifest['engine_sha256'][:24]}…")
    log(f"host    : {platform.platform()} | cpus={os.cpu_count()} | python={platform.python_version()}")

    engine_problems = verify_engine(root, manifest)
    if engine_problems:
        for problem in engine_problems:
            print(f"ENGINE VERIFICATION FAILED: {problem}", file=sys.stderr)
        return 2

    if args.gate_only:
        return score_gates(root, results_root)

    if not run_runtime_check(root):
        log("RUNTIME CHECK FAILED - refusing to consume solver time")
        return 2

    if not args.skip_guards and not run_guard_suite(root):
        log("GUARD SUITE FAILED - refusing to run scenarios against an engine "
            "that does not match its own tests")
        return 2

    if args.input is not None:
        # Your own workbook. The hash check exists so a run against a silently
        # different input is never compared against a baseline; a workbook that
        # was never in the manifest is a different case, not a corrupted one.
        # Gates 2 and 9 will report NOT_COMPARABLE for it, which is correct.
        workbook = args.input.resolve()
        if not workbook.is_file():
            log(f"no such workbook: {workbook}")
            return 2
        scenario_id = args.only.strip().upper() or workbook.stem.upper()[:60]
        log(f"ad-hoc scenario {scenario_id} from {workbook}")
        log("this workbook is not in SCENARIOS.json, so gates 2 and 9 will report "
            "NOT_COMPARABLE - there is no RC9.1 baseline to compare it against")
        row = {
            "scenario_id": scenario_id,
            "input": workbook.name,
            "time_limit_sec": mode_default_budget(args),
            "mode": args.mode or "DEEP",
            "num_workers": args.num_workers or 4,
            "solver_random_seed": 9000,
            "_input_path": workbook,
        }
        record = run_one(root, results_root, row, args)
        (results_root / "RUN_LEDGER.json").write_text(json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "package": manifest["package"], "engine_sha256": manifest["engine_sha256"],
            "ad_hoc_input": str(workbook), "runs": [record],
        }, indent=2), encoding="utf-8")
        gate_rc = 0 if args.skip_gates else score_gates(root, results_root)
        return 2 if record_failed(record) else gate_rc

    problems = verify_inputs(root, manifest["scenarios"])
    if problems:
        for p in problems:
            print(f"INPUT VERIFICATION FAILED: {p}", file=sys.stderr)
        return 2

    chosen = select(manifest["scenarios"], args.only, args.shard, args.shards)
    if not chosen:
        log("no scenarios selected")
        return 2
    log(f"scenarios: {[r['scenario_id'] for r in chosen]}")

    records = []
    for row in chosen:
        try:
            records.append(run_one(root, results_root, row, args))
        except subprocess.TimeoutExpired:
            log(f"TIMEOUT {row['scenario_id']} - hard kill, recorded as a failure")
            records.append({"scenario_id": row["scenario_id"], "exit_code": "TIMEOUT",
                            "seeds": depth_plan(args, row)[2],
                            "wall_sec": None, "budget_sec": row["time_limit_sec"],
                            "overran_budget": True})
        (results_root / "RUN_LEDGER.json").write_text(json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "package": manifest["package"], "engine_sha256": manifest["engine_sha256"],
            "host": {"platform": platform.platform(), "cpus": os.cpu_count()},
            "shard": args.shard, "shards": args.shards,
            "runs": records}, indent=2), encoding="utf-8")

    run_failed = [r["scenario_id"] for r in records if record_failed(r)]
    gate_rc = 0 if args.skip_gates else score_gates(root, results_root)
    log(f"results in {results_root}")
    log("Send back the whole results directory, including RUN_LEDGER.json and "
        "_gate_report/.")
    # Failures are the exit status (audit F-17 / H-02 / M-10): a failed or
    # timed-out scenario is 2, otherwise the release-gate verdict decides.
    if run_failed:
        log(f"FAILED scenarios: {run_failed}")
        return 2
    return gate_rc


if __name__ == "__main__":
    raise SystemExit(main())
