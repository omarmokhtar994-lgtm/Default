# © 2026 Omar Mokhtar. All rights reserved.
"""Phase L task 1: the engine's own outcome (BUSINESS_OUTCOME.json) on the run page.

Fixtures are real engine outcomes with people's names replaced: a language and
fixed-request conflict, a run with one impossible interval (shortfall schedule
attached), and a readiness check that passed."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.outcome import compact, read, view

HERE = Path(__file__).with_name("fixtures") / "outcomes"


def load(name):
    return json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))


class TheOutcome(unittest.TestCase):
    def test_conflict_outcome_names_rules_people_and_actions(self):
        v = view(load("conflict"))
        self.assertEqual(v["headline"], "No schedule satisfies all hard rules together")
        self.assertEqual(v["blockers"], [
            "language rules (minimum per interval and Language Working Window hours): relaxing this rule alone makes a schedule possible",
            "fixed requests (Fixed Request sheet): relaxing this rule alone makes a schedule possible"])
        first, second = v["people"][:2]  # Sunday's language hours differ, so it is its own row
        self.assertEqual((first["associate"], first["days"], first["window"]),
                         ("Associate 1 (English)", "Sun", "language hours 17:00-04:00"))
        self.assertEqual((second["associate"], second["days"], second["shift"]),
                         ("Associate 1 (English)", "Mon to Thu", "fixed 05:00 - 14:00"))
        self.assertEqual(v["people_total"], 24)
        self.assertTrue(v["actions"][0].startswith("24 fixed request(s) start outside their associate's language hours"))
        self.assertNotIn("tools/", " ".join(v["actions"]))  # a developer tool, not something the site's users run
        self.assertTrue(v["cannot_schedule"])
        self.assertFalse(v["ready"])

    def test_shortfall_rows_read_plainly(self):
        v = view(load("shortfall"))
        self.assertEqual(v["shortfalls"][0], "Sun 03:00: Nobody on the floor after breaks, needs 1, short by 1")
        self.assertEqual(v["blockers"], ["Sun 03:00: there is demand, but no one on the roster can be working then"])
        self.assertTrue(v["cannot_schedule"])

    def test_coded_finding_is_humanised_with_values(self):
        o = load("shortfall")
        o["resource_findings"] = [{"code": "WHOLE_WEEK_OVERAGE_CAP_EXCEEDED", "actual": 0.12, "maximum": 0.1}]
        self.assertEqual(view(o)["blockers"], ["Whole week overage cap exceeded (actual 0.12, maximum 0.1)"])

    def test_ready_outcome(self):
        v = view(load("ready"))
        self.assertTrue(v["ready"])
        self.assertFalse(v["cannot_schedule"])

    def test_compact_keeps_code_category_and_headline(self):
        self.assertEqual(compact(load("conflict")), {
            "code": "HARD_RULE_COMBINATION_INFEASIBLE", "category": "INPUT_OR_POLICY_ACTION_REQUIRED",
            "headline": "No schedule satisfies all hard rules together"})

    def test_read_finds_the_case_folder_outcome(self):
        results = Path(tempfile.mkdtemp())
        (results / "_gate_report").mkdir()
        (results / "_gate_report" / "BUSINESS_OUTCOME.json").write_text("{}", encoding="utf-8")
        (results / "ENGLISH_WEEK42").mkdir()
        shutil.copy(HERE / "conflict.json", results / "ENGLISH_WEEK42" / "BUSINESS_OUTCOME.json")
        self.assertEqual(read(results)["outcome_code"], "HARD_RULE_COMBINATION_INFEASIBLE")
        self.assertIsNone(read(results / "nothing"))

    def test_a_broken_outcome_file_reads_as_none(self):
        results = Path(tempfile.mkdtemp())
        (results / "CASE").mkdir()
        (results / "CASE" / "BUSINESS_OUTCOME.json").write_text("{not json", encoding="utf-8")
        self.assertIsNone(read(results))


if __name__ == "__main__":
    unittest.main()
