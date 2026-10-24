# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY: the 16-person team of tools/channel_scenarios.py, planned Mon to Fri with fair spread and the consistency
tick on, against what the same team gave with both off (measured: spread 81.25 h, 2.48 channel changes and 1.02
stretches under two hours per person-day; the timed search varies a little from run to run, so each limit has a margin).
The full set of 7 teams is run by hand: ``python tools/channel_scenarios.py``."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import channel_scenarios as sc  # noqa: E402


class TheScenarioTeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.got = sc.run_arm(sc.SCENARIOS["base_16"], True, True)

    def test_people_alike_end_the_week_far_closer_than_with_both_off(self):
        self.assertLessEqual(self.got["spread"], 81.25 * 0.35)

    def test_channels_change_no_more_often_than_with_both_off(self):
        self.assertLessEqual(self.got["moves_pp"], 2.48 * 1.05)

    def test_stretches_under_two_hours_are_fewer_than_with_both_off(self):
        self.assertLessEqual(self.got["stretches_pp"], 1.02 * 0.9)

    def test_coverage_and_rules_are_untouched(self):
        self.assertLessEqual(self.got["short"], 2.5 + 0.5)
        self.assertEqual(self.got["problems"], 0)
        self.assertLessEqual(self.got["slowest"], 25)


if __name__ == "__main__":
    unittest.main()
