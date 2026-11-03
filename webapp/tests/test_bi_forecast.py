# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI task 2 (owner, 2026-11-03: "I can give the count of calls for next week and it automatically calculates calls per interval", "see
trends", "calculate the OTF"): the shape of a program's week from its own history, a suggested week total, a total spread over days and
intervals in whole numbers, and offered versus forecast. Made-up numbers only."""
import random
import unittest
from datetime import date, timedelta

from webapp import forecast as F

STEP = 60
OPEN = list(range(24))
TODAY = date(2026, 11, 2)  # a Monday


def shape_for(weekday):
    """A known shape: flat 6 percent an hour, a peak of 14 percent at 10:00 on Mondays, nothing 00:00 to 06:00."""
    raw = [0.0] * 6 + [6.0] * 18
    if weekday == 0:
        raw[10] = 14.0
    total = sum(raw)
    return [v / total for v in raw]


def history(weeks=8, base=2000, growth=0, odd=None):
    days = {}
    for w in range(1, weeks + 1):
        monday = TODAY - timedelta(weeks=w)
        for d in range(7):
            day = monday + timedelta(days=d)
            total = base + growth * (weeks - w) + 100 * d
            days[day] = [round(total * s, 3) for s in shape_for(day.weekday())]
    for day, factor in (odd or {}).items():
        days[day] = [v * factor for v in days[day]]
    return days


class TheProfile(unittest.TestCase):
    def test_it_finds_the_shape_that_is_there(self):
        profile = F.build_profile(history(), STEP, today=TODAY)
        mon = profile.shares[0]
        truth = shape_for(0)
        for i in OPEN:
            self.assertAlmostEqual(mon[i], truth[i], delta=0.005)
        self.assertAlmostEqual(sum(mon), 1.0, places=9)
        self.assertAlmostEqual(sum(profile.day_shares.values()), 1.0, places=9)
        self.assertEqual(profile.thin, [])
        self.assertEqual(profile.excluded, [])

    def test_a_holiday_is_left_out_and_said(self):
        holiday = TODAY - timedelta(weeks=3)
        profile = F.build_profile(history(odd={holiday: 0.2}), STEP, today=TODAY)
        self.assertEqual([d for d, _ in profile.excluded], [holiday.isoformat()])
        self.assertAlmostEqual(profile.shares[0][10], shape_for(0)[10], delta=0.005)

    def test_a_day_the_owner_names_is_left_out(self):
        named = TODAY - timedelta(weeks=2, days=-1)
        profile = F.build_profile(history(), STEP, today=TODAY, exclude=[named])
        self.assertIn(named.isoformat(), [d for d, _ in profile.excluded])

    def test_a_weekday_with_too_little_history_is_thin_and_borrows_the_shape(self):
        days = history()
        for day in [d for d in days if d.weekday() == 5][:-2]:  # keep two Saturdays
            del days[day]
        profile = F.build_profile(days, STEP, today=TODAY)
        self.assertIn(5, profile.thin)
        self.assertAlmostEqual(sum(profile.shares[5]), 1.0, places=9)

    def test_a_weekday_never_seen_gets_the_average_shape(self):
        days = {d: v for d, v in history().items() if d.weekday() != 6}
        profile = F.build_profile(days, STEP, today=TODAY)
        self.assertIn(6, profile.thin)
        self.assertEqual(profile.weeks_used[6], 0)
        self.assertAlmostEqual(sum(profile.shares[6]), 1.0, places=9)

    def test_no_history_is_refused(self):
        with self.assertRaises(ValueError):
            F.build_profile({}, STEP, today=TODAY)

    def test_only_the_last_weeks_count(self):
        days = history(weeks=8)
        old = TODAY - timedelta(weeks=20)
        for d in range(7):
            days[old + timedelta(days=d)] = [100.0] * 24  # a flat shape, long ago
        profile = F.build_profile(days, STEP, weeks=8, today=TODAY)
        self.assertAlmostEqual(profile.shares[0][10], shape_for(0)[10], delta=0.005)

    def test_a_weekday_that_is_always_empty_is_closed_and_gets_no_volume(self):
        days = history()
        for d in [d for d in days if d.weekday() == 6]:
            days[d] = [0.0] * 24
        profile = F.build_profile(days, STEP, today=TODAY)
        self.assertEqual(profile.closed, [6])
        self.assertNotIn(6, profile.thin)
        self.assertEqual(profile.day_shares[6], 0.0)
        week = F.forecast_week(7000, profile)
        self.assertEqual(sum(week[6]), 0)
        self.assertEqual(sum(sum(v) for v in week.values()), 7000)
        with self.assertRaises(ValueError):
            F.forecast_week(7000, profile, day_totals={6: 100})

    def test_a_weekday_left_out_by_the_owner_is_not_called_closed(self):
        days = history()
        sundays = [d for d in days if d.weekday() == 6]
        profile = F.build_profile(days, STEP, today=TODAY, exclude=sundays)
        self.assertNotIn(6, profile.closed)
        self.assertIn(6, profile.thin)

    def test_a_real_looking_noisy_history_still_finds_the_peak(self):
        rng = random.Random(11)
        days = {d: [v * rng.uniform(0.9, 1.1) for v in vals] for d, vals in history().items()}
        profile = F.build_profile(days, STEP, today=TODAY)
        self.assertEqual(max(range(24), key=lambda i: profile.shares[0][i]), 10)
        self.assertEqual(profile.excluded, [])


class TheDistribution(unittest.TestCase):
    def test_it_always_adds_up(self):
        rng = random.Random(7)
        for _ in range(30):
            shares = [rng.random() for _ in range(rng.randint(3, 30))]
            norm = [s / sum(shares) for s in shares]
            total = rng.randint(0, 5000)
            out = F.distribute(total, norm)
            self.assertEqual(sum(out), total)
            self.assertTrue(all(isinstance(v, int) and v >= 0 for v in out))

    def test_a_small_total_goes_to_the_biggest_shares(self):
        self.assertEqual(sorted(F.distribute(3, [0.2] * 5)), [0, 0, 1, 1, 1])
        self.assertEqual(F.distribute(1, [0.1, 0.7, 0.2]), [0, 1, 0])

    def test_zero_and_bad_totals(self):
        self.assertEqual(F.distribute(0, [0.5, 0.5]), [0, 0])
        with self.assertRaises(ValueError):
            F.distribute(-1, [1.0])


class TheWeek(unittest.TestCase):
    def setUp(self):
        self.profile = F.build_profile(history(), STEP, today=TODAY)

    def test_the_total_is_kept_exactly(self):
        week = F.forecast_week(7000, self.profile)
        self.assertEqual(sum(sum(v) for v in week.values()), 7000)
        self.assertEqual(sorted(week), [0, 1, 2, 3, 4, 5, 6])
        self.assertTrue(all(len(v) == 24 for v in week.values()))

    def test_the_days_follow_their_shares(self):
        week = F.forecast_week(7000, self.profile)
        for d in range(7):
            self.assertAlmostEqual(sum(week[d]) / 7000, self.profile.day_shares[d], delta=0.001)

    def test_a_typed_day_total_wins_and_the_rest_share_what_is_left(self):
        week = F.forecast_week(7000, self.profile, day_totals={0: 1500})
        self.assertEqual(sum(week[0]), 1500)
        self.assertEqual(sum(sum(v) for v in week.values()), 7000)

    def test_typed_days_above_the_total_are_refused(self):
        with self.assertRaises(ValueError):
            F.forecast_week(1000, self.profile, day_totals={0: 700, 1: 400})

    def test_every_day_typed_must_equal_the_total(self):
        with self.assertRaises(ValueError):
            F.forecast_week(1000, self.profile, day_totals={d: 100 for d in range(7)})

    def test_a_total_below_the_number_of_open_intervals_still_works(self):
        week = F.forecast_week(5, self.profile)
        self.assertEqual(sum(sum(v) for v in week.values()), 5)


class TheSuggestion(unittest.TestCase):
    def test_a_rising_series_rises_a_little(self):
        got = F.suggest_total([1000, 1010, 1020, 1030, 1040, 1050])
        suggested, low, high = got
        self.assertGreater(suggested, 1035)
        self.assertLess(suggested, 1080)
        self.assertLessEqual(low, suggested)
        self.assertGreaterEqual(high, suggested)

    def test_a_flat_series_stays_flat_with_a_narrow_range(self):
        suggested, low, high = F.suggest_total([1000] * 6)
        self.assertEqual((suggested, low, high), (1000, 1000, 1000))

    def test_a_noisy_series_has_a_wider_range(self):
        _, l1, h1 = F.suggest_total([1000, 1005, 995, 1002, 998, 1001])
        _, l2, h2 = F.suggest_total([1000, 1300, 800, 1200, 900, 1100])
        self.assertGreater(h2 - l2, h1 - l1)

    def test_too_little_history_gives_nothing(self):
        self.assertIsNone(F.suggest_total([1000, 1100]))
        self.assertIsNone(F.suggest_total([]))


class TheOtf(unittest.TestCase):
    def test_offered_over_forecast(self):
        self.assertEqual(F.otf(110, 100), 110.0)
        self.assertEqual(F.otf(0, 100), 0.0)

    def test_no_forecast_has_no_otf(self):
        self.assertIsNone(F.otf(5, 0))
        self.assertIsNone(F.otf(5, -1))

    def test_a_total_is_the_ratio_of_sums_not_the_mean_of_ratios(self):
        self.assertEqual(F.otf_total([10, 0], [5, 5]), 100.0)
        self.assertIsNone(F.otf_total([1, 2], [0, 0]))

    def test_the_bands(self):
        self.assertEqual(F.band(89.9), "under")
        self.assertEqual(F.band(90.0), "on")
        self.assertEqual(F.band(110.0), "on")
        self.assertEqual(F.band(110.1), "over")
        self.assertEqual(F.band(None), "none")
        self.assertEqual(F.band(80.0, low=75.0, high=125.0), "on")


if __name__ == "__main__":
    unittest.main()
