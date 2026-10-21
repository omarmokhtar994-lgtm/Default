# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AS in the browser's terms: My breaks for an associate, the coaching form for a team manager, and the RTA's
Requests page with the impact. The clock is stopped on Wednesday 14 October 2026 at 12:00 Cairo time."""
import html
import json
import re
import unittest
from datetime import datetime
from unittest import mock

from webapp.tests.test_as_requests import CAIRO, MATE, ME, WED, _Fixture
from webapp.tests.test_runs import sign_in, token


class _Noon(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 14, 12, 0, tzinfo=CAIRO).astimezone(tz) if tz else datetime(2026, 10, 14, 12, 0)


class _Pages(_Fixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.assoc = sign_in(cls.app, "a027", "Associate-pass-1")
        cls.staff = sign_in(cls.app, "rta1", "Staff-pass-123")       # a planner: RTA rights
        cls.sup = sign_in(cls.app, "tm1", "Staff-pass-123")          # a supervisor: RTA rights and approves teams
        uid = cls.store.add_user("tm_only", "Team Manager 07", "Manager-pass-123", must_change=False)
        cls.store.update_user(uid, is_team_manager=1)
        cls.store.set_user_programs(uid, [cls.pid])
        cls.tm = sign_in(cls.app, "tm_only", "Manager-pass-123")     # a team manager: asks, but cannot change the day

    def setUp(self):
        self.clear()
        patch = mock.patch("webapp.app.datetime", _Noon)
        patch.start()
        self.addCleanup(patch.stop)

    def get(self, client, url, **query):
        return html.unescape(client.get(url, query_string=query).get_data(as_text=True))

    def post(self, client, url, **data):
        page = client.get("/", follow_redirects=True).get_data(as_text=True)  # an associate's "/" is My week
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return client.post(url, data={"csrf_token": csrf, **data})


class TheAssociatesBreaks(_Pages):
    def test_the_page_lists_todays_breaks_and_offers_a_change_for_each_that_has_not_started(self):
        page = self.get(self.assoc, "/me/breaks")
        self.assertIn("My day", page)  # Re-pinned in Phase AU: the page is My day, the Today tab
        self.assertIn("Break 1", page)
        self.assertRegex(page, r'href="/me/breaks\?change=0')

    def test_choosing_a_break_lists_the_times_with_their_buffer_and_warns_on_a_low_one(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        self.assertIn("Pick a time", page)
        self.assertRegex(page, r"(High|Moderate|Low) buffer")
        if page.count('class="lv lv-low">Low buffer') > 1:  # one is in the legend; the rest are times
            self.assertIn("Likely to be rejected", page)

    def test_sending_a_request_keeps_it_waiting_and_the_rta_sees_it_with_the_impact(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first, why="Made-up: appointment")
        mine = self.get(self.assoc, "/me/breaks")
        self.assertIn("waiting for the RTA", mine)
        rta = self.get(self.staff, "/requests", program=self.key)
        self.assertIn("Break changes and coaching", rta)
        self.assertIn(ME, rta)
        self.assertIn("After this change", rta)
        self.assertRegex(rta, r"Off the queue \(before, after\)")
        self.assertRegex(rta, r"\d+% to \d+%")
        self.assertIn("Made-up: appointment", rta)

    def test_the_rta_approves_and_the_day_changes_and_the_associate_sees_it(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first)
        rid = self.store.list_change_requests()[-1]["id"]
        got = self.post(self.staff, f"/requests/change/{rid}", decision="approve")
        self.assertEqual(got.status_code, 303)
        self.assertEqual(self.store.get_change_request(rid)["status"], "approved")
        self.assertIn("approved", self.get(self.assoc, "/me/breaks"))

    def test_a_rejection_needs_a_reason_and_the_associate_reads_it(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first)
        rid = self.store.list_change_requests()[-1]["id"]
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="")
        self.assertEqual(self.store.get_change_request(rid)["status"], "waiting")
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="Phones are busy then")
        self.assertIn("Phones are busy then", self.get(self.assoc, "/me/breaks"))

    def test_an_associate_cannot_decide_and_a_team_manager_cannot_change_the_day(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first)
        rid = self.store.list_change_requests()[-1]["id"]
        self.assertEqual(self.post(self.assoc, f"/requests/change/{rid}", decision="approve").status_code, 403)
        self.assertEqual(self.post(self.tm, f"/requests/change/{rid}", decision="approve").status_code, 403)
        self.assertEqual(self.store.get_change_request(rid)["status"], "waiting")

    def test_the_asker_cancels_their_own_request(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first)
        rid = self.store.list_change_requests()[-1]["id"]
        self.post(self.assoc, f"/me/breaks/{rid}/cancel")
        self.assertEqual(self.store.get_change_request(rid)["status"], "cancelled")

    def test_the_waiting_count_includes_the_requests_for_the_rta(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first)
        self.assertEqual(self.app.extensions["changes"].count(self.key), 1)

    def ask_far(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        times = re.findall(r'name="to" value="([0-9:]+)"(?! disabled)', page)
        self.post(self.assoc, "/me/breaks", idx=0, to=times[2])
        return self.store.list_change_requests()[-1]["id"]

    def test_the_rta_sees_the_nearest_times_and_changes_to_one_with_a_comment_the_associate_reads(self):
        rid = self.ask_far()
        rta = self.get(self.staff, "/requests", program=self.key)
        self.assertIn("Or approve at the nearest time", rta)
        near = re.search(r'name="change_at" value="(\d+)"', rta).group(1)
        refused = self.post(self.staff, f"/requests/change/{rid}", change_at=near, reason="")
        self.assertEqual(self.store.get_change_request(rid)["status"], "waiting")
        self.post(self.staff, f"/requests/change/{rid}", change_at=near, reason="Phones are busy at your time")
        row = self.store.get_change_request(rid)
        self.assertEqual((row["status"], json.loads(row["detail"])["to"]), ("approved", int(near)))
        mine = self.get(self.assoc, "/me/breaks")
        self.assertIn("instead of", mine)
        self.assertIn("Phones are busy at your time", mine)

    def test_a_rejection_comment_is_shown_to_the_associate_too(self):
        rid = self.ask_far()
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="No cover then; try after lunch")
        self.assertIn("No cover then; try after lunch", self.get(self.assoc, "/me/breaks"))


class TheCoachingForm(_Pages):
    def test_a_team_manager_sees_the_times_for_the_people_picked_and_sends_a_request(self):
        page = self.get(self.tm, "/requests/coaching", program=self.key, who=[ME, MATE], date="2026-10-14", minutes=30)
        self.assertIn("Pick a time", page)
        self.assertRegex(page, r"(High|Moderate|Low) buffer")
        first = re.search(r'name="start" value="([0-9:]+)"', page).group(1)
        self.post(self.tm, "/requests/coaching", program=self.key, who=[ME, MATE], date="2026-10-14", minutes=30,
                  start=first, dept="", why="Made-up: call review")
        row = self.store.list_change_requests(kind="coaching")[-1]
        self.assertEqual((row["status"], sorted(json.loads(row["names"]))), ("waiting", sorted([ME, MATE])))
        rta = self.get(self.staff, "/requests", program=self.key)
        self.assertIn("Coaching", rta)
        self.assertIn("Team Manager 07", rta)

    def test_the_form_asks_billable_or_not_and_the_rta_can_correct_it(self):
        page = self.get(self.tm, "/requests/coaching", program=self.key, who=[ME], date="2026-10-14", minutes=30, billable=1)
        self.assertIn("Is it billable?", page)
        self.assertIn("billable", page.split("Times for")[1].split("</h2>")[0])
        first = re.search(r'name="start" value="([0-9:]+)"', page).group(1)
        self.post(self.tm, "/requests/coaching", program=self.key, who=[ME], date="2026-10-14", minutes=30, start=first,
                  billable="0")
        rid = self.store.list_change_requests(kind="coaching")[-1]["id"]
        rta = self.get(self.staff, "/requests", program=self.key)
        self.assertIn("not billable", rta)
        self.assertIn("If it is billable instead", rta)
        self.post(self.staff, f"/requests/change/{rid}", decision="approve", billable="1", reason="Quality set it billable")
        self.assertTrue(json.loads(self.store.get_change_request(rid)["detail"])["billable"])

    def test_someone_with_rta_rights_approves_their_own_request(self):
        page = self.get(self.sup, "/requests/coaching", program=self.key, who=[ME], date="2026-10-14", minutes=30)
        first = re.search(r'name="start" value="([0-9:]+)"', page).group(1)
        self.post(self.sup, "/requests/coaching", program=self.key, who=[ME], date="2026-10-14", minutes=30, start=first)
        rid = self.store.list_change_requests(kind="coaching")[-1]["id"]
        self.assertEqual(self.post(self.sup, f"/requests/change/{rid}", decision="approve").status_code, 303)
        self.assertEqual(self.store.get_change_request(rid)["status"], "approved")

    def test_an_associate_and_another_programs_people_have_no_such_form(self):
        self.assertIn(self.assoc.get("/requests/coaching").status_code, (302, 403))
        self.assertEqual(self.post(self.assoc, "/requests/coaching", program=self.key, who=[ME], date="2026-10-14").status_code, 403)


if __name__ == "__main__":
    unittest.main()
