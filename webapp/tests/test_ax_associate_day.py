# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-23: "in associate view for today, if their shift is from 23:00 to 08:00 they still see today after
00:00 for the next day, not for the running shift, and they should see today and tomorrow somehow"): after midnight My day
shows the shift that is running (it started yesterday), then today's own shift if there is one, then tomorrow's. The made-up
night shift of test_as_requests: Associate 029, Wednesday 22:00 to 07:00."""
import html
import json
import unittest
from datetime import date, datetime
from unittest import mock

from webapp.tests.test_as_requests import CAIRO, NIGHT
from webapp.tests.test_as_pages import _Pages
from webapp.tests.test_runs import sign_in


def at(day, hour, minute=0):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            moment = datetime(2026, 10, day, hour, minute, tzinfo=CAIRO)
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)
    return Clock


class TheNightShiftAfterMidnight(_Pages):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.night_client = sign_in(cls.app, "a029", "Associate-pass-1")

    def page(self, clock):
        with mock.patch("webapp.app.datetime", clock):
            return html.unescape(self.night_client.get("/me/breaks").get_data(as_text=True))

    def test_after_midnight_the_running_shift_is_what_today_shows(self):
        page = self.page(at(15, 0, 30))  # Thursday 00:30: the shift that began Wednesday 22:00 is running
        self.assertIn("Your shift now", page)
        self.assertIn("started Wednesday 14 Oct", page)
        self.assertIn("22:00 - 07:00", page)
        self.assertIn("Now ", page)
        self.assertNotIn("You do not work today", page)

    def test_the_running_shifts_breaks_are_listed_with_changes_still_to_come(self):
        page = self.page(at(15, 0, 30))
        self.assertIn("Your breaks, 22:00 - 07:00", page)
        self.assertIn("Lunch", page)  # 03:00 still ahead

    def test_during_the_shift_on_its_own_day_nothing_changes(self):
        page = self.page(at(14, 23, 0))
        self.assertIn("Today, Wednesday", page)
        self.assertNotIn("Your shift now", page)

    def thursday_night(self):
        row = self.app.extensions["days"].version(self.key, date(2026, 10, 15))[0]
        week = json.loads(row["week"])
        for a in week["associates"]:
            if a["name"] == NIGHT:
                a["days"][4] = "22:00 - 07:00"
        week["breaks"] += [{"associate": NIGHT, "day": "Thu", "kind": "Break 1", "start": "00:30", "minutes": 15},
                           {"associate": NIGHT, "day": "Thu", "kind": "Lunch", "start": "03:00", "minutes": 30}]
        self.store.update_schedule(row["id"], week=json.dumps(week))
        self.addCleanup(self.store.update_schedule, row["id"], week=row["week"])
        self.app.extensions["days"]._pages.clear()

    def test_a_shift_that_starts_later_today_is_shown_after_the_running_one(self):
        self.thursday_night()
        page = self.page(at(15, 0, 30))
        self.assertIn("Your shift now", page)
        self.assertIn("Later today, Thursday", page)
        self.assertIn("Your shift starts at 22:00", page)

    def test_tomorrow_is_still_there(self):
        self.thursday_night()
        self.assertIn("Tomorrow, Thursday", self.page(at(14, 23, 0)))


if __name__ == "__main__":
    unittest.main()
