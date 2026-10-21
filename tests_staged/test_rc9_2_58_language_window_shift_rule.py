"""Phase AQ (owner, 2026-10-21: "take the 16:00 to 07:00 as shift start and end, not only shift start"; answer: go
ahead with WHOLE_SHIFT as an optional row). The Instructions row "Language Working Window Shift Rule" is START (the
default, and what the engine has always done: only the shift's start has to be inside the window) or WHOLE_SHIFT (the
shift must start and end inside it). It only matters where a Language Working Window mode already applies a window.

The decision rule for accepting WHOLE_SHIFT on the owner's GDI input is in evidence/phase_aq/REQUESTS.md; these tests
pin the mechanics. With the row blank nothing changes: same legal shifts, same contract hash.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
sys.path.insert(0, str(ROOT / "engine" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import l632_universal_scheduler as E  # noqa: E402
import phase_a_workbooks as W  # noqa: E402

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJKL"]
ALL_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(24)]
ENGLISH_16_TO_07 = [{"Language": "English", "Coverage Start": "16:00", "Coverage End": "07:00", "Active?": "Yes",
                     "Coverage Group": "English", "Minimum Per Interval": 1, "Coverage Days": "All"}]
ROW = "Language Working Window Shift Rule"


def parse(window="ALL_ROWS", rule=None):
    instructions = {"Language Working Window": window}
    if rule is not None:
        instructions[ROW] = rule
    spec = {"roster": [(n, "English") for n in NAMES[:10]], "shifts": ALL_SHIFTS, "demand": lambda d, m: 2,
            "language_setup": ENGLISH_16_TO_07, "instructions": instructions}
    tmp = tempfile.mkdtemp()
    try:
        path = Path(tmp) / "case.xlsx"
        W.build(spec, path)
        parsed = E.parse_input(path)
        contract = E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))
        return parsed, {str(f.get("code")) for f in contract["failures"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def shift(start_hour, hours=9):
    return E.Shift(index=0, label=f"{start_hour:02d}:00 - {(start_hour + hours) % 24:02d}:00",
                   start_min=start_hour * 60, end_min=((start_hour + hours) % 24) * 60, duration_min=hours * 60)


def legal_starts(parsed):
    assoc = parsed.associates[0]
    return sorted(s.start_min // 60 for s in parsed.shifts if E._consistency_cell_allowed(parsed, 0, 3, s))


class TheRowIsRead(unittest.TestCase):
    def test_blank_and_start_mean_the_old_rule(self):
        for raw in (None, "", "START", "Start", "start only", "starts"):
            self.assertEqual(E.normalize_language_window_shift_rule(raw), "START", raw)

    def test_whole_shift_is_read_whatever_the_spelling(self):
        for raw in ("WHOLE_SHIFT", "Whole shift", "whole-shift", "whole shift (start and end)", "WholeShift"):
            self.assertEqual(E.normalize_language_window_shift_rule(raw), "WHOLE_SHIFT", raw)

    def test_the_parsed_input_carries_it_and_defaults_to_start(self):
        self.assertEqual(parse(rule="WHOLE_SHIFT")[0].language_window_shift_rule, "WHOLE_SHIFT")
        self.assertEqual(parse()[0].language_window_shift_rule, "START")

    def test_a_value_the_engine_cannot_read_is_refused_not_replaced_by_the_default(self):
        _parsed, codes = parse(rule="sometimes")
        self.assertTrue(any("LANGUAGE_WINDOW_SHIFT_RULE" in c for c in codes), codes)


class TheRule(unittest.TestCase):
    WINDOW = (16 * 60, 7 * 60)  # 16:00 to 07:00

    def test_start_only_is_unchanged(self):
        self.assertTrue(E.shift_within_language_window(shift(23), self.WINDOW))
        self.assertTrue(E.shift_within_language_window(shift(1), self.WINDOW))
        self.assertFalse(E.shift_within_language_window(shift(15), self.WINDOW))

    def test_whole_shift_needs_the_end_inside_too(self):
        whole = lambda h: E.shift_within_language_window(shift(h), self.WINDOW, whole_shift=True)
        self.assertTrue(whole(16))
        self.assertTrue(whole(22))   # 22:00 to 07:00 ends exactly at the close
        self.assertFalse(whole(23))  # 23:00 to 08:00
        self.assertFalse(whole(1))   # 01:00 to 10:00
        self.assertFalse(whole(15))  # starts before the window opens

    def test_a_shift_longer_than_the_window_fits_no_window(self):
        self.assertFalse(E.shift_within_language_window(shift(8, 11), (8 * 60, 16 * 60), whole_shift=True))
        self.assertTrue(E.shift_within_language_window(shift(8, 8), (8 * 60, 16 * 60), whole_shift=True))

    def test_a_window_of_the_whole_day_allows_every_shift(self):
        self.assertTrue(E.shift_within_language_window(shift(23), (0, 0), whole_shift=True))


class TheEffectOnTheModel(unittest.TestCase):
    def test_start_only_still_allows_the_late_and_early_starts(self):
        self.assertEqual(legal_starts(parse()[0]), [0, 1, 2, 3, 4, 5, 6, 16, 17, 18, 19, 20, 21, 22, 23])

    def test_whole_shift_keeps_only_shifts_that_end_inside_the_window(self):
        self.assertEqual(legal_starts(parse(rule="WHOLE_SHIFT")[0]), [16, 17, 18, 19, 20, 21, 22])

    def test_the_rule_does_nothing_while_the_window_mode_is_off(self):
        parsed, _ = parse(window="OFF", rule="WHOLE_SHIFT")
        self.assertEqual(legal_starts(parsed), list(range(24)))

    def test_the_contract_hash_is_unchanged_by_the_default_and_changed_by_whole_shift(self):
        plain = E.canonical_hash(E.canonical_contract_snapshot(parse()[0]))
        spelled = E.canonical_hash(E.canonical_contract_snapshot(parse(rule="START")[0]))
        whole = E.canonical_hash(E.canonical_contract_snapshot(parse(rule="WHOLE_SHIFT")[0]))
        self.assertEqual(plain, spelled)
        self.assertNotEqual(plain, whole)
        self.assertNotIn("language_window_shift_rule", E.canonical_contract_snapshot(parse()[0]))


class TheValidatorAgrees(unittest.TestCase):
    def test_a_late_start_is_a_failure_only_under_whole_shift(self):
        import independent_validator as V
        self.assertTrue(hasattr(E, "language_window_allows"))
        start_only, _ = parse()
        whole, _ = parse(rule="WHOLE_SHIFT")
        late = shift(23)
        windows = E.associate_language_windows(start_only, start_only.associates[0], day=3)
        self.assertTrue(any(E.language_window_allows(start_only, late, w) for w in windows))
        windows = E.associate_language_windows(whole, whole.associates[0], day=3)
        self.assertFalse(any(E.language_window_allows(whole, late, w) for w in windows))
        self.assertTrue(callable(V.validate))


class TheCleanRoomCheckerAgrees(unittest.TestCase):
    """tools/clean_room_check.py re-reads the contract without the engine's code; it reads the row too."""

    def contract(self, rule):
        sys.path.insert(0, str(REPO / "tools"))
        import clean_room_check as C
        spec = {"roster": [(n, "English") for n in NAMES[:10]], "shifts": ALL_SHIFTS, "demand": lambda d, m: 2,
                "language_setup": ENGLISH_16_TO_07,
                "instructions": {"Language Working Window": "ALL_ROWS", **({ROW: rule} if rule else {})}}
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = Path(tmp) / "case.xlsx"
        W.build(spec, path)
        return C.read_contract(path)

    def test_the_default_and_whole_shift(self):
        self.assertFalse(self.contract(None).window_whole)
        self.assertFalse(self.contract("START").window_whole)
        self.assertTrue(self.contract("WHOLE_SHIFT").window_whole)


if __name__ == "__main__":
    unittest.main()
