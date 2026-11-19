# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 4b (owner, 2026-11-07): "add the holidays and things like that, as it might change".

Holidays, promotions, launches and outages are already events with a change in contacts. Phase BL adds to an event:
- Hours: normal (as now), closed (nobody is needed that day) or reduced (only inside a window the planner types). The change in
  contacts may be left at zero when the hours are not normal.
- A holiday in the past is not an ordinary week: weeks that hold a Holiday event for the channel are left out of the pattern the
  forecast learns the weekdays from, with a note saying which, so a holiday does not distort an ordinary Monday.
Dates are typed for each year, because holidays move. Made-up data only."""
import html
import unittest
from datetime import date, timedelta

from webapp import drivers as D
from webapp.tests.test_bi_volumes import KEY, SUN, book
from webapp.tests.test_bi_volumes_routes import PASSWORD, _Volumes
from webapp.tests.test_bj_volumes_book import scaled
from webapp.tests.test_runs import sign_in, token

TUE = SUN + timedelta(days=2)


def holiday(**kw):
    return {"kind": "Holiday", "name": "Founders day", "channels": ["Phone"], "start": TUE.isoformat(), "end": TUE.isoformat(), "change": -30, **kw}


class TheEventHours(unittest.TestCase):
    def test_an_event_is_normal_hours_unless_it_says_otherwise(self):
        self.assertEqual(D.clean_event(holiday())["hours"], "normal")
        self.assertIsNone(D.clean_event(holiday())["window"])

    def test_closed_and_reduced(self):
        self.assertEqual(D.clean_event(holiday(hours="closed", change=""))["hours"], "closed")
        got = D.clean_event(holiday(hours="reduced", open_from="10:00", open_to="14:00", change=""))
        self.assertEqual((got["hours"], got["window"], got["change"]), ("reduced", [600, 840], 0.0))

    def test_the_change_may_be_zero_only_when_the_hours_are_not_normal(self):
        with self.assertRaises(ValueError):
            D.clean_event(holiday(change="0"))
        D.clean_event(holiday(change="0", hours="closed"))

    def test_refusals_are_in_words(self):
        for kw, word in (({"hours": "half"}, "hours"), ({"hours": "reduced"}, "opening"), ({"hours": "reduced", "open_from": "10:00"}, "closing"),
                         ({"hours": "reduced", "open_from": "9am", "open_to": "14:00"}, "opening"),
                         ({"hours": "reduced", "open_from": "10:00", "open_to": "10:00"}, "same")):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError) as caught:
                    D.clean_event(holiday(**kw))
                self.assertIn(word, str(caught.exception))

    def test_a_saved_event_without_the_new_fields_still_reads(self):
        old = {"kind": "Holiday", "name": "Old", "channels": ["Phone"], "start": TUE.isoformat(), "end": TUE.isoformat(), "change": -10,
               "after_days": 0, "after_change": 0.0, "id": "e1"}
        doc = D.clean_document({"events": [old], "ai": []})
        self.assertEqual((doc["events"][0]["hours"], doc["events"][0]["window"]), ("normal", None))

    def test_the_weeks_that_hold_a_holiday_for_a_channel(self):
        events = [D.clean_event(holiday(start=(SUN - timedelta(days=12)).isoformat(), end=(SUN - timedelta(days=11)).isoformat())),
                  D.clean_event(holiday(kind="Promotion", start=(SUN - timedelta(days=30)).isoformat(), end=(SUN - timedelta(days=30)).isoformat())),
                  D.clean_event(holiday(channels=["Chat"], start=(SUN - timedelta(days=40)).isoformat(), end=(SUN - timedelta(days=40)).isoformat())),
                  D.clean_event(holiday(start=TUE.isoformat(), end=TUE.isoformat()))]
        got = D.holiday_weeks(events, "Phone", SUN)
        self.assertEqual(list(got), [(SUN - timedelta(weeks=2)).isoformat()])   # the week of the 12th day back; not a promotion, not chat, not this week
        self.assertEqual(got[(SUN - timedelta(weeks=2)).isoformat()], ["Founders day"])


class TheHoursInTheForecast(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})

    def needs(self, channel="Phone"):
        return self.vb.forecast(KEY, channel, SUN, total=8000)["needs"]

    def test_a_closed_day_needs_nobody_and_the_other_days_are_as_before(self):
        before = self.needs()
        self.vb.add_driver(KEY, "events", holiday(hours="closed", change=""), 1)
        after = self.needs()
        self.assertEqual(sum(after[2]), 0)
        self.assertEqual([after[d] for d in (0, 1, 3, 4, 5, 6)], [before[d] for d in (0, 1, 3, 4, 5, 6)])

    def test_a_reduced_day_needs_people_only_inside_its_window(self):
        self.vb.add_driver(KEY, "events", holiday(hours="reduced", open_from="10:00", open_to="14:00", change=""), 1)
        row = self.needs()[2]
        self.assertTrue(all(row[h] == 0 for h in list(range(0, 10)) + list(range(14, 24))), row)
        self.assertTrue(all(row[h] >= 1 for h in range(10, 14)), row)

    def test_it_touches_only_its_channels(self):
        chat_before = self.needs("Chat") if False else None
        scaled(self.store, {}, channel="Chat", per_week=3000, aht=420.0)
        chat_before = self.needs("Chat")
        self.vb.add_driver(KEY, "events", holiday(hours="closed", change=""), 1)   # Phone only
        self.assertEqual(self.needs("Chat"), chat_before)

    def test_closed_wins_over_reduced_on_the_same_day(self):
        self.vb.add_driver(KEY, "events", holiday(name="a", hours="reduced", open_from="10:00", open_to="14:00", change=""), 1)
        self.vb.add_driver(KEY, "events", holiday(name="b", hours="closed", change=""), 1)
        self.assertEqual(sum(self.needs()[2]), 0)

    def test_the_weekly_hours_still_apply_on_the_other_days(self):
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {"1": [540, 1260]}}}, 1)
        self.vb.add_driver(KEY, "events", holiday(hours="closed", change=""), 1)
        after = self.needs()
        self.assertEqual(after[1][3], 0)
        self.assertEqual(sum(after[2]), 0)


class ThePatternSkipsHolidayWeeks(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {3: 0.85})   # week 3 back is a mild 15% dip: clean to the usual rule, but a holiday week

    def used(self, **kw):
        f = self.vb.forecast(KEY, "Phone", SUN, total=8000, **kw)
        return f, set(f["weeks"]["used"])

    def week3(self):
        return (SUN - timedelta(weeks=3)).isoformat()

    def test_without_a_holiday_the_week_is_used(self):
        self.assertIn(self.week3(), self.used()[1])

    def test_a_holiday_in_that_week_leaves_it_out_and_says_so(self):
        day = SUN - timedelta(weeks=3) + timedelta(days=2)
        self.vb.add_driver(KEY, "events", holiday(name="Spring holiday", start=day.isoformat(), end=day.isoformat()), 1)
        f, used = self.used()
        self.assertNotIn(self.week3(), used)
        self.assertEqual(len(used), 6)   # the six newest clean weeks: it reached one week further back
        self.assertTrue([n for n in f["notes"] if "Spring holiday" in n and self.week3() in n], f["notes"])
        self.assertIn([self.week3(), "a holiday: Spring holiday"], [list(x) for x in f["weeks"]["skipped"]])

    def test_a_promotion_does_not_leave_a_week_out(self):
        day = SUN - timedelta(weeks=3) + timedelta(days=2)
        self.vb.add_driver(KEY, "events", holiday(kind="Promotion", start=day.isoformat(), end=day.isoformat()), 1)
        self.assertIn(self.week3(), self.used()[1])

    def test_a_holiday_for_another_channel_does_not_leave_it_out(self):
        day = SUN - timedelta(weeks=3) + timedelta(days=2)
        self.vb.add_driver(KEY, "events", holiday(channels=["Chat"], start=day.isoformat(), end=day.isoformat()), 1)
        self.assertIn(self.week3(), self.used()[1])


class TheHolidayOnThePage(_Volumes):
    def tearDown(self):
        self.store.set_volume_drivers(self.alpha, {}, 1)

    def add(self, client, **fields):
        base = {"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": SUN.isoformat(), "action": "add_event", "kind": "Holiday",
                "name": "Founders day", "start": TUE.isoformat(), "end": TUE.isoformat(), "change": "", "channels": "Phone", "hours": "closed"}
        return client.post("/volumes/drivers", data={**base, **fields}, follow_redirects=True)

    def test_a_closed_holiday_is_added_from_the_form_and_listed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = html.unescape(self.add(client).get_data(as_text=True))
        self.assertIn("Added the holiday Founders day", got)
        saved = self.vb.drivers(self.alpha)["events"][0]
        self.assertEqual((saved["hours"], saved["change"]), ("closed", 0.0))
        self.assertIn("closed", got)

    def test_a_reduced_holiday_keeps_its_window(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.add(client, hours="reduced", open_from="10:00", open_to="14:00")
        self.assertEqual(self.vb.drivers(self.alpha)["events"][0]["window"], [600, 840])

    def test_a_bad_window_saves_nothing_and_says_why(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = html.unescape(self.add(client, hours="reduced", open_from="10:00", open_to="").get_data(as_text=True))
        self.assertIn("closing", got)
        self.assertEqual(self.vb.drivers(self.alpha)["events"], [])


if __name__ == "__main__":
    unittest.main()
