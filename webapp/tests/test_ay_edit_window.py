# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "make it for everything and limit it 1 day back for everyone, 7 days for supervisor, unlimited for admin,
also the timezone should match their own on the PC"): every change posted from the day page (overtime, call-ins, cover, activities,
breaks, attendance, undo ...) is refused for a day older than yesterday; a supervisor may go 7 days back, an admin any distance. Today
is the viewer's: the zone their browser reports in the ``pc_tz`` cookie. (The app's ``TODAY`` setting stands in for it in most tests.)"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from webapp.tests.test_overtime_side import WED, _Overtime
from webapp.tests.test_runs import token

NAME = "Made-up Support 02"
CLOSED = "is closed to changes for your role"


class _Window(_Overtime):
    def setUp(self):
        self.was = self.app.config.get("TODAY")
        self.addCleanup(lambda: self.app.config.__setitem__("TODAY", self.was))
        self.sara = self.store.get_user_by_name("sara")["id"]
        self.ot = self.days.add_activity(self.key, WED, "Associate 021", "Overtime", "17:00", "18:00", 1)
        self.call = self.days.add_activity(self.key, WED, "Associate 004", "Called in", "10:00", "18:00", 1)
        self.aux = self.days.add_activity(self.key, WED, "Associate 008", "Training", "10:00", "10:30", 1)
        self.cover = self.days.add_cover(self.key, WED, NAME, "Support", "10:00", "12:00", 1)

        def clean():
            for i in (self.ot, self.call, self.aux):
                if self.store.get_activity(i):
                    self.store.delete_activity(i)
            if self.store.get_cover(self.cover):
                self.store.delete_cover(self.cover)
            self.store.update_user(self.sara, is_admin=0, is_supervisor=0)
        self.addCleanup(clean)

    def post(self, where, **more):
        return self.client.post(where, data={"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(),
                                             "view": "cover", **more}, follow_redirects=True).get_data(as_text=True)

    def today(self, days_after):
        self.app.config["TODAY"] = WED + timedelta(days=days_after)

    def everything_refused(self):
        pages = [self.post("/day/activity/cancel", id=str(self.ot)), self.post("/day/activity/cancel", id=str(self.call)),
                 self.post("/day/activity/cancel", id=str(self.aux)), self.post("/day/cover/cancel", id=str(self.cover)),
                 self.post("/day/undo-last"), self.post("/day/attendance", associate="Associate 008", status="Present"),
                 self.post("/day/break", associate="Associate 008", idx="0", at="12:00")]
        return [CLOSED in p for p in pages]


class TheEditWindow(_Window):
    def test_yesterday_and_today_can_be_changed(self):
        self.today(1)
        self.assertEqual(self.everything_refused(), [False] * 7)
        self.assertIsNone(self.store.get_activity(self.ot))
        self.assertIsNone(self.store.get_activity(self.call))
        self.assertIsNone(self.store.get_activity(self.aux))
        self.assertIsNone(self.store.get_cover(self.cover))

    def test_two_days_back_is_closed_for_every_change_and_the_page_says_so(self):
        self.today(2)
        self.assertEqual(self.everything_refused(), [True] * 7)
        for i in (self.ot, self.call, self.aux):
            self.assertIsNotNone(self.store.get_activity(i))
        self.assertIsNotNone(self.store.get_cover(self.cover))
        self.assertIn("1 day back", self.post("/day/undo-last"))

    def test_a_script_gets_the_refusal_as_json(self):
        self.today(5)
        got = self.client.post("/day/break", data={"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(),
                                                   "associate": "Associate 008", "idx": "0", "at": "12:00"},
                               headers={"Accept": "application/json"})
        self.assertEqual(got.status_code, 400)
        self.assertIn(CLOSED, got.get_json()["error"])

    def test_a_supervisor_has_7_days_and_an_admin_has_no_limit(self):
        self.store.update_user(self.sara, is_supervisor=1)
        self.today(7)
        self.assertEqual(self.everything_refused()[4], False)
        self.today(8)
        self.assertEqual(self.everything_refused()[4], True)
        self.store.update_user(self.sara, is_supervisor=0, is_admin=1)
        self.today(400)
        self.assertEqual(self.everything_refused()[4], False)

    def test_what_a_day_page_only_shows_is_not_held(self):
        self.today(30)
        got = self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), "view": "board"})
        self.assertEqual(got.status_code, 200)


class ThePcZone(_Window):
    """Today is counted in the zone the browser reports: at 12:00 UTC on 20 Oct it is already the 21st in Kiritimati (UTC+14) and
    still the 20th in Pago Pago (UTC-11)."""

    def at(self, zone):
        instant = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

        class Fixed(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz else instant

        self.app.config["TODAY"] = None
        self.client.set_cookie("pc_tz", zone)
        self.addCleanup(self.client.delete_cookie, "pc_tz")
        patch = mock.patch("webapp.app.datetime", Fixed)
        patch.start()
        self.addCleanup(patch.stop)

    def day_19(self):
        return self.client.post("/day/undo-last", data={"csrf_token": token(self.client), "program": self.key, "date": "2026-10-19",
                                                        "view": "cover"}, follow_redirects=True).get_data(as_text=True)

    def test_the_19th_is_closed_where_it_is_the_21st(self):
        self.at("Pacific/Kiritimati")
        self.assertIn(CLOSED, self.day_19())

    def test_the_19th_is_still_open_where_it_is_the_20th(self):
        self.at("Pacific/Pago_Pago")
        self.assertNotIn(CLOSED, self.day_19())

    def test_a_cookie_that_is_not_a_zone_falls_back_to_egypt(self):
        self.at("../../etc/passwd")
        self.assertNotIn(CLOSED, self.day_19())  # Egypt is the 20th at 15:00: the 19th is yesterday


if __name__ == "__main__":
    unittest.main()
