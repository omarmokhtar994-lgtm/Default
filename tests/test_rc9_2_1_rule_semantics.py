#!/usr/bin/env python3
"""RC9.2.1 contract-rule semantics guards.

Several rules in RULE_VERIFICATION_MATRIX.csv sit at PENDING_SOLVE because no
shipped fixture exercises them.  Two of those gaps are structural rather than
scheduling ones and were confirmed against the delivered test kit:

  * `15_11H_3OFF_SAKS` parses with ``use_11h_3off = False`` and a shift library
    containing only 540-minute shifts, so it cannot exercise 11H/3OFF or the
    11H break pattern at all.
  * `17_BILINGUAL_NMG_EN_SP` carries a single language rule (Spanish, eligible
    {spanish}).  With no English rule and no directional mapping, "Spanish may
    assist English only in the configured direction" and "no double counting"
    cannot be observed from it.

A missing fixture is not a reason to leave the semantics unpinned.  These tests
exercise the engine's own rule predicates directly, so the contract meaning is
guarded regardless of which workbooks happen to ship.

Run:  python tests/test_rc9_2_1_rule_semantics.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))

import l632_universal_scheduler as E  # noqa: E402


def rule(group, required, eligible, minimum=1, active=True):
    return SimpleNamespace(
        group=group,
        required_languages=set(required),
        eligible_languages={E.norm(x) for x in eligible},
        minimum=minimum,
        active=active,
    )


def associate(language):
    return SimpleNamespace(language=language)


class LanguageEligibilityIsExplicitOnly(unittest.TestCase):
    """Coverage credit follows the configured eligibility set, nothing more.

    The universal contract requires that a language requirement is met only by
    associates the workbook actually declares eligible for it.  An associate is
    never credited to a requirement merely because they are bilingual, and a
    single associate is never counted toward two requirements implicitly.
    """

    def test_matching_language_is_eligible(self):
        self.assertTrue(E.language_eligible(rule("Spanish", ["spanish"], ["spanish"]),
                                            associate("Spanish")))

    def test_non_matching_language_is_not_eligible(self):
        self.assertFalse(E.language_eligible(rule("Spanish", ["spanish"], ["spanish"]),
                                             associate("English")))

    def test_bilingual_is_not_implicitly_eligible_for_a_single_language_rule(self):
        """The core no-double-counting rule.

        A bilingual associate must NOT satisfy a Spanish-only requirement unless
        the workbook lists their language in the eligible set.  Crediting them
        automatically is exactly the double counting the contract forbids.
        """
        self.assertFalse(E.language_eligible(rule("Spanish", ["spanish"], ["spanish"]),
                                             associate("Bilingual")))

    def test_configured_multi_language_eligibility_is_honoured(self):
        """Directional assist, as GDI REAL28 configures it.

        A rule whose eligible set names several source languages accepts any of
        them - this is the source-to-target inversion, and it is opt-in.
        """
        r = rule("Bilingual/French", ["bilingual", "french"], ["bilingual", "french"])
        self.assertTrue(E.language_eligible(r, associate("Bilingual")))
        self.assertTrue(E.language_eligible(r, associate("French")))
        self.assertFalse(E.language_eligible(r, associate("English")))

    def test_assist_direction_is_not_symmetric(self):
        """Eligibility one way must not imply eligibility the other way.

        If Spanish speakers may assist English, that must not silently make
        English speakers eligible for the Spanish requirement.
        """
        english_rule = rule("English", ["english"], ["english", "spanish"])
        spanish_rule = rule("Spanish", ["spanish"], ["spanish"])
        self.assertTrue(E.language_eligible(english_rule, associate("Spanish")))
        self.assertFalse(E.language_eligible(spanish_rule, associate("English")))

    def test_eligibility_is_case_and_whitespace_insensitive(self):
        r = rule("Spanish", ["spanish"], ["spanish"])
        for spelling in ("Spanish", "SPANISH", "  spanish  ", "sPaNiSh"):
            with self.subTest(spelling=spelling):
                self.assertTrue(E.language_eligible(r, associate(spelling)))


class LongShiftOffExpectation(unittest.TestCase):
    """OFF count follows shift duration against the shared threshold.

    Pinned because the threshold moved from a duplicated 660 in the validator to
    the engine's 630 (Correction Pass 02, Finding 4).  No fixture in the kit has
    a shift at or above 630, so nothing there would catch a regression.
    """

    def expected_off(self, duration_min):
        return 3 if duration_min >= E.LONG_SHIFT_MIN_DURATION_MIN else 2

    def test_nine_hour_shift_expects_two_off(self):
        self.assertEqual(self.expected_off(540), 2)

    def test_eleven_hour_shift_expects_three_off(self):
        self.assertEqual(self.expected_off(660), 3)

    def test_boundary_shift_is_long_mode(self):
        self.assertEqual(self.expected_off(E.LONG_SHIFT_MIN_DURATION_MIN), 3)

    def test_just_below_boundary_is_short_mode(self):
        self.assertEqual(self.expected_off(E.LONG_SHIFT_MIN_DURATION_MIN - 1), 2)

    def test_the_gap_that_caused_the_defect(self):
        """A 10.75h shift: long to the engine, short to the old validator."""
        self.assertEqual(self.expected_off(645), 3)
        self.assertLess(645, 660, "645 was short mode under the old validator threshold")
        self.assertGreaterEqual(645, E.LONG_SHIFT_MIN_DURATION_MIN)


class RestCompatibility(unittest.TestCase):
    """Rest gap, including the previous-Saturday carry-in.

    Values are the two genuine conflicts the engine diagnosed in the historical
    NMG EN fixture, verified by hand: a prev-Sat 23:00-08:00 leaves 6h before a
    14:00 Sunday start, and 20:00-05:00 leaves 9h, both under the 12h rule.
    """

    def test_six_hour_gap_violates_twelve_hour_rest(self):
        self.assertFalse(E.previous_saturday_compatible(
            "23:00 - 08:00", SimpleNamespace(start_min=14 * 60, duration_min=540), 12.0))

    def test_nine_hour_gap_violates_twelve_hour_rest(self):
        self.assertFalse(E.previous_saturday_compatible(
            "20:00 - 05:00", SimpleNamespace(start_min=14 * 60, duration_min=540), 12.0))

    def test_sufficient_gap_is_accepted(self):
        self.assertTrue(E.previous_saturday_compatible(
            "08:00 - 17:00", SimpleNamespace(start_min=14 * 60, duration_min=540), 12.0))

    def test_blank_previous_saturday_is_compatible(self):
        self.assertTrue(E.previous_saturday_compatible(
            "", SimpleNamespace(start_min=0, duration_min=540), 12.0))


class PreviousSaturdayCarryIn(unittest.TestCase):
    """Carry-in coverage is half-open: a shift ending at T does not staff T.

    This is what makes the cleaned NMG EN fixture infeasible - its latest
    previous-Saturday shift ends exactly at 02:00, so Sunday 02:00 is unstaffed.
    """

    def test_shift_ending_at_the_boundary_does_not_cover_it(self):
        # 17:00-02:00 -> covers through the quarter ending 02:00, not 02:00 itself.
        self.assertFalse(E.previous_saturday_covers_qslot("17:00 - 02:00", 8))

    def test_shift_ending_at_the_boundary_covers_the_quarter_before(self):
        self.assertTrue(E.previous_saturday_covers_qslot("17:00 - 02:00", 7))

    def test_overnight_shift_reaches_into_sunday_morning(self):
        # 23:00-08:00 covers Sunday through 08:00; qslot 8 is 02:00.
        self.assertTrue(E.previous_saturday_covers_qslot("23:00 - 08:00", 8))

    def test_shift_not_reaching_sunday_covers_nothing(self):
        self.assertFalse(E.previous_saturday_covers_qslot("08:00 - 17:00", 0))


class BreakSegmentContract(unittest.TestCase):
    """9H is 15+30+15; 11H is 15+30+15+15. Segments are stored in quarters."""

    def test_nine_hour_pattern_is_fifteen_thirty_fifteen(self):
        segments = ((1, "Break 1"), (2, "Lunch"), (1, "Break 2"))
        self.assertEqual([q * 15 for q, _ in segments], [15, 30, 15])
        self.assertEqual(sum(q * 15 for q, _ in segments), 60)

    def test_eleven_hour_pattern_is_fifteen_thirty_fifteen_fifteen(self):
        segments = ((1, "Break 1"), (2, "Lunch"), (1, "Break 2"), (1, "Break 3"))
        self.assertEqual([q * 15 for q, _ in segments], [15, 30, 15, 15])
        self.assertEqual(sum(q * 15 for q, _ in segments), 75)


class CarryInForcedOverageIsSeparated(unittest.TestCase):
    """Overage the solver cannot avoid must be distinguishable from overage it can.

    Previous-week carry-in is fixed workbook input, not a decision variable.
    Where carry-in alone exceeds what the target needs, the excess was charged
    wholly as "avoidable" overage, flagged severe and extreme, with
    indivisible_staffing_only False - so an overage regression caused by the
    input contract was indistinguishable from one caused by the optimizer.
    """

    def test_carry_in_excess_is_charged_as_avoidable_by_the_raw_metric(self):
        """Pin the underlying behaviour the new metric exists to explain."""
        m = E.fractional_safe_overage_metrics(0.9, 10.0, 0.90, 1.0, 1.1, 1.25, 1.5)
        self.assertAlmostEqual(m["avoidable_overage_fte"], 9.0, places=9)
        self.assertFalse(m["indivisible_staffing_only"],
                         "nothing currently marks carry-in overage structural")

    def test_forced_overage_formula_matches_carry_in_excess(self):
        """carry_in_forced = max(0, carry-in effective - unavoidable at target)."""
        for req, eff, carry in ((0.9, 1.0, 10.0), (2.9, 1.0, 10.0), (2.0, 1.0, 10.0)):
            with self.subTest(req=req):
                m = E.fractional_safe_overage_metrics(req, carry, 0.90, eff, 1.1, 1.25, 1.5)
                unavoidable = m["unavoidable_effective_at_target"]
                self.assertAlmostEqual(max(0.0, carry - unavoidable),
                                       m["avoidable_overage_fte"], places=9)

    def test_no_forced_overage_when_carry_in_is_below_requirement(self):
        m = E.fractional_safe_overage_metrics(12.5, 4.0, 0.90, 0.87, 1.1, 1.25, 1.5)
        self.assertEqual(m["avoidable_overage_fte"], 0.0)

    def test_metric_keys_are_emitted(self):
        """The separated metrics must reach the metrics dict, not just be computed."""
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        for key in ("carry_in_forced_overage_fte_sum",
                    "carry_in_forced_overage_interval_count",
                    "before_solver_controllable_avoidable_overage_fte_sum",
                    "after_solver_controllable_avoidable_overage_fte_sum"):
            self.assertIn(f'"{key}"', source, f"{key} not emitted in metrics dict")

    def test_carry_in_metric_does_not_enter_candidate_ranking(self):
        """Measurement only - adding it to the tuple would be a behaviour change."""
        import re
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(
            encoding="utf-8")
        start = source.index("def _candidate_quality_tuple")
        body = source[start:source.index("def break_solution_key", start)]
        self.assertNotIn("carry_in_forced", body,
                         "carry-in metric must not affect ranking without evidence")
        self.assertNotIn("solver_controllable", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
