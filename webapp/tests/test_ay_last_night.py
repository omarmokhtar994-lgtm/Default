# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "I can't remove previous days call in or OT or if someone joined from outside the roster"): a shift that
began last night and runs into this day's morning keeps its overtime, call-in and cover under last night's date. Those showed on this day
(the timeline, the board) but the lists with a Delete button held only this day's own records, so they could be removed only by opening
yesterday's page. Now this day's lists also hold last night's that run past midnight, each with a Delete that acts on its own date and
brings the person back to this day. Made-up names."""
import html
import re
import unittest
from datetime import timedelta

from webapp.tests.test_overtime_side import NIGHT, WED, _Overtime
from webapp.tests.test_runs import token

THU = WED + timedelta(days=1)
LATE_COVER = "Made-up Support 03"


class TheRecordsOfLastNight(_Overtime):
    def setUp(self):
        # Associate 014 works Wed 21:00 to Thu 06:00: an hour of overtime after it is Wednesday's, 06:00 to 07:00 on Thursday
        self.ot = self.days.add_activity(self.key, WED, NIGHT, "Overtime", "06:00", "07:00", 1)
        letters = self.days.page(self.key, WED)["view"].get("channels")
        channel = next((r["letter"] for r in (letters or {}).get("rows", []) if "language" not in r), "")
        self.cover = self.days.add_cover(self.key, WED, LATE_COVER, "Support", "22:00", "02:00", 1, channel=channel)
        self.addCleanup(lambda: self.days.store.get_activity(self.ot) and self.days.cancel_activity(self.key, WED, self.ot, 1))
        self.addCleanup(lambda: self.days.store.get_cover(self.cover) and self.days.cancel_cover(self.key, WED, self.cover, 1))

    def page(self, view="cover"):
        got = self.client.get("/day", query_string={"program": self.key, "date": THU.isoformat(), "view": view})
        return html.unescape(got.get_data(as_text=True))

    def form_for(self, body, action, kind_id):
        found = re.search(r'<form[^>]*action="' + action + r'"[^>]*>(?:(?!</form>).)*name="id" value="' + str(kind_id) +
                          r'"(?:(?!</form>).)*</form>', body, re.S)
        return found.group(0) if found else ""

    def test_last_nights_overtime_is_listed_on_this_day_with_a_delete_for_its_own_date(self):
        form = self.form_for(self.page(), "/day/activity/cancel", self.ot)
        self.assertTrue(form, "no delete for last night's overtime on this day")
        self.assertIn(f'name="date" value="{WED.isoformat()}"', form)
        self.assertIn(f'name="anchor" value="{THU.isoformat()}"', form)  # back to the day the page showed

    def test_deleting_it_from_this_day_removes_it_and_returns_to_this_day(self):
        form = self.form_for(self.page(), "/day/activity/cancel", self.ot)
        data = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', form))
        got = self.client.post("/day/activity/cancel", data=data)
        self.assertEqual(got.status_code, 303)
        self.assertIn(f"date={THU.isoformat()}", got.headers["Location"])
        self.assertIsNone(self.days.store.get_activity(self.ot))

    def test_last_nights_cover_is_listed_with_a_delete_and_removed_from_this_day(self):
        body = self.page()
        form = self.form_for(body, "/day/cover/cancel", self.cover)
        self.assertTrue(form, "no delete for last night's cover on this day")
        self.assertIn(f'name="date" value="{WED.isoformat()}"', form)
        self.assertIn("Delete cover", form)
        data = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', form))
        got = self.client.post("/day/cover/cancel", data=data)
        self.assertIn(f"date={THU.isoformat()}", got.headers["Location"])
        self.assertEqual(self.days.covers(self.key, WED), [])

    def test_a_shift_that_ended_before_midnight_is_not_listed_on_the_next_day(self):
        got = self.days.add_activity(self.key, WED, "Associate 008", "Training", "15:00", "15:30", 1, with_whom="Lina", why="Fixture")  # was a VTO (Phase AY)
        self.addCleanup(lambda: self.days.store.get_activity(got) and self.days.cancel_activity(self.key, WED, got, 1))
        self.assertFalse(self.form_for(self.page(), "/day/activity/cancel", got))


if __name__ == "__main__":
    unittest.main()
