#!/usr/bin/env python3
"""Direct A/B of the joint refinement function that B-13 changes.

Reproduces the production call site as faithfully as possible outside a full
run. Production passes four things a naive call omits, and all four are
reconstructible from a completed sweep's checkpoints:

  1. the PRODUCTION BOUNDS, derived as the engine derives them (~line 15376):
        min_after_target = max(0, incumbent.after_target - tolerance)
        min_after_floor  = incumbent.after_floor
  2. an ANCHOR POOL, not a single anchor -- production passes
        adaptive_nondominated_anchor_pool(parsed, anchors, maximum=12)
  3. FEEDBACK CUTS, built by derive_adaptive_feedback_cuts over the anchors,
     exactly as production does at lines 14955 / 15324 / 15479
  4. lexicographic ordering with the workbook's target tolerance

Usage: joint_direct.py <tree> <workbook> <checkpoint_dir> <seed> <time_limit> <max_cells>
"""
import sys, json, io
from pathlib import Path

tree, book, ckdir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
seed, tlimit, mcells = int(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
sys.path.insert(0, str(Path(tree) / "engine" / "_tools"))
import l632_universal_scheduler as eng

TOLERANCE = 1  # the sweep's --primary-target-tolerance

parsed = eng.parse_input(book)

# (2) every checkpointed candidate becomes an anchor, then the engine's own
#     pool selector picks the diverse nondominated set, as production does.
raw = []
for f in sorted(ckdir.glob("*.json")):
    try:
        raw.append(eng.deserialize_break_candidate(parsed, json.loads(f.read_text())))
    except Exception:
        pass
if not raw:
    print(json.dumps({"result": "NO_ANCHORS"})); raise SystemExit
pool = eng.adaptive_nondominated_anchor_pool(parsed, raw, maximum=12)

# (3) real feedback cuts, derived from every anchor exactly as production does
cuts = []
for sk, so in pool:
    try:
        cuts.extend(eng.derive_adaptive_feedback_cuts(parsed, sk, so, maximum=24))
    except Exception:
        pass

# (1) bounds from the best clean incumbent, as production picks it
try:
    inc = min([p for p in pool if eng.candidate_pool_class(parsed, p[0], p[1]) == "compliant"] or pool,
              key=lambda it: eng.break_solution_key(parsed, it[1]))
except Exception:
    inc = pool[0]
min_after_target = max(0, int(inc[1].metrics.get("after_target", 0) or 0) - TOLERANCE)
min_after_floor = int(inc[1].metrics.get("after_floor", 0) or 0)

log = io.StringIO()
out = eng.solve_joint_shift_off_language_break_refinement(
    parsed, pool, inc[0],
    pattern_width=115, time_limit=tlimit, workers=2, log=log,
    random_seed=seed, max_changed_cells=mcells,
    max_shift_options_per_cell=10, max_patterns_per_shift=64,
    exception_cap=0,
    min_after_target=min_after_target, min_after_floor=min_after_floor,
    feedback_cuts=tuple(cuts),
    lexicographic=True, lexicographic_target_tolerance=TOLERANCE,
    operator_name="b13_direct_probe",
)

res = {"tree": tree.rstrip("/").split("/")[-1], "seed": seed,
       "anchors": len(pool), "cuts": len(cuts),
       "min_after_target": min_after_target, "min_after_floor": min_after_floor,
       "inc_before_floor": int(inc[1].metrics.get("before_floor", 0) or 0),
       "inc_after_floor": int(inc[1].metrics.get("after_floor", 0) or 0)}
if out is None:
    res["result"] = "NO_SOLUTION"
else:
    m = out[1].metrics
    res["result"] = "SOLVED"
    for k in ("before_floor", "after_floor", "before_target", "after_target"):
        res[k] = int(m.get(k, 0) or 0)
res["log"] = [l for l in log.getvalue().splitlines() if "JOINT" in l][:2]
print(json.dumps(res))
