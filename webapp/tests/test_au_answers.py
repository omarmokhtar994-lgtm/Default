# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: the answer to a leave request or a swap reaches the person who asked in the site (a count on My weeks and a
banner, once) and the LOB's group, as break and coaching answers do. Only a final answer counts: refused, approved,
declined; "the TM approved, the RTA decides next" is shown on the page already."""
import re
import unittest

from webapp.tests.test_as_pages import _Pages
from webapp.tests.test_as_requests import ME, WED


class TheLeaveAndSwapAnswers(_Pages):
    def setUp(self):
        super().setUp()
        from webapp.notify import DEFAULT_KINDS
        with self.store._db() as db:
            db.execute("delete from notify_items")
            db.execute("delete from leave_requests")
            db.execute("delete from swap_requests")
        self.store.set_notify(self.key, link="https://hooks.slack.com/services/T000/B000/xxxxxxxxxxxxxxxxxxxxxxxx",
                              service="slack", mode="on", kinds=",".join(DEFAULT_KINDS), hold=0)

    def ask_leave(self):
        self.post(self.assoc, "/me/leave", kind="Planned leave", first="2026-10-15", last="2026-10-15", note="")
        return self.store.list_leave()[-1]["id"]

    def said(self):
        return [i for i in self.store.notify_items(unit=self.key) if i["kind"] == "request"]

    def test_a_refusal_shows_on_the_menu_and_as_a_banner_once_and_goes_to_the_group(self):
        rid = self.ask_leave()
        self.assertNotRegex(self.get(self.assoc, "/me"), r'My weeks <span class="count"')
        self.post(self.sup, f"/requests/leave/{rid}", decision="refuse", reason="Busy week")
        self.assertEqual(self.store.get_leave(rid)["status"], "refused")
        self.assertRegex(self.get(self.assoc, "/me/breaks"), r'My weeks <span class="count"[^>]*>1</span>')
        weeks = self.get(self.assoc, "/me")
        self.assertIn("New answer", weeks)
        self.assertIn("Busy week", weeks)
        self.assertNotIn("New answer", self.get(self.assoc, "/me"))
        (item,) = self.said()
        self.assertEqual(item["associate"], ME)
        self.assertIn("Planned leave", item["text"])
        self.assertIn("refused", item["text"])
        self.assertIn("Busy week", item["text"])

    def test_the_first_step_is_not_news(self):
        rid = self.ask_leave()
        self.post(self.sup, f"/requests/leave/{rid}", decision="approve")           # the TM approves; the RTA decides next
        if self.store.get_leave(rid)["status"] == "waiting_rta":
            self.assertNotIn("New answer", self.get(self.assoc, "/me"))
            self.assertEqual(self.said(), [])

    def test_cancelling_your_own_leave_is_not_news(self):
        rid = self.ask_leave()
        self.post(self.assoc, f"/me/leave/{rid}/cancel")
        self.assertNotIn("New answer", self.get(self.assoc, "/me"))

    def test_a_refused_swap_is_news_to_the_one_who_offered_it(self):
        swap = self.store.add_swap(program=self.key, day="2026-10-16", asker=ME, asker_user=self.me["id"],
                                   other="Associate 012", asker_cell="11:00 - 20:00", other_cell="09:00 - 18:00",
                                   status="waiting_tm")
        self.app.extensions["swaps"].decide(swap, self.store.get_user(self.users["tm1"]["id"]), False, "Not that day")
        weeks = self.get(self.assoc, "/me")
        self.assertIn("New answer", weeks)
        self.assertIn("Associate 012", weeks)
        self.assertIn("Not that day", weeks)
        self.assertTrue([i for i in self.said() if "Swap" in i["text"]])


if __name__ == "__main__":
    unittest.main()
