# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU (owner, 2026-10-21): an associate can see the rest of the week's breaks and ask to move a break for today and
tomorrow, no later. The clock is stopped on Wednesday 14 October 2026 at 12:00 Cairo time."""
import json
import re
import unittest
from datetime import timedelta

from webapp.tests.test_as_pages import _Pages
from webapp.tests.test_as_requests import ME, THU, WED, at


class TheNextDay(_Pages):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        thu = cls.app.extensions["days"].version(cls.key, THU)[0]
        week = json.loads(thu["week"])
        week["breaks"] += [{"associate": ME, "day": "Thu", "kind": "Break 1", "start": "13:00", "minutes": 15},
                           {"associate": ME, "day": "Thu", "kind": "Lunch", "start": "15:00", "minutes": 30}]
        cls.store.update_schedule(thu["id"], week=json.dumps(week))

    def test_the_day_page_lists_tomorrows_breaks_with_a_way_to_change_them(self):
        page = self.get(self.assoc, "/me/breaks")
        self.assertIn("Tomorrow, Thursday", page)
        self.assertRegex(page, r'href="/me/breaks\?day=tomorrow&change=0')

    def test_choosing_a_break_for_tomorrow_offers_times_across_the_whole_shift(self):
        page = self.get(self.assoc, "/me/breaks", day="tomorrow", change=0)
        self.assertIn("Move Break 1 tomorrow (now 13:00", page)
        times = re.findall(r'name="to" value="([0-9:]+)"', page)
        self.assertIn("11:30", times)       # not held back by the clock: tomorrow's shift has not started
        self.assertRegex(page, r'name="day" value="tomorrow"')

    def test_a_request_for_tomorrow_is_kept_for_tomorrow_and_the_rta_moves_that_day(self):
        page = self.get(self.assoc, "/me/breaks", day="tomorrow", change=0)
        to = re.findall(r'name="to" value="([0-9:]+)"(?! disabled)', page)[0]
        self.post(self.assoc, "/me/breaks", idx=0, to=to, day="tomorrow")
        row = self.store.list_change_requests()[-1]
        self.assertEqual(row["shift_date"], THU.isoformat())
        self.post(self.staff, f"/requests/change/{row['id']}", decision="approve")
        self.assertEqual(self.store.get_change_request(row["id"])["status"], "approved")
        moved = self.app.extensions["days"].page(self.key, THU)
        seg = next(s for lane in moved["view"]["lanes"] if lane["name"] == ME for s in lane["segments"] if s["offset"] == 0)
        self.assertEqual(f"{seg['breaks'][0]['start'] // 60:02d}:{seg['breaks'][0]['start'] % 60:02d}", to)

    def test_the_rta_sees_tomorrows_request_with_its_impact_and_the_date(self):
        page = self.get(self.assoc, "/me/breaks", day="tomorrow", change=0)
        to = re.findall(r'name="to" value="([0-9:]+)"(?! disabled)', page)[0]
        self.post(self.assoc, "/me/breaks", idx=0, to=to, day="tomorrow")
        rta = self.get(self.staff, "/day", program=self.key, date="2026-10-14", view="requests")
        self.assertIn("Thu 15 Oct", rta)
        self.assertIn("After this change", rta)
        self.assertNotIn("cannot be worked out", rta)

    def test_a_request_for_the_day_after_tomorrow_is_refused_by_the_book(self):
        book = self.app.extensions["changes"]
        user = self.store.get_user(self.me["id"])
        with self.assertRaises(ValueError):
            book.ask_break(self.key, ME, user, 0, "11:30", "", at(WED, 12), on=WED + timedelta(days=2))

    def test_the_weeks_tab_shows_the_breaks_of_the_rest_of_the_week(self):
        weeks = self.get(self.assoc, "/me")
        thu = weeks[weeks.index("Thu 15 Oct"):]
        self.assertIn("Break 1 13:00 to 13:15", thu[:400])


if __name__ == "__main__":
    unittest.main()
