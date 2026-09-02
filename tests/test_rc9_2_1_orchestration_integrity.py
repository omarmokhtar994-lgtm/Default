#!/usr/bin/env python3
"""Guards for Stage-2 attempt planning, wall-clock budgeting and bound certificates.

Three defects, one theme: the orchestration layer quietly reported or assumed
more than it had.  The attempt plan ran objective modes nobody asked for, the
budget planner emitted a negative phase that became an over-allocation, and a
bound certificate that measured nothing published a relative gap of 0.0.

Run:  python tests/test_rc9_2_1_orchestration_integrity.py
"""
from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

from phase_b_adaptive import make_bound_certificate  # noqa: E402
from phase_b_maturity import (  # noqa: E402
    GlobalBudgetManager,
    adaptive_break_attempt_plan,
    build_global_budget_plan,
)

SKELETON = [{
    "before_target": 200, "before_floor": 240, "before_100": 100,
    "floor_gaps": 12, "severe_floor_gaps": 1, "max_floor_run": 2,
    "before_avoidable_overage_fte_sum": 10.0, "minimum_exception_count": 0,
}]

# What default_break_objective_modes returns outside quality_gate_mode="fail".
ENGINE_DEFAULT_WARN_MODES = [
    "target_priority", "coverage_rebalance", "balanced", "floor_protected", "target_100",
]


def modes_in(tasks):
    return list(dict.fromkeys(task.objective_mode for task in tasks))


