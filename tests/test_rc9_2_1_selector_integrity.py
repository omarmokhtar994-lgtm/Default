#!/usr/bin/env python3
"""RC9.2.1 candidate-ranking integrity guards.

These tests pin the defects corrected in the RC9.2.1 deficit-quantization pass
so they cannot silently return.  They are pure selector/metric tests: no CP-SAT
solve, no workbook, so they run in seconds and are safe to gate every commit.

Run:  python tests/test_rc9_2_1_selector_integrity.py
"""
from __future__ import annotations

import sys
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import l632_universal_scheduler as E  # noqa: E402


def contract(target: float, floor: float, active_days: int = 7, per_day: int = 36):
    """Minimal ParsedInput stand-in for pure ranking tests."""
    return SimpleNamespace(
        target_ratio=target,
        floor_ratio=floor,
        active=[[True] * per_day] * active_days,
    )


# NMG EN as recorded in the RC9.2.1 solver audit: target 90%, configured floor
# 75%, protected safety tier 80%, 252 active intervals.
NMG_EN = contract(0.90, 0.75)


def metrics(floor_deficit: float, avoidable_overage: float, **overrides):
    """Coverage-identical candidate differing only in deficit and overage."""
    base = {
        "active_intervals": 252,
        "before_target": 228,
        "before_90": 228,
        "before_80": 230,
        "before_floor": 232,
        "before_100": 219,
        "before_severe_floor_gap_count": 19,
        "before_max_consecutive_floor_gaps": 10,
        "before_floor_deficit_sum": floor_deficit,
        "before_floor_deficit_max": 0.05,
        "before_target_deficit_sum": 0.0,
        "floor_deficit_sum": floor_deficit,
        "floor_deficit_max": 0.05,
        "before_avoidable_overage_fte_sum": avoidable_overage,
        "before_avoidable_overage_peak_fte": avoidable_overage / 100.0,
        "before_avoidable_overage_stddev_fte": avoidable_overage / 500.0,
    }
    base.update(overrides)
    return base


def winner(parsed, a, b, prefix="before"):
    """Return 'a', 'b' or 'tie' under the engine's own ranking."""
    ta = E._candidate_quality_tuple(parsed, a, prefix)
    tb = E._candidate_quality_tuple(parsed, b, prefix)
    if ta > tb:
        return "a"
    if tb > ta:
        return "b"
    return "tie"


def decided_at(parsed, a, b, prefix="before"):
    """Index of the first differing tuple position, or None if identical."""
    ta = E._candidate_quality_tuple(parsed, a, prefix)
    tb = E._candidate_quality_tuple(parsed, b, prefix)
    return next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), None)


class OverageMustNotBeMaskedByDeficitNoise(unittest.TestCase):
    """The RC9.2.1 defect: sub-operational deficit differences outranked overage.

    Before the fix, a floor-deficit difference of one part in 1e8 beat a 141 FTE
    avoidable-overage difference, because the raw float sat above the balance
    block in a lexicographic tuple.
    """

    def test_negligible_deficit_difference_does_not_outrank_large_overage(self):
        worse_overage = metrics(1.20000000, 1244.11)
        better_overage = metrics(1.20000001, 1103.08)
        self.assertEqual(
            winner(NMG_EN, worse_overage, better_overage), "b",
            "A 1e-8 floor-deficit difference must not outrank 141 FTE of "
            "avoidable overage; the balance block is being masked again.",
        )

    def test_sub_quantum_deficit_differences_tie_so_balance_can_decide(self):
        quantum = E.FLOOR_DEFICIT_COMPARISON_QUANTUM
        a = metrics(1.20, 1244.11)
        b = metrics(1.20 + quantum * 0.4, 1103.08)
        self.assertEqual(
            winner(NMG_EN, a, b), "b",
            "Deficit differences below one quantum must fall through to the "
            "balance/overage terms.",
        )

    def test_balance_block_is_actually_reached(self):
        a = metrics(1.20000000, 1244.11)
        b = metrics(1.20000001, 1103.08)
        index = decided_at(NMG_EN, a, b)
        tuple_a = E._candidate_quality_tuple(NMG_EN, a, "before")
        overage_index = tuple_a.index(-1244.11)
        self.assertEqual(
            index, overage_index,
            "Comparison must be decided by the avoidable-overage term, not by a "
            "deficit term above it.",
        )


class FloorPriorityMustSurviveTheFix(unittest.TestCase):
    """The fix must not weaken the floor to buy balance - that inverts priority.

    The notepad is explicit: never reduce floor quality to improve overage.  A
    materially worse floor deficit must still lose regardless of how good its
    overage is.
    """

    def test_material_deficit_difference_still_outranks_overage(self):
        quantum = E.FLOOR_DEFICIT_COMPARISON_QUANTUM
        good_floor_bad_overage = metrics(1.20, 9999.00)
        bad_floor_good_overage = metrics(1.20 + quantum * 5, 1.00)
        self.assertEqual(
            winner(NMG_EN, good_floor_bad_overage, bad_floor_good_overage), "a",
            "A materially worse floor deficit must never be bought with better "
            "overage.",
        )

    def test_target_still_outranks_everything(self):
        strong_target = metrics(9.99, 9999.00, before_target=229, before_90=229)
        weak_target = metrics(0.00, 1.00, before_target=228, before_90=228)
        self.assertEqual(
            winner(NMG_EN, strong_target, weak_target), "a",
            "Workbook target must remain the primary objective.",
        )

    def test_protected_tier_still_outranks_floor_and_balance(self):
        strong_protected = metrics(9.99, 9999.00, before_80=231)
        weak_protected = metrics(0.00, 1.00, before_80=230, before_floor=252)
        self.assertEqual(
            winner(NMG_EN, strong_protected, weak_protected), "a",
            "The 80% protected tier under a 90% target must outrank floor and "
            "balance.",
        )

    def test_higher_tier_upside_remains_last(self):
        more_100s = metrics(1.20, 1244.11, before_100=240)
        better_overage = metrics(1.20, 1103.08, before_100=200)
        self.assertEqual(
            winner(NMG_EN, more_100s, better_overage), "b",
            "100% upside must not outrank balance at equal target - this is the "
            "original RC9.1 selector defect.",
        )


