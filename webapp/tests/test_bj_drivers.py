# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "ask necessary questions for promotions: start, end, expected increase %; customer increase year over year; will AI reduce
volumes, from which channel, what % in which period, and if it will increase in the next period then to how much"): what a promotion, event, growth figure,
last year's week or an AI period does to a week's contacts, day by day and channel by channel. Made-up numbers."""
import unittest
from datetime import date, timedelta

from webapp import drivers as D

SUN = date(2026, 11, 8)
WEEK = [SUN + timedelta(days=k) for k in range(7)]


def event(**kw):
    base = {"kind": "Promotion", "name": "Black Friday", "channels": ["Phone", "Chat"], "start": "2026-11-10", "end": "2026-11-12", "change": 25,
            "after_days": 0, "after_change": 0}
    return D.clean_event({**base, **kw})


def ai(**kw):
    base = {"channel": "Chat", "start": "2026-11-01", "end": "2026-11-30", "change": -10, "move_to": "", "move_share": 0}
    return D.clean_ai({**base, **kw})


class TheEvents(unittest.TestCase):
    def test_a_promotion_changes_only_its_days_and_channels(self):
        f = D.day_factors([event()], [], "Phone", WEEK)
        self.assertEqual([round(x, 6) for x in f], [1, 1, 1.25, 1.25, 1.25, 1, 1])          # Sun 08 .. Sat 14: Tue 10 to Thu 12
        self.assertEqual(D.day_factors([event()], [], "Email", WEEK), [1.0] * 7)

    def test_a_dip_after_the_promotion_is_a_second_window(self):
        f = D.day_factors([event(after_days=2, after_change=-20)], [], "Phone", WEEK)
        self.assertEqual([round(x, 6) for x in f], [1, 1, 1.25, 1.25, 1.25, 0.8, 0.8])

    def test_two_events_on_one_day_multiply(self):
        f = D.day_factors([event(), event(name="Launch", start="2026-11-11", end="2026-11-11", change=10)], [], "Phone", WEEK)
        self.assertAlmostEqual(f[3], 1.25 * 1.10)

    def test_a_drop_and_a_rise_are_both_allowed(self):
        self.assertAlmostEqual(D.day_factors([event(kind="Outage", change=-60, start="2026-11-08", end="2026-11-08")], [], "Phone", WEEK)[0], 0.4)

    def test_every_field_is_checked(self):
        for bad in ({"start": "2026-11-12", "end": "2026-11-10"}, {"start": "tomorrow"}, {"change": 900}, {"change": -100}, {"change": "abc"},
                    {"channels": []}, {"channels": ["Fax"]}, {"kind": "Party"}, {"name": ""}, {"name": "x" * 200}, {"after_days": 40},
                    {"after_days": 3, "after_change": 900}, {"start": "2026-01-01", "end": "2030-01-01"}):
            with self.assertRaises(ValueError, msg=bad):
                event(**bad)

    def test_a_name_is_text_never_markup_and_has_no_formula_lead(self):
        e = event(name="<b>Sale</b>")
        self.assertEqual(e["name"], "<b>Sale</b>")      # kept as typed: pages escape it
        with self.assertRaises(ValueError):
            event(name="=cmd|' /C calc'!A0")


class TheAi(unittest.TestCase):
    def test_a_reduction_applies_to_its_channel_and_period(self):
        f = D.day_factors([], [ai(start="2026-11-10", end="2026-11-12")], "Chat", WEEK)
        self.assertEqual([round(x, 6) for x in f], [1, 1, 0.9, 0.9, 0.9, 1, 1])
        self.assertEqual(D.day_factors([], [ai()], "Phone", WEEK), [1.0] * 7)

    def test_the_next_period_can_reduce_more_or_less_or_increase(self):
        rows = [ai(start="2026-11-01", end="2026-11-10", change=-10), ai(start="2026-11-11", end="2026-12-31", change=-25)]
        f = D.day_factors([], rows, "Chat", WEEK)
        self.assertEqual([round(x, 6) for x in f], [0.9, 0.9, 0.9, 0.75, 0.75, 0.75, 0.75])
        up = D.day_factors([], [ai(start="2026-11-12", end="2026-12-31", change=15)], "Chat", WEEK)
        self.assertAlmostEqual(up[4], 1.15)

    def test_events_and_ai_multiply_in_one_day(self):
        f = D.day_factors([event(channels=["Chat"], start="2026-11-10", end="2026-11-10", change=20)], [ai(start="2026-11-10", end="2026-11-10")], "Chat", WEEK)
        self.assertAlmostEqual(f[2], 1.2 * 0.9)

    def test_part_of_what_ai_removes_can_come_back_on_another_channel(self):
        rows = [ai(channel="Phone", change=-20, move_to="Chat", move_share=50, start="2026-11-09", end="2026-11-10")]
        base = [100, 200, 300, 400, 500, 600, 700]                                 # Phone contacts per day before AI
        moved = D.ai_moves(rows, "Phone", WEEK, base)
        self.assertEqual(moved["Chat"], [0, 20, 30, 0, 0, 0, 0])                   # 50 % of the 20 % removed on Mon 09 and Tue 10
        self.assertEqual(D.ai_moves([ai()], "Chat", WEEK, base), {})

    def test_every_field_is_checked(self):
        for bad in ({"channel": "Fax"}, {"change": -150}, {"change": 700}, {"start": "x"}, {"end": "2026-10-01"}, {"move_to": "Chat", "move_share": 50, "channel": "Chat"},
                    {"move_to": "Phone", "move_share": 150, "channel": "Chat", "change": -10}, {"move_to": "Phone", "move_share": 50, "channel": "Chat", "change": 10},
                    {"move_to": "Fax", "move_share": 10, "channel": "Chat", "change": -5}):
            with self.assertRaises(ValueError, msg=bad):
                ai(**bad)


class TheGrowth(unittest.TestCase):
    def test_growth_is_a_percent_a_year_and_is_checked(self):
        self.assertEqual(D.clean_growth({"Phone": "8", "Chat": "", "Email": None}, "growth"), {"yoy": {"Phone": 8.0}, "method": "growth"})
        for bad in ({"Phone": "-80"}, {"Phone": "300"}, {"Phone": "abc"}, {"Fax": "5"}):
            with self.assertRaises(ValueError, msg=bad):
                D.clean_growth(bad, "measured")
        with self.assertRaises(ValueError):
            D.clean_growth({}, "magic")

    def test_a_weekly_factor_from_a_yearly_rate(self):
        self.assertAlmostEqual(D.weekly_factor(52.0, 52), 1.52, places=9)         # a year of weeks is the whole rate
        self.assertAlmostEqual(D.weekly_factor(10.0, 26), 1.1 ** 0.5, places=9)
        self.assertEqual(D.weekly_factor(0.0, 5), 1.0)

    def test_the_level_is_brought_to_the_forecast_week_by_growth(self):
        # Each past week is brought forward to the forecast week at the stated rate; the middle of those is the level (so one odd week cannot move it).
        pts = [(-6, 1000.0), (-4, 1000.0), (-2, 1000.0)]                          # flat history, 52 % a year stated: grown 6, 4 and 2 weeks
        self.assertAlmostEqual(D.growth_level(pts, 52.0), 1000 * 1.52 ** (4 / 52), places=6)
        self.assertEqual(D.growth_level(pts, 0.0), 1000.0)

    def test_history_that_already_grows_at_the_stated_rate_gives_this_weeks_level(self):
        pts = [(o, 1000 * 1.52 ** (o / 52)) for o in (-6, -5, -3, -2)]
        self.assertAlmostEqual(D.growth_level(pts, 52.0), 1000.0, places=6)

    def test_nothing_to_grow_is_refused(self):
        with self.assertRaises(ValueError):
            D.growth_level([], 5.0)


class TheLastYear(unittest.TestCase):
    def test_last_years_week_grown_by_the_year_over_year_rate(self):
        self.assertEqual(D.last_year_total(12000, 8.0), 12960)
        self.assertEqual(D.last_year_total(12000, None), 12000)
        with self.assertRaises(ValueError):
            D.last_year_total(-5, 0)


class TheRowsOfADocument(unittest.TestCase):
    def test_add_and_remove_keep_ids_stable_and_cap_the_count(self):
        doc = {}
        doc = D.add_row(doc, "events", event())
        doc = D.add_row(doc, "events", event(name="B"))
        ids = [r["id"] for r in doc["events"]]
        self.assertEqual(len(set(ids)), 2)
        doc = D.remove_row(doc, "events", ids[0])
        self.assertEqual([r["name"] for r in doc["events"]], ["B"])
        self.assertEqual(D.remove_row(doc, "events", "nope"), doc)
        for _ in range(D.MAX_ROWS - 1):                                  # one is there already: the list is now full
            doc = D.add_row(doc, "events", event())
        self.assertEqual(len(doc["events"]), D.MAX_ROWS)
        with self.assertRaises(ValueError):
            D.add_row(doc, "events", event())

    def test_what_is_stored_is_only_what_is_known(self):
        doc = D.clean_document({"events": [event()], "ai": [ai()], "growth": {"yoy": {"Phone": 5.0}, "method": "measured"}, "evil": "<script>", "skip_weeks": ["2026-10-04", "x"],
                                "last_year": {"2026-11-08": {"Phone": 12000, "Fax": 5}}})
        self.assertNotIn("evil", doc)
        self.assertEqual(doc["skip_weeks"], ["2026-10-04"])
        self.assertEqual(doc["last_year"], {"2026-11-08": {"Phone": 12000}})


class TheOverlapAndTheParts(unittest.TestCase):
    def test_two_ai_periods_on_one_channel_cannot_overlap(self):
        doc = D.add_row({}, "ai", ai(start="2026-11-01", end="2026-11-30"))
        with self.assertRaises(ValueError) as why:
            D.add_row(doc, "ai", ai(start="2026-11-30", end="2026-12-31", change=-25))
        self.assertIn("overlaps", str(why.exception))
        D.add_row(doc, "ai", ai(start="2026-12-01", end="2026-12-31", change=-25))      # the next period starts the day after
        D.add_row(doc, "ai", ai(channel="Phone", start="2026-11-15", end="2026-11-20"))  # another channel is free

    def test_events_may_overlap(self):
        doc = D.add_row({}, "events", event())
        self.assertEqual(len(D.add_row(doc, "events", event(name="B"))["events"]), 2)

    def test_an_unknown_list_is_refused(self):
        with self.assertRaises(ValueError):
            D.add_row({}, "notes", event())

    def test_adding_does_not_change_the_document_it_was_given(self):
        doc = D.add_row({}, "events", event())
        before = repr(doc)
        D.add_row(doc, "events", event(name="B"))
        D.remove_row(doc, "events", doc["events"][0]["id"])
        self.assertEqual(repr(doc), before)

    def test_a_cleaned_document_cleans_to_itself(self):
        doc = D.add_row(D.add_row({}, "events", event()), "ai", ai(move_to="Phone", move_share=40))
        doc = D.with_growth(doc, {"Phone": "6"}, "growth")
        doc = D.with_last_year(doc, "2025-11-09", {"Phone": "11,500", "Chat": ""})
        doc = D.with_skip_weeks(doc, ["2026-10-04", "2026-10-04", "2026-09-27"])
        self.assertEqual(D.clean_document(doc), doc)

    def test_growth_last_year_and_skipped_weeks_are_set_strictly(self):
        doc = D.with_growth({}, {"Phone": "6"}, "growth")
        self.assertEqual(doc["growth"], {"yoy": {"Phone": 6.0}, "method": "growth"})
        self.assertEqual(D.with_last_year({}, "2025-11-09", {"Phone": "11,500", "Chat": ""})["last_year"], {"2025-11-09": {"Phone": 11500}})
        self.assertEqual(D.with_skip_weeks({}, ["2026-10-04", "2026-09-27", "2026-10-04"])["skip_weeks"], ["2026-09-27", "2026-10-04"])
        for call in (lambda: D.with_last_year({}, "2025-11-09", {"Phone": "-4"}), lambda: D.with_last_year({}, "x", {"Phone": 4}),
                     lambda: D.with_last_year({}, "2025-11-09", {"Fax": 4}), lambda: D.with_last_year({}, "2025-11-09", {"Phone": "1.5"}),
                     lambda: D.with_skip_weeks({}, ["x"]), lambda: D.with_skip_weeks({}, [(date(2026, 1, 4) + timedelta(weeks=k)).isoformat() for k in range(D.MAX_SKIPPED + 1)])):
            with self.assertRaises(ValueError):
                call()

    def test_a_stored_document_that_is_not_a_document_is_empty(self):
        for raw in (None, [], "x", 5):
            self.assertEqual(D.clean_document(raw), D.clean_document({}))
        self.assertEqual(D.clean_document({})["growth"], {"yoy": {}, "method": "measured"})

    def test_a_damaged_stored_row_is_an_error_not_a_quiet_drop(self):
        with self.assertRaises(ValueError):
            D.clean_document({"events": [{"kind": "Promotion"}]})


class TheWaterfall(unittest.TestCase):
    EVEN = [1 / 7] * 7

    def test_one_driver_at_a_time_and_each_step_says_what_it_added(self):
        w = D.waterfall(7000, self.EVEN, WEEK, "Phone", [{**event(), "id": "1"}], [])
        self.assertEqual(w["total"], 7750)                                          # 3 of 7 days at +25 %
        self.assertEqual([(s["kind"], s["id"], s["name"], s["days"], s["delta"], s["total"]) for s in w["steps"]],
                         [("event", "1", "Black Friday", [2, 3, 4], 750, 7750)])
        self.assertEqual([round(f, 6) for f in w["factors"]], [1, 1, 1.25, 1.25, 1.25, 1, 1])

    def test_the_steps_add_up_to_the_total_exactly(self):
        rows = [{**event(channels=["Chat"], change=10, start="2026-11-08", end="2026-11-14"), "id": "1"}]
        ai_rows = [{**ai(start="2026-11-08", end="2026-11-14", change=-10), "id": "2"}]
        w = D.waterfall(7001, self.EVEN, WEEK, "Chat", rows, ai_rows)
        self.assertEqual([s["kind"] for s in w["steps"]], ["event", "ai"])
        self.assertEqual(7001 + sum(s["delta"] for s in w["steps"]), w["total"])
        self.assertEqual(w["total"], round(7001 * 1.1 * 0.9))

    def test_a_driver_that_misses_the_week_or_the_channel_is_not_a_step(self):
        w = D.waterfall(7000, self.EVEN, WEEK, "Email", [{**event(), "id": "1"}], [{**ai(start="2027-01-01", end="2027-01-31"), "id": "2"}])
        self.assertEqual((w["steps"], w["total"], w["factors"]), ([], 7000, [1.0] * 7))

    def test_a_closed_day_adds_nothing(self):
        shares = [0, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6]
        w = D.waterfall(6000, shares, WEEK, "Phone", [{**event(start="2026-11-08", end="2026-11-08", change=50), "id": "1"}], [])
        self.assertEqual((w["total"], w["steps"][0]["delta"]), (6000, 0))

    def test_shares_and_days_must_match(self):
        with self.assertRaises(ValueError):
            D.waterfall(100, [1.0], WEEK, "Phone", [], [])


if __name__ == "__main__":
    unittest.main()
