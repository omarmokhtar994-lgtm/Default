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

import html
import io

from openpyxl import load_workbook

from webapp import outlook as O
from webapp.programs import ProgramBook
from webapp.tests.test_bi_volumes import KEY, SUN, book, weights
from webapp.tests.test_bi_volumes_routes import PASSWORD, TODAY, _Volumes
from webapp.tests.test_runs import sign_in, token

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


def long_history(store, weeks, base=7000.0, slope=0.0, season=lambda w: 1.0, channel="Phone", aht=300.0, key=KEY, last=SUN, skip=()):
    """``weeks`` whole weeks ending the Saturday before ``last`` (a Sunday): week k (0 = oldest) totals (base + slope k) times the season of its week of
    the year, spread over the weekdays and hours by the shape the other volume tests use."""
    rows = []
    for k in range(weeks):
        sunday = last - timedelta(weeks=weeks - k)
        if k in skip:
            continue
        total = (base + slope * k) * season(O.woy(sunday))
        for off in range(7):
            day = sunday + timedelta(days=off)
            wts = weights(day.weekday())
            day_total = total / 7 * (1.3 if day.weekday() in (6, 0) else 1.0) / (1 + 0.6 / 7)
            s = sum(wts.values())
            rows += [(day.isoformat(), h * 60, round(day_total * v / s), aht) for h, v in wts.items()]
    store.replace_volume_rows(key, channel, rows, 1)


def event(**kw):
    return {"kind": "Promotion", "name": "Big sale", "channels": ["Phone"], "start": "2027-03-01", "end": "2027-03-10", "change": 25, **kw}