class DeficitBucketing(unittest.TestCase):
    def test_bucket_is_monotonic_and_integral(self):
        q = E.FLOOR_DEFICIT_COMPARISON_QUANTUM
        self.assertIsInstance(E._deficit_bucket(1.0), int)
        self.assertEqual(E._deficit_bucket(0.0), 0)
        self.assertLess(E._deficit_bucket(1.0), E._deficit_bucket(1.0 + q * 2))
        self.assertEqual(E._deficit_bucket(1.0), E._deficit_bucket(1.0 + q * 0.4))

    def test_negative_and_none_are_safe(self):
        self.assertEqual(E._deficit_bucket(-5.0), 0)
        self.assertEqual(E._deficit_bucket(None), 0)

    def test_zero_quantum_disables_bucketing_without_crashing(self):
        self.assertEqual(E._deficit_bucket(1.0, 0.0), 0)


class PrefixedMetricResolution(unittest.TestCase):
    """Before-break ranking must read before-break deficits when available."""

    def test_prefers_prefixed_key(self):
        m = {"before_floor_deficit_sum": 1.0, "floor_deficit_sum": 99.0}
        self.assertEqual(E._prefixed_metric(m, "before", "floor_deficit_sum"), 1.0)

    def test_falls_back_to_bare_key_for_legacy_candidates(self):
        m = {"floor_deficit_sum": 7.0}
        self.assertEqual(E._prefixed_metric(m, "before", "floor_deficit_sum"), 7.0)

    def test_missing_everywhere_is_zero(self):
        self.assertEqual(E._prefixed_metric({}, "before", "floor_deficit_sum"), 0.0)

    def test_after_prefix_resolves_independently(self):
        m = {"before_floor_deficit_sum": 1.0, "after_floor_deficit_sum": 5.0}
        self.assertEqual(E._prefixed_metric(m, "after", "floor_deficit_sum"), 5.0)


class ProtectedTierSelectionAcrossTargets(unittest.TestCase):
    """Protected tiers must follow the workbook contract, not a fixed table."""

    def test_target90_floor75_protects_80_only(self):
        m = {"before_100": 1, "before_90": 2, "before_80": 3}
        self.assertEqual(
            E._protected_tier_counts(contract(0.90, 0.75), m, "before"), (3,))

    def test_target100_floor80_protects_90_only(self):
        m = {"before_100": 1, "before_90": 2, "before_80": 3}
        self.assertEqual(
            E._protected_tier_counts(contract(1.00, 0.80), m, "before"), (2,))

    def test_target100_floor75_protects_90_then_80(self):
        m = {"before_100": 1, "before_90": 2, "before_80": 3}
        self.assertEqual(
            E._protected_tier_counts(contract(1.00, 0.75), m, "before"), (2, 3))

    def test_target80_has_no_protected_tier_between_target_and_floor(self):
        m = {"before_100": 1, "before_90": 2, "before_80": 3}
        self.assertEqual(
            E._protected_tier_counts(contract(0.80, 0.75), m, "before"), ())

    def test_upside_tiers_are_target_relative(self):
        m = {"before_100": 7, "before_90": 9}
        self.assertEqual(E._target_secondary_counts(m, "before", 1.00), ())
        self.assertEqual(E._target_secondary_counts(m, "before", 0.90), (7,))
        self.assertEqual(E._target_secondary_counts(m, "before", 0.80), (9, 7))


class DeterminismAndTotalOrder(unittest.TestCase):
    def test_ranking_is_deterministic(self):
        m = metrics(1.2, 1244.11)
        first = E._candidate_quality_tuple(NMG_EN, m, "before")
        for _ in range(50):
            self.assertEqual(E._candidate_quality_tuple(NMG_EN, m, "before"), first)

    def test_all_terms_are_comparable_scalars(self):
        t = E._candidate_quality_tuple(NMG_EN, metrics(1.2, 1244.11), "before")
        for i, value in enumerate(t):
            self.assertIsInstance(
                value, (int, float, bool),
                f"tuple position {i} is {type(value)}; non-scalar terms make "
                "sorting order-dependent",
            )

    def test_identical_metrics_tie_exactly(self):
        self.assertEqual(winner(NMG_EN, metrics(1.2, 500.0), metrics(1.2, 500.0)), "tie")

    def test_empty_metrics_does_not_crash(self):
        E._candidate_quality_tuple(NMG_EN, {}, "before")
        E._candidate_quality_tuple(NMG_EN, {}, "after")


class ReleaseIdentityIntegrity(unittest.TestCase):
    """The wrapper must never stamp runs with a stale release name."""

    def test_wrapper_release_matches_engine_version(self):
        sys.path.insert(0, str(ROOT / "engine"))
        import importlib

        runner = importlib.import_module("RUN_UNIVERSAL_PRODUCTION")
        self.assertEqual(
            runner.RELEASE, E.VERSION,
            "Wrapper RELEASE has drifted from the engine VERSION it invokes; "
            "runs would be recorded under the wrong release.",
        )

    def test_engine_version_is_rc9_2_1(self):
        self.assertEqual(
            E.VERSION, "L6.3.2.6-RC9.2.2-BUDGETED-SEARCH-AND-BREAK-CONCURRENCY-RC1")


