# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM, task 4 (owner, 2026-11-10: "super advanced and super best forecasting tool but still simple").

The suggested week total is worked out by several methods; each is scored on the program's own past (every one of the last eight clean weeks is
predicted from the weeks before it only) and the one with the lowest error gives the suggestion, with its accuracy on the page. With fewer than eight
clean weeks, or the year-over-year method chosen, everything is as it was. The total stays the planner's. Made-up data."""
import unittest
from datetime import timedelta

from webapp import forecast as F, forecast_methods as M
from webapp.tests.test_bi_volumes import KEY, SUN, book, history
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_runs import sign_in


def weeks(totals, end=SUN):
    """Totals oldest first as (week start, total), the last one the week before ``end``."""
    n = len(totals)
    return [(end - timedelta(weeks=n - i), float(t)) for i, t in enumerate(totals)]


class TheMethods(unittest.TestCase):
    def test_the_trend_is_the_one_the_site_always_used(self):
        s = weeks([1000, 1040, 1080, 1120, 1160, 1200])
        points = [(-(6 - i), t) for i, (_, t) in enumerate(s)]
        self.assertEqual(M.predict("trend", s, SUN), F.suggest_total(points)[0])

    def test_recent_weighs_the_newest_weeks_most(self):
        self.assertAlmostEqual(M.predict("recent", weeks([900, 1000, 1000, 1000, 2000]), SUN), (1000 * 1 + 1000 * 2 + 1000 * 3 + 2000 * 4) / 10)

    def test_last_week_is_last_week(self):
        self.assertEqual(M.predict("last_week", weeks([5, 6, 7]), SUN), 7)

    def test_seasonal_is_last_year_grown_by_the_recent_ratio(self):
        totals = [1000.0] * 60
        totals[60 - 52] = 3000.0                                    # the same week a year before the target was a peak
        for i in range(56, 60):
            totals[i] = 1100.0                                      # the last four weeks run 10 % over the same four a year before
        self.assertAlmostEqual(M.predict("seasonal", weeks(totals), SUN), 3000 * 1.1)
        self.assertIsNone(M.predict("seasonal", weeks([1000] * 30), SUN))

    def test_the_blend_is_the_middle_of_the_others(self):
        s = weeks([1000, 1000, 1000, 1000, 1000, 1600])
        others = sorted(M.predict(n, s, SUN) for n in ("trend", "recent", "last_week"))
        self.assertEqual(M.predict("blend", s, SUN), others[1])

    def test_nothing_reads_the_target_week_or_later(self):
        s = weeks([1000] * 10)
        target = s[6][0]
        poisoned = s[:6] + [(d, 10 ** 9) for d, _ in s[6:]]
        for name in M.METHODS:
            self.assertEqual(M.predict(name, poisoned, target), M.predict(name, s[:6], target), name)

    def test_too_little_history_has_no_answer(self):
        one = weeks([1000])
        for name in ("trend", "recent", "seasonal", "blend"):
            self.assertIsNone(M.predict(name, one, SUN), name)
        self.assertEqual(M.predict("last_week", one, SUN), 1000)
        for name in M.METHODS:
            self.assertIsNone(M.predict(name, [], SUN), name)
        with self.assertRaises(ValueError):
            M.predict("magic", one, SUN)


class TheUnusualWeeks(unittest.TestCase):
    def test_a_doubled_week_is_marked_and_says_why(self):
        s = weeks([1000, 1010, 990, 1005, 2100, 1000, 995, 1010, 1002, 998])
        got = M.unusual(s)
        self.assertEqual(list(got), [s[4][0]])
        self.assertIn("2,100", got[s[4][0]])

    def test_a_steady_rise_marks_nothing(self):
        self.assertEqual(M.unusual(weeks([1000 + 40 * i for i in range(12)])), {})

    def test_a_flat_history_marks_nothing_even_with_no_spread(self):
        self.assertEqual(M.unusual(weeks([1000] * 10)), {})


