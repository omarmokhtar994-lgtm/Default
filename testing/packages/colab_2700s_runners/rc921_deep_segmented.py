#!/usr/bin/env python3
"""RC9.2.1 DEEP runner — 14,400 s budget executed as resumable segments.

Why segments
------------
A four-hour unattended run does not survive a Colab disconnect. It did not
survive in our own container either: two attempts were killed at 10 and 40
minutes. The engine checkpoints its skeletons and its tested combinations, so
the same budget can be reached as N shorter segments, each resuming the last.

A segment that dies costs one segment, not the run.

What resume actually does
-------------------------
`--resume` makes the engine reload `debug/SKELETON_CHECKPOINTS.json` and
`debug/TESTED_COMBINATIONS.json` and skip work already proven. It refuses a
checkpoint written by a different run_id, so a stale directory cannot silently
contaminate a run - if you change the input or the engine, start a clean
results directory.

Usage
-----
    python rc921_deep_segmented.py --package-root . --only CRICUT_VOICE
    python rc921_deep_segmented.py --only CRICUT_VOICE --segment-sec 2400
    python rc921_deep_segmented.py --only CRICUT_VOICE --continue-from 3
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


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def segment_state(case_root: Path) -> dict:
    """What the engine has banked so far, read from its own checkpoints."""
    state = {"skeletons": 0, "tested_combinations": 0, "run_id": None}
    debug = case_root / "debug"
    for name, key in (("SKELETON_CHECKPOINTS.json", "skeletons"),
                      ("TESTED_COMBINATIONS.json", "tested_combinations")):
        path = debug / name
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                state[key] = len(data) if isinstance(data, (list, dict)) else 0
            except (OSError, json.JSONDecodeError):
                pass
    identity = debug / "RUN_IDENTITY.json"
    if identity.exists():
        try:
            state["run_id"] = json.loads(identity.read_text(encoding="utf-8")).get("run_id")
        except (OSError, json.JSONDecodeError):
            pass
    return state


def run_segment(root: Path, results_root: Path, row: dict, index: int,
                seconds: int, workers: int, resume: bool) -> dict:
    scenario = row["scenario_id"]
    command = [
        sys.executable, "-u", str(root / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"),
        "--input", str(root / "inputs" / row["input"]),
        "--output-root", str(results_root),
        "--schedule-id", scenario,
        "--mode", "DEEP",
        "--time-limit", str(seconds),
        "--num-workers", str(workers),
        "--solver-random-seed", str(row.get("solver_random_seed", 9000)),
        "--overwrite",
    ]
    if resume:
        command.append("--resume")
    started = time.time()
    logfile = results_root / f"{scenario}_segment{index}.log"
    log(f"segment {index}: {scenario} for {seconds}s "
        f"({'resuming' if resume else 'fresh start'})")
    with logfile.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT,
                              timeout=seconds + 1800)
    elapsed = round(time.time() - started, 1)
    state = segment_state(results_root / scenario)
    log(f"segment {index}: exit={proc.returncode} wall={elapsed}s "
        f"skeletons_banked={state['skeletons']}")
    return {"segment": index, "seconds": seconds, "wall_sec": elapsed,
            "exit_code": proc.returncode, "state_after": state,
            "log": str(logfile)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package-root", type=Path, default=Path("."))
    ap.add_argument("--results-root", type=Path, default=None)
    ap.add_argument("--only", required=True,
                    help="scenario id - run ONE scenario per instance at this budget")
    ap.add_argument("--segment-sec", type=int, default=0)
    ap.add_argument("--segments", type=int, default=0)
    ap.add_argument("--continue-from", type=int, default=1,
                    help="restart at this segment number after a disconnect")
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--i-understand-segments-do-not-accumulate-budget",
                    action="store_true",
                    help="override the refusal to segment; see the note in main()")
    args = ap.parse_args()

    root = args.package_root.resolve()
    results_root = (args.results_root or root / "results").resolve()
    results_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / "SCENARIOS.json").read_text(encoding="utf-8"))

    wanted = args.only.strip().upper()
    row = next((r for r in manifest["scenarios"] if r["scenario_id"] == wanted), None)
    if row is None:
        raise SystemExit(f"Unknown scenario {wanted}. Known: "
                         f"{[r['scenario_id'] for r in manifest['scenarios']]}")

    seg_sec = args.segment_sec or row.get("segment_sec", 2400)
    segments = args.segments or row.get("segments", 6)

    # Segmenting DOES NOT reach the target budget, and run 1 proved it. Each
    # segment calls build_global_budget_plan(seg_sec), so it plans its phases
    # for the SEGMENT, not the target: at 2400s Stage 1 gets ~332s, which fits
    # two or three of the fifteen skeleton profiles. Resume carries the skeleton
    # pool forward but not the budget, so N segments are N independent runs
    # sharing a pool - roughly 15 hours of Colab compute produced no completed
    # portfolio on any scenario.
    #
    # Run the full budget in ONE session instead. A running cell is not idle, so
    # a four-hour run holds a Colab session; write results to Drive so a
    # disconnect costs the run rather than the results.
    if segments > 1 and not args.i_understand_segments_do_not_accumulate_budget:
        print(
            "\nREFUSING TO SEGMENT.\n\n"
            f"  Asking for {segments} x {seg_sec}s does NOT give this scenario "
            f"{row['time_limit_sec']}s of search.\n"
            "  Every segment re-plans its phase budget for the segment length, so "
            "Stage 1\n  gets the same small window each time and the skeleton "
            "portfolio never completes.\n\n"
            "  Run the whole budget in one session:\n\n"
            f"      --segments 1 --segment-sec {row['time_limit_sec']}\n\n"
            "  Keep the tab open and write results to Drive. If you genuinely want "
            "segments\n  anyway, pass "
            "--i-understand-segments-do-not-accumulate-budget.\n",
            file=sys.stderr)
        return 2
    workers = args.num_workers or os.cpu_count() or 4

    log(f"scenario : {wanted}")
    log(f"budget   : {row['time_limit_sec']}s as {segments} x {seg_sec}s")
    log(f"host     : {platform.platform()} | cpus={os.cpu_count()}")
    log(f"resuming : from segment {args.continue_from}")

    records = []
    for index in range(args.continue_from, segments + 1):
        # Segment 1 starts fresh only when there is nothing banked yet; a
        # --continue-from always resumes.
        banked = segment_state(results_root / wanted)
        resume = index > 1 or banked["skeletons"] > 0
        try:
            records.append(run_segment(root, results_root, row, index,
                                       seg_sec, workers, resume))
        except subprocess.TimeoutExpired:
            log(f"segment {index}: hard timeout - recorded and stopping")
            records.append({"segment": index, "exit_code": "TIMEOUT",
                            "seconds": seg_sec})
            break
        (results_root / f"{wanted}_SEGMENT_LEDGER.json").write_text(json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "scenario": wanted, "target_budget_sec": row["time_limit_sec"],
            "segment_sec": seg_sec, "segments_planned": segments,
            "host": {"platform": platform.platform(), "cpus": os.cpu_count()},
            "segments_run": records}, indent=2), encoding="utf-8")

    log("scoring release gates")
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "release_gate_report.py"),
         str(results_root), "--out-dir", str(results_root / "_gate_report")],
        capture_output=True, text=True, timeout=1800)
    print(proc.stdout)
    log(f"done. If a segment was lost, re-run with --continue-from <that number>.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