class AttemptPlanHonoursTheRequestedObjectiveModes(unittest.TestCase):
    """`preferred_modes` was concatenated ahead of the caller's list.

    Every plan therefore ran all seven preferred modes whatever was asked for,
    which silently voided --break-objective-modes and spread a fixed Stage-2
    budget over modes the caller had excluded.
    """

    def test_a_single_requested_mode_yields_a_single_mode(self):
        tasks = adaptive_break_attempt_plan(SKELETON, [3], ["target_priority"])
        self.assertEqual(modes_in(tasks), ["target_priority"])
        self.assertEqual(len(tasks), 1, "one skeleton, one width, one mode")

    def test_the_engine_default_does_not_gain_the_quality_guard_modes(self):
        """In warn mode the engine deliberately omits those two modes."""
        tasks = adaptive_break_attempt_plan(SKELETON, [3], ENGINE_DEFAULT_WARN_MODES)
        got = modes_in(tasks)
        self.assertNotIn("release_quality_guard", got)
        self.assertNotIn("quality_convergence", got)
        self.assertEqual(sorted(got), sorted(ENGINE_DEFAULT_WARN_MODES))

    def test_no_plan_ever_schedules_an_unrequested_mode(self):
        for size in range(1, len(ENGINE_DEFAULT_WARN_MODES) + 1):
            for asked in itertools.combinations(ENGINE_DEFAULT_WARN_MODES, size):
                with self.subTest(asked=asked):
                    got = modes_in(adaptive_break_attempt_plan(SKELETON, [2, 3], list(asked)))
                    self.assertEqual(set(got), set(asked))

    def test_a_caller_specific_mode_is_kept_and_ranked_last(self):
        tasks = adaptive_break_attempt_plan(SKELETON, [3], ["custom_mode", "target_priority"])
        self.assertEqual(modes_in(tasks), ["target_priority", "custom_mode"])

    def test_relative_order_of_surviving_modes_is_unchanged(self):
        """The fix narrows the set; it must not reorder what remains."""
        tasks = adaptive_break_attempt_plan(SKELETON, [3], ENGINE_DEFAULT_WARN_MODES)
        self.assertEqual(
            modes_in(tasks),
            ["target_priority", "coverage_rebalance", "floor_protected", "balanced", "target_100"])

    def test_an_empty_request_still_produces_a_plan(self):
        self.assertTrue(adaptive_break_attempt_plan(SKELETON, [3], []))

    def test_the_production_default_plan_is_unchanged_by_the_fix(self):
        """The wrapper passes all seven modes explicitly, so nothing moves there.

        This is what bounds the blast radius: every run made through
        RUN_UNIVERSAL_PRODUCTION.py with default --break-objective-modes gets
        exactly the plan it got before. The fix only changes a request that
        actually restricts the modes - the case that was broken.
        """
        wrapper = (ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py").read_text(encoding="utf-8")
        line = next(l for l in wrapper.splitlines() if l.startswith("DEFAULT_BREAK_OBJECTIVES"))
        production_modes = line.split("=", 1)[1].strip().strip('"').split(",")
        self.assertEqual(len(production_modes), 7)

        widths = [24, 44, 60, 115]          # wrapper default --pattern-widths
        skeletons = SKELETON * 6
        tasks = adaptive_break_attempt_plan(skeletons, widths, production_modes)
        self.assertEqual(len(tasks), len(skeletons) * len(widths) * len(production_modes))
        self.assertEqual(set(modes_in(tasks)), set(production_modes))
        # Ranking order for the full set is the preferred order verbatim.
        self.assertEqual(modes_in(tasks), [
            "target_priority", "release_quality_guard", "coverage_rebalance",
            "quality_convergence", "floor_protected", "balanced", "target_100"])

    def test_task_count_is_skeletons_times_widths_times_modes(self):
        skeletons = SKELETON * 3
        tasks = adaptive_break_attempt_plan(skeletons, [1, 2, 3], ["target_priority", "balanced"])
        self.assertEqual(len(tasks), 3 * 3 * 2)


class BudgetPlanNeverExceedsOrUndercutsTheRun(unittest.TestCase):
    """At total=60 the per-phase floors sum to 110.

    `plan["break_search"] += total - sum(plan)` turned that into -20;
    GlobalBudgetManager clamped it to zero and ran a 60-second budget as an
    80-second allocation, so cumulative phase deadlines sat past the run's own
    final deadline.
    """

    def _plans(self):
        totals = list(range(1, 130)) + [180, 300, 480, 600, 900, 1800, 3600, 14400, 43200]
        for total in totals:
            for flags in itertools.product((True, False), repeat=5):
                allow, coord, joint, post, lock = flags
                yield total, build_global_budget_plan(
                    total, allow_exceptions=allow, coordinated_repair=coord,
                    joint_refinement=joint, post_break_repair=post,
                    target_lock_recovery=lock)

    def test_no_phase_is_ever_negative(self):
        for total, plan in self._plans():
            negative = {name: sec for name, sec in plan.items() if sec < 0}
            self.assertFalse(negative, f"total={total} produced {negative}")

    def test_every_plan_sums_to_the_effective_total(self):
        for total, plan in self._plans():
            self.assertEqual(sum(plan.values()), max(60, total), f"total={total}")

    def test_the_manager_never_over_allocates(self):
        for total, plan in self._plans():
            manager = GlobalBudgetManager(total_seconds=total, phase_seconds=plan)
            self.assertEqual(sum(manager.phase_seconds.values()), manager.total_seconds,
                             f"total={total}")

    def test_the_sixty_second_case_specifically(self):
        plan = build_global_budget_plan(60, allow_exceptions=True, coordinated_repair=True,
                                        target_lock_recovery=True)
        self.assertGreaterEqual(plan["break_search"], 0)
        self.assertEqual(sum(plan.values()), 60)
        manager = GlobalBudgetManager(total_seconds=60, phase_seconds=plan)
        self.assertEqual(sum(manager.phase_seconds.values()), 60)

    def test_no_phase_deadline_runs_past_the_final_deadline(self):
        for total, plan in self._plans():
            manager = GlobalBudgetManager(total_seconds=total, phase_seconds=plan)
            for phase in plan:
                self.assertLessEqual(
                    manager.deadline(phase), manager.final_deadline + 1e-6,
                    f"total={total} phase={phase} ends after the run does")

    def test_a_manager_given_an_oversized_plan_rescales_it(self):
        manager = GlobalBudgetManager(
            total_seconds=100,
            phase_seconds={"stage1_search": 400, "break_search": 400, "finalization": 400})
        self.assertEqual(sum(manager.phase_seconds.values()), 100)
        self.assertTrue(all(v >= 0 for v in manager.phase_seconds.values()))

    def test_a_large_realistic_budget_is_untouched(self):
        plan = build_global_budget_plan(14400, allow_exceptions=True, coordinated_repair=True,
                                        target_lock_recovery=True)
        self.assertEqual(sum(plan.values()), 14400)
        self.assertGreater(plan["stage1_search"], 0)
        self.assertGreater(plan["break_search"], 0)
        self.assertGreater(plan["finalization"], 0)


class BoundCertificateDistinguishesUnmeasuredFromTight(unittest.TestCase):

    def test_nothing_measured_reports_none_not_zero(self):
        cert = make_bound_certificate([
            {"status": "FEASIBLE", "sense": "maximize",
             "objective_value": None, "best_objective_bound": None}])
        self.assertIsNone(cert["maximum_relative_gap"],
                          "0.0 reads as a proven-tight bound; nothing was measured")
        self.assertEqual(cert["measured_stage_count"], 0)
        self.assertFalse(cert["all_stages_optimal"])

    def test_a_genuinely_tight_bound_still_reports_zero(self):
        cert = make_bound_certificate([
            {"status": "OPTIMAL", "sense": "maximize",
             "objective_value": 100.0, "best_objective_bound": 100.0}])
        self.assertEqual(cert["maximum_relative_gap"], 0.0)
        self.assertEqual(cert["measured_stage_count"], 1)
        self.assertTrue(cert["all_stages_optimal"])

    def test_a_mixed_certificate_reports_the_measured_maximum(self):
        cert = make_bound_certificate([
            {"status": "OPTIMAL", "sense": "maximize",
             "objective_value": 90.0, "best_objective_bound": 100.0},
            {"status": "FEASIBLE", "sense": "maximize",
             "objective_value": None, "best_objective_bound": None}])
        self.assertEqual(cert["maximum_relative_gap"], 0.1)
        self.assertEqual(cert["measured_stage_count"], 1)
        self.assertFalse(cert["all_stages_optimal"])

    def test_an_empty_certificate_measures_nothing(self):
        cert = make_bound_certificate([])
        self.assertIsNone(cert["maximum_relative_gap"])
        self.assertEqual(cert["stage_count"], 0)


class ProtectedBenchmarkStatusIsNotAConstant(unittest.TestCase):
    """The engine published protected_benchmark_status="PASS" unconditionally.

    All four executed RC9.2.1 runs carry that value with both protected
    minimums empty, and tools/release_gate_report.py reads exactly this field
    for gate 4 - so gate 4 passed on a benchmark that never ran.
    """

    def test_the_literal_pass_is_gone_from_the_summary_row(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        self.assertFalse(
            '"protected_benchmark_status": "PASS",' in source,
            "the summary row must derive this from whether a minimum was configured")

    def test_it_is_conditioned_on_a_configured_minimum(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        compact = " ".join(source.split())
        self.assertTrue(
            '"protected_benchmark_status": ( "PASS" if (protected_before80_min is not None '
            'or protected_after80_min is not None) else "NOT_CONFIGURED")' in compact,
            "protected_benchmark_status must report NOT_CONFIGURED when neither "
            "protected minimum was supplied")


if __name__ == "__main__":
    unittest.main(verbosity=2)
