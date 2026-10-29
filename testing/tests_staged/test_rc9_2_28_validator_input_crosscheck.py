"""The validator cross-checks parse_input against the raw workbook (audit F-13).

The validator used the engine's own parse_input, so a parser defect was
invisible to it. independent_input_crosscheck re-reads roster, demand and
leave/OFF cells with openpyxl alone. These tests inject each parser defect into
a correct parse and require a failure, and require 0 failures on the untouched
parse of every shipped workbook.
"""
import copy
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
sys.path.insert(0, str(ROOT / "engine" / "tools"))
import l632_universal_scheduler as E  # noqa: E402
import independent_validator as V  # noqa: E402

INPUTS = next(p for p in (ROOT / "inputs", REPO / "packages" / "rc9_2_2_production" / "inputs") if p.exists())
VOICE = INPUTS / "Cricut_Voice_RC9_1_READY_SKELETON.xlsx"  # preferences and fixed requests both enabled


def failing(parsed, book=VOICE):
    return {m["check"] for m in V.independent_input_crosscheck(book, parsed)["mismatches"]}


class CorrectParsesPass(unittest.TestCase):
    def test_every_shipped_workbook_crosschecks_clean(self):
        for book in sorted(INPUTS.glob("*.xlsx")):
            with self.subTest(book=book.name):
                result = V.independent_input_crosscheck(book, E.parse_input(book))
                self.assertEqual(result["mismatches"], [])
                self.assertEqual(result["not_checked"], [])
                self.assertEqual(result["checks"]["roster"], "PASS")
                self.assertEqual(result["checks"]["demand"], "PASS")


class InjectedParserDefectsFail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = E.parse_input(VOICE)
        assert cls.parsed.use_preferences and cls.parsed.fixed_enabled

    def fresh(self):
        return copy.deepcopy(self.parsed)

    def test_a_dropped_associate(self):
        p = self.fresh()
        p.associates = p.associates[1:]
        self.assertIn("roster", failing(p))

    def test_demand_read_one_interval_late(self):
        p = self.fresh()
        p.requirements = [day[-1:] + day[:-1] for day in p.requirements]
        self.assertIn("demand", failing(p))

    def test_demand_read_from_the_wrong_day(self):
        p = self.fresh()
        p.requirements = p.requirements[1:] + p.requirements[:1]
        self.assertIn("demand", failing(p))

    def test_a_leave_cell_that_vanishes(self):
        p = self.fresh()
        hit = next((a, d) for a in p.associates for d, v in enumerate(a.preferences)
                   if E.preference_kind(v) in {"leave", "off"})
        hit[0].preferences = list(hit[0].preferences)
        hit[0].preferences[hit[1]] = ""
        self.assertIn("preference", failing(p))

    def test_a_fabricated_fixed_request(self):
        p = self.fresh()
        assoc, day = next((a, d) for a in p.associates for d, v in enumerate(a.fixed_schedule) if not str(v).strip())
        assoc.fixed_schedule = list(assoc.fixed_schedule)
        assoc.fixed_schedule[day] = "09:00 - 18:00"
        self.assertIn("fixed", failing(p))

    def test_a_mismatch_fails_the_whole_validation(self):
        src = (ROOT / "engine" / "tools" / "independent_validator.py").read_text()
        self.assertIn('failures.append({"type":"INPUT_CROSSCHECK_MISMATCH", **mismatch})', src)
        self.assertIn('warnings.append({"type":"INPUT_CROSSCHECK_NOT_CHECKED", **skipped})', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
