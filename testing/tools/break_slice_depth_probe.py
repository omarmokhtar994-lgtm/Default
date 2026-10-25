"""Does break-search depth buy anything, or is 20s already converged?

The adaptive break search clamps every attempt up to a 20-second minimum, and
10 of 25 attempts in the A35 verification run returned UNKNOWN at that limit -
the same too-shallow signature as A34. Before adding a third slice-floor fix on
faith, measure it: one good skeleton, solve_breaks at a range of time limits.
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine" / "_tools"))
import l632_universal_scheduler as E

workbook, profile_name, width, out_path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
skeleton_sec = float(sys.argv[5])
slices = [float(x) for x in sys.argv[6].split(",")]

parsed = E.parse_input(Path(workbook))
profile = next(p for p in E.skeleton_profiles() if p["name"] == profile_name)
hard = E.HardConfig(hard_floor=(parsed.floor_mode == "hard"))

skeleton = E.build_skeleton(parsed, profile, hard, skeleton_sec, 2, sys.stderr, random_seed=0)
base = E.calculate_metrics(parsed, skeleton, {(a, d): None for a, d, _ in E.scheduled_cells(skeleton)}, [])
print(json.dumps({"stage": "skeleton", "profile": profile_name, "cp_status": skeleton.cp_status,
                  "before_target": base.get("before_target"),
                  "before_floor": base.get("before_floor")}), flush=True)

rows = []
for slice_sec in slices:
    started = time.time()
    sol = E.solve_breaks(parsed, skeleton, width, False, slice_sec, 2, sys.stderr,
                         objective_mode="target_priority", random_seed=9000)
    m = sol.metrics or {}
    row = {"stage": "breaks", "slice_sec": slice_sec, "cp_status": sol.cp_status,
           "elapsed_sec": round(time.time() - started, 1),
           "before_target": m.get("before_target"), "after_target": m.get("after_target"),
           "after_floor": m.get("after_floor"),
           "target_losses_from_breaks": m.get("target_losses_from_breaks")}
    rows.append(row)
    print(json.dumps(row), flush=True)
    Path(out_path).write_text(json.dumps(rows, indent=2))