class TheOutlookInTheBook(unittest.TestCase):
    NEXT = SUN + timedelta(weeks=1)

    def setUp(self):
        self.store, self.vb = book()

    def outlook(self, months=6, **kw):
        return self.vb.outlook(KEY, "Phone", start=self.NEXT, months=months, **kw)

    def test_a_year_of_months_each_with_a_range_and_a_basis(self):
        long_history(self.store, 60, season=yearly)
        got = self.outlook(12)
        self.assertEqual([m["month"] for m in got["months"]][:2] + [got["months"][-1]["month"]], ["2026-11", "2026-12", "2027-10"])   # 12 calendar months, the first partial
        self.assertTrue(got["months"][0]["partial"])
        self.assertFalse(got["months"][-1]["partial"])
        self.assertTrue(all(m["low"] < m["expected"] < m["high"] for m in got["months"]))
        self.assertEqual({m["bases"].get("learned", 0) > 0 for m in got["months"]}, {True})
        self.assertEqual(got["total"]["expected"], sum(m["expected"] for m in got["months"]))
        self.assertEqual(got["model"]["kind"], "seasonal")

    def test_the_levels_add_up_months_weeks_days(self):
        long_history(self.store, 60)
        got = self.outlook(3)
        days = [d for w in got["weeks"] for d in w["days"] if got["start"] <= d["date"] <= got["end"]]
        self.assertAlmostEqual(sum(d["expected"] for d in days), got["total"]["expected"], delta=len(days))
        self.assertAlmostEqual(sum(m["expected"] for m in got["months"]), got["total"]["expected"], delta=len(got["months"]))
        for w in got["weeks"]:
            self.assertAlmostEqual(sum(d["expected"] for d in w["days"]), w["expected"], delta=7)

    def test_a_flat_history_gives_the_weeks_total_spread_by_weekday(self):
        long_history(self.store, 60)
        got = self.outlook(2)
        self.assertAlmostEqual(got["weeks"][2]["expected"], 7000, delta=300)

    def test_a_promotion_lifts_only_its_days(self):
        long_history(self.store, 60)
        plain = self.outlook(6)
        self.vb.add_driver(KEY, "events", event(), 1)
        lifted = self.outlook(6)
        march = lambda g: next(m for m in g["months"] if m["month"] == "2027-03")  # noqa: E731
        gain = march(lifted)["expected"] - march(plain)["expected"]
        self.assertGreater(gain, 0)
        self.assertEqual(next(m for m in lifted["months"] if m["month"] == "2027-02")["expected"], next(m for m in plain["months"] if m["month"] == "2027-02")["expected"])
        day = next(d for w in lifted["weeks"] for d in w["days"] if d["date"] == "2027-03-02")
        self.assertAlmostEqual(day["factor"], 1.25)
        self.assertIn("Big sale", day["events"])

    def test_a_typed_year_over_year_rate_replaces_the_measured_trend(self):
        long_history(self.store, 60)
        flat = self.outlook(12)
        self.vb.set_growth(KEY, {"Phone": "20", "Chat": "", "Email": ""}, "growth", 1)
        grown = self.outlook(12)
        self.assertGreater(grown["months"][-1]["expected"] / flat["months"][-1]["expected"], 1.12)
        self.assertLess(grown["months"][1]["expected"] / flat["months"][1]["expected"], 1.08)

    def test_eleven_months_say_what_they_have_not_seen(self):
        long_history(self.store, 48, season=yearly)
        got = self.outlook(12)
        self.assertEqual(got["model"]["kind"], "partial")
        self.assertTrue([m for m in got["months"] if m["bases"].get("unseen", 0)])
        self.assertTrue([n for n in got["notes"] if "seasonal pattern" in n], got["notes"])

    def test_a_typed_index_fills_a_month_the_history_lacks(self):
        long_history(self.store, 48, season=yearly)
        before = self.outlook(12)
        gap = next(m["month"] for m in before["months"] if m["bases"].get("unseen", 0) == m["weeks"])
        self.vb.set_outlook_index(KEY, "Phone", {int(gap[5:]): "130"}, 1)
        after = self.outlook(12)
        one = lambda g: next(m for m in g["months"] if m["month"] == gap)  # noqa: E731
        self.assertGreater(one(after)["bases"].get("typed", 0), 0)
        self.assertAlmostEqual(one(after)["expected"] / one(before)["expected"], 1.3, delta=0.05)

    def test_under_26_weeks_stop_at_8_weeks_and_say_how_much_history_is_needed(self):
        long_history(self.store, 20)
        got = self.outlook(6)
        self.assertEqual(got["model"]["kind"], "trend")
        self.assertLessEqual(len(got["weeks"]), 9)
        self.assertTrue([n for n in got["notes"] if "26 weeks" in n], got["notes"])

    def test_too_little_history_is_refused_in_words(self):
        long_history(self.store, 2)
        with self.assertRaises(ValueError) as caught:
            self.outlook(3)
        self.assertIn("3", str(caught.exception))
        _, empty = book()
        with self.assertRaises(ValueError):
            empty.outlook(KEY, "Phone", start=self.NEXT, months=3)

    def test_a_holiday_week_in_the_past_does_not_bend_the_line(self):
        long_history(self.store, 60, skip=())
        base = self.outlook(3)["weeks"][2]["expected"]
        # a week of very low volume, marked as a holiday: left out, so the forecast stays where it was
        long_history(self.store, 60, last=SUN)
        quiet = SUN - timedelta(weeks=5)
        rows = [(r["day"], r["minute"], r["offered"] * (0.3 if quiet.isoformat() <= r["day"] < (quiet + timedelta(days=7)).isoformat() else 1.0), 300.0)
                for r in self.store.volume_rows(KEY, "Phone", (SUN - timedelta(weeks=60)).isoformat(), (SUN - timedelta(days=1)).isoformat())]
        self.store.replace_volume_rows(KEY, "Phone", [(d, m, round(o), a) for d, m, o, a in rows], 1)
        hol = {"kind": "Holiday", "name": "Long holiday", "channels": ["Phone"], "start": quiet.isoformat(), "end": (quiet + timedelta(days=6)).isoformat(), "change": -70}
        self.vb.add_driver(KEY, "events", hol, 1)
        self.assertAlmostEqual(self.outlook(3)["weeks"][2]["expected"], base, delta=base * 0.04)

    def test_each_site_gets_its_share_and_they_add_up(self):
        long_history(self.store, 60)
        doc = {"sites": [{"name": "Internal", "lob": ""}, {"name": "Sutherland", "lob": ""}],
               "rules": [{"channel": "Phone", "days": list(range(7)), "from": 0, "to": 1440, "shares": {"Internal": 60, "Sutherland": 40}}]}
        self.vb.set_sites(KEY, doc, 1)
        whole, a, b = self.outlook(3), self.outlook(3, site="Internal"), self.outlook(3, site="Sutherland")
        self.assertAlmostEqual(a["total"]["expected"] / whole["total"]["expected"], 0.6, delta=0.01)
        self.assertAlmostEqual(a["total"]["expected"] + b["total"]["expected"], whole["total"]["expected"], delta=3)
        with self.assertRaises(ValueError):
            self.outlook(3, site="Nowhere")

    def test_the_months_asked_for_are_one_to_twenty_four(self):
        long_history(self.store, 60)
        for bad in (0, 25, -1):
            with self.assertRaises(ValueError):
                self.outlook(bad)


