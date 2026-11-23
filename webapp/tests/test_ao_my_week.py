# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AO (owner, 2026-10-20: "From associate view they can't see next week schedule or all schedule raised for them
and inuse for future weeks. They can't see their schedule breaks or coachings etc"; answer: based on the RTA). My week
offers this week and every later week that has a schedule kept, and each day lists the breaks, lunch and the aux
(coaching, meetings and the like) the RTA's day holds for the associate."""
import json
import unittest
from datetime import date
from unittest import mock

from webapp.tests import test_ag_swaps
from webapp.tests.test_ag_leave import _Clock
from webapp.tests.test_channel_people import add_version
from webapp.tests.test_runs import sign_in

WED = date(2026, 10, 14)
ME = "Associate 027"   # Wed 11:00 - 20:00 in the fixture week of 11 Oct


class TheMyWeek(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_ag_swaps.Swaps.setUpClass.__func__(cls)
        later = add_version(cls.store, cls.key, "2026-10-18", [(ME, "English"), ("Associate 028", "English")],
                            in_use=True)
        row = cls.store.get_schedule(later)
        week = json.loads(row["week"])
        week["associates"][0]["days"][1] = "09:00 - 18:00"
        cls.store.update_schedule(later, week=json.dumps(week))
        older = add_version(cls.store, cls.key, "2026-10-04", [(ME, "English"), ("Associate 999", "English")],
                            in_use=True)
        wed = cls.app.extensions["days"].version(cls.key, WED)[0]
        week = json.loads(wed["week"])
        week["breaks"] += [{"associate": ME, "day": "Wed", "kind": "Break 1", "start": "13:00", "minutes": 15},
                           {"associate": ME, "day": "Wed", "kind": "Lunch", "start": "15:00", "minutes": 30}]
        cls.store.update_schedule(wed["id"], week=json.dumps(week))
        cls.me = sign_in(cls.app, "a027", "Associate-pass-1")

    @classmethod
    def tearDownClass(cls):
        test_ag_swaps.Swaps.tearDownClass.__func__(cls)

    def get(self, url):
        with mock.patch("webapp.app.datetime", _Clock):
            return self.me.get(url).get_data(as_text=True)

    def test_the_picker_lists_this_week_and_the_later_ones_that_have_a_schedule(self):
        page = self.get("/me")
        self.assertIn('<option value="2026-10-11" selected>', page)
        self.assertIn('<option value="2026-10-18">', page)
        self.assertNotIn('<option value="2026-10-04"', page)  # a week that is over

    def test_a_later_week_shows_its_own_days(self):
        page = self.get("/me?week=2026-10-18")
        self.assertIn("18 Oct to 24 Oct", page)
        row = page.split("Mon 19 Oct")[1].split("</tr>")[0]
        self.assertIn("09:00 - 18:00", row)

    def test_an_unknown_week_falls_back_to_this_one(self):
        self.assertIn("Wed 14 Oct", self.get("/me?week=2031-01-02"))

    def test_the_days_list_their_breaks(self):
        row = self.get("/me").split("Wed 14 Oct")[1].split("</tr>")[0]
        self.assertIn("Break 1 13:00 to 13:15", row)
        self.assertIn("Lunch 15:00 to 15:30", row)

    def test_recorded_coaching_is_listed(self):
        self.app.extensions["days"].add_item(self.key, WED, ME, "Coaching", "19:00", 30, 1)
        row = self.get("/me").split("Wed 14 Oct")[1].split("</tr>")[0]
        self.assertIn("Coaching 19:00 to 19:30", row)

    def test_a_name_only_on_an_older_kept_week_still_finds_its_schedule(self):
        self.assertIn("Associate 999", self.app.extensions["leave"].names(self.key))


if __name__ == "__main__":
    unittest.main()