class SkeletonOnlyLeaderboardIsAuditable(unittest.TestCase):
    """A skeleton-only leaderboard must explain its own champion selection.

    The deficit and overage columns decide the champion once target, protected
    tier, floor and gap quality tie.  They were previously omitted from
    skeleton-only exports, so the artifact could not be audited after the fact -
    which is exactly what a before-break proof run is for.
    """

    def _rows(self):
        sk = E.SkeletonSolution("p1", "FEASIBLE", 0.0, 0.0, [], [], {})
        sk.diagnostics["no_break_metrics"] = metrics(1.25, 1244.11)
        sk.selected_shift_index = [[0]]
        return E.before_break_leaderboard_rows([sk], sk)

    def test_deficit_and_overage_columns_are_populated(self):
        row = self._rows()[0]
        for key in ("floor_deficit_sum", "target_deficit_sum",
                    "before_avoidable_overage_fte_sum", "before_target_overage_fte_sum"):
            self.assertIn(key, row, f"{key} missing from skeleton-only leaderboard row")
            self.assertIsNotNone(row[key], f"{key} exported as blank")

    def test_values_match_the_candidate_metrics(self):
        row = self._rows()[0]
        self.assertAlmostEqual(row["floor_deficit_sum"], 1.25, places=9)
        self.assertAlmostEqual(row["before_avoidable_overage_fte_sum"], 1244.11, places=9)

    def test_bucket_is_exported_for_traceability(self):
        row = self._rows()[0]
        self.assertEqual(row["floor_deficit_bucket"], E._deficit_bucket(1.25))

