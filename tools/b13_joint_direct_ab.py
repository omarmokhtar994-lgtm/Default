#!/usr/bin/env python3
"""Direct A/B of the joint refinement function that B-13 changes.

The phase scheduler puts joint refinement ~540s into a run, past what this
environment can keep a process alive for, and phases overrun their deadlines so
the offset cannot be targeted reliably. This bypasses the scheduler: it loads a
REAL skeleton and break solution checkpointed by a completed sweep, and calls
solve_joint_shift_off_language_break_refinement directly on each code version.

Same parsed contract, same anchor, same seed, same limits. The only difference
is which tree's module is imported.
"""
import sys, json, io
from pathlib import Path

tree, book, ckpt, seed = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
sys.path.insert(0, str(Path(tree) / "engine" / "_tools"))
import l632_universal_scheduler as eng

parsed = eng.parse_input(book)
payload = json.loads(ckpt.read_text())
skel, brk = eng.deserialize_break_candidate(parsed, payload)

log = io.StringIO()
out = eng.solve_joint_shift_off_language_break_refinement(
    parsed, [(skel, brk)], skel,
    pattern_width=115, time_limit=float(sys.argv[5]), workers=2, log=log,
    random_seed=seed, max_changed_cells=int(sys.argv[6]),
    max_shift_options_per_cell=10, max_patterns_per_shift=64,
    exception_cap=0, operator_name="b13_direct_probe",
)

res = {"tree": tree.split("/")[-1], "seed": seed,
       "anchor_before_floor": int(brk.metrics.get("before_floor", 0) or 0),
       "anchor_after_floor": int(brk.metrics.get("after_floor", 0) or 0),
       "anchor_before_target": int(brk.metrics.get("before_target", 0) or 0),
       "anchor_after_target": int(brk.metrics.get("after_target", 0) or 0)}
if out is None:
    res["result"] = "NO_SOLUTION"
else:
    _, sol = out
    m = sol.metrics
    res["result"] = "SOLVED"
    for k in ("before_floor", "after_floor", "before_target", "after_target"):
        res[k] = int(m.get(k, 0) or 0)
res["log"] = [l for l in log.getvalue().splitlines() if "JOINT" in l][:3]
print(json.dumps(res))