class TheBackTest(unittest.TestCase):
    def test_a_rising_history_does_not_pick_last_week(self):
        got = M.backtest(weeks([1000 + 50 * i for i in range(16)]), SUN)
        self.assertEqual(got["tested"], 8)
        self.assertEqual(got["best"], "trend")
        self.assertLess(got["methods"]["trend"]["wape"], got["methods"]["last_week"]["wape"])
        self.assertLess(got["methods"]["last_week"]["bias"], 0)       # it always comes in under a rising line

    def test_a_flat_history_ties_and_the_first_method_wins(self):
        got = M.backtest(weeks([1000] * 12), SUN)
        self.assertEqual(got["best"], "trend")
        self.assertEqual(got["methods"]["trend"]["wape"], 0.0)
        self.assertEqual(got["range"], 0.0)

    def test_fewer_than_four_tested_weeks_picks_nothing(self):
        got = M.backtest(weeks([1000] * 7), SUN)
        self.assertEqual(got["tested"], 3)
        self.assertIsNone(got["best"])

    def test_weeks_of_zero_do_not_divide(self):
        got = M.backtest(weeks([0] * 12), SUN)
        self.assertIsNone(got["best"])
        self.assertEqual(got["tested"], 8)

    def test_one_enormous_week_does_not_choose_the_method(self):
        base = [1000 + 50 * i for i in range(16)]
        spiked = list(base)
        spiked[10] = 50000
        clean = [w for w in weeks(spiked) if w[0] not in M.unusual(weeks(spiked))]
        self.assertEqual(M.backtest(clean, SUN)["best"], M.backtest(weeks(base), SUN)["best"])


class TheSuggestion(unittest.TestCase):
    def test_with_eight_flat_weeks_the_suggestion_is_what_it_was_and_says_how_good_it_is(self):
        store, vb = book()
        history(store, weeks=8)
        f = vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(f["suggestion"]["method"], "trend")
        acc = f["accuracy"]
        self.assertEqual(acc["tested"], 4)
        self.assertEqual(acc["used"], "trend")
        self.assertIn("trend", acc["methods"])

    def test_with_six_weeks_there_is_no_back_test_and_the_trend_stands(self):
        store, vb = book()
        history(store, weeks=6)
        f = vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(f["suggestion"]["method"], "trend")
        self.assertIsNone(f["accuracy"]["best"])

    def test_the_year_over_year_method_is_left_alone(self):
        store, vb = book()
        history(store, weeks=10)
        vb.set_growth(KEY, {"Phone": 10}, "growth", 1)
        f = vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(f["suggestion"]["method"], "growth")
        self.assertEqual(f["accuracy"]["used"], "growth")

    def test_the_total_is_still_the_planners(self):
        store, vb = book()
        history(store, weeks=12)
        f = vb.forecast(KEY, "Phone", SUN)
        self.assertTrue(f["needs_total"])
        self.assertEqual(f["calls"], [])


class ThePage(_Volumes):
    def test_the_table_of_methods_is_on_the_forecast_with_a_number_to_take(self):
        self.history(self.alpha, weeks=12)
        page = sign_in(self.app, "plan_a", PASSWORD).get("/volumes", query_string={"program": self.alpha, "tab": "forecast"}).get_data(as_text=True)
        self.assertIn("How well each method did on your own weeks", page)
        self.assertIn("Use this number", page)
        self.assertIn("The suggestion above stays the trend", page)
        self.assertNotIn("onclick", page)

    def test_with_little_history_the_table_is_not_shown(self):
        self.history(self.bravo, weeks=4)
        page = sign_in(self.app, "plan_b", PASSWORD).get("/volumes", query_string={"program": self.bravo, "tab": "forecast"}).get_data(as_text=True)
        self.assertNotIn("How well each method did", page)


if __name__ == "__main__":
    unittest.main()
