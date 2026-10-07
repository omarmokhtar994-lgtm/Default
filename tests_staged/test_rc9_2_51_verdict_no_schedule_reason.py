"""Phase G, task 4: a NOT_RELEASABLE run with no schedule says why.

External audit P1-03 (evidence/external_reviews/CHATGPT_FINAL_AUDIT_2026_10_07_EVALUATION.md):
"distinguish proven infeasibility from exhausted search". The engine's
BUSINESS_OUTCOME already does (HARD_RULE_COMBINATION_INFEASIBLE vs category
SEARCH_INCOMPLETE), but the Phase F release verdict only said "gate 8
independent validation not run". It now carries the reason as a note; the
verdict value itself does not change.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("release_gate_report_g4", REPO / "tools" / "release_gate_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = load()


def no_schedule(category="", code=""):
    return {"case": "CASE", "gate4_quality_retention": "NO_EVIDENCE", "gate5_break_regression": "NO_EVIDENCE",
            "gate5_detail": "no summary produced", "gate8_independent_validation": "NO_EVIDENCE",
            "outcome_category": category, "outcome_code": code}


def notes(row):
    return " | ".join(GATE.release_verdict(row)["notes"])


class TheReasonIsNamed(unittest.TestCase):
    def test_search_ran_out_is_named(self):
        text = notes(no_schedule("SEARCH_INCOMPLETE", "HARD_FEASIBILITY_SEARCH_INCOMPLETE"))
        self.assertIn("ran out of time", text)
        self.assertIn("not proof", text)

    def test_break_search_ran_out_is_named_the_same_way(self):
        self.assertIn("ran out of time", notes(no_schedule("SEARCH_INCOMPLETE", "BREAK_SEARCH_TIME_EXHAUSTED")))

    def test_proven_contradiction_is_named(self):
        text = notes(no_schedule("INPUT_OR_POLICY_ACTION_REQUIRED", "HARD_RULE_COMBINATION_INFEASIBLE"))
        self.assertIn("contradict", text)
        self.assertIn("proven", text)

    def test_missing_outcome_is_named_unknown(self):
        self.assertIn("reason not recorded", notes(no_schedule()))

    def test_verdict_value_unchanged(self):
        for row in (no_schedule("SEARCH_INCOMPLETE"), no_schedule("", "HARD_RULE_COMBINATION_INFEASIBLE"), no_schedule()):
            self.assertEqual(GATE.release_verdict(row)["verdict"], "NOT_RELEASABLE")

    def test_a_validated_schedule_gets_no_no_schedule_note(self):
        row = dict(no_schedule("SEARCH_INCOMPLETE"), gate8_independent_validation="PASS",
                   gate4_quality_retention="PASS", gate5_break_regression="PASS", gate5_detail="")
        self.assertNotIn("no schedule", notes(row))


class TheReportReadsTheOutcomeFile(unittest.TestCase):
    def test_report_reads_business_outcome_from_the_case(self):
        tmp = Path(tempfile.mkdtemp())
        case = tmp / "results" / "NOSCHED"
        (case / "debug").mkdir(parents=True)
        (case / "UNIVERSAL_RUN_IDENTITY.json").write_text(json.dumps({"engine_sha256": "x"}), encoding="utf-8")
        (case / "debug" / "BUSINESS_OUTCOME.json").write_text(json.dumps(
            {"outcome_code": "HARD_FEASIBILITY_SEARCH_INCOMPLETE", "outcome_category": "SEARCH_INCOMPLETE"}),
            encoding="utf-8")
        argv = sys.argv
        sys.argv = ["release_gate_report.py", str(tmp / "results"), "--out-dir", str(tmp / "out")]
        try:
            rc = GATE.main()
        finally:
            sys.argv = argv
        verdict = json.loads((tmp / "out" / "RELEASE_VERDICT.json").read_text())
        self.assertEqual(rc, 3)
        self.assertIn("ran out of time", " ".join(verdict["cases"]["NOSCHED"]["notes"]))


if __name__ == "__main__":
    unittest.main()
