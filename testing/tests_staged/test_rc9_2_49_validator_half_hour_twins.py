"""Phase F, task 2 follow-up: the validator accepts the :30 twins the switch adds.

Measured defect (Phase F run F_CHAT_HALF, 2026-10-07): with "Allow Half-Hour
Starts" = Yes the independent validator failed the run with
INPUT_CROSSCHECK_MISMATCH, check "shifts": its raw-workbook catalog held only
the shift sheet's rows, so every :30 twin read as a shift the engine invented.

The validator now derives the twins itself from the raw workbook: only when
the workbook's own switch says Yes, and only a start 30 minutes after an
on-the-hour catalog shift of the same length. Any other shift missing from the
workbook still fails, and the switch itself is cross-checked against the parse.
"""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(ROOT / "engine" / "tools"))
import build_synthetic_suite as B  # noqa: E402
import independent_validator as V  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
TEMPLATE = REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx"


def workbook(switch=None):
    names, langs = B.english(14)
    settings = {"Short Break Count": 0, "Lunch Count": 0}
    if switch is not None:
        settings["Allow Half-Hour Starts"] = switch
    case = dict(id="F2_VAL", tier="test", associates=14, shift_starts=[8 * 60, 12 * 60], shift_minutes=540,
                shrinkage=0.0, interval_minutes=60, names=names, languages=langs,
                language_rules=B.ENGLISH_RULE, settings=settings)
    demand = [[(3.0 if 8 <= h < 21 else None) for h in range(24)] for _ in range(7)]
    out = Path(tempfile.mkdtemp()) / "F2_VAL.xlsx"
    B.build_workbook(TEMPLATE, out, copy.deepcopy(case), E, demand)
    return out


def crosscheck(book, parsed):
    return V.independent_input_crosscheck(book, parsed)


def with_shift(parsed, start, minutes, flagged=True):
    p = copy.deepcopy(parsed)
    end = (start + minutes) % 1440
    label = f"{E.hhmm(start)} - {E.hhmm(end)}"
    p.shifts.append(E.Shift(len(p.shifts), label, start, end, minutes, half_hour_fallback=flagged))
    return p


class TwinsFromTheSwitchAreAccepted(unittest.TestCase):
    def test_switch_on_untouched_parse_crosschecks_clean(self):
        book = workbook("Yes")
        parsed = E.parse_input(book)
        self.assertTrue(any(s.half_hour_fallback for s in parsed.shifts))
        result = crosscheck(book, parsed)
        self.assertEqual(result["checks"]["shifts"], "PASS", result["mismatches"])
        self.assertEqual(result["mismatches"], [])


class ValidationIsNotWeakened(unittest.TestCase):
    def test_switch_on_a_shift_no_rule_derives_still_fails(self):
        book = workbook("Yes")
        p = with_shift(E.parse_input(book), 8 * 60 + 15, 540)
        self.assertIn("shifts", {m["check"] for m in crosscheck(book, p)["mismatches"]})

    def test_switch_on_a_twin_of_a_different_length_still_fails(self):
        book = workbook("Yes")
        p = with_shift(E.parse_input(book), 8 * 60 + 30, 480)
        self.assertIn("shifts", {m["check"] for m in crosscheck(book, p)["mismatches"]})

    def test_switch_off_a_twin_still_fails(self):
        book = workbook()
        p = with_shift(E.parse_input(book), 8 * 60 + 30, 540)
        self.assertIn("shifts", {m["check"] for m in crosscheck(book, p)["mismatches"]})

    def test_parsed_switch_disagreeing_with_the_workbook_fails(self):
        book = workbook()
        p = copy.deepcopy(E.parse_input(book))
        p.allow_half_hour_starts = True
        self.assertIn("request_switches", {m["check"] for m in crosscheck(book, p)["mismatches"]})


if __name__ == "__main__":
    unittest.main()
