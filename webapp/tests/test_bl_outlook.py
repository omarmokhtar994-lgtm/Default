# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 7 (owner, 2026-11-07): "based on historical trends I need an actual estimated forecast for the upcoming months, and I can add
YoY customer increase, promotions with durations, holidays; ... some programs might have 10 to 11 months"; the forecast "needs to be year,
week and day levels".

The model is the weekly total's trend (a robust line, its growth held to 50 percent a year) times a seasonal index per week of the year that
the history has seen. What the history has not seen is said so, never presented as learned:
  52 weeks or more: every week of the year the history covers is learned (a band of 10 percent each side);
  26 to 51 weeks: the weeks of the year it covers are learned; the rest are the trend alone, marked "no seasonal pattern yet" (20 percent);
  under 26 weeks: the trend alone, at most 8 weeks ahead (15 percent); fewer than 3 whole weeks cannot be forecast.
The planner's year-over-year rate, when chosen, replaces the measured trend; a seasonal index typed for a month the history lacks is used and
marked "typed". Made-up series with known answers."""
import math
import unittest
from datetime import date, timedelta

from webapp import outlook as O

FIRST = date(2025, 1, 5)    # a Sunday


def series(weeks, base=1000.0, slope=0.0, season=lambda w: 1.0, start=FIRST, skip=()):
    """(week start, total) for ``weeks`` whole weeks: base + slope per week, times a seasonal shape of the week of the year."""
    out = []
    for k in range(weeks):
        d = start + timedelta(weeks=k)
        if k in skip:
            continue
        out.append((d, (base + slope * k) * season(O.woy(d))))
    return out


def yearly(w):          # a peak in the autumn weeks and a dip in the early weeks
    return 1.0 + 0.3 * math.sin(2 * math.pi * (w - 30) / 52.0)


class TheWeekOfTheYear(unittest.TestCase):
    def test_a_week_is_one_of_52_and_the_last_days_join_the_last_week(self):
        self.assertEqual(O.woy(date(2026, 1, 1)), 0)
        self.assertEqual(O.woy(date(2026, 1, 7)), 0)
        self.assertEqual(O.woy(date(2026, 1, 8)), 1)
        self.assertEqual(O.woy(date(2026, 12, 31)), 51)
        self.assertEqual(O.woy(date(2024, 12, 31)), 51)   # a leap year's 366th day too


class TheFit(unittest.TestCase):
    def test_fewer_than_three_whole_weeks_cannot_be_forecast(self):
        with self.assertRaises(ValueError) as caught:
            O.fit(series(2))
        self.assertIn("3", str(caught.exception))

    def test_the_kind_follows_the_weeks_of_history(self):
        self.assertEqual(O.fit(series(60)).kind, "seasonal")
        self.assertEqual(O.fit(series(52)).kind, "seasonal")
        self.assertEqual(O.fit(series(51)).kind, "partial")
        self.assertEqual(O.fit(series(26)).kind, "partial")
        self.assertEqual(O.fit(series(25)).kind, "trend")
        self.assertEqual(O.fit(series(3)).kind, "trend")

    def test_weeks_left_out_do_not_count_or_bend_the_line(self):
        data = series(60)
        data[10] = (data[10][0], 5000.0)               # a week that was far off
        clean = O.fit(data, left_out=[data[10][0]])
        self.assertEqual(clean.weeks, 59)
        self.assertAlmostEqual(O.project(clean, data[-1][0] + timedelta(weeks=1))["expected"], 1000.0, delta=15)


class TheProjection(unittest.TestCase):
    def week(self, model, weeks_ahead, **kw):
        return O.project(model, model.last + timedelta(weeks=weeks_ahead), **kw)

    def test_a_flat_history_forecasts_flat_with_a_learned_band(self):
        model = O.fit(series(60))
        got = self.week(model, 10)
        self.assertAlmostEqual(got["expected"], 1000.0, delta=10)
        self.assertEqual(got["basis"], "learned")
        self.assertAlmostEqual(got["low"], got["expected"] * 0.9, delta=1)
        self.assertAlmostEqual(got["high"], got["expected"] * 1.1, delta=1)

    def test_a_yearly_peak_comes_back_next_year(self):
        model = O.fit(series(104, season=yearly))
        for ahead in (1, 12, 26, 40):
            when = model.last + timedelta(weeks=ahead)
            want = 1000.0 * yearly(O.woy(when))
            got = O.project(model, when)
            self.assertAlmostEqual(got["expected"] / want, 1.0, delta=0.06, msg=ahead)
            self.assertEqual(got["basis"], "learned")

    def test_growth_and_a_season_together_are_told_apart(self):
        model = O.fit(series(110, base=1000, slope=3, season=yearly))
        for ahead in (4, 15, 30, 45):
            when = model.last + timedelta(weeks=ahead)
            want = (1000 + 3 * (109 + ahead)) * yearly(O.woy(when))
            self.assertAlmostEqual(O.project(model, when)["expected"] / want, 1.0, delta=0.08, msg=ahead)

    def test_growth_goes_on_at_the_measured_rate(self):
        model = O.fit(series(60, base=1000, slope=5))
        got = self.week(model, 20)
        self.assertAlmostEqual(got["expected"], 1000 + 5 * (59 + 20), delta=40)

    def test_growth_is_held_to_half_again_a_year(self):
        model = O.fit(series(70, base=1000, slope=100))   # +5 times a year at the measured rate
        top = self.week(model, 52)["expected"]
        now = self.week(model, 0)["expected"]
        self.assertLessEqual(top, now * 1.5 * 1.001)

    def test_a_typed_year_over_year_rate_replaces_the_measured_trend(self):
        model = O.fit(series(60, base=1000, slope=5))
        flat = self.week(model, 52, yoy=0.0)["expected"]
        up = self.week(model, 52, yoy=20.0)["expected"]
        self.assertAlmostEqual(up / flat, 1.2, delta=0.01)
        self.assertAlmostEqual(flat, model.level, delta=model.level * 0.02)

    def test_eleven_months_learn_what_they_cover_and_say_so_for_the_rest(self):
        model = O.fit(series(48, season=yearly))          # 48 weeks from early January: weeks 0 to 47 of the year
        covered = O.project(model, FIRST + timedelta(weeks=20))
        unseen = O.project(model, FIRST + timedelta(weeks=50))
        self.assertEqual((covered["basis"], unseen["basis"]), ("learned", "unseen"))
        self.assertAlmostEqual(unseen["low"] / unseen["expected"], 0.8, delta=0.001)
        self.assertAlmostEqual(unseen["high"] / unseen["expected"], 1.2, delta=0.001)
        again = O.project(model, FIRST + timedelta(weeks=52))      # the first week of the next year is the first week of this one
        self.assertEqual(again["basis"], "learned")
        self.assertAlmostEqual(again["index"], O.project(model, FIRST)["index"])

    def test_a_typed_index_fills_a_month_the_history_lacks_and_is_marked_typed(self):
        model = O.fit(series(48, season=yearly))
        when = FIRST + timedelta(weeks=50)                # mid December
        plain = O.project(model, when)
        typed = O.project(model, when, typed={when.month: 130.0})
        self.assertEqual(typed["basis"], "typed")
        self.assertAlmostEqual(typed["expected"] / plain["expected"], 1.3, delta=0.001)
        learned = O.project(model, FIRST + timedelta(weeks=20), typed={(FIRST + timedelta(weeks=20)).month: 300.0})
        self.assertEqual(learned["basis"], "learned")     # what the history has seen is never overridden

    def test_under_26_weeks_the_trend_alone_reaches_8_weeks(self):
        model = O.fit(series(20, base=1000, slope=2))
        near = O.project(model, model.last + timedelta(weeks=8))
        self.assertEqual(near["basis"], "trend")
        self.assertAlmostEqual(near["low"] / near["expected"], 0.85, delta=0.001)
        self.assertIsNone(O.project(model, model.last + timedelta(weeks=9)))

    def test_a_projection_is_never_negative(self):
        model = O.fit(series(60, base=1000, slope=-15))
        self.assertGreaterEqual(self.week(model, 100)["expected"], 0.0)


if __name__ == "__main__":
    unittest.main()
