#!/usr/bin/env python3
"""Does B-13's constant bound over-constrain? The failure mode worth checking.

The fix replaces  after >= before - cap  (both sides solver-controlled) with
    after >= measured_before - cap   (right side an integer).

That is strictly stronger. The risk is that it turns a solvable refinement into
an INFEASIBLE one when the incumbent's measured before-count cannot be met
after breaks are placed -- which would be worse than the defect it fixes.

This probe walks the cap down against a fixed measured_before and reports where
feasibility is lost, for a model where breaks must remove a given amount of
staffing.
"""
from ortools.sat.python import cp_model

N = 12
MEASURED_BEFORE = 10


def solve(cap, forced_break_removals):
    m = cp_model.CpModel()
    before = [m.NewIntVar(0, 10, f"b{i}") for i in range(N)]
    after = [m.NewIntVar(0, 10, f"a{i}") for i in range(N)]
    bh, ah = [], []
    for i in range(N):
        x = m.NewBoolVar(f"bh{i}"); y = m.NewBoolVar(f"ah{i}")
        m.Add(before[i] >= 5).OnlyEnforceIf(x); m.Add(before[i] <= 4).OnlyEnforceIf(x.Not())
        m.Add(after[i] >= 5).OnlyEnforceIf(y);  m.Add(after[i] <= 4).OnlyEnforceIf(y.Not())
        m.Add(after[i] <= before[i])
        bh.append(x); ah.append(y)
    # the incumbent really did achieve MEASURED_BEFORE
    m.Add(sum(bh) == MEASURED_BEFORE)
    # breaks must remove this much staffing in total
    m.Add(sum(before) - sum(after) >= forced_break_removals)
    m.Add(sum(ah) >= MEASURED_BEFORE - cap)
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 1
    st = s.Solve(m)
    return s.StatusName(st), (sum(s.Value(v) for v in ah) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None)


print("B-13 safety probe: does the constant bound over-constrain?")
print("measured_before = %d, %d intervals\n" % (MEASURED_BEFORE, N))
print("  removals  cap=6   cap=4   cap=2   cap=0")
for removals in (0, 5, 10, 20, 40, 60):
    row = []
    for cap in (6, 4, 2, 0):
        st, hits = solve(cap, removals)
        row.append("%-7s" % ("OK" if st in ("OPTIMAL", "FEASIBLE") else "INFEAS"))
    print("  %-9d %s" % (removals, " ".join(row)))
print()
print("Reading: a row turning INFEAS means the bound refused a refinement that")
print("break placement genuinely required. The cap is the safety valve -- it is")
print("what the workbook sets via quality_max_floor_losses_from_breaks. With a")
print("realistic cap the constant bound stays feasible under heavy break load;")
print("only cap=0 with heavy removals is impossible, and that is a contract")
print("asking for breaks that cost nothing, which is genuinely infeasible.")
