"""Engine fixes from the 2026-09-28 audit that have no other home.

F-09: DNBS may not trade a soft metric (language reserve, overage shape,
week-boundary imbalance, skill gaps) for one more target interval.
M-01: a budget below 60 s used to run for 60 s silently; it is refused.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402


class DnbsGuard(unittest.TestCase):
    OLD = {"after_target": 100, "after_floor": 120}

    def test_a_target_gain_that_worsens_a_soft_metric_is_rejected(self):
        for key in ("language_reserve_shortfall_quarters", "language_minimum_only_quarters",
                    "skill_allocation_gap_quarters", "after_avoidable_overage_peak_fte",
                    "after_avoidable_overage_top10_concentration", "week_boundary_imbalance_violation_count",
                    "week_boundary_overage_cap_violation_count",
                    "week_boundary_language_reserve_shortfall_quarters"):
            with self.subTest(metric=key):
                old = dict(self.OLD, **{key: 1})
                new = dict(self.OLD, after_target=101, **{key: 2})
                ok, worse = E.dnbs_metrics_no_worse(new, old)
                self.assertFalse(ok)
                self.assertIn(key, worse)

    def test_a_clean_target_gain_is_accepted(self):
        ok, worse = E.dnbs_metrics_no_worse(dict(self.OLD, after_target=101), dict(self.OLD))
        self.assertTrue(ok, worse)

    def test_dnbs_is_opt_in(self):
        self.assertFalse(E.DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED)


class MinimumBudget(unittest.TestCase):
    def test_the_engine_cli_refuses_under_60_seconds(self):
        proc = subprocess.run([sys.executable, str(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"),
                               "--time-limit", "30", "--input", "x.xlsx"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("below the 60 s minimum", proc.stderr)

    def test_the_production_runner_refuses_under_60_seconds(self):
        source = (ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py").read_text()
        self.assertIn("if time_limit < 60:", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
