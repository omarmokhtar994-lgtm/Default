# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU (owner, 2026-10-21): the RTA decides break changes and coaching on the RTA tab itself (no switching to the
Requests page), and an associate has two tabs: Today (the day, the breaks, asking to move one) and Weeks (the week
and the weeks after it, leave, swaps)."""
import re
import unittest

from webapp.tests.test_as_pages import _Pages
from webapp.tests.test_runs import sign_in


class TheRtaTab(_Pages):
    def ask(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first, why="Made-up: appointment")
        return self.store.list_change_requests()[-1]["id"]

    def test_the_rta_tab_has_a_requests_view_with_the_count_and_the_decision_controls(self):
        rid = self.ask()
        day = self.get(self.staff, "/day", program=self.key, date="2026-10-14")
        self.assertRegex(day, r'>Requests <span class="count">1</span>')
        tab = self.get(self.staff, "/day", program=self.key, date="2026-10-14", view="requests")
        self.assertIn("Break changes and coaching", tab)
        self.assertIn("Made-up: appointment", tab)
        self.assertIn("Approve as asked", tab)
        self.assertIn(f"/requests/change/{rid}", tab)
        self.assertRegex(tab, r'name="back" value="/day\?')

    def test_deciding_from_the_tab_comes_back_to_the_tab(self):
        rid = self.ask()
        got = self.post(self.staff, f"/requests/change/{rid}", decision="approve",
                        back=f"/day?program={self.key.replace(' ', '+')}&date=2026-10-14&view=requests")
        self.assertEqual(got.status_code, 303)
        self.assertIn("view=requests", got.headers["Location"])
        self.assertEqual(self.store.get_change_request(rid)["status"], "approved")

    def test_a_back_address_off_the_site_is_ignored(self):
        rid = self.ask()
        got = self.post(self.staff, f"/requests/change/{rid}", decision="approve", back="https://evil.example/x")
        self.assertTrue(got.headers["Location"].startswith("/requests"))

    def test_the_tab_is_for_one_lob_so_the_merged_view_sends_you_to_the_timeline(self):
        got = self.staff.get("/day", query_string={"program": self.key, "date": "2026-10-14", "view": "requests",
                                                   "merge": "1"})
        self.assertIn(got.status_code, (200, 303))
        if got.status_code == 303:
            self.assertNotIn("view=requests", got.headers["Location"])

    def test_someone_who_cannot_change_the_day_sees_the_list_without_the_buttons(self):
        self.ask()
        tab = self.get(self.tm, "/day", program=self.key, date="2026-10-14", view="requests")
        self.assertNotIn("Approve as asked", tab)


class TheAssociatesTabs(_Pages):
    def test_both_pages_carry_the_two_tabs(self):
        for url, here in (("/me/breaks", "Today"), ("/me", "Weeks")):
            page = self.get(self.assoc, url)
            self.assertRegex(page, r'<nav class="tabs" aria-label="My pages">')
            self.assertRegex(page, rf'class="on" aria-current="page">{here}</a>')
            self.assertIn(">Today</a>", page)
            self.assertIn(">Weeks</a>", page)

    def test_today_holds_the_shift_the_breaks_and_the_requests_and_weeks_does_not_hold_today(self):
        today = self.get(self.assoc, "/me/breaks")
        self.assertIn("Your shift", today)
        self.assertIn("Break 1", today)
        weeks = self.get(self.assoc, "/me")
        self.assertIn("The week", weeks)
        self.assertIn("Request leave", weeks)
        self.assertNotIn('id="today-h"', weeks)

    def test_an_associate_lands_on_today(self):
        got = self.assoc.get("/")
        self.assertEqual(got.status_code, 302)
        self.assertTrue(got.headers["Location"].endswith("/me/breaks"))

    def test_the_menu_names_the_two_pages(self):
        page = self.get(self.assoc, "/me")
        self.assertRegex(page, r'(?s)<nav aria-label="Main">.*My day.*My weeks')


class ThePolish(_Pages):
    def test_the_coaching_list_has_a_search_box_and_scrolls(self):
        page = self.get(self.tm, "/requests/coaching", program=self.key)
        self.assertIn('data-filter="coach-list"', page)
        self.assertIn('id="coach-list"', page)
        self.assertIn("pick-list", page)

    def test_a_break_request_reads_as_a_move(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
        self.post(self.assoc, "/me/breaks", idx=0, to=first)
        self.assertRegex(self.get(self.assoc, "/me/breaks"), r"Break 1, move from 13:00 to \d\d:\d\d")


if __name__ == "__main__":
    unittest.main()
