"""B-4: are the target intervals lost to breaks actually recoverable?

Reconstruct the exact skeleton the run selected from its exported before-break
workbook, then ask solve_breaks for a placement that loses NOTHING -- every
before-break target interval held after breaks. CP-SAT answering INFEASIBLE is
a proof that the losses are forced by the roster and the break contract.
Anything else means break placement gave up coverage it had room to keep.
"""
import json, sys, time
from pathlib import Path

ENGINE_DIR = sys.argv[1]
INPUT = Path(sys.argv[2])
BEFORE_WB = Path(sys.argv[3])
LOCK = int(sys.argv[4])
SECONDS = float(sys.argv[5])
sys.path.insert(0, ENGINE_DIR)
import l632_universal_scheduler as E

parsed = E.parse_input(INPUT)
skeleton = E.load_seed_skeleton(parsed, BEFORE_WB, profile="b4_probe_reconstructed")
if skeleton is None:
    raise SystemExit("could not reconstruct the skeleton from the before-break workbook")
metrics = E.calculate_metrics(
    parsed, skeleton, {(a, d): None for a, d, _ in E.scheduled_cells(skeleton)}, [])
print(json.dumps({
    "reconstructed": True,
    "cp_status": skeleton.cp_status,
    "before_target": metrics.get("before_target"),
    "before_floor": metrics.get("before_floor"),
    "active_intervals": metrics.get("active_intervals"),
}, indent=1), flush=True)

full_width = 115
for tag, lock in (("no_loss_lock", LOCK), ("one_loss_lock", LOCK - 1), ("two_loss_lock", LOCK - 2)):
    started = time.time()
    solution = E.solve_breaks(
        parsed, skeleton, full_width, False, SECONDS, 2, sys.stderr,
        exception_cap=0, diagnostic_any_cell=False,
        objective_mode="coverage_rebalance",
        min_target_hits=lock, random_seed=0,
    )
    row = {
        "probe": tag,
        "min_target_hits": lock,
        "cp_status": solution.cp_status,
        "elapsed_sec": round(time.time() - started, 1),
    }
    if solution.cp_status in {"OPTIMAL", "FEASIBLE"}:
        m = solution.metrics or {}
        row.update({
            "after_target": m.get("after_target"),
            "after_floor": m.get("after_floor"),
            "target_losses_from_breaks": m.get("target_losses_from_breaks"),
            "no_break_exceptions": len(solution.no_break_cells),
            "hard_clean": bool(E.skeleton_hard_clean(parsed, m)),
        })
    print(json.dumps(row), flush=True)
    if solution.cp_status in {"OPTIMAL", "FEASIBLE"}:
        break
