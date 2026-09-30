#!/usr/bin/env python3
"""Run manifest scenarios in parallel shards after one shared guard pass."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=int, default=2)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results_parallel")
    parser.add_argument("--mode", choices=["SMOKE", "QUICK", "DEEP", "OVERNIGHT"], default="QUICK")
    parser.add_argument("--time-limit", type=int, default=0)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--only", default="")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    instances = max(1, min(8, args.instances))
    guard = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=ROOT)
    if guard.returncode:
        return guard.returncode
    processes = []
    selected_ids = [value.strip() for value in args.only.split(",") if value.strip()]
    for shard in range(instances):
        command = [
            sys.executable, str(ROOT / "runners" / "rc922_runner.py"),
            "--package-root", str(ROOT), "--results-root", str(args.results_root),
            "--shard", str(shard), "--shards", str(instances), "--mode", args.mode,
            "--num-workers", str(max(1, args.num_workers)), "--skip-guards", "--skip-gates",
        ]
        if args.time_limit: command += ["--time-limit", str(args.time_limit)]
        if selected_ids:
            shard_ids = selected_ids[shard::instances]
            if not shard_ids:
                continue
            command += ["--only", ",".join(shard_ids)]
        if args.resume: command.append("--resume")
        processes.append(subprocess.Popen(command, cwd=ROOT))
    run_code=max((process.wait() for process in processes),default=0)
    if run_code:
        return run_code
    gate=subprocess.run([
        sys.executable,str(ROOT / "runners" / "rc922_runner.py"),
        "--package-root",str(ROOT),"--results-root",str(args.results_root),"--gate-only",
    ],cwd=ROOT)
    return gate.returncode

if __name__ == "__main__":
    raise SystemExit(main())
