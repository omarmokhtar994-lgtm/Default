"""The joint-refinement bounds: what they can and cannot protect.

BACKGROUND. Two bounds in the joint refinement model have the shape

    model.Add(sum(after_hits) >= sum(before_hits) - cap)

where `before_hit` is a `model.NewBoolVar`, not a measured constant. Both sides
are therefore solver-controlled, and the inequality is satisfiable two ways:
protect the after-state, which is the intent, or LOWER THE BEFORE-STATE, which
is cheaper.

W1 once made the floor bound unconditional on the theory that it protected the
floor. Three paired seeds showed the opposite -- AE_IT_B2B's before_floor pinned
at exactly 91 whenever the bound was active, against 91/98/97 when it was not,
with a worse after-floor every time -- and it was reverted.

A corrected version bounding against measured constants was then built, applied,
and measured: no case where it helped, one seed showing a small loss. It was
reverted too. The engine already passes `min_after_floor` as a constant at two
of the four call sites, and where it does, that bound is tighter than the
variable one, so replacing the variable one is a no-op.

WHAT THIS FILE IS FOR. The code is unchanged, deliberately. What must not be
lost is the REASON, so that the next person to look at these bounds does not
repeat either mistake: believing the variable form protects something, or
believing replacing it is free improvement.

These tests assert the property directly against CP-SAT. They do not touch the
engine's behaviour.
"""
import unittest

from ortools.sat.python import cp_model


def _solve(bound, *, n=12, cap=2, measured_before=10):
    """Minimal model with the engine's shape: before/after coverage bools."""
    m = cp_model.CpModel()
    before = [m.NewIntVar(0, 10, f"b{i}") for i in range(n)]
    after = [m.NewIntVar(0, 10, f"a{i}") for i in range(n)]
    bh, ah = [], []
    for i in range(n):
        x = m.NewBoolVar(f"bh{i}")
        y = m.NewBoolVar(f"ah{i}")
        m.Add(before[i] >= 5).OnlyEnforceIf(x)
        m.Add(before[i] <= 4).OnlyEnforceIf(x.Not())
        m.Add(after[i] >= 5).OnlyEnforceIf(y)
        m.Add(after[i] <= 4).OnlyEnforceIf(y.Not())
        m.Add(after[i] <= before[i])          # breaks only remove staffing
        bh.append(x)
        ah.append(y)
    if bound == "variable":                    # the shape in the engine today
        m.Add(sum(ah) >= sum(bh) - cap)
    elif bound == "constant":                  # bounded against a measurement
        m.Add(sum(ah) >= measured_before - cap)
    m.Minimize(sum(after) + sum(before))       # any pressure to shed staffing
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 1
    s.parameters.max_time_in_seconds = 10
    st = s.Solve(m)
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE), s.StatusName(st)
    return sum(s.Value(v) for v in bh), sum(s.Value(v) for v in ah)


class JointBoundShape(unittest.TestCase):
    def test_the_variable_bound_protects_nothing(self):
        """`after >= before - cap` with both sides variable is not a protection.

        The solver satisfies it by driving `before` down until the inequality is
        trivial, so the answer is identical to having no bound at all.
        """
        none_before, none_after = _solve("none")
        var_before, var_after = _solve("variable")
        self.assertEqual(
            (var_before, var_after), (none_before, none_after),
            "the variable bound gave a different answer from no bound at all; "
            "if this now differs, the model shape has changed and the reasoning "
            "recorded in evidence/B13_JOINT_BOUNDS_DEGRADE_BEFORE.md needs revisiting")

    def test_a_constant_bound_does_protect(self):
        """Bounding against a measured integer cannot be gamed.

        Nothing on the right-hand side is a decision variable, so the solver
        cannot buy slack by degrading the schedule.
        """
        _, after_hits = _solve("constant", measured_before=10, cap=2)
        self.assertGreaterEqual(
            after_hits, 8,
            "a constant bound must hold the after-state at measured_before - cap")

    def test_the_engine_still_passes_a_constant_bound_somewhere(self):
        """`min_after_floor` / `min_after_target` are the protection that works.

        Two of the four joint call sites pass them and two pass None. Where they
        are passed they are tighter than the variable bound, which is why
        replacing the variable bound measured as a no-op. If these disappear,
        the only remaining protection becomes the one that protects nothing.
        """
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1]
                  / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertIn("min_after_floor is not None and floor_hits", source,
                      "the constant floor bound has gone; that is the one that works")
        self.assertIn("min_after_target is not None and target_hits", source,
                      "the constant target bound has gone; that is the one that works")


if __name__ == "__main__":
    unittest.main()
