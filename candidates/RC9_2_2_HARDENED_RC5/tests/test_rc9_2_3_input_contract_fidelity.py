#!/usr/bin/env python3
"""The workbook contract must mean what it says.

Four silent coercions used to let the engine schedule a contract the business
never wrote. Each one produced a plausible-looking result, which is why none
was caught by a passing gate:

  A-1  zero breaks configured -> a hard-coded 15/30/15 (60 min) was inserted
  A-2  an invalid Interval Minutes -> silently became 60
  A-3  "All Days" -> rejected, because norm() keeps inner spaces
  A-7  a day index outside 0..6 -> "no language rules apply anywhere"

The rule these pin: ABSENT may take a default; SUPPLIED-AND-INVALID must fail
closed. A value that was typed and then ignored is the dangerous case.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402


def _im(**kw):
    return {E.norm(k.replace("_", " ")): v for k, v in kw.items()}


class BreakContractIsHonoured(unittest.TestCase):
    """A-1. Break minutes drive required headcount, so a rewritten break
    contract sizes the roster for a different business agreement."""

    def test_an_absent_contract_keeps_the_historical_default(self):
        self.assertEqual(
            E._parse_break_segments({}),
            ((1, "Break 1"), (2, "Lunch"), (1, "Break 2")),
        )

    def test_zero_breaks_means_zero_breaks(self):
        warnings = []
        segments = E._parse_break_segments(
            _im(short_break_count=0, lunch_count=0), warnings)
        self.assertEqual(segments, ())
        self.assertEqual(warnings, [], "an explicit zero is valid, not an error")

    def test_a_negative_count_is_rejected_not_swallowed(self):
        warnings = []
        E._parse_break_segments(_im(short_break_count=-3, lunch_count=1), warnings)
        self.assertTrue(any(w.startswith("HARD_INVALID_BREAK_CONTRACT:") for w in warnings))

    def test_an_unsupported_duration_is_rejected_not_coerced(self):
        warnings = []
        E._parse_break_segments(
            _im(short_break_count=2, short_break_duration_minutes=20,
                lunch_count=1, lunch_duration_minutes=30), warnings)
        self.assertTrue(any("Short Break Duration Minutes" in w for w in warnings),
                        "a 20-minute break must not silently become 15")

    def test_a_supported_duration_is_honoured_exactly(self):
        warnings = []
        segments = E._parse_break_segments(
            _im(short_break_count=1, short_break_duration_minutes=45,
                lunch_count=1, lunch_duration_minutes=60), warnings)
        self.assertEqual(warnings, [])
        self.assertEqual(sum(q * 15 for q, _ in segments), 105)

    def test_the_warning_code_is_one_preflight_already_fails_closed_on(self):
        """`validate_input_contract` turns any HARD_ parser warning into a
        contract failure. Using that prefix is what makes this fail closed."""
        warnings = []
        E._parse_break_segments(_im(lunch_duration_minutes=7), warnings)
        self.assertTrue(warnings and warnings[0].startswith("HARD_"))


class IntervalGranularityIsHonoured(unittest.TestCase):
    """A-2. This is the denominator of every coverage number in the release."""

    class _WS:
        title = "FT Wise 60 Min"
        max_row = 1
        max_column = 1
        def cell(self, *_a, **_k):
            return SimpleNamespace(value=None)

    def test_a_valid_value_is_used(self):
        for value in (15, 30, 60):
            self.assertEqual(
                E._detect_interval_minutes(self._WS(), 1, _im(interval_minutes=value), []),
                value,
            )

    def test_an_invalid_value_is_reported_not_silently_replaced(self):
        for value in (7, 45, 0, "abc"):
            warnings = []
            E._detect_interval_minutes(self._WS(), 1, _im(interval_minutes=value), warnings)
            self.assertTrue(
                any(w.startswith("HARD_INVALID_INTERVAL_MINUTES:") for w in warnings),
                f"{value!r} was accepted silently",
            )

    def test_an_absent_value_still_infers_without_complaint(self):
        warnings = []
        E._detect_interval_minutes(self._WS(), 1, {}, warnings)
        self.assertEqual(warnings, [], "absent is not an error; it is inferred")


class AliasMatchingIgnoresSpacing(unittest.TestCase):
    """A-3. norm() keeps inner spaces, so single-word aliases never matched the
    spellings people actually type. Third recurrence of the A51 assumption."""

    def test_the_spaced_spellings_people_write_are_accepted(self):
        for text in ("All", "All Days", "all days", "Every Day", "7 Days", "Daily"):
            self.assertEqual(sorted(E._parse_language_days(text)), list(range(7)), text)

    def test_genuinely_invalid_text_is_still_rejected(self):
        for text in ("garbage", "Sun-Funday", "Noneday"):
            with self.assertRaises(ValueError, msg=text):
                E._parse_language_days(text)

    def test_the_real_day_vocabulary_still_parses(self):
        self.assertEqual(sorted(E._parse_language_days("Sun-Thu")), [0, 1, 2, 3, 4])
        self.assertEqual(sorted(E._parse_language_days("Weekdays")), [1, 2, 3, 4, 5])
        self.assertEqual(sorted(E._parse_language_days("Weekends")), [0, 6])


class LanguageRuleLookupRejectsABadDay(unittest.TestCase):
    """A-7. "No language rules apply anywhere" is the most dangerous possible
    default for a coverage rule, and it used to be what a wrong day produced."""

    def _parsed(self):
        rule = E.LanguageRule(
            language="Spanish", group="Spanish", start_min=0, end_min=0,
            minimum=2, active=True,
            required_languages={"spanish"}, eligible_languages={"spanish"},
        )
        return SimpleNamespace(language_rules=[rule])

    def test_every_real_weekday_matches(self):
        parsed = self._parsed()
        for day in range(7):
            self.assertEqual(len(E.language_rules_at(parsed, 600, 15, day=day)), 1)

    def test_the_cyclic_next_sunday_scope_maps_to_sunday(self):
        parsed = self._parsed()
        self.assertEqual(
            len(E.language_rules_at(parsed, 600, 15, day=7)),
            len(E.language_rules_at(parsed, 600, 15, day=0)),
        )

    def test_an_out_of_range_day_raises_instead_of_returning_nothing(self):
        parsed = self._parsed()
        for day in (8, 99, -1):
            with self.assertRaises(ValueError, msg=str(day)):
                E.language_rules_at(parsed, 600, 15, day=day)


class NoPackagedWorkbookChangesBehaviour(unittest.TestCase):
    """These fixes must be inert on every contract that exists today."""

    def test_break_and_interval_contracts_are_unchanged_and_warning_free(self):
        inputs = sorted((ROOT / "inputs").glob("*.xlsx"))
        if not inputs:
            self.skipTest("packaged inputs not present")
        for path in inputs:
            with self.subTest(workbook=path.name):
                parsed = E.parse_input(path)
                hard = [w for w in parsed.parser_warnings
                        if w.startswith(("HARD_INVALID_BREAK_CONTRACT",
                                         "HARD_INVALID_INTERVAL_MINUTES"))]
                self.assertEqual(hard, [], f"{path.name} newly fails the contract check")
                self.assertEqual(sum(q * 15 for q, _ in parsed.break_segments_q), 60)
                self.assertIn(parsed.interval_minutes, (15, 30, 60))


if __name__ == "__main__":
    unittest.main(verbosity=2)
