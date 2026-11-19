"""The shift-consistency polish ships as its own workbook (follow-up to audit F-35).

F-35: the polish replaced the measured schedule but never the published one.
Business decision (2026-10-04): never rewrite the selected schedule; publish
the polished week beside it, as `<id>_MORE_CONSISTENT_CANDIDATE.xlsx`, the way
MAX_TARGET and MAX_FLOOR already ship. The planner chooses.

This file proves what F-35 lacked: the workbook written for the polished week
really is the polished week (its start times are the polish record's "after",
not "before"), the selected schedule is untouched, the independent validator
recognises and passes it, and the runner approves it only if its coverage,
recomputed by the validator, is no worse than the selected schedule's.

Written to FAIL on the engine before this change and pass after.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

RUN = REPO / "fixtures" / "real_runs" / "language_hours"
BOOK = RUN / "Cricut_Voice_LANGUAGE_HOURS.xlsx"
CANDIDATE = RUN / "VOICE_FINAL_SHEET_CANDIDATE.json.gz"
ROLE = "MORE_CONSISTENT_CANDIDATE"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


IV = load(ROOT / "engine" / "tools" / "independent_validator.py", "iv_c37")
RUNNER = load(ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py", "runner_c37")


class TheRoleExistsEverywhere(unittest.TestCase):
    def test_the_engine_runner_and_cleanup_know_the_role(self):
        self.assertIn(ROLE, E.EXPORT_ROLE_ORDER)
        self.assertEqual(E.EXPORT_ROLE_ORDER[-1], "BALANCED_CANDIDATE")
        self.assertIn(ROLE, RUNNER.ALTERNATIVE_EXPORT_ROLES)
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertIn('output_path.with_name(prefix + "_MORE_CONSISTENT_CANDIDATE" + output_path.suffix)', source)


class TheSelectedScheduleIsNeverRewritten(unittest.TestCase):
    def pair(self, name):
        return (type("S", (), {"profile": name})(), type("B", (), {"profile": name})())

    def test_an_applied_polish_adds_an_export_and_leaves_the_selection(self):
        selected, polished = self.pair("selected"), self.pair("polished")
        selection = {"recommended": selected, "exports": [("RECOMMENDED_FINAL", selected)]}
        self.assertTrue(E.add_more_consistent_export(selection, polished, {"status": "APPLIED"}))
        self.assertIs(selection["recommended"], selected)
        self.assertIs(E.recommended_export_pair(selection), selected)
        self.assertEqual([r for r, _ in selection["exports"]], ["RECOMMENDED_FINAL", ROLE])
        self.assertIs(dict(selection["exports"])[ROLE], polished)

    def test_nothing_is_added_when_the_polish_kept_or_changed_nothing(self):
        for status in ("NO_CHANGE", "KEPT_ORIGINAL", "SKIPPED_NO_TIME"):
            selected = self.pair("selected")
            selection = {"recommended": selected, "exports": [("RECOMMENDED_FINAL", selected)]}
            self.assertFalse(E.add_more_consistent_export(selection, self.pair("p"), {"status": status}), status)
            self.assertEqual(len(selection["exports"]), 1)


class TheWorkbookCarriesThePolishedWeek(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = E.parse_input(BOOK)
        with gzip.open(CANDIDATE, "rt", encoding="utf-8") as fh:
            cls.skeleton, cls.solution = E.deserialize_break_candidate(cls.parsed, json.load(fh))
        cls.p_skeleton, cls.p_solution, cls.record = E.shift_consistency_polish(
            cls.parsed, cls.skeleton, cls.solution, time_limit_sec=60)
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = cls.tmp / f"case_L6_3_2_3_{ROLE}.xlsx"
        E.write_output_workbook(BOOK, cls.out, cls.parsed, cls.p_skeleton, cls.p_solution,
                                E.capacity_diagnostics(cls.parsed), [], {}, [], artifact_type=ROLE)

    def published_summary(self, path):
        names = [a.name for a in self.parsed.associates]
        sched, _ = IV.parse_output_schedule(path, names)
        idx = {E.norm(s.label): s.index for s in self.parsed.shifts}
        rows = [[idx.get(E.norm(v)) for v in sched[E.norm(a.name)]] for a in self.parsed.associates]
        sk = E.SkeletonSolution("pub", "FEASIBLE", 0.0, 0.0,
                                [list(sched[E.norm(a.name)]) for a in self.parsed.associates], rows, {})
        return E.shift_consistency_summary(self.parsed, sk)

    def test_the_fixture_polish_changes_the_week(self):
        self.assertEqual(self.record["status"], "APPLIED")
        self.assertNotEqual(self.record["before"], self.record["after"])

    def test_the_workbook_is_the_polished_week_not_the_original(self):
        published = self.published_summary(self.out)
        for key in ("distinct_start_times", "start_movement_hours", "associates_with_one_start_time"):
            self.assertEqual(published[key], self.record["after"][key], key)

    def test_the_validator_recognises_and_passes_it(self):
        self.assertEqual(IV.declared_artifact_type(self.out), "FINAL_AFTER_BREAKS")
        result = IV.validate(BOOK, self.out, ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
        self.assertEqual(result["hard_fail_count"], 0, result["failures"][:3])


class TheRunnerApprovesItOnlyIfCoverageIsNoWorse(unittest.TestCase):
    MAIN = {"after_target": 248, "after_floor": 253, "after100": 240, "after90": 250, "after80": 255,
            "severe_floor_gaps": 10, "language_gap_count": 0, "zero_staffed_active_quarters": 0,
            "coverage_split_gap_count": 0, "break_concurrency_violation_count": 1}

    def test_same_coverage_is_approved(self):
        self.assertEqual(RUNNER.more_consistent_coverage_verdict(self.MAIN, dict(self.MAIN)), (True, []))

    def test_any_coverage_loss_is_named_and_not_approved(self):
        worse = dict(self.MAIN, after_floor=252, severe_floor_gaps=11)
        ok, losses = RUNNER.more_consistent_coverage_verdict(self.MAIN, worse)
        self.assertFalse(ok)
        self.assertEqual(sorted(losses), ["after_floor", "severe_floor_gaps"])

    def test_the_outcome_text_offers_it_only_when_approved(self):
        row = {"role": ROLE, "status": "PASS", "coverage_no_worse": True,
               "workbook": "/x/case_L6_3_2_3_MORE_CONSISTENT_CANDIDATE.xlsx",
               "consistency": {"before": {"start_movement_hours": 54.0, "distinct_start_times": 59},
                               "after": {"start_movement_hours": 33.0, "distinct_start_times": 57}}}
        outcome = {"independent_validation": {"alternative_exports": [row]}}
        text = RUNNER._outcome_detail_text(outcome)
        self.assertIn("case_L6_3_2_3_MORE_CONSISTENT_CANDIDATE.xlsx", text)
        self.assertIn("54.0 h -> 33.0 h", text)
        refused = {"independent_validation": {"alternative_exports": [dict(row, coverage_no_worse=False)]}}
        self.assertNotIn("MORE_CONSISTENT_CANDIDATE.xlsx", RUNNER._outcome_detail_text(refused))


if __name__ == "__main__":
    unittest.main()
