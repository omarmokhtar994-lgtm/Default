# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T7: My week on a phone (sample ag05).

Today's card: the shift, a band of what the person is on through it (channels, breaks), and in words what they are on
now and what comes next. Under it the week, a day a line, with the shift and any leave or swap asked for that day;
then their requests, and the forms to ask for leave and to offer a swap.
"""
import datetime as dt
import unittest
from unittest import mock

from webapp.day import my_day
from webapp.programs import ProgramBook
from webapp.tests.test_runs import TOKEN, sign_in


def view(name="Associate 05", runs=((960, 1230, "C"), (1260, 1500, "P"))):
    seg = {"offset": 0, "label": "16:00 - 01:00", "start": 960, "end": 1500, "status": "Present",
           "breaks": [{"idx": 0, "kind": "Break 1", "start": 1110, "minutes": 15},
                      {"idx": 1, "kind": "Lunch", "start": 1230, "minutes": 30}]}
    return {"lanes": [{"name": name, "segments": [seg]}], "channels": {"runs": {name: list(runs)}}}


class TheTodayCard(unittest.TestCase):
    def test_the_band(self):
        found = my_day(view(), "Associate 05", 1140)
        self.assertEqual(found["label"], "16:00 - 01:00")
        self.assertEqual([(p["lo"], p["hi"], p["kind"]) for p in found["band"]],
                         [(960, 1110, "C"), (1110, 1125, "break"), (1125, 1230, "C"), (1230, 1260, "break"),
                          (1260, 1500, "P")])

    def test_now_and_next_in_words(self):
        self.assertEqual(my_day(view(), "Associate 05", 1140)["said"],
                         "Now on Chat until 20:30. Then Lunch, 30 minutes, and Phone from 21:00.")
        self.assertEqual(my_day(view(), "Associate 05", 1250)["said"], "Now on Lunch until 21:00. Then Phone from 21:00.")
        self.assertEqual(my_day(view(), "Associate 05", 1400)["said"], "Now on Phone until 01:00. Then your shift ends.")

    def test_before_after_and_off(self):
        self.assertEqual(my_day(view(), "Associate 05", 600)["said"], "Your shift starts at 16:00.")
        self.assertEqual(my_day(view(), "Associate 05", 1510)["said"], "Your shift ended at 01:00.")
        self.assertIsNone(my_day(view(), "Associate 06", 600))

    def test_without_a_channel_plan(self):
        found = my_day(view(runs=()), "Associate 05", 1000)
        self.assertEqual([p["kind"] for p in found["band"]], ["work", "break", "work", "break", "work"])
        self.assertEqual(found["said"], "Now working until 18:30. Then Break 1, 15 minutes.")


class _Tuesday(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 10, 13, 10, 0, tzinfo=tz)


class ThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)
        pid = next(p["id"] for p in ProgramBook(cls.store).tree() if p["name"] == "SAKS")
        uid = cls.store.add_user("a12", "Associate 012", "Associate-pass-1", must_change=False)
        cls.store.update_user(uid, is_associate=1, roster_name="Associate 012")
        cls.store.set_user_programs(uid, [pid])
        cls.me = sign_in(cls.app, "a12", "Associate-pass-1")

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def page(self):
        with mock.patch("webapp.app.datetime", _Tuesday):
            return self.me.get("/me").get_data(as_text=True)

    def test_today_and_the_week(self):
        page = self.page()
        self.assertIn("Today, Tuesday", page)
        self.assertIn('<b class="me-shift">09:00 - 18:00</b>', page)
        self.assertIn('class="me-band"', page)
        week = page[page.index('aria-labelledby="week-h"'):]
        days = [("Sun 11 Oct", "OFF"), ("Mon 12 Oct", "OFF"), ("Tue 13 Oct", "09:00 - 18:00"),
                ("Wed 14 Oct", "09:00 - 18:00"), ("Thu 15 Oct", "09:00 - 18:00"), ("Fri 16 Oct", "16:00 - 01:00"),
                ("Sat 17 Oct", "16:00 - 01:00")]
        for day, cell in days:
            self.assertRegex(week, rf"<th scope=\"row\">{day}</th><td>{cell}</td>")

    def test_a_day_with_leave_asked_says_so(self):
        tok = TOKEN.search(self.page()).group(1)
        with mock.patch("webapp.app.datetime", _Tuesday):
            self.me.post("/me/leave", data={"csrf_token": tok, "kind": "Planned leave", "first": "2026-10-16",
                                            "last": "2026-10-16"})
        week = self.page()
        week = week[week.index('aria-labelledby="week-h"'):]
        self.assertRegex(week, r'<th scope="row">Fri 16 Oct</th><td>16:00 - 01:00</td><td>Planned leave: waiting for your TM</td>')

    def test_the_forms_are_sheets_on_a_phone(self):
        page = self.page()
        self.assertIn('<details class="sheet"', page)
        self.assertIn('<summary>Request leave</summary>', page)
        self.assertIn('<summary>Offer a swap</summary>', page)


if __name__ == "__main__":
    unittest.main()
