# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BR (owner, 2026-11-18: "develop current forecast first to be perfect"): each weekday's interval shape is pooled over the chosen weeks
(its contacts summed, over the weekday's total), the candidate that met its pre-registered rule (evidence/phase_br/RULES.md, R1). Made-up volumes."""
import unittest
from datetime import date, timedelta

from webapp import forecast as F

STEP = 360                      # four intervals a day keeps the hand-worked numbers small
TARGET = date(2026, 6, 7)       # a Sunday
MONDAYS = ([0, 10, 10, 0], [0, 30, 10, 0], [0, 10, 20, 0])   # oldest first


def history():
    days = {}
    for k, monday in enumerate(MONDAYS):
        start = TARGET - timedelta(weeks=len(MONDAYS) - k)
        for off in range(7):
            day = start + timedelta(days=off)
            days[day] = [float(v) for v in (monday if day.weekday() == 0 else [0, 10, 10, 0])]
    return days


class ThePooledShape(unittest.TestCase):
    def setUp(self):
        days = history()
        self.profile = F.build_profile(days, STEP, F.choose_weeks(days, STEP, TARGET, weeks=3))

    def test_a_weekday_shape_is_its_contacts_summed_over_the_weeks(self):
        # Monday: 50 of 90 contacts in the second interval, 40 of 90 in the third (the median of the day shares would give 0.5 and 0.5)
        mon = self.profile.shares[0]
        self.assertAlmostEqual(mon[1], 50 / 90, places=12)
        self.assertAlmostEqual(mon[2], 40 / 90, places=12)
        self.assertEqual((mon[0], mon[3]), (0.0, 0.0))

    def test_the_day_mix_is_still_the_median_of_the_week_shares(self):
        # untouched by R1: Monday's share of each week is 20/140, 40/160 and 30/150; the median is 0.2, then renormalised with the other days
        mix = [20 / 140, 40 / 160, 30 / 150]
        others = sorted(20 / t for t in (140, 160, 150))[1]
        expected = sorted(mix)[1] / (sorted(mix)[1] + 6 * others)
        self.assertAlmostEqual(self.profile.day_shares[0], expected, places=12)


if __name__ == "__main__":
    unittest.main()
