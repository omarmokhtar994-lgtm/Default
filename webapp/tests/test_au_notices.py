# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: when the RTA decides a break change or coaching request, the person who asked is told in the site: a count
on their menu and a banner with the answer and the comment, until they have looked at it. Someone deciding their own
request, or cancelling it, is not told about it."""
import re
import unittest

from webapp.tests.test_as_pages import _Pages
from webapp.tests.test_as_requests import ME, MATE, WED


class TheNotices(_Pages):
    def ask_break(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        to = re.findall(r'name="to" value="([0-9:]+)"(?! disabled)', page)[0]
        self.post(self.assoc, "/me/breaks", idx=0, to=to)
        return self.store.list_change_requests()[-1]["id"]

    def ask_coaching(self):
        self.post(self.tm, "/requests/coaching", program=self.key, date="2026-10-14", start="14:00", minutes="30",
                  dept="Quality", why="Made-up", who=[ME, MATE])
        return self.store.list_change_requests()[-1]["id"]

    def test_a_rejection_shows_on_the_menu_and_as_a_banner_until_it_is_seen(self):
        rid = self.ask_break()
        self.assertNotRegex(self.get(self.assoc, "/me"), r'My day <span class="count"')
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="Phones are busy then")
        weeks = self.get(self.assoc, "/me")
        self.assertRegex(weeks, r'My day <span class="count"[^>]*>1</span>')
        today = self.get(self.assoc, "/me/breaks")
        self.assertIn("New answer", today)
        self.assertIn("Phones are busy then", today)
        again = self.get(self.assoc, "/me")
        self.assertNotRegex(again, r'My day <span class="count"')
        self.assertNotIn("New answer", self.get(self.assoc, "/me/breaks"))

    def test_an_approval_is_an_answer_too(self):
        rid = self.ask_break()
        self.post(self.staff, f"/requests/change/{rid}", decision="approve")
        self.assertIn("New answer", self.get(self.assoc, "/me/breaks"))

    def test_the_team_manager_is_told_about_their_coaching_request(self):
        rid = self.ask_coaching()
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="Not that day")
        page = self.get(self.tm, "/requests/coaching", program=self.key)
        self.assertIn("New answer", page)
        self.assertIn("Not that day", page)
        self.assertNotIn("New answer", self.get(self.tm, "/requests/coaching", program=self.key))

    def test_cancelling_your_own_request_is_not_news(self):
        rid = self.ask_break()
        self.post(self.assoc, f"/me/breaks/{rid}/cancel")
        self.assertNotIn("New answer", self.get(self.assoc, "/me/breaks"))

    def test_the_rta_deciding_their_own_request_is_not_news_to_them(self):
        self.post(self.staff, "/requests/coaching", program=self.key, date="2026-10-14", start="14:00", minutes="30",
                  dept="Quality", why="Made-up", who=[ME])
        rid = self.store.list_change_requests()[-1]["id"]
        self.post(self.staff, f"/requests/change/{rid}", decision="approve")
        self.assertNotIn("New answer", self.get(self.staff, "/requests/coaching", program=self.key))


if __name__ == "__main__":
    unittest.main()


class TheGroupMessages(TheNotices):
    """Owner, 2026-10-21: "message on Slack/Teams same as the changes being done now": the LOB's group is told how a
    break change or coaching request was answered, in the same posts as the RTA's changes."""
    def setUp(self):
        super().setUp()
        from webapp.notify import DEFAULT_KINDS
        with self.store._db() as db:
            db.execute("delete from notify_items")
        self.store.set_notify(self.key, link="https://hooks.slack.com/services/T000/B000/xxxxxxxxxxxxxxxxxxxxxxxx",
                              service="slack", mode="on", kinds=",".join(DEFAULT_KINDS), hold=0)

    def said(self):
        return [i for i in self.store.notify_items(unit=self.key) if i["kind"] == "request"]

    def test_the_kind_exists_and_is_on_by_default(self):
        from webapp.notify import DEFAULT_KINDS, KINDS
        self.assertEqual(KINDS["request"], "Answers to break change and coaching requests")
        self.assertIn("request", DEFAULT_KINDS)

    def test_a_rejection_is_posted_with_its_reason(self):
        rid = self.ask_break()
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="Phones are busy then")
        (item,) = self.said()
        self.assertEqual(item["associate"], ME)
        self.assertIn("rejected", item["text"])
        self.assertIn("Phones are busy then", item["text"])
        self.assertEqual(item["status"], "waiting")

    def test_a_plain_break_approval_is_only_the_move_the_rta_made(self):
        rid = self.ask_break()
        self.post(self.staff, f"/requests/change/{rid}", decision="approve")
        self.assertEqual(self.said(), [])
        self.assertTrue([i for i in self.store.notify_items(unit=self.key) if i["kind"] == "break"])

    def test_an_approval_at_another_time_says_so_with_the_comment(self):
        page = self.get(self.assoc, "/me/breaks", change=0)
        times = re.findall(r'name="to" value="([0-9:]+)"(?! disabled)', page)
        self.post(self.assoc, "/me/breaks", idx=0, to=times[2])
        rid = self.store.list_change_requests()[-1]["id"]
        rta = self.get(self.staff, "/requests", program=self.key)
        near = re.search(r'name="change_at" value="(\d+)"', rta).group(1)
        self.post(self.staff, f"/requests/change/{rid}", change_at=near, reason="Phones are busy at your time")
        (item,) = self.said()
        self.assertIn("instead of", item["text"])
        self.assertIn("Phones are busy at your time", item["text"])

    def test_a_coaching_answer_is_posted_for_each_person(self):
        rid = self.ask_coaching()
        self.post(self.staff, f"/requests/change/{rid}", decision="approve")
        texts = [i["text"] for i in self.said()]
        self.assertEqual(len(texts), 2)
        self.assertTrue(all("Coaching" in t and "approved" in t for t in texts))
        self.assertEqual({i["associate"] for i in self.said()}, {ME, MATE})

    def test_a_lob_that_unticked_it_posts_nothing(self):
        from webapp.notify import DEFAULT_KINDS
        self.store.set_notify(self.key, kinds=",".join(k for k in DEFAULT_KINDS if k != "request"))
        rid = self.ask_break()
        self.post(self.staff, f"/requests/change/{rid}", decision="reject", reason="No")
        self.assertEqual([i["status"] for i in self.said()], ["skipped"])
