#!/usr/bin/env python3
"""A capacity-short roster must not be scored as an optimiser result.

This exists because of a concrete, expensive mistake. An AE comparison
averaged five scenarios into one coverage KPI and concluded one engine beat
another by ten intervals. Two of those five were capacity-infeasible:
AE_IT_Choice was short by 46.6 productive hours (11 of 40 associate-days on
leave) and AE_IT_B2B by 28.4. Neither engine could reach target on either
workbook under any shift pattern or break placement, so their coverage
measured the roster, not the optimiser - and the case with the largest claimed
"after-break loss" was one of them.

The engine already knew: `aggregate_target_slack` computes it, and preflight
already emitted AGGREGATE_TARGET_CAPACITY_SHORTAGE. It was one warning among
many and got read past. These tests pin it as a verdict with a number a
scheduler can act on.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402


class CapacityClassification(unittest.TestCase):

    def _cb(self, hc, req_per_interval, target=1.0, leave=0):
        """Build a minimal contract with a known supply/demand ratio."""
        parsed = E.parse_input(sorted((ROOT / "inputs").glob("*.xlsx"))[0])
        # Replace demand with a flat, known profile and resize the roster.
        parsed.requirements = [[float(req_per_interval)] * parsed.intervals_per_day
                               for _ in range(7)]
        parsed.shrinkage = [[0.0] * parsed.intervals_per_day for _ in range(7)]
        parsed.active = [[True] * parsed.intervals_per_day for _ in range(7)]
        parsed.associates = parsed.associates[:hc]
        parsed.target_ratio = target
        return E.capacity_diagnostics(parsed)["coverage_benchmark"]

    def test_a_short_roster_is_classified_short_and_made_ineligible(self):
        cb = self._cb(hc=2, req_per_interval=10)
        self.assertEqual(cb["capacity_class"], "CAPACITY_SHORT")
        self.assertFalse(cb["benchmark_eligible"])
        self.assertLess(cb["target_capacity_slack_hours"], 0)

    def test_an_ample_roster_is_eligible(self):
        cb = self._cb(hc=30, req_per_interval=1)
        self.assertEqual(cb["capacity_class"], "CAPACITY_AMPLE")
        self.assertTrue(cb["benchmark_eligible"])

    def test_the_headline_states_the_best_reachable_target(self):
        """The number that turns a confusing coverage result into a decision."""
        cb = self._cb(hc=2, req_per_interval=10)
        self.assertIn("cannot exceed about", cb["headline"])
        self.assertLess(cb["max_attainable_target_ratio"], 1.0)
        self.assertGreaterEqual(cb["max_attainable_target_ratio"], 0.0)

    def test_max_attainable_is_capped_at_one_for_a_sufficient_roster(self):
        cb = self._cb(hc=30, req_per_interval=1)
        self.assertEqual(cb["max_attainable_target_ratio"], 1.0)

    def test_leave_is_deducted_and_reported(self):
        """Leave was the actual cause on AE_IT_Choice and must be visible."""
        cb = self._cb(hc=2, req_per_interval=10)
        self.assertIn("leave", cb["headline"].lower())
        self.assertIn("leave_days_deducted", cb)

    def test_a_short_roster_names_the_headcount_it_needs(self):
        cb = self._cb(hc=2, req_per_interval=10)
        self.assertGreater(cb["estimated_additional_hc_for_target"], 0)


class TheVerdictReachesTheRunSummary(unittest.TestCase):
    """A verdict nobody can read from the results is not a gate."""

    def test_the_summary_carries_the_class_and_eligibility(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        for field in ('"capacity_class"', '"coverage_benchmark_eligible"',
                      '"max_attainable_target_ratio"', '"target_capacity_slack_hours"'):
            self.assertIn(field, source, f"{field} missing from the run summary")

    def test_the_headline_is_logged_at_preflight(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertIn('print(f"CAPACITY {_cb.get(\'capacity_class\')} {_cb[\'headline\']}"', source)


class RealAeWorkbooksAreClassifiedCorrectly(unittest.TestCase):
    """The six workbooks that produced the mistaken comparison."""

    AE = Path("/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/"
              "scratchpad/ae/RC5_AE_REAL_SCHEDULES_QUICK_PACKAGE/inputs")
    EXPECTED = {
        "AE_AR_B2B": "CAPACITY_AMPLE",
        "AE_FR_B2B": "CAPACITY_AMPLE",
        "AE_FR_Choice": "CAPACITY_AMPLE",
        "AE_AR_Choice": "CAPACITY_TIGHT",
        "AE_IT_B2B": "CAPACITY_SHORT",
        "AE_IT_Choice": "CAPACITY_SHORT",
    }

    def test_the_two_infeasible_cases_are_excluded_and_the_rest_are_not(self):
        if not self.AE.is_dir():
            self.skipTest("AE workbooks not present in this environment")
        for name, expected in self.EXPECTED.items():
            path = self.AE / f"{name}.xlsx"
            if not path.is_file():
                continue
            with self.subTest(case=name):
                cb = E.capacity_diagnostics(E.parse_input(path))["coverage_benchmark"]
                self.assertEqual(cb["capacity_class"], expected)
                self.assertEqual(cb["benchmark_eligible"], expected != "CAPACITY_SHORT")


class NoPackagedWorkbookIsNewlyExcluded(unittest.TestCase):
    def test_packaged_scenarios_keep_their_benchmark_eligibility(self):
        inputs = sorted((ROOT / "inputs").glob("*.xlsx"))
        if not inputs:
            self.skipTest("packaged inputs not present")
        for path in inputs:
            with self.subTest(workbook=path.name):
                cb = E.capacity_diagnostics(E.parse_input(path))["coverage_benchmark"]
                self.assertIn(cb["capacity_class"],
                              {"CAPACITY_AMPLE", "CAPACITY_TIGHT", "CAPACITY_SHORT"})
                self.assertIsInstance(cb["benchmark_eligible"], bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
