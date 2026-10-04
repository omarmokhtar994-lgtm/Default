"""Audit F-35: the schedule the engine measures must be the schedule it publishes.

Found in the Phase C4 impact A/B (Voice, seed 9000, exit 4). After selection,
the shift-consistency polish replaced selection["recommended"] with a polished
pair, and every audit metric, quality gate and outcome number was then taken
from it. The workbook writer iterated selection["exports"], which still held
the pre-polish pair. So:

  * no published workbook ever carried the polish (measured on six runs,
    evidence/production_readiness_audit/phase_c/F35_POLISH_NOT_PUBLISHED.txt);
  * when the polish moved a shift by an hour, the audit and the workbook
    disagreed on overage statistics, and the parity gate blocked a valid
    schedule (FAIL_METRIC_PARITY).

Decision (business, 2026-10-04): keep the published schedules exactly as they
are. The polish is withheld until it is validated on its own, and the engine
refuses to publish if the pair it measured is not the pair it writes.

Written to FAIL on the engine before the fix and pass after.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

SOURCE = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
_START = SOURCE.index("\ndef run_case(") + 1
RUN_CASE = SOURCE[_START:SOURCE.index("\ndef ", _START + 1)]  # the whole function


def pair(name):
    return (SimpleNamespace(profile=name), SimpleNamespace(profile=name))


class TheMeasuredPairIsThePublishedPair(unittest.TestCase):
    def test_the_recommended_export_is_returned_when_it_is_the_measured_pair(self):
        recommended = pair("a")
        selection = {"recommended": recommended,
                     "exports": [("RECOMMENDED_FINAL", recommended), ("MAX_TARGET_CANDIDATE", pair("b"))]}
        self.assertIs(E.recommended_export_pair(selection), recommended)

    def test_a_recommended_pair_that_is_not_exported_is_refused(self):
        # The F-35 shape: recommended replaced, exports left holding the original.
        original, polished = pair("original"), pair("polished")
        selection = {"recommended": polished, "exports": [("RECOMMENDED_FINAL", original)]}
        with self.assertRaises(E.PublishedScheduleMismatch):
            E.recommended_export_pair(selection)

    def test_run_case_checks_it_before_anything_is_measured_or_written(self):
        check = RUN_CASE.index("chosen_skeleton, chosen_breaks = recommended_export_pair(selection)")
        self.assertLess(check, RUN_CASE.index("break_capacity_headcount_requirement(\n            parsed, chosen_skeleton"))
        self.assertLess(check, RUN_CASE.index('for role, (sk, br) in selection["exports"]:'))


class ThePolishNeverReplacesTheSelectedSchedule(unittest.TestCase):
    """Re-pinned 2026-10-04, same day: the first F-35 fix withheld the polish
    (audit status WITHHELD_PENDING_VALIDATION). The business then chose to
    publish the polished week as its own workbook, MORE_CONSISTENT_CANDIDATE,
    beside the selected schedule (tests_staged/test_rc9_2_37_more_consistent_
    candidate.py). What must hold for good: the polish never replaces the
    selected, measured, published pair."""

    def test_run_case_never_replaces_the_recommended_pair(self):
        self.assertNotIn('selection["recommended"] = (polished_skeleton, polished_breaks)', RUN_CASE)
        self.assertNotIn('selection["recommended"] =', RUN_CASE[RUN_CASE.index("polish_on = ("):])

    def test_an_applied_polish_goes_to_its_own_export(self):
        self.assertIn("add_more_consistent_export(selection, (polished_skeleton, polished_breaks), polish_record)",
                      RUN_CASE)

    def test_the_polish_itself_is_kept(self):
        self.assertTrue(callable(E.shift_consistency_polish))


if __name__ == "__main__":
    unittest.main()
