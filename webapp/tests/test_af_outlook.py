# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, F3 and F4: absences already known for later days, and the rest of the week (owner, 2026-10-14).

- F3: the RTA records unplanned leave, sick or public holiday for later days, from one day to another; a day the
  person does not work is said, not recorded.
- F4: the Week page shows, for each day still to come, the known absences, the hours short, the overtime needed and
  the days off to cancel (Rescue the day's proposals for that day).
"""
import datetime as dt
import unittest
from unittest import mock

from webapp.tests.test_channel_day import WED, _Day

THU, SAT = WED + dt.timedelta(days=1), WED + dt.timedelta(days=3)


class LaterDays(_Day):
    def test_sick_for_the_rest_of_the_week(self):
        found = self.days.record_absences(self.key, "Associate 001", "Sick", THU, SAT, self.omar)
        self.assertEqual(found["done"], [THU, THU + dt.timedelta(days=1)])
        self.assertEqual(found["off"], [SAT])  # Associate 001 is off on Saturday
        seg = next(s for lane in self.days.page(self.key, THU)["view"]["lanes"] if lane["name"] == "Associate 001"
                   for s in lane["segments"] if s["offset"] == 0)
        self.assertEqual(seg["status"], "Sick")

    def test_refused(self):
        # re-pinned in Phase AI: the owner added exam leave (2026-10-15)
        for status, first, last, said in (("Late", THU, THU, "unplanned leave, sick, public holiday or exam leave"),
                                          ("Sick", SAT, THU, "The last day must be on or after the first"),
                                          ("Sick", THU, THU + dt.timedelta(days=15), "14 days at most")):
            with self.subTest(status=status, last=last), self.assertRaisesRegex(ValueError, said):
                self.days.record_absences(self.key, "Associate 001", status, first, last, self.omar)

    def test_the_rest_of_the_week(self):
        self.days.record_absences(self.key, "Associate 001", "Sick", THU, THU, self.omar)
        rows = self.days.outlook(self.key, dt.date(2026, 10, 11), today=WED)
        self.assertEqual([r["date"] for r in rows], [THU, THU + dt.timedelta(days=1), SAT])
        self.assertEqual(rows[0]["absent"], ["Associate 001 (sick)"])
        for key in ("short_hours", "short_intervals", "overtime", "dayoff"):
            self.assertIn(key, rows[0])

    def test_a_week_that_is_over_or_to_come(self):
        self.assertEqual(self.days.outlook(self.key, dt.date(2026, 10, 11), today=dt.date(2026, 10, 20)), [])
        self.assertEqual(len(self.days.outlook(self.key, dt.date(2026, 10, 11), today=dt.date(2026, 10, 1))), 7)


class _Clock(dt.datetime):
    """The website's clock stopped on Wednesday 14 October 2026 at 10:00 Egypt time."""

    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 10, 14, 10, 0, tzinfo=tz)


class OnThePages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def test_the_rta_records_later_absences(self):
        page = self.admin.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}").get_data(as_text=True)
        self.assertIn("Absences known for later days", page)
        got = self.admin.post("/day/absences", data={"csrf_token": self.token(self.admin), "program": self.key,
                                                      "date": WED.isoformat(), "associate": "Associate 002",
                                                      "status": "Unplanned leave", "first": THU.isoformat(),
                                                      "last": THU.isoformat()})
        self.assertEqual(got.status_code, 303)
        shown = self.admin.get(got.headers["Location"]).get_data(as_text=True)
        self.assertIn("Associate 002 is off on Thu 15 Oct", shown)  # Associate 002 is off on Thursday

    def test_the_week_page_shows_the_rest_of_the_week(self):
        with mock.patch("webapp.app.datetime", _Clock):
            page = self.admin.get(f"/week?program={self.key.replace(' ', '+')}&week=2026-10-11").get_data(as_text=True)
        self.assertIn('aria-labelledby="out-h"', page)
        self.assertIn("The rest of the week", page)
        self.assertIn("Thu 15 Oct", page)
        self.assertNotIn("Tue 13 Oct</th>", page)


if __name__ == "__main__":
    unittest.main()
