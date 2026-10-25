"""B-5: do the objective's weight tiers actually implement a priority order?

The coefficients form a ladder (8, 40, 400, ... 3.2e9) that reads like a
lexicographic priority. A weighted sum only behaves that way if the MAXIMUM
total a tier can contribute is smaller than ONE unit of the tier above it.
Otherwise a large number of low-priority terms can outvote a high-priority one,
which is the defect a weighted-sum scalarization is known for.

This reads the built model and checks that property tier by tier, using each
objective variable's declared domain for its maximum contribution.
"""
import json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import l632_universal_scheduler as E

parsed = E.parse_input(Path(sys.argv[2]))
profile = next(p for p in E.skeleton_profiles() if p["name"] == sys.argv[3])
hard = E.HardConfig(hard_floor=(parsed.floor_mode == "hard"))

cap = {}
cp = E.import_cp_sat()
original = cp.CpModel.minimize


def capture(self, expr):
    original(self, expr)
    proto = self.proto
    cap["coeffs"] = [int(c) for c in proto.objective.coeffs]
    cap["idx"] = [int(v) for v in proto.objective.vars]
    cap["domains"] = [list(v.domain) for v in proto.variables]


cp.CpModel.minimize = capture
try:
    E.build_skeleton(parsed, profile, hard, 1.0, 1, sys.stderr, random_seed=0)
finally:
    cp.CpModel.minimize = original

tiers = defaultdict(lambda: {"terms": 0, "max_total": 0})
for coeff, var in zip(cap["coeffs"], cap["idx"]):
    if not coeff:
        continue
    dom = cap["domains"][var if var >= 0 else ~var]
    hi = max(abs(dom[0]), abs(dom[-1])) if dom else 0
    t = tiers[abs(coeff)]
    t["terms"] += 1
    t["max_total"] += abs(coeff) * hi

order = sorted(tiers)
print(f"{'weight':>12} {'terms':>6} {'max total contribution':>23}  {'< one unit of next tier?':>24}")
violations = 0
for i, w in enumerate(order):
    nxt = order[i + 1] if i + 1 < len(order) else None
    ok = "-" if nxt is None else ("YES" if tiers[w]["max_total"] < nxt else "NO")
    if ok == "NO":
        violations += 1
    print(f"{w:>12,} {tiers[w]['terms']:>6} {tiers[w]['max_total']:>23,}  {ok:>24}")
print()
print(json.dumps({
    "distinct_weight_tiers": len(order),
    "tiers_that_can_outvote_the_tier_above": violations,
    "behaves_as_a_priority_order": violations == 0,
}, indent=1))