class DiagnosticBreakSolutionsAreNotPromoted(unittest.TestCase):
    """Stage 2 must separate solver bootstrap from production selection.

    Stage 1 has done this since RC8.9 via skeleton_release_diagnostic_only.
    Stage 2 had no counterpart, and the gap was load-bearing: a diagnostic break
    solve runs with diagnostic_mode set, which drops the soft objective terms
    including the break-concurrency penalty.  Under the default "warn" gate the
    concurrency cap is then neither hard constraint nor penalty.

    Measured on Cricut Chat: the diagnostic fallback reached 8 concurrent breaks
    against a configured cap of 4, violated it 68 times, and cost 55 target
    intervals (187 -> 132, 22.7% of active) - yet was promoted, because the pool
    is filtered by minimum exception count first and a zero-exception probe wins
    that filter by construction.
    """

    def _solution(self, objective_mode, exceptions=0, profile="p"):
        return E.BreakSolution(
            profile=profile, skeleton_profile="sk", cp_status="FEASIBLE",
            elapsed_sec=0.0, objective=0.0, pattern_width=115, exception_mode=False,
            selected_pattern={}, no_break_cells=set(range(exceptions)), patterns=[],
            diagnostics={"objective_mode": objective_mode}, metrics={},
        )

    def test_diagnostic_fallback_is_recognised(self):
        self.assertTrue(E.break_release_diagnostic_only(
            self._solution("diagnostic_zero_exception_fallback")))

    def test_diagnostic_assignment_is_recognised(self):
        self.assertTrue(E.break_release_diagnostic_only(
            self._solution("diagnostic_zero_exception_assignment")))

    def test_min_exceptions_probe_is_recognised(self):
        """solve_breaks sets diagnostic_mode = (objective_mode == 'min_exceptions')."""
        self.assertTrue(E.break_release_diagnostic_only(self._solution("min_exceptions")))

    def test_production_modes_are_not_flagged(self):
        for mode in ("target_priority", "fallback_revalidation", "before_breaks_only"):
            with self.subTest(mode=mode):
                self.assertFalse(E.break_release_diagnostic_only(self._solution(mode)))

    def test_diagnostic_profile_name_is_recognised(self):
        self.assertTrue(E.break_release_diagnostic_only(
            self._solution("target_priority", profile="fully_compliant_diagnostic_fallback")))

    def test_exclusion_runs_before_the_minimum_exception_filter(self):
        """The ordering that made the defect reachable.

        A zero-exception diagnostic probe must not evict a production candidate
        that needs one exception. If the min-exception filter ran first it would.
        """
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        start = source.index("def select_export_candidates")
        body = source[start:start + 3000]
        exclusion = body.index("break_release_diagnostic_only")
        min_filter = body.index("min_exceptions = min(")
        self.assertLess(exclusion, min_filter,
                        "diagnostic exclusion must precede the minimum-exception "
                        "filter, or a zero-exception probe wins by construction")

    def test_exclusion_is_a_preference_not_a_prohibition(self):
        """If every candidate is diagnostic, the pool must survive."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        self.assertIn("if production_pool:", source,
                      "a scenario whose only solution is diagnostic must still "
                      "produce that solution")

    def test_exclusion_is_reported(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        self.assertIn("diagnostic_break_candidates_excluded", source)
        self.assertIn("diagnostic_break_fallback_used", source)


class Stage1FundsDepthBeforeWidth(unittest.TestCase):
    """45 seconds is not a short attempt; on AE AR B2B it is no attempt.

    The old `max(45.0, remaining * 0.82 / attempts_left)` clamped the slice up
    rather than clamping the portfolio down, so a window that could not pay for
    the portfolio ran it anyway at a depth that produced nothing.  Probe
    evidence (evidence/STAGE1_SLICE_DEPTH_PROBE.md): AE AR B2B returns UNKNOWN
    at 45s and FEASIBLE at 150s for the same profile and seed.
    """

    def test_the_minimum_slice_is_above_the_measured_no_solution_point(self):
        self.assertGreater(
            E.STAGE1_MIN_MEANINGFUL_SLICE_SEC, 45.0,
            "45s is the slice every recorded RC9.2.1 run used and the slice at "
            "which AE AR B2B produced no skeleton at all")

    def test_a_window_that_funds_nothing_reports_zero(self):
        self.assertEqual(E.stage1_fundable_profile_count(0), 0)
        self.assertEqual(E.stage1_fundable_profile_count(-100), 0)
        self.assertEqual(
            E.stage1_fundable_profile_count(E.STAGE1_MIN_MEANINGFUL_SLICE_SEC * 0.5), 0)

    def test_the_count_never_promises_more_depth_than_the_window_holds(self):
        for window in (0, 30, 100, 240, 500, 1000, 3000, 14400):
            count = E.stage1_fundable_profile_count(window)
            with self.subTest(window=window):
                self.assertLessEqual(
                    count * E.STAGE1_MIN_MEANINGFUL_SLICE_SEC,
                    window * E.STAGE1_SLICE_UTILIZATION + 1e-9,
                    "the funded portfolio must fit inside the window")

    def test_the_count_grows_with_the_window(self):
        counts = [E.stage1_fundable_profile_count(w) for w in range(0, 4000, 50)]
        self.assertEqual(counts, sorted(counts))
        self.assertGreater(counts[-1], counts[0])

    def test_the_real_regression_window_funds_almost_nothing(self):
        """150s was the actual AE AR B2B Stage-1 window for 15 profiles."""
        self.assertLessEqual(
            E.stage1_fundable_profile_count(150), 1,
            "a 150-second window cannot honestly fund a fifteen-profile portfolio")

    def test_the_slice_never_drops_to_the_old_forty_five_second_floor(self):
        """The exact call shape the recorded runs made, at every scenario size."""
        for attempts_left in range(1, 18):
            with self.subTest(attempts_left=attempts_left):
                self.assertGreaterEqual(
                    E.stage1_slice_seconds(150.0, attempts_left),
                    E.STAGE1_MIN_MEANINGFUL_SLICE_SEC)

    def test_the_slice_never_exceeds_the_window_it_was_given(self):
        """A floor that overruns the deadline just moves the starvation later."""
        for remaining in (0, 1, 45, 150, 400, 1000, 5000, 20000):
            for attempts_left in (1, 3, 15, 40):
                with self.subTest(remaining=remaining, attempts_left=attempts_left):
                    proposed = E.stage1_slice_seconds(remaining, attempts_left)
                    self.assertLessEqual(
                        proposed,
                        max(E.STAGE1_MIN_MEANINGFUL_SLICE_SEC,
                            remaining * E.STAGE1_SLICE_UTILIZATION) + 1e-9)

    def test_a_wide_window_still_shares_evenly(self):
        """Depth-first must not become depth-only: a funded portfolio splits."""
        wide = E.stage1_slice_seconds(9000.0, 15)
        self.assertGreater(wide, E.STAGE1_MIN_MEANINGFUL_SLICE_SEC)
        self.assertAlmostEqual(wide, 9000.0 * E.STAGE1_SLICE_UTILIZATION / 15, places=6)

    def test_the_slice_is_capped(self):
        self.assertLessEqual(E.stage1_slice_seconds(10 ** 6, 1), E.STAGE1_MAX_SLICE_SEC)

    def test_the_forty_five_second_floor_is_gone_from_the_stage1_loop(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertFalse(
            "max(45.0, remaining * 0.82 / attempts_left)" in source,
            "the Stage-1 slice must no longer clamp up to a 45-second floor")

    def test_the_loop_uses_the_helper(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertTrue(
            "slice_sec = stage1_slice_seconds(remaining, attempts_left)" in source,
            "the Stage-1 loop must take its slice from the guarded helper")


class Stage2AnchorStaysInsideItsReservation(unittest.TestCase):
    """The anchor protects ONE break solve; it is not the break search.

    `guard_slice = min(900.0, max(45.0, remaining * 0.80))` ignored the
    reservation the audit reported. On the AE AR B2B verification run the
    record said `reserved_seconds: 77` and the anchor spent **599.7** seconds
    of a 678-second phase, leaving 78 seconds for the adaptive break search:
    six attempts at 20s covering three of the seven requested objective modes.
    Gate 5 failed at 6.0% target loss with the search effectively never run.

    The 600 seconds bought nothing measurable: the anchor returned objective
    156703574, the same value a 20-second attempt on the same skeleton, width
    and objective mode reached.
    """

    def test_the_anchor_gets_its_reservation_not_the_phase(self):
        """The exact numbers from the AE AR B2B verification run."""
        granted = E.stage2_anchor_slice_seconds(77, 678)
        self.assertEqual(granted, 77.0)
        self.assertLess(granted, 599.7,
                        "the anchor must no longer outspend its reservation")

    def test_the_adaptive_search_keeps_the_rest_of_the_phase(self):
        for remaining in (300, 678, 1200, 5000):
            with self.subTest(remaining=remaining):
                granted = E.stage2_anchor_slice_seconds(77, remaining)
                self.assertGreaterEqual(
                    remaining - granted, remaining * 0.20,
                    "the break search that follows must keep the phase")

    def test_the_phase_share_is_a_ceiling_not_the_allowance(self):
        """A large reservation still cannot take the whole phase."""
        for remaining in (100, 500, 2000):
            with self.subTest(remaining=remaining):
                granted = E.stage2_anchor_slice_seconds(10 ** 6, remaining)
                self.assertLessEqual(granted, remaining * E.STAGE2_ANCHOR_MAX_PHASE_SHARE + 1e-9)
                self.assertLessEqual(granted, E.STAGE2_ANCHOR_MAX_SLICE_SEC)

    def test_it_never_exceeds_the_time_that_is_left(self):
        for reserved in (0, 30, 77, 500, 5000):
            for remaining in (0, 10, 46, 100, 900, 10000):
                with self.subTest(reserved=reserved, remaining=remaining):
                    self.assertLessEqual(
                        E.stage2_anchor_slice_seconds(reserved, remaining), remaining + 1e-9)

    def test_a_tiny_reservation_still_buys_a_real_solve(self):
        """The reservation is a floor to protect, not a cap to shrink under."""
        self.assertGreaterEqual(E.stage2_anchor_slice_seconds(5, 600),
                                E.STAGE2_ANCHOR_MIN_SLICE_SEC)

    def test_it_is_never_negative(self):
        for reserved in (-100, 0, 77):
            for remaining in (-50, 0, 1):
                with self.subTest(reserved=reserved, remaining=remaining):
                    self.assertGreaterEqual(
                        E.stage2_anchor_slice_seconds(reserved, remaining), 0.0)

    def test_the_phase_grab_is_gone_from_the_anchor(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertFalse(
            "guard_slice = min(900.0, max(45.0, remaining * 0.80))" in source,
            "the anchor must not take 80% of the break-search phase")
        self.assertTrue(
            "guard_slice = stage2_anchor_slice_seconds(stage2_guard_reserve_sec, remaining)" in source,
            "the anchor must take its slice from the guarded helper")

    def test_the_audit_records_what_the_anchor_was_actually_granted(self):
        """`reserved_seconds` alone hid a 7.8x overrun for a whole release."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertTrue('"granted_seconds": round(guard_slice, 3),' in source)