class TheOutlookOnThePage(_Volumes):
    THIS_SUNDAY = TODAY - timedelta(days=(TODAY.weekday() + 1) % 7)

    def setUp(self):
        self.store.set_volume_settings(self.alpha, {}, 1)
        self.store.set_volume_drivers(self.alpha, {}, 1)
        long_history(self.store, 60, key=self.alpha, last=self.THIS_SUNDAY)

    def tearDown(self):
        self.store.set_volume_settings(self.alpha, {}, 1)
        self.store.set_volume_drivers(self.alpha, {}, 1)

    def get(self, client=None, **q):
        client = client or sign_in(self.app, "plan_a", PASSWORD)
        return html.unescape(client.get("/volumes", query_string={"program": self.alpha, "tab": "outlook", "channel": "Phone", **q}).get_data(as_text=True))

    def test_the_year_level_lists_the_months_with_a_range_and_a_basis(self):
        page = self.get(months="6")
        self.assertIn("Expected", page)
        self.assertRegex(page, r"(Nov|Dec|Jan|Feb|Mar|Apr|May)\s+20\d\d")
        self.assertIn("learned from the history", page)

    def test_the_week_level_opens_a_week_in_the_forecast_with_its_total(self):
        page = self.get(level="week", months="2")
        self.assertRegex(page, r'href="/volumes\?[^"]*tab=forecast[^"]*total=\d+')

    def test_the_day_level_shows_the_days_events_and_all(self):
        week = (self.THIS_SUNDAY + timedelta(weeks=3)).isoformat()
        self.vb.add_driver(self.alpha, "events", {"kind": "Holiday", "name": "Founders day", "channels": ["Phone"], "start": week, "end": week,
                                                  "change": -30}, 1)
        page = self.get(level="day", owk=week, months="3")
        self.assertIn("Founders day", page)
        self.assertIn("-30%", page)

    def test_a_short_history_says_how_much_is_needed(self):
        self.store.delete_volume_days(self.alpha, "Phone", "2015-01-01", "2099-12-31")
        long_history(self.store, 20, key=self.alpha, last=self.THIS_SUNDAY)
        self.assertIn("26 weeks", self.get(months="6"))

    def test_a_site_is_picked_and_says_it_is_its_share(self):
        doc = {"sites": [{"name": "Internal", "lob": ""}, {"name": "Sutherland", "lob": ""}],
               "rules": [{"channel": "Phone", "days": list(range(7)), "from": 0, "to": 1440, "shares": {"Internal": 60, "Sutherland": 40}}]}
        self.vb.set_sites(self.alpha, doc, 1)
        try:
            self.assertIn("Sutherland", self.get())
            self.assertIn("Internal's share", self.get(site="Internal"))
        finally:
            self.vb.set_sites(self.alpha, {"sites": [], "rules": []}, 1)

    def test_a_bad_request_is_a_word_not_a_crash(self):
        for q in ({"months": "abc"}, {"months": "99"}, {"months": "0"}, {"level": "x"}, {"owk": "not-a-date"}, {"channel": "Fax"}, {"site": "Nowhere"}):
            with self.subTest(q=q):
                client = sign_in(self.app, "plan_a", PASSWORD)
                self.assertEqual(client.get("/volumes", query_string={"program": self.alpha, "tab": "outlook", **q}).status_code, 200)
        self.assertIn("1 to 24", self.get(months="99"))

    def test_the_index_for_a_month_is_typed_saved_and_a_bad_one_saves_nothing(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.post("/volumes/outlook-index", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "idx.12": "130", "idx.1": ""},
                          follow_redirects=True)
        self.assertEqual(self.vb.outlook_index(self.alpha, "Phone"), {12: 130.0})
        bad = client.post("/volumes/outlook-index", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "idx.2": "5", "idx.12": "200"},
                          follow_redirects=True)
        self.assertIn("February", html.unescape(bad.get_data(as_text=True)))
        self.assertEqual(self.vb.outlook_index(self.alpha, "Phone"), {12: 130.0})

    def test_a_team_manager_looks_but_cannot_change_and_the_token_is_needed(self):
        tm = sign_in(self.app, "tm_a", PASSWORD)
        self.assertEqual(tm.get("/volumes", query_string={"program": self.alpha, "tab": "outlook"}).status_code, 200)
        self.assertEqual(tm.post("/volumes/outlook-index", data={"program": self.alpha, "csrf_token": token(tm), "channel": "Phone", "idx.1": "120"}).status_code, 403)
        planner = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(planner.post("/volumes/outlook-index", data={"program": self.alpha, "channel": "Phone", "idx.1": "120"}).status_code, 400)

    def test_the_download_has_the_three_levels_and_they_agree(self):
        got = sign_in(self.app, "plan_a", PASSWORD).get("/volumes/outlook.xlsx", query_string={"program": self.alpha, "channel": "Phone", "months": "3"})
        self.assertEqual(got.status_code, 200)
        wb = load_workbook(io.BytesIO(got.get_data()))
        self.assertEqual(wb.sheetnames, ["Months", "Weeks", "Days"])
        def total(name, col):
            ws = wb[name]
            return sum(r[col] for r in ws.iter_rows(min_row=2, values_only=True) if isinstance(r[col], (int, float)))
        months, weeks = total("Months", 2), total("Weeks", 2)
        self.assertGreater(months, 0)
        self.assertAlmostEqual(months, weeks, delta=weeks * 0.12)    # the first and last weeks are cut by the month ends

    def test_the_tab_is_in_the_menu_of_the_volumes_pages(self):
        self.assertIn('tab=outlook', html.unescape(sign_in(self.app, "plan_a", PASSWORD).get("/volumes", query_string={"program": self.alpha, "tab": "settings"}).get_data(as_text=True)))


if __name__ == "__main__":
    unittest.main()
