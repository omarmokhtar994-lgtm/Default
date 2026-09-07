#!/usr/bin/env python3
"""RC9.2.1 scenario runner — shared core for every Colab variant.

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
        "--overwrite",
    ]
    if args.stage:
        command += ["--stage", args.stage]
    if args.language_working_window:
        command += ["--language-working-window", args.language_working_window]
    if args.resume:
        command.append("--resume")
    log(f"START {scenario}  budget={budget}s  workers={command[command.index('--num-workers')+1]}")
    started = time.time()
    logfile = results_root / f"{scenario}.log"
    with logfile.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT,
                              timeout=budget + 1800)
    elapsed = round(time.time() - started, 1)
    log(f"DONE  {scenario}  exit={proc.returncode}  wall={elapsed}s  "
        f"({'within' if elapsed <= budget else 'OVER'} budget)")
    return {"scenario_id": scenario, "exit_code": proc.returncode,
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
    """The 291 offline guards. Fast, no solver, and they must pass first.

    If the engine in this package is not the engine the guards expect, nothing
    produced afterwards is worth comparing.
    """
    log("running offline guard suite")
    ok = True
    for suite in sorted((root / "tests").glob("test_rc9_2_1_*.py")):
        proc = subprocess.run([sys.executable, str(suite)],
                              capture_output=True, text=True, timeout=1800)
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or [""]
        status = "OK" if proc.returncode == 0 else "FAILED"
        log(f"   {suite.name:48} {status}  {tail[0][:40]}")
        if proc.returncode != 0:
            ok = False
            print((proc.stderr or proc.stdout)[-3000:], file=sys.stderr)
    return ok


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
                    choices=["OFF", "MINIMUM_ROWS", "ALL_ROWS"], default=None,
                    help="override the workbook's Language Working Window setting.")
    ap.add_argument("--input", type=Path, default=None,
                    help="run a workbook that is not in SCENARIOS.json - your own live "
                         "scenario. Skips the manifest hash check for that file only; "
                         "the manifest scenarios stay hash-verified.")
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--skip-guards", action="store_true")
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

    if args.gate_only:
        return score_gates(root, results_root)

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
        if not args.skip_guards and not run_guard_suite(root):
            log("GUARD SUITE FAILED - refusing to run")
            return 2
        record = run_one(root, results_root, row, args)
        (results_root / "RUN_LEDGER.json").write_text(json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "package": manifest["package"], "engine_sha256": manifest["engine_sha256"],
            "ad_hoc_input": str(workbook), "runs": [record],
        }, indent=2), encoding="utf-8")
        return score_gates(root, results_root)

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
                            "wall_sec": None, "budget_sec": row["time_limit_sec"],
                            "overran_budget": True})
        (results_root / "RUN_LEDGER.json").write_text(json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "package": manifest["package"], "engine_sha256": manifest["engine_sha256"],
            "host": {"platform": platform.platform(), "cpus": os.cpu_count()},
            "shard": args.shard, "shards": args.shards,
            "runs": records}, indent=2), encoding="utf-8")

    score_gates(root, results_root)
    log(f"results in {results_root}")
    log("Send back the whole results directory, including RUN_LEDGER.json and "
        "_gate_report/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