class BreakSearchFundsDepthBeforeWidth(unittest.TestCase):
    """20 seconds of break search produces no schedule at all.

    Third instance of the clamp-up pattern, after A34's 45-second Stage-1 floor
    and A35's anchor. `budget_manager.slice_seconds(..., minimum=20.0)` raised
    the even split to 20s and ran it many times: the A35 verification run made
    25 attempts at exactly 20.0s, ten of which returned UNKNOWN, and shipped
    after_target 156.

    Measured on AE AR B2B from a 168/168 skeleton (width 115, target_priority):

        20s UNKNOWN | 60s UNKNOWN | 90s 160 | 120s 160 | 150s 160
        180s 162    | 450s 162

    One attempt at 180s ships 162 - six intervals better than 25 attempts at
    20s, with after_floor at a full 168.
    """

    def test_the_minimum_is_above_the_measured_no_solution_point(self):
        self.assertGreater(
            E.BREAK_MIN_MEANINGFUL_SLICE_SEC, 60.0,
            "60s is the longest slice measured to return no schedule at all")

    def test_the_minimum_reaches_the_measured_plateau(self):
        """90-150s all return 160; 180s is where 162 appears."""
        self.assertGreaterEqual(E.BREAK_MIN_MEANINGFUL_SLICE_SEC, 180.0)

    def test_the_old_twenty_second_floor_is_gone(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertFalse(
            "minimum=20.0," in source,
            "the adaptive break search must not clamp attempts up to 20 seconds")
        self.assertTrue(
            "minimum=BREAK_MIN_MEANINGFUL_SLICE_SEC," in source,
            "the break slice must come from the measured minimum")

    def test_a_short_tail_stops_instead_of_running_attempts_that_cannot_converge(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertFalse(
            "if slice_sec < 10:" in source,
            "a 10-second guard still admits attempts that return UNKNOWN")
        self.assertTrue(
            "if slice_sec < BREAK_MIN_MEANINGFUL_SLICE_SEC:" in source,
            "the loop must stop when the phase cannot fund a real attempt")

    def test_stopping_early_is_recorded_not_silent(self):
        """A28's lesson: a search that stops short must say so in the audit."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertTrue(
            '"cp_status": "STOPPED_INSUFFICIENT_BREAK_SEARCH_DEPTH",' in source)
        self.assertTrue(
            '"ADAPTIVE_BREAK_SEARCH_STOPPED_INSUFFICIENT_DEPTH",' in source)

    def test_a_funded_phase_still_shares_across_attempts(self):
        """Depth-first must not become one-attempt-only."""
        from phase_b_maturity import GlobalBudgetManager
        manager = GlobalBudgetManager(
            total_seconds=7200, phase_seconds={"break_search": 7200})
        wide = manager.slice_seconds(
            "break_search", attempts_left=8,
            minimum=E.BREAK_MIN_MEANINGFUL_SLICE_SEC, maximum=900.0, share=0.86)
        self.assertGreater(wide, E.BREAK_MIN_MEANINGFUL_SLICE_SEC,
                           "a large phase must still split, not floor out")
        self.assertLessEqual(wide, 900.0)


class BreakConcurrencyPenaltyCanActuallyInfluenceTheSolution(unittest.TestCase):
    """The guard existed, was measured, was reported - and could not bite.

    In warn mode the excess-concurrency penalty was a fixed 5,000 while break
    objective `target_miss` weights run from 80,000,000 to 4,800,000,000. The
    solver would therefore accept roughly 640,000 concurrency violations before
    they cost as much as one missed target interval.

    NMG EN+SP recorded 18 violations and lost 35 of 252 target intervals to
    breaks - more than placing breaks blind would have cost (11.1% of a shift
    is break time; it lost 13.9%). Cricut Voice, on the same engine, absorbed
    97% of that structural cost. The machinery works; the penalty could not
    steer it.
    """

    WEIGHTS = {"target_miss": 3_200_000_000, "floor_miss": 420_000_000}

    def _parsed(self, explicit=None):
        return SimpleNamespace(break_concurrency_penalty_weight=explicit)

    def test_the_derived_weight_is_commensurate_with_a_missed_target(self):
        w = E.break_concurrency_weight(self._parsed(), self.WEIGHTS)
        self.assertGreaterEqual(w, self.WEIGHTS["target_miss"],
                                "an excess break removes coverage; it must cost "
                                "what that coverage costs")

    def test_the_old_fixed_default_could_not_bite(self):
        """Pins the arithmetic that made the guard inert."""
        self.assertGreater(self.WEIGHTS["target_miss"] // 5000, 100_000,
                           "5,000 against these weights is not a penalty")

    def test_a_workbook_value_still_wins_outright(self):
        w = E.break_concurrency_weight(self._parsed(explicit=250), self.WEIGHTS)
        self.assertEqual(w, 250, "an explicit business setting is authoritative")

    def test_a_workbook_value_is_never_below_one(self):
        self.assertGreaterEqual(E.break_concurrency_weight(self._parsed(explicit=0), self.WEIGHTS), 1)

    def test_a_weightless_objective_still_gets_a_real_penalty(self):
        w = E.break_concurrency_weight(self._parsed(), {})
        self.assertGreaterEqual(w, 5000, "never weaker than the old default")

    def test_floor_led_objectives_scale_on_floor(self):
        """Some break modes lead on floor_miss, not target_miss."""
        w = E.break_concurrency_weight(self._parsed(), {"target_miss": 80_000_000,
                                                        "floor_miss": 4_800_000_000})
        self.assertEqual(w, 4_800_000_000)

    def test_the_fixed_constant_is_gone_from_the_objective(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertFalse(
            'getattr(parsed, "break_concurrency_penalty_weight", 5000) * concurrency_excess' in source,
            "the objective must not hardcode the inert 5,000 default")
        self.assertEqual(
            source.count("break_concurrency_weight(parsed, weights) * concurrency_excess"), 2,
            "both concurrency penalty sites must use the derived weight")

    def test_fail_mode_is_still_a_hard_constraint(self):
        """Scaling the penalty must not weaken the enforced path."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertTrue(
            'add_break_family(model.Add(break_count <= concurrency_cap), "break_concurrency")' in source)


class BalancedCandidateIsExportedNotOnlyTheExtremes(unittest.TestCase):
    """The frontier's two ends were exported; the knee was not.

    On NMG EN+SP the recommended candidate scored after_target 153 /
    after_floor 203, MAX_FLOOR scored 130 / 223 - twenty-three target intervals
    given up - and a candidate at 150 / 212, with 26% less avoidable overage and
    five fewer extreme-overage intervals, sat between them and was exported
    nowhere. A planner could not choose it because it was never written out.
    """

    # The real NMG EN+SP leaderboard, after_target / after_floor / overage.
    LEADERBOARD = [
        (153, 203, 29.96), (153, 205, 32.41), (150, 212, 22.07), (150, 211, 22.07),
        (148, 213, 20.41), (148, 213, 21.20), (143, 214, 22.68), (140, 213, 18.89),
        (138, 215, 20.88), (136, 217, 20.06), (130, 223, 18.86),
    ]

    def _key(self, row):
        at, af, ov = row
        return (at + af, af, -ov)

    def test_it_selects_the_knee_not_an_end(self):
        best = max(self.LEADERBOARD, key=self._key)
        self.assertEqual(best[:2], (150, 212),
                         "coverage-sum must pick the knee of the real frontier")

    def test_the_knee_beats_both_extremes_on_total_coverage(self):
        knee = max(self.LEADERBOARD, key=self._key)
        recommended = self.LEADERBOARD[0]
        max_floor = min(self.LEADERBOARD, key=lambda r: r[0])
        self.assertGreater(knee[0] + knee[1], recommended[0] + recommended[1])
        self.assertGreater(knee[0] + knee[1], max_floor[0] + max_floor[1])

    def test_ties_break_toward_floor_then_lower_overage(self):
        """148/213 at 20.41 must beat 148/213 at 21.20."""
        tied = [(148, 213, 21.20), (148, 213, 20.41)]
        self.assertEqual(max(tied, key=self._key)[2], 20.41)

    def test_the_role_exists_and_is_ordered_last(self):
        self.assertIn("BALANCED_CANDIDATE", E.EXPORT_ROLE_ORDER)
        self.assertEqual(E.EXPORT_ROLE_ORDER[-1], "BALANCED_CANDIDATE")

    def test_the_manifest_cap_is_derived_not_hardcoded(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertFalse('"maximum_schedule_workbooks": 4,' in source,
                         "the manifest must not claim a cap the engine no longer has")
        self.assertTrue('"maximum_schedule_workbooks": len(EXPORT_ROLE_ORDER),' in source)

    def test_it_is_not_exported_when_it_duplicates_another_role(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertTrue("if balanced not in (recommended, strict, max_floor):" in source,
                        "a duplicate export would just be noise")


class HeadcountNeededForBreaksIsMeasuredNotAggregated(unittest.TestCase):
    """`capacity_diagnostics` answers a different question than the planner asks.

    Its aggregate estimate is a necessary condition, not a sufficient one: a
    roster can hold enough weekly productive hours and still have nowhere to
    put a break, because coverage has a shape. On NMG EN+SP the aggregate said
    "+2 associates" while the shipped schedule finished 99 target intervals
    short; on Cricut Chat it said "+1" against 69 short. These pin the
    shape-aware measurement that replaces that answer in the summary.
    """

    BREAK_Q = 4  # one 60-minute break per shift, 15-minute quarters

    def _parsed(self, headcount=10, shrinkage=0.0, per_day_intervals=1,
                concurrent_absolute=99):
        return SimpleNamespace(
            qslots_per_interval=1,
            intervals_per_day=per_day_intervals,
            active=[[True] * per_day_intervals for _ in range(7)],
            requirements=[[10.0] * per_day_intervals for _ in range(7)],
            shrinkage=[[shrinkage] * per_day_intervals for _ in range(7)],
            target_ratio=1.0,
            break_segments_q=[(self.BREAK_Q, None)],
            break_max_concurrent_ratio=1.0,
            break_max_concurrent_absolute=concurrent_absolute,
            associates=[object()] * headcount,
            shifts=[SimpleNamespace(duration_q=36)],
        )

    def _measure(self, parsed, staffed, worked_days):
        """Run the metric with coverage pinned to a flat `staffed` count."""
        skeleton = SimpleNamespace(
            assignment=[["SHIFT"] * 1 for _ in range(worked_days)])
        with unittest.mock.patch.object(
            E, "scheduled_covering_qslot", lambda *a, **k: [None] * staffed
        ), unittest.mock.patch.object(
            E, "prior_covering_associates", lambda *a, **k: []
        ):
            return E.break_capacity_headcount_requirement(parsed, skeleton)

    def test_a_schedule_with_slack_everywhere_needs_no_extra_headcount(self):
        out = self._measure(self._parsed(), staffed=20, worked_days=5)
        self.assertEqual(out["break_capacity_deficit"], 0)
        self.assertEqual(out["status"], "BREAK_CAPACITY_SUFFICIENT")
        self.assertEqual(out["estimated_additional_headcount_for_breaks"], 0)
        self.assertEqual(out["headcount_needed_for_breaks"], out["current_headcount"])

    def test_a_schedule_pinned_at_target_can_place_no_break_losslessly(self):
        """The NMG EN+SP shape: staffed == requirement in every slot."""
        out = self._measure(self._parsed(), staffed=10, worked_days=5)
        self.assertEqual(out["lossless_break_capacity"], 0)
        self.assertEqual(out["zero_target_slack_ratio"], 1.0)
        self.assertEqual(out["break_capacity_deficit"], 5 * self.BREAK_Q)
        self.assertEqual(out["status"], "BREAK_CAPACITY_SHORT")
        self.assertGreater(out["estimated_additional_headcount_for_breaks"], 0)

    def test_the_concurrency_cap_bounds_capacity_not_the_raw_slack(self):
        """Ten spare bodies do not mean ten people may break at once."""
        capped = self._measure(
            self._parsed(concurrent_absolute=2), staffed=20, worked_days=5)
        self.assertEqual(capped["lossless_break_capacity"], 2 * 7,
                         "seven active slots, two lossless breaks each")

    def test_shrinkage_grosses_the_requirement_up_before_slack_is_taken(self):
        """Shrinkage is out-of-office time, so it raises what must be staffed."""
        out = self._measure(self._parsed(shrinkage=0.5), staffed=15, worked_days=5)
        self.assertEqual(out["zero_target_slack_ratio"], 1.0,
                         "10 required at 50% shrinkage needs 20 staffed, not 10")

    def test_the_needed_headcount_is_the_current_plus_the_shortfall(self):
        out = self._measure(self._parsed(headcount=10), staffed=10, worked_days=5)
        self.assertEqual(out["current_headcount"], 10)
        self.assertEqual(
            out["headcount_needed_for_breaks"],
            out["current_headcount"] + out["estimated_additional_headcount_for_breaks"])

    def test_a_surplus_is_not_sold_as_a_guarantee_that_breaks_land_free(self):
        """Measured on NMG13: reported a 6-slot surplus and still gave up 9
        target intervals to breaks. The metric counts room per slot; it does
        not know whether a legal placement can reach that room, because break
        windows, spacing and per-associate timing constrain where a break may
        go. A deficit proves headcount is short. A surplus proves only that
        headcount is not the constraint."""
        out = self._measure(self._parsed(), staffed=20, worked_days=5)
        self.assertIn("Headcount is not the constraint", out["headline"])
        self.assertNotIn("Breaks fit", out["headline"])
        self.assertIn("windows and spacing", out["headline"])

    def test_the_estimate_is_published_as_a_lower_bound(self):
        """Each added associate is assumed to land on the binding slots, which
        is optimistic. Reporting it as exact would send a planner to their
        finance partner with a number that cannot be defended."""
        out = self._measure(self._parsed(), staffed=10, worked_days=5)
        self.assertIn("lower bound", out["estimate_basis"])
        self.assertIn("lower bound", out["headline"])

    def test_the_headline_names_the_headcount_a_planner_has_to_act_on(self):
        out = self._measure(self._parsed(headcount=10), staffed=10, worked_days=5)
        total = out["headcount_needed_for_breaks"]
        self.assertIn(str(total), out["headline"])

    def test_it_is_measured_on_a_skeleton_that_exists_at_the_call_site(self):
        """The first wiring called it with `chosen_skeleton` in the Stage-1
        region, where that name is not bound until Stage 2 has selected."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        early = source.index("measured_on=\"best_shippable_before_breaks\"")
        binding = source.index("chosen_skeleton, chosen_breaks = selection[\"recommended\"]")
        late = source.index("measured_on=\"recommended_final_skeleton\"")
        self.assertLess(early, binding, "the pre-break measurement must not need Stage 2")
        self.assertLess(binding, late, "the final measurement must follow the selection")

    def test_a_skeleton_only_run_gets_the_answer_before_it_returns(self):
        """BEFORE_BREAKS_ONLY exists to answer whether a roster is worth taking
        to Stage 2, and it returns long before the Stage-2 measurement runs.
        Pinning only that the call exists would have missed exactly that: the
        first wiring put the measurement after the branch had already returned.
        """
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        branch = source.index("        if skeleton_only:\n            hard_clean_skeletons")
        measure = source.index('measured_on="before_breaks_only_export"')
        summary = source.index('"break_capacity_status": break_capacity["status"],', branch)
        ret = source.index("            return 0\n", branch)
        self.assertLess(branch, measure, "measured inside the skeleton-only branch")
        self.assertLess(measure, summary, "and before its summary row is written")
        self.assertLess(summary, ret, "and before the branch returns")

    def test_the_full_run_measures_on_a_skeleton_that_could_actually_ship(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertIn("best_shippable_before_skeleton or best_before_skeleton", source)

    def test_the_planner_sees_it_in_the_workbook_not_only_the_summary_csv(self):
        """A planner asking finance for headcount reads the Feasibility
        Certificate, not the run summary CSV."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        certificate = source[source.index('_replace_sheet(wb, "Feasibility Certificate")'):]
        certificate = certificate[:certificate.index("leader_ws = ")]
        for label in ("Current Headcount", "Headcount Needed Including Breaks",
                      "Additional Headcount Needed For Breaks", "Headcount Verdict"):
            self.assertIn(f'["{label}"', certificate,
                          f"the certificate must state {label}")

    def test_the_summary_publishes_the_headcount_fields(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        for field in ("current_headcount", "headcount_needed_for_breaks",
                      "additional_headcount_for_breaks", "break_capacity_status",
                      "zero_target_slack_ratio"):
            self.assertIn(f'"{field}":', source, f"{field} must reach the summary row")


class TheOutputWorkbookOpensOnAnAnswerNotOnEvidence(unittest.TestCase):
    """28 audit sheets and a 110-row Production Summary is the right amount of
    evidence and the wrong amount of reading.

    A planner opening the workbook has to decide one thing - publish this
    roster or go ask for headcount - and every fact needed for that decision
    was spread across three sheets and ninety rows of contract metadata. The
    fix adds a sheet; it removes nothing, because the audit sheets are the
    reason the schedule can be defended.
    """

    def setUp(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        start = source.index('_replace_sheet(wb, "Read Me First")')
        self.block = source[source.index("readme_rows: List[List[Any]] = ["):start + 600]
        self.source = source

    def test_it_is_the_first_sheet_the_workbook_opens_on(self):
        self.assertIn("wb.move_sheet(readme_ws, offset=-wb.sheetnames.index(readme_ws.title))",
                      self.source, "a summary buried at sheet 29 is not a summary")
        self.assertIn("wb.active = 0", self.source)

    def test_it_answers_the_publish_or_ask_for_headcount_question(self):
        for label in ("Result", "Coverage at target, after breaks",
                      "Intervals given up to place breaks",
                      "Current headcount", "Headcount needed including breaks",
                      "Intervals below floor", "Associates with no break"):
            self.assertIn(f'["{label}"', self.block, f"a planner needs {label}")

    def test_it_states_coverage_as_a_share_not_a_bare_count(self):
        """`after_target 153` means nothing without the denominator."""
        self.assertIn("f\"{hits} of {active_intervals} ({hits / active_intervals:.0%})\"",
                      self.source)

    def test_it_does_not_divide_by_zero_on_an_empty_contract(self):
        self.assertIn("if not active_intervals:", self.source)

    def test_no_audit_sheet_was_removed_to_make_room(self):
        """Readability must not cost the evidence that defends the schedule."""
        for sheet in ("Production Summary", "Feasibility Certificate",
                      "Candidate Leaderboard", "Validation Log",
                      "Coverage Before Breaks", "FT Wise After Breaks",
                      "No-Break Exceptions", "Break Spacing Audit"):
            self.assertIn(f'_replace_sheet(wb, "{sheet}")', self.source,
                          f"{sheet} must still be written")

    def test_the_before_breaks_artifact_does_not_claim_breaks_were_placed(self):
        """That artifact runs through this same writer against a placeholder
        break solution, so its "after breaks" columns repeat the before-break
        numbers and its quality gate is measured on a schedule with no breaks.
        The first draft printed 'Coverage at target, after breaks 174 of 252',
        'Intervals given up to place breaks 0' and 'Release gate FAIL' at the
        top of a workbook whose breaks were never assigned."""
        head = self.source[self.source.index("before_breaks_only = artifact_type"):
                           self.source.index('_replace_sheet(wb, "Read Me First")')]
        branch = head[:head.index("    else:")]
        self.assertIn("breaks are NOT assigned", branch)
        self.assertIn("This is not a production schedule.", branch)
        self.assertIn("Coverage at target, before breaks", branch)
        self.assertNotIn("after breaks", branch)
        self.assertNotIn("Intervals given up to place breaks", branch)

    def test_the_gate_result_is_labelled_rather_than_hidden(self):
        """A failing gate stays visible; what changes is the claim it makes."""
        self.assertIn("so it does not decide this artifact", self.source)
        self.assertIn("quality_gate.get('status')", self.source)

    def test_the_no_break_count_is_omitted_where_it_would_read_as_good_news(self):
        """Zero associates without a break, in a workbook where nobody has one."""
        self.assertIn('if not before_breaks_only:\n        readme_rows.append(["Associates with no break"',
                      self.source)

    def test_it_points_at_where_the_detail_lives(self):
        self.assertIn('["Where to look next",', self.block)


class TheBeforeBreakLeaderboardSaysWhichSkeletonCanActuallyTakeItsBreaks(unittest.TestCase):
    """The leaderboard ranks on coverage, which is right for a mode called
    "best before breaks" and an incomplete basis for choosing one.

    Measured on NMG13 in BEFORE_BREAKS_ONLY: the top skeleton scored 174
    before-target and needed five more associates before its breaks could be
    placed without dropping an interval below target. The skeleton the full run
    shipped scored 161 and needed none. A planner reading only the coverage
    column picks the first and finds the staffing gap after committing to it.
    """

    SOURCE = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()

    def test_the_rows_carry_the_headcount_the_skeleton_would_need(self):
        block = self.SOURCE[self.SOURCE.index("def before_break_leaderboard_rows("):]
        block = block[:block.index("def _protected_tier_counts(")]
        for field in ("break_capacity_status", "break_capacity_deficit",
                      "headcount_needed_for_breaks", "additional_headcount_for_breaks"):
            self.assertIn(f'"{field}":', block)

    def test_the_columns_reach_the_exported_sheet(self):
        for header in ("Break Capacity Status", "Headcount Needed Including Breaks",
                       "Additional Headcount Needed"):
            self.assertIn(f'"{header}"', self.SOURCE)

    def test_the_measurement_is_bounded_to_the_rows_that_are_exported(self):
        """It walks every quarter-slot of every skeleton handed to it, and the
        skeleton pool is not bounded."""
        self.assertIn("if parsed is not None and position < break_capacity_rows:", self.SOURCE)
        self.assertIn("break_capacity_rows=max(1, int(export_top_skeletons))", self.SOURCE)

    def test_callers_that_pass_no_contract_still_work(self):
        """Two callers build this leaderboard for failure artifacts; adding a
        required argument there would turn a reported failure into a crash."""
        signature = self.SOURCE[self.SOURCE.index("def before_break_leaderboard_rows("):]
        signature = signature[:signature.index('"""')]
        self.assertIn("parsed: Optional[ParsedInput] = None", signature)
        self.assertIn("break_capacity_rows: int = 0", signature)

    def test_an_unmeasured_row_is_blank_not_a_confident_zero(self):
        """A blank says "not measured". A zero says "needs nobody"."""
        block = self.SOURCE[self.SOURCE.index("def before_break_leaderboard_rows("):]
        block = block[:block.index("def _protected_tier_counts(")]
        self.assertIn('capacity.get("status", "")', block)
        self.assertIn('capacity.get("break_capacity_deficit", "")', block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
