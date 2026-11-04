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


class TheChoiceOfWeeks(unittest.TestCase):
    """Owner, 2026-11-04: "must be the same count of days, so if 6 Sundays there must be 6 Saturdays": whole weeks are chosen, and every weekday is read
    from the same weeks. A week with any problem is left out as a whole and an older clean week takes its place."""

    def choice(self, days, weeks=6, **kw):
        return F.choose_weeks(days, STEP, TODAY, weeks=weeks, **kw)

    def test_every_open_weekday_is_read_from_the_same_weeks(self):
        c = self.choice(history(weeks=10))
        self.assertEqual(len(c.used), 6)
        self.assertEqual(c.used, sorted(c.used))
        self.assertEqual(c.used[-1], TODAY - timedelta(weeks=1))
        self.assertEqual(c.skipped, [])
        self.assertFalse(c.short)

    def test_a_holiday_drops_the_whole_week_and_an_older_week_takes_its_place(self):
        days = history(weeks=10, odd={TODAY - timedelta(weeks=3, days=-1): 0.2})   # a Tuesday at a fifth of the usual
        c = self.choice(days)
        bad = TODAY - timedelta(weeks=3)
        self.assertNotIn(bad, c.used)
        self.assertEqual(len(c.used), 6)
        self.assertIn(TODAY - timedelta(weeks=7), c.used)                        # the next older week stepped in
        self.assertEqual([w for w, _ in c.skipped], [bad.isoformat()])
        self.assertIn("Tue", c.skipped[0][1])

    def test_a_day_with_no_data_drops_its_week(self):
        days = history(weeks=10)
        del days[TODAY - timedelta(weeks=2, days=-2)]                              # a Wednesday is missing
        c = self.choice(days)
        self.assertNotIn(TODAY - timedelta(weeks=2), c.used)
        self.assertIn("Wed", dict(c.skipped)[(TODAY - timedelta(weeks=2)).isoformat()])

    def test_a_week_left_out_by_the_planner_is_left_out_whole(self):
        left = TODAY - timedelta(weeks=1)
        c = self.choice(history(weeks=10), exclude_weeks=[left.isoformat()])
        self.assertNotIn(left, c.used)
        self.assertEqual(dict(c.skipped)[left.isoformat()], "left out by you")
        self.assertEqual(len(c.used), 6)

    def test_a_partial_day_drops_its_week(self):
        days = history(weeks=10)
        day = TODAY - timedelta(weeks=2, days=-2)
        days[day] = [v if i < 11 else 0.0 for i, v in enumerate(days[day])]      # only the first hours of a day came in
        c = self.choice(days)
        self.assertNotIn(TODAY - timedelta(weeks=2), c.used)
        self.assertIn("part", dict(c.skipped)[(TODAY - timedelta(weeks=2)).isoformat()])

    def test_a_week_far_from_the_usual_total_is_left_out(self):
        days = history(weeks=10)
        for d in range(7):
            day = TODAY - timedelta(weeks=4) + timedelta(days=d)
            days[day] = [v * 1.9 for v in days[day]]
        c = self.choice(days)
        self.assertNotIn(TODAY - timedelta(weeks=4), c.used)
        self.assertIn("total", dict(c.skipped)[(TODAY - timedelta(weeks=4)).isoformat()])

    def test_a_weekday_that_is_always_empty_is_closed_not_missing(self):
        days = history(weeks=10)
        for d in [d for d in days if d.weekday() == 6]:
            days[d] = [0.0] * 24
        c = self.choice(days)
        self.assertEqual(c.closed, [6])
        self.assertEqual(c.skipped, [])
        self.assertEqual(len(c.used), 6)

    def test_fewer_clean_weeks_than_wanted_still_works_with_what_there_is(self):
        c = self.choice(history(weeks=4), weeks=6)
        self.assertEqual(len(c.used), 4)
        self.assertTrue(c.short)

    def test_under_three_clean_weeks_is_refused_with_the_reasons(self):
        days = history(weeks=2)
        with self.assertRaises(ValueError) as caught:
            F.build_profile(days, STEP, self.choice(days))
        self.assertIn("3", str(caught.exception))

    def test_no_history_is_refused(self):
        with self.assertRaises(ValueError):
            self.choice({})

    def test_weeks_not_before_the_forecast_week_are_never_used(self):
        days = history(weeks=8)
        later = TODAY + timedelta(weeks=1)
        for d in range(7):
            days[later + timedelta(days=d)] = [1.0] * 24
        c = self.choice(days)
        self.assertTrue(all(w < TODAY for w in c.used))


