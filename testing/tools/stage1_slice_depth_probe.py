"""Measure Stage-1 skeleton quality as a function of the per-profile time slice.

Every RC9.2.1 run recorded so far pinned every Stage-1 attempt to the 45s
minimum-slice floor. Nothing in the project measures what a profile produces
when it is actually given time, so the slice floor cannot be chosen from
evidence. This probe calls build_skeleton directly at a range of time limits
and records before-break target/floor coverage for each.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine" / "_tools"))
import l632_universal_scheduler as E

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: stage1_slice_depth_probe.py <workbook.xlsx> <profile> "
        "<out.json> <comma-separated slice seconds>")
workbook, profile_name, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
slices = [float(x) for x in sys.argv[4].split(",")]

parsed = E.parse_input(Path(workbook))
profile = next(p for p in E.skeleton_profiles() if p["name"] == profile_name)
hard = E.HardConfig(hard_floor=(parsed.floor_mode == "hard"))

records = []
for slice_sec in slices:
    started = time.time()
    solution = E.build_skeleton(parsed, profile, hard, slice_sec, 2, sys.stderr, random_seed=0)
    row = {
        "profile": profile_name,
        "slice_sec": slice_sec,
        "cp_status": solution.cp_status,
        "elapsed_sec": round(time.time() - started, 1),
        "objective": solution.objective,
    }
    if solution.cp_status in {"OPTIMAL", "FEASIBLE"}:
        metrics = E.calculate_metrics(
            parsed, solution, {(a, d): None for a, d, _ in E.scheduled_cells(solution)}, []
        )
        row["before_target"] = metrics.get("before_target")
        row["before_floor"] = metrics.get("before_floor")
        row["severe_floor_gaps"] = metrics.get("severe_floor_gaps")
    records.append(row)
    print(json.dumps(row), flush=True)
    Path(out_path).write_text(json.dumps(records, indent=2))
