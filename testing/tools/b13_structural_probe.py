#!/usr/bin/env python3
"""B-13 structural probe: can the solver satisfy the bound by degrading BEFORE?

The engine's joint refinement contains, with both sides solver-controlled:

    model.Add(sum(after_hits) >= sum(before_hits) - cap)

where before_hit and after_hit are both model.NewBoolVar tied to coverage.
The claim is that this is satisfiable by LOWERING before rather than protecting
after. This probe builds that exact shape and asks CP-SAT directly.

It is a model of the constraint, not a run of the engine. That is the point:
the question is what the constraint PERMITS, which is a property of the
formulation and does not depend on budget, seed or workbook.
"""
from ortools.sat.python import cp_model

N, CAP = 12, 2


def build(bound_kind, measured_before=None):
    m = cp_model.CpModel()
    # staffing per interval; before_hit/after_hit mirror the engine's pattern of
    # a bool tied to a coverage threshold.
    before_staff = [m.NewIntVar(0, 10, f"bs{i}") for i in range(N)]
    after_staff = [m.NewIntVar(0, 10, f"as{i}") for i in range(N)]
    before_hit, after_hit = [], []
    for i in range(N):
        bh = m.NewBoolVar(f"bh{i}"); ah = m.NewBoolVar(f"ah{i}")
        m.Add(before_staff[i] >= 5).OnlyEnforceIf(bh)
        m.Add(before_staff[i] <= 4).OnlyEnforceIf(bh.Not())
        m.Add(after_staff[i] >= 5).OnlyEnforceIf(ah)
        m.Add(after_staff[i] <= 4).OnlyEnforceIf(ah.Not())
        # breaks only remove staff: after <= before
        m.Add(after_staff[i] <= before_staff[i])
        before_hit.append(bh); after_hit.append(ah)

    # the skeleton could staff every interval; nothing forces it to
    for i in range(N):
        m.Add(before_staff[i] <= 8)

    if bound_kind == "gameable":
        m.Add(sum(after_hit) >= sum(before_hit) - CAP)
    elif bound_kind == "constant":
        m.Add(sum(after_hit) >= measured_before - CAP)

    # A mild pressure to remove staff, standing in for the engine's real
    # objective terms (overage, cost, break placement). The point is not the
    # objective -- it is what the CONSTRAINT still permits under any pressure.
    m.Minimize(sum(after_staff) + sum(before_staff))
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 1
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return (sum(s.Value(b) for b in before_hit), sum(s.Value(a) for a in after_hit))


print("B-13 structural probe -- %d intervals, cap %d\n" % (N, CAP))

free = build("none")
print("  no bound at all          before_hits=%2d  after_hits=%2d" % free)

game = build("gameable")
print("  GAMEABLE  after>=before-cap   before_hits=%2d  after_hits=%2d" % game)

const = build("constant", measured_before=10)
print("  CONSTANT  after>=10-cap       before_hits=%2d  after_hits=%2d" % const)

print()
print("Reading:")
print("  The gameable bound is satisfied at before_hits=%d. The solver did not" % game[0])
print("  protect the after-state; it lowered the before-state until the")
print("  inequality became trivial. 'after >= before - cap' costs nothing when")
print("  before is driven to %d." % game[0])
print()
print("  The constant bound forces after_hits >= %d regardless of what the" % (10 - CAP))
print("  skeleton does, because the right-hand side is a measured integer the")
print("  solver cannot move. Result: after_hits=%d." % const[1])
print()
print("  VERDICT: the gameable form protects nothing." if game[1] <= const[1]
      else "  VERDICT: gameable form held up; claim NOT reproduced.")
