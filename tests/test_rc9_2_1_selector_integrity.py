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
            E.VERSION, "L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1")


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
