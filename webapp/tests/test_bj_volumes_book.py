# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04): the volume book with the same N whole weeks for every weekday, a saved forecast that keeps its own grid, and the drivers
(promotions and events, AI and automation, year-over-year growth, last year) in the suggestion. Made-up numbers; weeks start on Sunday here."""
import unittest
from datetime import date, timedelta

from webapp import drivers as D, forecast as F
from webapp.tests.test_bi_volumes import KEY, STEP, SUN, book, history, weights

TUE, THU = date(2026, 11, 10), date(2026, 11, 12)
SAT = SUN + timedelta(days=6)
UNITS = 1.3 + 1.3 + 5.0            # Sun and Mon carry 1.3 units, the five other days 1.0: see history() in test_bi_volumes
SHARE_TUE_TO_THU = 3 / (UNITS)     # 3 units of 7.6


def scaled(store, scale, weeks=12, per_week=7000, channel="Phone", aht=300.0, key=KEY):
    """Like history(), with week w (1 = the week before SUN) scaled by scale.get(w, 1.0)."""
    rows = []
    for w in range(1, weeks + 1):
        sunday = SUN - timedelta(weeks=w)
        for k in range(7):
            day = sunday + timedelta(days=k)
            wts = weights(day.weekday())
            total = per_week * scale.get(w, 1.0) / 7 * (1.3 if day.weekday() in (6, 0) else 1.0)
            s = sum(wts.values())
            for h, v in wts.items():
                rows.append((day.isoformat(), h * 60, round(total * v / s), aht))
    store.replace_volume_rows(key, channel, rows, 1)


def event(**kw):
    return {"kind": "Promotion", "name": "Black Friday", "channels": ["Phone"], "start": TUE.isoformat(), "end": THU.isoformat(), "change": 25, **kw}


def ai(**kw):
    return {"channel": "Chat", "start": SUN.isoformat(), "end": SAT.isoformat(), "change": -10, **kw}


class TheWeeksOfHistory(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})

    def test_six_weeks_by_default_and_they_are_the_newest(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual(f["weeks"]["wanted"], 6)
        self.assertEqual(f["weeks"]["used"], [(SUN - timedelta(weeks=k)).isoformat() for k in range(6, 0, -1)])

    def test_every_open_weekday_is_read_from_the_same_weeks(self):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual(set(f["profile"]["weeks_used"].values()), {6})          # six Sundays means six Saturdays
        self.assertEqual(len(f["profile"]["weeks_used"]), 7)

    def test_the_number_of_weeks_is_adjustable_by_the_call_and_by_the_setting(self):
        self.assertEqual(len(self.vb.forecast(KEY, "Phone", SUN, total=8000, weeks=4)["weeks"]["used"]), 4)
        self.vb.set_settings(KEY, {"Phone": {"forecast_weeks": 8}}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual((f["weeks"]["wanted"], len(f["weeks"]["used"]), set(f["profile"]["weeks_used"].values())), (8, 8, {8}))
        for bad in (2, 27, 0, -4):
            with self.assertRaises(ValueError, msg=bad):
                self.vb.forecast(KEY, "Phone", SUN, total=8000, weeks=bad)

    def test_a_week_left_out_is_replaced_by_an_older_clean_week(self):
        out = (SUN - timedelta(weeks=2)).isoformat()
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000, skip_weeks=[out])
        self.assertNotIn(out, f["weeks"]["used"])
        self.assertEqual(len(f["weeks"]["used"]), 6)
        self.assertIn((SUN - timedelta(weeks=7)).isoformat(), f["weeks"]["used"])
        self.assertIn([out, "left out by you"], f["weeks"]["skipped"])
        self.assertEqual(set(f["profile"]["weeks_used"].values()), {6})

    def test_a_holiday_week_is_left_out_as_a_whole_with_its_reason(self):
        scaled(self.store, {3: 0.3})
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        week = (SUN - timedelta(weeks=3)).isoformat()
        self.assertNotIn(week, f["weeks"]["used"])
        self.assertEqual(len(f["weeks"]["used"]), 6)
        self.assertIn(week, [w for w, _ in f["weeks"]["skipped"]])

    def test_the_stored_left_out_weeks_apply_until_the_call_says_otherwise(self):
        out = (SUN - timedelta(weeks=1)).isoformat()
        self.vb.set_skip_weeks(KEY, [out], 1)
        self.assertNotIn(out, self.vb.forecast(KEY, "Phone", SUN, total=8000)["weeks"]["used"])
        self.assertIn(out, self.vb.forecast(KEY, "Phone", SUN, total=8000, skip_weeks=[])["weeks"]["used"])

    def test_too_little_history_is_said_in_words_and_gives_no_calls(self):
        store, vb = book()
        history(store, weeks=2)
        f = vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertIn("clean week", f["error"])
        self.assertEqual(f["calls"], [])


class TheSavedForecast(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})

    def test_the_saved_forecast_keeps_its_grid_when_history_changes(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        before = self.vb.forecast(KEY, "Phone", SUN)
        scaled(self.store, {}, per_week=14000)
        after = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual((after["source"], after["total"]), ("saved", 8000))
        self.assertEqual(after["calls"], before["calls"])
        self.assertEqual(sum(sum(d) for d in after["calls"]), 8000)

    def test_the_saved_forecast_survives_the_history_being_purged(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        want = self.vb.forecast(KEY, "Phone", SUN)["calls"]
        self.store.purge_volumes_before("2099-01-01")
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual((f["error"], f["calls"], f["source"]), ("", want, "saved"))

    def test_a_typed_total_still_beats_the_saved_one(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN, total=9000)
        self.assertEqual((f["source"], f["total"], sum(sum(d) for d in f["calls"])), ("typed", 9000, 9000))

    def test_the_weeks_behind_the_saved_forecast_are_kept_with_it(self):
        out = (SUN - timedelta(weeks=2)).isoformat()
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1, weeks=5, skip_weeks=[out])
        basis = self.store.volume_forecast(KEY, "Phone", SUN.isoformat())["basis"]
        self.assertEqual(len(basis["weeks"]["used"]), 5)
        self.assertIn(out, [w for w, _ in basis["weeks"]["skipped"]])
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(f["weeks"]["used"], basis["weeks"]["used"])

    def test_typed_days_are_kept_exactly_in_the_saved_grid(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {0: 2000}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(sum(f["calls"][0]), 2000)
        self.assertEqual(sum(sum(d) for d in f["calls"]), 8000)

    def test_saving_with_no_history_is_refused_and_keeps_nothing(self):
        store, vb = book()
        with self.assertRaises(ValueError):
            vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        self.assertIsNone(store.volume_forecast(KEY, "Phone", SUN.isoformat()))

    def test_bad_totals_are_refused_and_keep_nothing(self):
        for total, days in ((-5, {}), ("abc", {}), (100, {0: 200}), (None, {})):
            with self.assertRaises(ValueError, msg=(total, days)):
                self.vb.save_forecast(KEY, "Phone", SUN, total, days, 1)
        self.assertIsNone(self.store.volume_forecast(KEY, "Phone", SUN.isoformat()))

    def test_a_changed_setting_changes_the_people_but_not_the_calls(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        a = self.vb.forecast(KEY, "Phone", SUN)
        self.vb.set_settings(KEY, {"Phone": {"sl_target": 95}}, 1)
        b = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(a["calls"], b["calls"])
        self.assertGreater(sum(map(sum, b["needs"])), sum(map(sum, a["needs"])))

    def test_the_handle_time_the_forecast_was_made_with_is_kept_too(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        scaled(self.store, {}, aht=420.0)
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN)["aht"], 300.0)

    def test_a_forecast_saved_before_grids_were_kept_still_works(self):
        self.store.set_volume_forecast(KEY, "Phone", SUN.isoformat(), 8000, {}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual((f["source"], f["total"], sum(sum(d) for d in f["calls"])), ("saved", 8000, 8000))

    def test_the_report_uses_the_saved_grid_and_not_todays_history(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        scaled(self.store, {}, per_week=14000)
        self.assertEqual(self.vb._otf_week(KEY, "Phone", SUN)["total"], 8000)

    def test_a_later_event_does_not_change_a_saved_forecast(self):
        self.vb.save_forecast(KEY, "Phone", SUN, 8000, {}, 1)
        before = self.vb.forecast(KEY, "Phone", SUN)["calls"]
        self.vb.add_driver(KEY, "events", event(), 1)
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN)["calls"], before)


class TheDriversInTheSuggestion(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})
        scaled(self.store, {}, per_week=3000, channel="Chat", aht=420.0)

    def base(self, channel="Phone", **kw):
        return self.vb.forecast(KEY, channel, SUN, **kw)["suggestion"]["base"]

    def test_with_nothing_set_nothing_is_added(self):
        s = self.vb.forecast(KEY, "Phone", SUN)["suggestion"]
        self.assertEqual((s["steps"], s["final"], s["method"]), ([], s["base"], "trend"))

    def test_a_promotion_raises_the_suggestion_by_the_share_of_the_days_it_covers(self):
        base = self.base()
        self.vb.add_driver(KEY, "events", event(), 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        s = f["suggestion"]
        self.assertEqual(s["base"], base)
        self.assertAlmostEqual(s["final"], base * (1 + 0.25 * SHARE_TUE_TO_THU), delta=base * 0.003)
        self.assertEqual((f["source"], f["total"]), ("suggestion", s["final"]))
        self.assertEqual([(x["kind"], x["name"], x["days"]) for x in s["steps"]], [("event", "Black Friday", [2, 3, 4])])   # Tue, Wed, Thu

    def test_the_steps_add_up_exactly(self):
        base = self.base()
        self.vb.add_driver(KEY, "events", event(), 1)
        self.vb.add_driver(KEY, "events", event(name="Launch", start=SUN.isoformat(), end=SUN.isoformat(), change=40, after_days=2, after_change=-20), 1)
        s = self.vb.forecast(KEY, "Phone", SUN)["suggestion"]
        self.assertEqual(len(s["steps"]), 2)
        self.assertEqual(base + sum(x["delta"] for x in s["steps"]), s["final"])
        self.assertEqual(s["steps"][-1]["total"], s["final"])

    def test_ai_reduces_its_own_channel_only(self):
        chat, phone = self.base("Chat"), self.base("Phone")
        self.vb.add_driver(KEY, "ai", ai(), 1)
        c = self.vb.forecast(KEY, "Chat", SUN)["suggestion"]
        self.assertAlmostEqual(c["final"], chat * 0.9, delta=chat * 0.002)
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN)["suggestion"]["final"], phone)

    def test_a_later_ai_period_can_reduce_more(self):
        chat = self.base("Chat")
        self.vb.add_driver(KEY, "ai", ai(end=(SUN + timedelta(days=2)).isoformat(), change=-10), 1)
        self.vb.add_driver(KEY, "ai", ai(start=(SUN + timedelta(days=3)).isoformat(), change=-30), 1)
        want = chat * (1 - 0.1 * 3.6 / UNITS - 0.3 * 4.0 / UNITS)
        self.assertAlmostEqual(self.vb.forecast(KEY, "Chat", SUN)["suggestion"]["final"], want, delta=chat * 0.003)

    def test_a_share_of_what_ai_removes_comes_back_on_another_channel(self):
        phone, chat = self.base("Phone"), self.base("Chat")
        self.vb.add_driver(KEY, "ai", ai(channel="Phone", change=-20, move_to="Chat", move_share=50), 1)
        p = self.vb.forecast(KEY, "Phone", SUN)["suggestion"]
        c = self.vb.forecast(KEY, "Chat", SUN)["suggestion"]
        removed = phone - p["final"]
        moved = c["final"] - chat
        self.assertAlmostEqual(removed, phone * 0.2, delta=phone * 0.002)
        self.assertAlmostEqual(moved, removed * 0.5, delta=3)                     # the contacts that left are the contacts that arrived
        self.assertEqual([x["kind"] for x in c["steps"]], ["move"])
        self.assertEqual(chat + sum(x["delta"] for x in c["steps"]), c["final"])

    def test_a_source_with_no_history_moves_nothing_and_says_so(self):
        store, vb = book()
        scaled(store, {}, per_week=3000, channel="Chat", aht=420.0)
        vb.add_driver(KEY, "ai", ai(channel="Phone", change=-20, move_to="Chat", move_share=50), 1)
        c = vb.forecast(KEY, "Chat", SUN)
        self.assertEqual(c["suggestion"]["steps"], [])
        self.assertTrue(any("Phone" in n for n in c["notes"]))

    def test_growth_replaces_the_trend_when_the_planner_says_so(self):
        self.vb.set_growth(KEY, {"Phone": 52}, "growth", 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        pts = [(-w, t) for w, (_, t) in zip(range(6, 0, -1), f["suggestion"]["weeks"])]
        self.assertEqual(f["suggestion"]["method"], "growth")
        self.assertEqual(f["suggestion"]["base"], int(round(D.growth_level(pts, 52.0))))
        self.assertGreater(f["suggestion"]["base"], 7000)

    def test_growth_for_a_channel_without_a_rate_falls_back_to_the_trend_and_says_so(self):
        self.vb.set_growth(KEY, {"Phone": 52}, "growth", 1)
        c = self.vb.forecast(KEY, "Chat", SUN)
        self.assertEqual(c["suggestion"]["method"], "trend")
        self.assertTrue(any("Chat" in n and "rate" in n for n in c["notes"]))

    def test_the_measured_method_ignores_a_typed_rate(self):
        self.vb.set_growth(KEY, {"Phone": 52}, "measured", 1)
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN)["suggestion"]["method"], "trend")

    def test_last_year_is_a_second_suggestion_grown_by_the_rate(self):
        self.vb.set_growth(KEY, {"Phone": 8}, "measured", 1)
        self.vb.set_last_year(KEY, SUN, {"Phone": "12,000"}, 1)
        f = self.vb.forecast(KEY, "Phone", SUN)
        self.assertEqual(f["last_year"], {"week": "2025-11-09", "total": 12000, "grown": 12960, "yoy": 8.0})
        self.assertEqual(f["suggestion"]["method"], "trend")                       # not used unless chosen
        g = self.vb.forecast(KEY, "Phone", SUN, base="last_year")
        self.assertEqual((g["suggestion"]["method"], g["suggestion"]["base"], g["total"]), ("last_year", 12960, 12960))

    def test_choosing_last_year_without_a_figure_is_an_error_not_a_guess(self):
        f = self.vb.forecast(KEY, "Phone", SUN, base="last_year")
        self.assertIn("last year", f["error"].lower())
        self.assertEqual(f["calls"], [])
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN, total=8000, base="last_year")["total"], 8000)      # a typed total needs no suggestion
        with self.assertRaises(ValueError):
            self.vb.forecast(KEY, "Phone", SUN, base="magic")

    def test_a_typed_total_is_exact_and_the_event_only_shapes_its_days(self):
        plain = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.vb.add_driver(KEY, "events", event(), 1)
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual(sum(sum(d) for d in f["calls"]), 8000)
        for d in (2, 3, 4):
            self.assertGreater(sum(f["calls"][d]), sum(plain["calls"][d]))
        for d in (0, 1, 5, 6):
            self.assertLess(sum(f["calls"][d]), sum(plain["calls"][d]))
        self.assertEqual(f["day_factors"], [1.0, 1.0, 1.25, 1.25, 1.25, 1.0, 1.0])

    def test_typed_days_stay_exactly_as_typed_with_an_event(self):
        self.vb.add_driver(KEY, "events", event(), 1)
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000, day_totals={2: 1000})
        self.assertEqual(sum(f["calls"][2]), 1000)
        self.assertEqual(sum(sum(d) for d in f["calls"]), 8000)

    def test_an_event_in_another_week_changes_nothing_here(self):
        base = self.base()
        self.vb.add_driver(KEY, "events", event(start="2026-12-01", end="2026-12-03"), 1)
        s = self.vb.forecast(KEY, "Phone", SUN)["suggestion"]
        self.assertEqual((s["steps"], s["final"]), ([], base))

    def test_the_same_event_on_another_channel_changes_nothing_here(self):
        base = self.base("Chat")
        self.vb.add_driver(KEY, "events", event(channels=["Phone"]), 1)
        self.assertEqual(self.vb.forecast(KEY, "Chat", SUN)["suggestion"]["final"], base)

    def test_drivers_belong_to_their_program(self):
        self.vb.add_driver(KEY, "events", event(), 1)
        self.assertEqual(self.vb.drivers("Program 02 Other")["events"], [])

    def test_removing_a_driver_takes_its_effect_away(self):
        base = self.base()
        doc = self.vb.add_driver(KEY, "events", event(), 1)
        self.vb.remove_driver(KEY, "events", doc["events"][0]["id"], 1)
        self.assertEqual(self.vb.forecast(KEY, "Phone", SUN)["suggestion"]["final"], base)

    def test_bad_drivers_are_refused_and_keep_nothing(self):
        for key, row in (("events", event(change=900)), ("ai", ai(channel="Fax")), ("notes", event())):
            with self.assertRaises(ValueError, msg=(key, row)):
                self.vb.add_driver(KEY, key, row, 1)
        self.assertEqual(self.vb.drivers(KEY)["events"], [])
        self.assertEqual(self.vb.drivers(KEY)["ai"], [])

    def test_the_band_follows_the_drivers(self):
        scaled(self.store, {1: 1.04, 2: 0.97, 3: 1.02, 4: 0.99, 5: 1.05, 6: 0.96})
        a = self.vb.forecast(KEY, "Phone", SUN)["suggestion"]
        self.vb.add_driver(KEY, "events", event(), 1)
        b = self.vb.forecast(KEY, "Phone", SUN)["suggestion"]
        self.assertGreater(b["high"], a["high"])
        self.assertLessEqual(b["low"], b["final"])
        self.assertLessEqual(b["final"], b["high"])


if __name__ == "__main__":
    unittest.main()
