#!/usr/bin/env python3
"""RC9.2.2 scenario runner core retained under its legacy import name.

Compatibility note: use ``rc922_runner.py`` for all RC9.2.2/RC5 Colab and
production runs. This file remains import-compatible for older automation and
is not the release identity.

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
"""
from __future__ import annotations

import argparse
import json
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
    import hashlib
    engine=root/'engine'/'_tools'/'l632_universal_scheduler.py'
    if not engine.is_file(): return [f"missing engine: {engine}"]
    actual=hashlib.sha256(engine.read_bytes()).hexdigest()
    expected=str(manifest.get('engine_sha256') or '')
    return [] if expected and actual==expected else [f"engine sha256 {actual[:16]} != manifest {expected[:16] or 'missing'}"]


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
                                   "DEEP": 14400, "OVERNIGHT": 21600}[args.mode or "QUICK"])


def _terminate_process_tree(proc: subprocess.Popen, grace_seconds: float = 15.0) -> None:
    """Terminate the engine and its descendants, including on Colab interrupt."""
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


def _run_engine(command: list[str], logfile: Path, timeout: int) -> int:
    """Run one case with a process group that can be safely stopped/resumed."""
    with logfile.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
        try:
            return int(proc.wait(timeout=timeout))
        except KeyboardInterrupt:
            _terminate_process_tree(proc)
            raise
        except subprocess.TimeoutExpired:
            _terminate_process_tree(proc)
            raise


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
    mode_budgets = {"SMOKE": 900, "QUICK": 3600, "DEEP": 14400, "OVERNIGHT": 21600}
    if args.time_limit:
        budget = int(args.time_limit)
    elif args.mode:
        budget = mode_budgets[args.mode]
    else:
        budget = int(row["time_limit_sec"])
    command = [
        sys.executable, "-u", str(root / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"),
        "--input", str(row.get("_input_path") or (root / "inputs" / row["input"])),
        "--output-root", str(results_root),
        "--schedule-id", scenario,
        "--mode", args.mode or row.get("mode", "DEEP"),
        "--time-limit", str(budget),
        "--num-workers", str(args.num_workers or row.get("num_workers", 4)),
        "--solver-random-seed", str(row.get("solver_random_seed", 9000)),
    ]
    if args.stage:
        command += ["--stage", args.stage]
    if args.language_working_window:
        command += ["--language-working-window", args.language_working_window]
    if args.resume:
        command.append("--resume")
    if args.overwrite:
        command.append("--overwrite")
    log(f"START {scenario}  budget={budget}s  workers={command[command.index('--num-workers')+1]}")
    started = time.time()
    logfile = results_root / f"{scenario}.log"
    return_code = _run_engine(command, logfile, budget + 1800)
    elapsed = round(time.time() - started, 1)
    log(f"DONE  {scenario}  exit={return_code}  wall={elapsed}s  "
        f"({'within' if elapsed <= budget else 'OVER'} budget)")
    return {"scenario_id": scenario, "exit_code": return_code,
            "wall_sec": elapsed, "budget_sec": budget,
            "overran_budget": elapsed > budget, "log": str(logfile)}


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
    """The offline guards. Fast, no solver, and they must pass first.

    If the engine in this package is not the engine the guards expect, nothing
    produced afterwards is worth comparing.
    """
    log("running offline guard suite")
    ok = True
    for suite in sorted((root / "tests").glob("test_rc9_2_*.py")):
        proc = subprocess.run([sys.executable, str(suite)],
                              capture_output=True, text=True, timeout=1800)
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or [""]
        status = "OK" if proc.returncode == 0 else "FAILED"
        log(f"   {suite.name:48} {status}  {tail[0][:40]}")
        if proc.returncode != 0:
            ok = False
            print((proc.stderr or proc.stdout)[-3000:], file=sys.stderr)
    return ok


def run_runtime_check(root: Path) -> bool:
    """Reject a solver run before any optimization budget is consumed."""
    checker = root / "tools" / "runtime_environment_check.py"
    if not checker.is_file():
        print(f"RUNTIME CHECK FAILED: missing {checker}", file=sys.stderr)
        return False
    log("checking pinned runtime and CP-SAT compatibility")
    proc = subprocess.run(
        [sys.executable, str(checker)], capture_output=True, text=True, timeout=120
    )
    if proc.returncode:
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        return False
    log("runtime check PASS")
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
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--overwrite", action="store_true",
                    help="explicitly replace an existing schedule-id; off by default")
    ap.add_argument("--skip-guards", action="store_true")
    ap.add_argument("--gate-only", action="store_true", help="re-score existing results")
    ap.add_argument("--skip-gates", action="store_true",
                    help="defer release-gate scoring; used by parallel shards")
    args = ap.parse_args()

    root = args.package_root.resolve()
    results_root = (args.results_root or root / "results").resolve()
    results_root.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(root)
    log(f"package : {manifest['package']}")
    log(f"engine  : {manifest['engine_release']}")
    log(f"sha256  : {manifest['engine_sha256'][:24]}…")
    log(f"host    : {platform.platform()} | cpus={os.cpu_count()} | python={platform.python_version()}")

    engine_problems=verify_engine(root,manifest)
    if engine_problems:
        for problem in engine_problems: print(f"ENGINE VERIFICATION FAILED: {problem}",file=sys.stderr)
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
            "mode": args.mode or "QUICK",
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
        gate_rc=0 if args.skip_gates else score_gates(root, results_root)
        return int(record.get('exit_code') or 0) or gate_rc

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
        except KeyboardInterrupt:
            log(f"INTERRUPTED {row['scenario_id']} - engine process tree terminated; resume is safe")
            records.append({"scenario_id": row["scenario_id"], "exit_code": "INTERRUPTED",
                            "wall_sec": None, "budget_sec": row["time_limit_sec"],
                            "overran_budget": False})
            ledger_name = "RUN_LEDGER.json" if args.shards == 1 else f"RUN_LEDGER_SHARD_{args.shard:02d}.json"
            (results_root / ledger_name).write_text(json.dumps({
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "package": manifest["package"], "engine_sha256": manifest["engine_sha256"],
                "host": {"platform": platform.platform(), "cpus": os.cpu_count()},
                "shard": args.shard, "shards": args.shards,
                "runs": records}, indent=2), encoding="utf-8")
            return 130
        except subprocess.TimeoutExpired:
            log(f"TIMEOUT {row['scenario_id']} - hard kill, recorded as a failure")
            records.append({"scenario_id": row["scenario_id"], "exit_code": "TIMEOUT",
                            "wall_sec": None, "budget_sec": row["time_limit_sec"],
                            "overran_budget": True})
        ledger_name = "RUN_LEDGER.json" if args.shards == 1 else f"RUN_LEDGER_SHARD_{args.shard:02d}.json"
        (results_root / ledger_name).write_text(json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "package": manifest["package"], "engine_sha256": manifest["engine_sha256"],
            "host": {"platform": platform.platform(), "cpus": os.cpu_count()},
            "shard": args.shard, "shards": args.shards,
            "runs": records}, indent=2), encoding="utf-8")

    run_failed=any(record.get('exit_code') not in (0,'0') for record in records)
    gate_rc=0 if args.skip_gates else score_gates(root, results_root)
    log(f"results in {results_root}")
    log("Send back the whole results directory, including RUN_LEDGER.json and "
        "_gate_report/.")
    return 2 if run_failed else gate_rc


if __name__ == "__main__":
    raise SystemExit(main())