class TheProfile(unittest.TestCase):
    def profile(self, days, weeks=6, **kw):
        return F.build_profile(days, STEP, F.choose_weeks(days, STEP, TODAY, weeks=weeks, **kw))

    def test_it_finds_the_shape_that_is_there(self):
        p = self.profile(history(weeks=10))
        mon, truth = p.shares[0], shape_for(0)
        for i in OPEN:
            self.assertAlmostEqual(mon[i], truth[i], delta=0.005)
        self.assertAlmostEqual(sum(mon), 1.0, places=9)
        self.assertAlmostEqual(sum(p.day_shares.values()), 1.0, places=9)

    def test_every_open_weekday_stands_on_the_same_number_of_weeks(self):
        p = self.profile(history(weeks=10), weeks=6)
        self.assertEqual(set(p.weeks_used.values()), {6})
        self.assertEqual(len(p.used), 6)

    def test_growth_between_the_weeks_does_not_bias_the_day_mix(self):
        flat = self.profile(history(weeks=10))
        rising = self.profile(history(weeks=10, base=2000, growth=150))
        for d in range(7):
            self.assertAlmostEqual(rising.day_shares[d], flat.day_shares[d], delta=0.02)

    def test_noise_does_not_move_the_peak(self):
        rng = random.Random(11)
        days = {d: [v * rng.uniform(0.9, 1.1) for v in vals] for d, vals in history(weeks=10).items()}
        p = self.profile(days)
        self.assertEqual(max(range(24), key=lambda i: p.shares[0][i]), 10)

    def test_a_closed_weekday_has_no_share_and_no_hours(self):
        days = history(weeks=10)
        for d in [d for d in days if d.weekday() == 6]:
            days[d] = [0.0] * 24
        p = self.profile(days)
        self.assertEqual(p.closed, [6])
        self.assertEqual(p.day_shares[6], 0.0)
        self.assertEqual(sum(p.shares[6]), 0.0)
        week = F.forecast_week(7000, p)
        self.assertEqual(sum(week[6]), 0)
        self.assertEqual(sum(sum(v) for v in week.values()), 7000)
        with self.assertRaises(ValueError):
            F.forecast_week(7000, p, day_totals={6: 100})

    def test_the_weeks_used_and_skipped_are_kept_for_the_page(self):
        days = history(weeks=10, odd={TODAY - timedelta(weeks=3, days=-1): 0.2})
        p = self.profile(days)
        self.assertEqual(len(p.used), 6)
        self.assertEqual(len(p.skipped), 1)


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
        days = history(weeks=10)
        self.profile = F.build_profile(days, STEP, F.choose_weeks(days, STEP, TODAY))

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
        pts = [(-6 + i, 1000 + 10 * i) for i in range(6)]                       # six weeks ending last week
        suggested, low, high = F.suggest_total(pts)
        self.assertAlmostEqual(suggested, 1055, delta=1)                         # the line's end (1050) plus half a week's slope
        self.assertLessEqual(low, suggested)
        self.assertGreaterEqual(high, suggested)

    def test_a_flat_series_stays_flat_with_a_narrow_range(self):
        self.assertEqual(F.suggest_total([(-i, 1000) for i in range(1, 7)]), (1000, 1000, 1000))

    def test_a_noisy_series_has_a_wider_range(self):
        _, l1, h1 = F.suggest_total(list(zip(range(-6, 0), [1000, 1005, 995, 1002, 998, 1001])))
        _, l2, h2 = F.suggest_total(list(zip(range(-6, 0), [1000, 1300, 800, 1200, 900, 1100])))
        self.assertGreater(h2 - l2, h1 - l1)

    def test_a_skipped_week_leaves_a_gap_the_line_respects(self):
        # growth of 10 a week with week -3 left out: the slope is still 10, not the 12.5 a naive index would give
        pts = [(-6, 1000), (-5, 1010), (-4, 1020), (-2, 1040), (-1, 1050)]
        suggested, _, _ = F.suggest_total(pts)
        self.assertAlmostEqual(suggested, 1055, delta=1)

    def test_planning_further_ahead_adds_more_of_the_trend_but_never_all_of_it(self):
        pts = [(-9 + i, 1000 + 10 * i) for i in range(6)]                        # last point three weeks before the forecast week
        near = F.suggest_total([(x + 3, y) for x, y in pts])[0]                  # last point one week before
        far = F.suggest_total(pts)[0]
        self.assertGreater(far, near)
        self.assertLess(far, 1050 + 3 * 10)

    def test_too_little_history_gives_nothing(self):
        self.assertIsNone(F.suggest_total([(-1, 1000), (-2, 1100)]))
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
