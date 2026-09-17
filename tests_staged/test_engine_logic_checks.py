#!/usr/bin/env python3
"""Fast logic checks for the engine's equations and predicates.

One assertion set per function, hand-derived from what the function is supposed
to mean -- not snapshotted from what it currently returns. A snapshot test
passes on a bug; these are written so that a wrong equation fails.

Whole suite is pure Python: no CP-SAT, no workbook, no IO. Designed to run in
about a second so it can sit in front of every commit.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "E", ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
E = importlib.util.module_from_spec(spec)
sys.modules["E"] = E
spec.loader.exec_module(E)
import canonical_metrics as CM  # noqa: E402


def parsed_stub(**kw):
    """A parsed-like object carrying every field the function under test reads.

    Deliberately explicit: C-1 showed that omitting a field silently selects a
    more permissive shadow default, so a stub that leaves fields out would test
    the fallback rather than the equation.
    """
    base = dict(
        active=[[True] * 24 for _ in range(7)],
        requirements=[[10.0] * 24 for _ in range(7)],
        shrinkage=[[0.0] * 24 for _ in range(7)],
        target_ratio=1.0, floor_ratio=0.80, hard_floor_ratio=None,
        interval_minutes=60, intervals_per_day=24,
        opening_guard_enabled=False, opening_minimum=0, opening_intervals=0,
        language_rules=[], language_windows={}, language_working_window_mode="OFF",
        next_sunday_overage_cap_ratio=1.35, next_sunday_max_adjacent_raw_change=3,
        whole_week_overage_cap_ratio=1.35, whole_week_max_adjacent_raw_change=3,
        break_max_concurrent_ratio=0.25, break_max_concurrent_absolute=0,
        quality_max_floor_gap_ratio=0.10, quality_max_severe_gap_ratio=0.05,
        quality_max_consecutive_floor_gaps=3,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TimeAndNumericPrimitives(unittest.TestCase):
    def test_hhmm_wraps_the_day(self):
        self.assertEqual(E.hhmm(0), "00:00")
        self.assertEqual(E.hhmm(9 * 60 + 5), "09:05")
        self.assertEqual(E.hhmm(1439), "23:59")
        self.assertEqual(E.hhmm(1440), "00:00", "1440 is midnight, not 24:00")
        self.assertEqual(E.hhmm(1440 + 75), "01:15", "past midnight must wrap")

    def test_minute_of_day_reads_each_supported_form(self):
        self.assertEqual(E.minute_of_day("09:30"), 570)
        self.assertEqual(E.minute_of_day(0.5), 720, "an Excel time serial is a day fraction")
        self.assertEqual(E.minute_of_day(570), 570, "a plain integer is minutes")
        self.assertIsNone(E.minute_of_day("25:00"), "hour 25 is not a time")
        self.assertIsNone(E.minute_of_day("09:99"), "minute 99 is not a time")
        self.assertIsNone(E.minute_of_day(""), "blank is absent, not midnight")
        self.assertIsNone(E.minute_of_day(None))

    def test_parse_time_window_needs_two_times(self):
        self.assertEqual(E.parse_time_window("09:00 - 17:00"), (540, 1020))
        self.assertEqual(E.parse_time_window("0900-1700"), (540, 1020))
        self.assertEqual(E.parse_time_window("09:00"), (None, None), "one time is not a window")
        self.assertEqual(E.parse_time_window(""), (None, None))
        self.assertEqual(E.parse_time_window("2026-07-12"), (None, None),
                         "a date must not be read as a window")

    def test_inclusive_window_handles_the_overnight_wrap(self):
        self.assertTrue(E.minute_in_inclusive_window(600, 540, 1020))
        self.assertTrue(E.minute_in_inclusive_window(540, 540, 1020), "start is inclusive")
        self.assertTrue(E.minute_in_inclusive_window(1020, 540, 1020), "end is inclusive")
        self.assertFalse(E.minute_in_inclusive_window(300, 540, 1020))
        # 22:00 -> 06:00 wraps midnight
        self.assertTrue(E.minute_in_inclusive_window(1380, 1320, 360))
        self.assertTrue(E.minute_in_inclusive_window(60, 1320, 360))
        self.assertFalse(E.minute_in_inclusive_window(600, 1320, 360))
        self.assertTrue(E.minute_in_inclusive_window(600, None, None),
                        "no window means no restriction")

    def test_shift_parts_durations(self):
        self.assertEqual(E.shift_parts("09:00 - 18:00"), (540, 1080, 540))
        st, en, dur = E.shift_parts("22:00 - 07:00")
        self.assertEqual((st, en), (1320, 420))
        self.assertEqual(dur, 540, "an overnight shift wraps to a positive duration")
        self.assertEqual(E.shift_parts("00:00 - 00:00")[2], 1440,
                         "equal start and end is a full day, not zero")
        self.assertIsNone(E.shift_parts("not a shift"))
        self.assertIsNone(E.shift_parts(""))

    def test_circular_minute_distance_is_a_metric(self):
        self.assertEqual(E.circular_minute_distance(0, 0), 0)
        self.assertEqual(E.circular_minute_distance(0, 60), 60)
        self.assertEqual(E.circular_minute_distance(60, 0), 60, "must be symmetric")
        self.assertEqual(E.circular_minute_distance(0, 1380), 60, "must take the short way round")
        self.assertEqual(E.circular_minute_distance(0, 720), 720, "720 is the maximum")
        for a, b in ((0, 100), (300, 1400), (719, 721)):
            self.assertLessEqual(E.circular_minute_distance(a, b), 720)

    def test_ceil_units_rounds_up_only_past_the_tolerance(self):
        """Note the default scale is 100 -- ceil_units returns hundredths."""
        self.assertEqual(E.ceil_units(10.0, 1), 10, "an exact value must not round up")
        self.assertEqual(E.ceil_units(10.0000000001, 1), 10,
                         "float noise must not add a whole unit")
        self.assertEqual(E.ceil_units(10.5, 1), 11)
        self.assertEqual(E.ceil_units(0.0, 1), 0)
        self.assertEqual(E.ceil_units(10.0), 1000, "the default scale is 100")

    def test_scaled_effective_factor_and_threshold(self):
        scale = E.JOINT_COVERAGE_SCALE
        self.assertEqual(E.scaled_effective_factor(0.0), scale,
                         "no shrinkage is a factor of 1.0, scaled")
        self.assertEqual(E.scaled_effective_factor(0.5), scale // 2)
        self.assertGreater(E.scaled_effective_factor(0.999), 0,
                           "the factor must stay positive so it can be divided by")
        self.assertGreater(E.scaled_coverage_threshold(10.0, 1.0, 4),
                           E.scaled_coverage_threshold(10.0, 0.8, 4),
                           "a higher ratio must demand more")

    def test_to_float_is_permissive_and_strict_float_is_not(self):
        self.assertEqual(E.to_float("50%"), 0.5)
        self.assertEqual(E.to_float("abc", 7.0), 7.0, "to_float falls back by design")
        self.assertIsNone(E.strict_float("abc"), "strict_float refuses text")
        self.assertIsNone(E.strict_float("=SUM(A1)"), "a formula is not a value")
        self.assertIsNone(E.strict_float(True), "a bool is not a number here")
        self.assertIsNone(E.strict_float("50%"), "percent needs opting in")
        self.assertEqual(E.strict_float("50%", allow_percent=True), 0.5)
        self.assertEqual(E.strict_float("12.5"), 12.5)

    def test_yes_accepts_affirmatives_and_defaults_on_blank(self):
        for v in ("yes", "Y", "TRUE", "1", "enabled", "on"):
            self.assertTrue(E.yes(v), f"{v!r} is affirmative")
        for v in ("no", "N", "false", "0"):
            self.assertFalse(E.yes(v))
        self.assertTrue(E.yes("", True), "blank uses the caller's default")
        self.assertFalse(E.yes("", False))

    def test_safe_name_never_returns_empty(self):
        self.assertEqual(E.safe_name("AE AR B2B"), "AE_AR_B2B")
        self.assertEqual(E.safe_name("///"), "item", "a name must always be usable as a filename")

    def test_norm_collapses_whitespace_and_case(self):
        self.assertEqual(E.norm("  Ada   LOVELACE "), "ada lovelace")
        self.assertEqual(E.norm(None), "")


class DomainPredicates(unittest.TestCase):
    def test_preference_kind_vocabulary(self):
        self.assertEqual(E.preference_kind("leave"), "leave")
        self.assertEqual(E.preference_kind(" OFF "), "off")
        self.assertEqual(E.preference_kind(""), "blank")
        self.assertEqual(E.preference_kind("None"), "blank")
        self.assertEqual(E.preference_kind("09:00 - 18:00"), "shift")
        # C-3: recorded as the current contract, not as desirable behaviour.
        self.assertEqual(E.preference_kind("Annual Leave"), "other",
                         "C-3: unrecognised text is 'other' and blocks nothing")

    def test_rest_compatible_at_the_exact_boundary(self):
        # previous 09:00 +9h ends 18:00; next day 06:00 start => 12h rest
        prev = SimpleNamespace(start_min=540, duration_min=540)
        nxt = SimpleNamespace(start_min=360, duration_min=540)
        self.assertTrue(E.rest_compatible(prev, nxt, 12.0), "exactly 12h must pass")
        self.assertFalse(E.rest_compatible(prev, nxt, 12.25), "12h15 must fail on 12h rest")
        self.assertTrue(E.rest_compatible(prev, nxt, 8.0))

    def test_previous_saturday_compatible_fails_open_on_unparseable_text(self):
        sunday = SimpleNamespace(start_min=360, duration_min=540)
        self.assertTrue(E.previous_saturday_compatible("", sunday, 12.0),
                        "no carry-in means no constraint")
        self.assertTrue(E.previous_saturday_compatible("overtime", sunday, 12.0),
                        "B-11 family: unparseable text silently drops the rest rule")
        self.assertFalse(E.previous_saturday_compatible("22:00 - 07:00", sunday, 12.0),
                         "07:00 finish then 06:00 start is negative rest")

    def test_shift_start_contract_allows_respects_the_step(self):
        self.assertTrue(E.shift_start_contract_allows(540, 540, 1020, 30))
        self.assertTrue(E.shift_start_contract_allows(570, 540, 1020, 30))
        self.assertFalse(E.shift_start_contract_allows(555, 540, 1020, 30),
                         "09:15 is off a 30-minute grid anchored at 09:00")
        self.assertFalse(E.shift_start_contract_allows(300, 540, 1020, 30),
                         "outside the window is refused whatever the step")

    def test_is_day_header_rejects_decoys(self):
        self.assertTrue(E._is_day_header("sun", "Sun", "Sunday"))
        self.assertTrue(E._is_day_header("sunday", "Sun", "Sunday"))
        self.assertTrue(E._is_day_header("sunday 12 jul", "Sun", "Sunday"),
                        "a date suffix is still that day")
        self.assertFalse(E._is_day_header("sunday totals", "Sun", "Sunday"),
                         "a summary column is not a day column")
        self.assertFalse(E._is_day_header("saturation", "Sat", "Saturday"))
        self.assertFalse(E._is_day_header("monthly total", "Mon", "Monday"))


class CoverageAndThresholdMath(unittest.TestCase):
    def test_coverage_quality_limits_scale_with_the_active_count(self):
        p = parsed_stub()
        small = E.coverage_quality_limits(p, 10)
        large = E.coverage_quality_limits(p, 1000)
        for key in ("maximum_floor_gaps", "maximum_severe_gaps"):
            self.assertLessEqual(small[key], large[key],
                                 f"{key} must not shrink as the schedule grows")
            self.assertGreaterEqual(small[key], 0)

    def test_maximum_concurrent_breaks_is_monotone_and_bounded(self):
        p = parsed_stub()
        previous = -1
        for staffed in range(0, 40):
            allowed = E.maximum_concurrent_breaks(p, staffed)
            self.assertGreaterEqual(allowed, previous, "more staff cannot allow fewer breaks")
            self.assertLessEqual(allowed, max(1, staffed),
                                 "never allow more concurrent breaks than people")
            previous = allowed

    def test_fractional_safe_overage_excludes_unavoidable_rounding(self):
        # requirement 10, target 100%, no shrinkage: 10 staff is exactly on target
        m = E.fractional_safe_overage_metrics(10.0, 10.0, 1.0, 1.0, 1.10, 1.25, 1.50)
        self.assertAlmostEqual(float(m["avoidable_overage_fte"]), 0.0, places=6,
                               msg="meeting target exactly is not overage")
        over = E.fractional_safe_overage_metrics(10.0, 14.0, 1.0, 1.0, 1.10, 1.25, 1.50)
        self.assertGreater(float(over["avoidable_overage_fte"]), 0.0,
                           "4 FTE above a met target is avoidable overage")
        under = E.fractional_safe_overage_metrics(10.0, 6.0, 1.0, 1.0, 1.10, 1.25, 1.50)
        self.assertAlmostEqual(float(under["avoidable_overage_fte"]), 0.0, places=6,
                               msg="understaffing is never overage")

    def test_whole_week_raw_cap_is_never_below_the_requirement(self):
        p = parsed_stub()
        cap = E.whole_week_raw_cap(p, 0, 0)
        need = E.whole_week_raw_requirement(p, 0, 0)
        self.assertGreaterEqual(cap, need,
                                "a cap below the target would make the contract self-contradictory")

    def test_whole_week_cap_respects_a_harder_opening_minimum(self):
        p = parsed_stub(opening_guard_enabled=True, opening_minimum=50, opening_intervals=2)
        self.assertGreaterEqual(E.whole_week_raw_cap(p, 0, 0), 50,
                                "the cap must not sit below a hard opening minimum")

    def test_adjacent_raw_limit_never_below_the_configured_change(self):
        p = parsed_stub(whole_week_max_adjacent_raw_change=3)
        self.assertGreaterEqual(E.whole_week_adjacent_raw_limit(p, 0, 0, 1), 3)


class BudgetMath(unittest.TestCase):
    def test_fundable_profile_count_is_a_report_not_a_truncation(self):
        """Its docstring is explicit: "Reporting only: the loop does not
        truncate its portfolio up front". So 0 at a tiny window is the correct
        statement "this window cannot pay for a full-depth profile", not a
        promise that nothing runs."""
        self.assertEqual(E.stage1_fundable_profile_count(0, minimum_slice_sec=45), 0)
        previous = -1
        for window in (0, 45, 90, 180, 450, 600, 3600):
            got = E.stage1_fundable_profile_count(window, minimum_slice_sec=45)
            self.assertGreaterEqual(got, previous,
                                    "a larger window cannot report fewer fundable profiles")
            previous = got
        with self.assertRaises(ValueError, msg="a non-positive slice floor is a caller error"):
            E.stage1_fundable_profile_count(600, minimum_slice_sec=0)

    def test_a_lower_floor_funds_at_least_as_many_profiles(self):
        wide = E.stage1_fundable_profile_count(600, minimum_slice_sec=45)
        tight = E.stage1_fundable_profile_count(600, minimum_slice_sec=240)
        self.assertGreaterEqual(wide, tight, "B-3: a smaller slice floor funds more profiles")

    def test_stage1_slice_never_exceeds_what_remains(self):
        for remaining in (30, 120, 600, 3600):
            for attempts in (1, 3, 15):
                slice_sec = E.stage1_slice_seconds(remaining, attempts, minimum_slice_sec=45)
                self.assertGreater(slice_sec, 0)
                self.assertLessEqual(slice_sec, max(remaining, 45) + 1e-6,
                                     "a slice cannot outrun the remaining budget")

    def test_stage2_anchor_slice_is_bounded_by_the_reservation(self):
        for reserved, remaining in ((60, 600), (600, 60), (300, 300)):
            got = E.stage2_anchor_slice_seconds(reserved, remaining)
            self.assertGreater(got, 0)
            self.assertLessEqual(got, max(reserved, remaining) + 1e-6)

    def test_the_bounded_stage2_reserve_never_starves_the_primary_search(self):
        """guaranteed_stage2_reserve_seconds is an upper bound, not a
        reservation -- at a 300s total it returns the whole 300. The invariant
        that matters lives on the bounded function, its only consumer, which
        clamps it by what the primary search can spare."""
        self.assertEqual(E.guaranteed_stage2_reserve_seconds(300), 300,
                         "the raw figure is an unclamped upper bound")
        for total, primary in ((300, 120), (1800, 900), (3600, 1800)):
            r = E.bounded_stage2_guard_reserve_seconds(total, primary)
            self.assertLessEqual(r, max(0, primary - 45),
                                 "the anchor must leave the primary search something to run")
            self.assertLessEqual(r, E.guaranteed_stage2_reserve_seconds(total))
        self.assertEqual(E.bounded_stage2_guard_reserve_seconds(300, 60), 0,
                         "too short to fund a real break solve means reserve nothing")
        self.assertGreaterEqual(E.bounded_stage2_guard_reserve_seconds(300, 120), 45,
                                "the engine selfcheck pins this same floor")

    def test_exception_cap_descent_targets_descend_towards_zero(self):
        targets = list(E.exception_cap_descent_targets(5, 10))
        self.assertTrue(all(t >= 0 for t in targets), "a cap is never negative")
        self.assertEqual(sorted(targets, reverse=True), list(targets),
                         "descent targets must be non-increasing")


class SelectionMath(unittest.TestCase):
    def test_deficit_bucket_quantizes_and_preserves_order(self):
        q = E.FLOOR_DEFICIT_COMPARISON_QUANTUM
        self.assertEqual(E._deficit_bucket(0.0), 0)
        self.assertGreaterEqual(E._deficit_bucket(10 * q), E._deficit_bucket(1 * q),
                                "a bigger deficit must never bucket lower")
        self.assertEqual(E._deficit_bucket(q * 0.4), E._deficit_bucket(q * 0.45),
                         "differences below the quantum must be indistinguishable")

    def test_protected_tiers_sit_strictly_between_floor_and_target(self):
        m = {"before_90": 5, "before_80": 9}
        # target 100, floor 80 -> 90 is meaningful, 80 is the floor itself
        self.assertEqual(E._protected_tier_counts(parsed_stub(target_ratio=1.0, floor_ratio=0.80),
                                                  m, "before"), (5,))
        # target 90, floor 80 -> nothing strictly between
        self.assertEqual(E._protected_tier_counts(parsed_stub(target_ratio=0.90, floor_ratio=0.80),
                                                  m, "before"), ())
        # target 100, floor 75 -> both 90 and 80 are meaningful
        self.assertEqual(E._protected_tier_counts(parsed_stub(target_ratio=1.0, floor_ratio=0.75),
                                                  m, "before"), (5, 9))

    def test_secondary_counts_only_report_tiers_above_target(self):
        m = {"after_100": 3, "after_90": 7}
        self.assertEqual(E._target_secondary_counts(m, "after", 1.0), (),
                         "nothing sits above a 100% target")
        self.assertEqual(E._target_secondary_counts(m, "after", 0.90), (3,))
        self.assertEqual(E._target_secondary_counts(m, "after", 0.80), (7, 3))

    def test_dominance_is_irreflexive_and_antisymmetric(self):
        p = parsed_stub()

        def pair(**m):
            base = {"after_target": 100, "after_floor": 150, "after_100": 10, "after_90": 40,
                    "after_80": 80, "before_target": 100, "hard_floor_gap_count": 0,
                    "severe_floor_gap_count": 0, "max_consecutive_floor_gaps": 0,
                    "floor_deficit_sum": 0.0, "week_boundary_after_target": 5,
                    "week_boundary_after_floor": 6, "after_avoidable_overage_fte_sum": 0.0,
                    "after_extreme_overage_count": 0, "after_severe_overage_count": 0}
            base.update(m)
            return (SimpleNamespace(), SimpleNamespace(metrics=base))

        a = pair()
        b = pair(after_target=99)
        self.assertFalse(E.candidate_dominates(p, a, a), "nothing dominates itself")
        self.assertTrue(E.candidate_dominates(p, a, b), "strictly more target dominates")
        self.assertFalse(E.candidate_dominates(p, b, a), "dominance cannot run both ways")
        c = pair(after_target=101, after_floor=149)
        self.assertFalse(E.candidate_dominates(p, a, c), "a genuine trade-off is not dominance")
        self.assertFalse(E.candidate_dominates(p, c, a))


class CanonicalMetricSurface(unittest.TestCase):
    def test_aliases_round_trip_to_the_canonical_name(self):
        for canon, aliases in CM.ALIASES.items():
            for alias in aliases:
                got = CM.canonicalize_metrics({alias: 4}, "engine",
                                              stage=CM.STAGE_FULL_SCHEDULE)
                self.assertEqual(got.get(canon), 4, f"{alias} must resolve to {canon}")

    def test_every_canonical_field_is_its_own_alias(self):
        """A canonical surface must survive being canonicalized again.

        `compare_metric_surfaces` canonicalizes whatever it is handed, so a
        caller that passes an already-canonical surface must not lose fields.
        One field of 41 breaks this: after_avoidable_overage_top10_concentration
        does not list its own name among its aliases, so re-canonicalizing a
        canonical surface silently drops it to MISSING_CANONICAL_METRIC.

        Latent in production -- both sides emit one of the two spellings that
        ARE aliases -- but it is a real trap for any new caller.
        """
        offenders = [c for c, a in CM.ALIASES.items() if c not in a]
        self.assertEqual(
            offenders, ["after_avoidable_overage_top10_concentration"],
            "if this list changes, the alias table gained or lost a self-referential gap")

    def test_identical_surfaces_agree(self):
        m = {CM.ALIASES[f][0]: 1 for f in CM.PARITY_FIELDS}
        r = CM.compare_metric_surfaces(m, m, engine_stage=CM.STAGE_FULL_SCHEDULE,
                                       validator_stage=CM.STAGE_FULL_SCHEDULE)
        self.assertEqual(r["status"], "PASS", r["mismatches"])
        self.assertEqual(r["mismatches"], [])

    def test_a_single_differing_field_is_reported(self):
        m = {CM.ALIASES[f][0]: 1 for f in CM.PARITY_FIELDS}
        n = dict(m); n["after_target"] = 2
        r = CM.compare_metric_surfaces(m, n, engine_stage=CM.STAGE_FULL_SCHEDULE,
                                       validator_stage=CM.STAGE_FULL_SCHEDULE)
        self.assertNotEqual(r["status"], "PASS")
        self.assertEqual([x["field"] for x in r["mismatches"]], ["after_target"])

    def test_a_stage_disagreement_blocks(self):
        m = {CM.ALIASES[f][0]: 1 for f in CM.PARITY_FIELDS}
        r = CM.compare_metric_surfaces(m, m, engine_stage=CM.STAGE_FULL_SCHEDULE,
                                       validator_stage=CM.STAGE_BEFORE_BREAKS_ONLY)
        self.assertNotEqual(r["status"], "PASS")
        self.assertIn("run_stage", [x["field"] for x in r["mismatches"]])


class BreakPatternLegality(unittest.TestCase):
    """Generated patterns must satisfy the rules they were generated under."""

    def test_every_generated_pattern_obeys_its_own_constraints(self):
        duration_q = 36           # 9 hours
        segments = ((2, "Lunch"), (1, "Break"))
        margin, gap = 2, 4
        patterns = E._generic_break_patterns(
            duration_q, segments, limit=60,
            edge_margin_q=margin, minimum_gap_q=gap,
            preferred_gap_q=8, normal_max_gap_q=10)
        self.assertTrue(patterns, "a 9h shift with 45 minutes of breaks must be placeable")
        for p in patterns:
            starts = [s for s, _, _ in p.breaks]
            self.assertEqual(starts, sorted(starts), "segments must be in time order")
            for start, length, _ in p.breaks:
                self.assertGreaterEqual(start, margin, "a break cannot start inside the edge margin")
                self.assertLessEqual(start + length, duration_q - margin,
                                     "a break cannot run past the trailing margin")
            for i in range(1, len(p.breaks)):
                prev_start, prev_len, _ = p.breaks[i - 1]
                self.assertGreaterEqual(p.breaks[i][0] - (prev_start + prev_len), gap,
                                        "the minimum gap is a hard rule")

    def test_a_shift_too_short_for_its_breaks_yields_nothing(self):
        self.assertEqual(
            E._generic_break_patterns(4, ((2, "Lunch"), (1, "Break")), limit=10), [],
            "an unplaceable duration must return no pattern rather than an illegal one")

    def test_patterns_are_distinct(self):
        patterns = E._generic_break_patterns(36, ((2, "Lunch"),), limit=50,
                                             edge_margin_q=2, minimum_gap_q=2)
        seen = [p.breaks for p in patterns]
        self.assertEqual(len(seen), len(set(seen)), "duplicate patterns waste solver width")


if __name__ == "__main__":
    unittest.main(verbosity=1)
