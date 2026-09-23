#!/usr/bin/env python3
"""Guards for what B-4, B-5 and B-6 measured.

Two of those three turned out not to be defects, and one fix was written and
reverted because the data disproved its premise. These tests pin the facts that
made each call, so the calls stay checkable rather than remembered.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import l632_universal_scheduler as E  # noqa: E402
from phase_b_maturity import (  # noqa: E402
    PHASE_MINIMUM_VIABLE_SECONDS, build_global_budget_plan,
)

INT64_MAX = 2 ** 63 - 1


class PhaseViabilityIsReportedNotEnforced(unittest.TestCase):
    """B-4. The reporting must not quietly become an allocation rule again.

    A first version of this dropped any phase allocated below its entry guard
    and gave the seconds to break search. Phase deadlines are cumulative, so a
    phase inherits time earlier phases underran: post_break_repair held a
    nominal 19s against a 35s guard on a real run and still attempted a repair.
    Dropping on nominal allocation would have deleted real work.
    """

    def plan(self, total, stage1_need=0, diagnostics=None):
        return build_global_budget_plan(
            total, allow_exceptions=False, coordinated_repair=True,
            joint_refinement=True, post_break_repair=True,
            target_lock_recovery=True, finalization_reserve_sec=120,
            safe_incumbent_reserve_sec=180, conflict_refinement_reserve_sec=120,
            coordinated_repair_reserve_sec=300, joint_refinement_reserve_sec=900,
            stage1_minimum_seconds=stage1_need, diagnostics=diagnostics)

    def test_the_plan_is_unchanged_by_asking_for_diagnostics(self):
        for total in (900, 1800, 3600, 14400):
            with self.subTest(total=total):
                need = int(total * 0.45)
                self.assertEqual(self.plan(total, need), self.plan(total, need, {}))

    def test_a_phase_below_its_entry_guard_is_still_funded(self):
        # The reverted behaviour would have zeroed these.
        plan = self.plan(900, 405)
        self.assertGreater(plan["target_lock_recovery"], 0)
        self.assertGreater(plan["post_break_repair"], 0)

    def test_the_plan_still_sums_to_the_total_and_stays_integral(self):
        for total in (60, 300, 900, 3600, 14400):
            with self.subTest(total=total):
                plan = self.plan(total, int(total * 0.45), {})
                self.assertTrue(all(isinstance(v, int) for v in plan.values()))
                self.assertEqual(sum(plan.values()), max(60, total))

    def test_every_value_stays_coercible_for_the_budget_manager(self):
        # GlobalBudgetManager runs int() over every value; a nested dict in the
        # plan would break every run.
        plan = self.plan(900, 405, {})
        for name, value in plan.items():
            with self.subTest(phase=name):
                self.assertIsInstance(int(value), int)

    def test_the_diagnostic_names_the_phase_that_cannot_run_at_quick(self):
        diagnostics = {}
        self.plan(900, 405, diagnostics)
        at_risk = diagnostics["phases_below_minimum_viable_slice"]
        self.assertIn("target_lock_recovery", at_risk)
        row = at_risk["target_lock_recovery"]
        self.assertLess(row["allocated"], row["minimum_viable"])

    def test_target_lock_recovery_cannot_be_funded_at_quick_by_any_setting(self):
        # Its ceiling at 900s is below its own entry guard even when Stage 1
        # asks for nothing, which is why this is structural rather than tuning.
        best_case = self.plan(900, 0)["target_lock_recovery"]
        self.assertLess(best_case, PHASE_MINIMUM_VIABLE_SECONDS["target_lock_recovery"])

    def test_a_deep_run_funds_every_phase_above_its_guard(self):
        diagnostics = {}
        self.plan(14400, 6480, diagnostics)
        self.assertEqual(diagnostics["phases_below_minimum_viable_slice"], {})

    def test_each_minimum_matches_the_guard_the_phase_enforces(self):
        # The numbers are read off the phases themselves; if a guard moves, the
        # table must move with it or the diagnostic starts lying.
        source = ENGINE.read_text(encoding="utf-8")
        for phase, expected in (("run_target_lock_recovery_phase", 65),
                                ("run_post_break_repair_phase", 35),
                                ("run_coordinated_shift_off_break_loop", 45)):
            with self.subTest(phase=phase):
                body = source[source.index(f"def {phase}("):]
                body = body[:body.index("\ndef ", 10)]
                self.assertIn(f"remaining < {expected}", body)


class TheObjectiveIsAWeightedSumNotAPriorityOrder(unittest.TestCase):
    """B-5. Pin the measurement, and the reasons it is not a bug."""

    def test_priority_is_enforced_by_hard_constraints_not_by_weights(self):
        # This is why the 400M:1 range is not a correctness problem: a
        # guarantee is expressed as a bound, not as a large coefficient.
        import inspect
        params = inspect.signature(E.solve_breaks).parameters
        self.assertIn("min_target_hits", params)
        self.assertIn("min_floor_hits", params)

    def test_candidate_order_is_a_lexicographic_tuple_not_the_objective(self):
        self.assertTrue(hasattr(E, "_candidate_quality_tuple"))

    def test_the_declared_weights_stay_far_inside_int64(self):
        # A weight change that pushed the worst case near the limit would be a
        # real overflow bug. Measured worst case across the eight packaged
        # rosters is 7.0e12 - 1.5e13, about 6e5x of headroom. The bound below
        # is that measurement rounded up hard: the largest declared weight
        # against a generous 1e6 for terms-times-domain.
        worst_weight = max(
            abs(v)
            for profile in E.skeleton_profiles()
            for v in profile.values()
            if isinstance(v, int) and not isinstance(v, bool)
        )
        self.assertLess(worst_weight * (10 ** 6), INT64_MAX // 100)

    def test_no_declared_weight_is_negative(self):
        # Every term in this objective is a penalty to be minimized. A negative
        # weight would turn one into a reward, which no amount of tuning the
        # others could correct. Verified true across all 17 profiles today.
        for profile in E.skeleton_profiles():
            with self.subTest(profile=profile["name"]):
                for key, value in profile.items():
                    if isinstance(value, str) or isinstance(value, bool):
                        continue
                    self.assertGreaterEqual(value, 0, key)

    def test_only_the_documented_field_is_float_valued(self):
        # CP-SAT objective coefficients must be integral. `whole_week_balance_
        # scale` is a multiplier applied before the coefficient is formed, not
        # a coefficient itself; a float appearing anywhere else would mean a
        # weight is being fed to the model unrounded.
        float_fields = {
            key
            for profile in E.skeleton_profiles()
            for key, value in profile.items()
            if isinstance(value, float)
        }
        self.assertEqual(float_fields, {"whole_week_balance_scale"})


class SymmetryIsAlreadyBrokenBySolverPresolve(unittest.TestCase):
    """B-6. Pin why no manual symmetry breaking was added."""

    def test_the_engine_does_not_pin_symmetry_level(self):
        # Leaving it alone is the decision: OR-Tools defaults it to the enabled
        # level, and presolve installs an orbitope on these rosters. Setting it
        # by hand would need its own evidence.
        source = ENGINE.read_text(encoding="utf-8")
        self.assertNotIn("symmetry_level", source)

    def test_the_solver_default_is_the_enabled_level(self):
        from ortools.sat.python import cp_model
        self.assertGreaterEqual(cp_model.CpSolver().parameters.symmetry_level, 1)

    def test_no_hand_written_symmetry_breaking_was_added(self):
        # An orbitope from presolve and a hand-rolled ordering constraint can
        # interact badly; if one is ever added it must come with its own A/B.
        source = ENGINE.read_text(encoding="utf-8")
        for marker in ("symmetry_break", "lexicographic_associate_order",
                       "break_associate_symmetry"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main(verbosity=1)
