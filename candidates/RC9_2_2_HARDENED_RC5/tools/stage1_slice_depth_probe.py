"""Measure Stage-1 skeleton quality as a function of the per-profile time slice.

Every RC9.2.1 run recorded so far pinned every Stage-1 attempt to the 45s
minimum-slice floor. Nothing in the project measures what a profile produces
when it is actually given time, so the slice floor cannot be chosen from
evidence. This probe calls build_skeleton directly at a range of time limits
and records before-break target/floor coverage for each.

COLD vs WARM. The first version of this probe called build_skeleton with no
hint, and STAGE1_MIN_MEANINGFUL_SLICE_SEC was set from those numbers. The
Stage-1 portfolio loop never solves that way: it always passes
hint_skeleton=select_stage1_hint_skeleton(...), so by the time the portfolio
runs, every profile is warm-started from the skeletons already found. A floor
measured cold and applied warm measures the wrong thing, which is how a 900s
run came to attempt zero of fifteen profiles with 171 seconds in hand.

Pass `warm` as the fifth argument to reproduce the loop's own conditions: the
probe first builds the anchor the run has in hand (the hard-feasibility probe,
then the profile itself) and hints every timed solve from it.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine" / "_tools"))
import l632_universal_scheduler as E

if len(sys.argv) not in (5, 6):
    raise SystemExit(
        "usage: stage1_slice_depth_probe.py <workbook.xlsx> <profile> "
        "<out.json> <comma-separated slice seconds> [cold|warm]")
workbook, profile_name, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
slices = [float(x) for x in sys.argv[4].split(",")]
mode = (sys.argv[5] if len(sys.argv) == 6 else "cold").strip().lower()
if mode not in {"cold", "warm"}:
    raise SystemExit("mode must be 'cold' or 'warm'")

parsed = E.parse_input(Path(workbook))
profile = next(p for p in E.skeleton_profiles() if p["name"] == profile_name)
hard = E.HardConfig(hard_floor=(parsed.floor_mode == "hard"))

anchors = []
if mode == "warm":
    # profile=None is the hard-feasibility probe: build_skeleton substitutes
    # the all-zero-weight profile, which is what run_case solves first.
    for anchor_profile, anchor_sec in ((None, 60.0), (profile, 60.0)):
        hint = E.select_stage1_hint_skeleton(parsed, anchors) if anchors else None
        anchor = E.build_skeleton(parsed, anchor_profile, hard, anchor_sec, 2,
                                  sys.stderr, random_seed=0, hint_skeleton=hint)
        print(json.dumps({
            "anchor": (anchor_profile or {}).get("name", "hard_feasibility_probe"),
            "cp_status": anchor.cp_status,
            "elapsed_sec": round(anchor.elapsed_sec, 2)}), flush=True)
        if anchor.cp_status in {"OPTIMAL", "FEASIBLE"}:
            E.ensure_before_break_metrics(parsed, anchor)
            anchors.append(anchor)
    if not anchors:
        raise SystemExit("warm mode needs a feasible anchor and found none")

records = []
for slice_sec in slices:
    started = time.time()
    hint = E.select_stage1_hint_skeleton(parsed, anchors) if anchors else None
    solution = E.build_skeleton(parsed, profile, hard, slice_sec, 2, sys.stderr,
                                random_seed=0, hint_skeleton=hint)
    row = {
        "profile": profile_name,
        "mode": mode,
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
