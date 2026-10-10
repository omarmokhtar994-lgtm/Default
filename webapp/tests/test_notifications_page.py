# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AB (approved sample 02): the Notifications page. Admins paste each LOB's Teams or Slack group link once; it is
kept on the server and only its last four characters are shown again, anywhere. They set what posts, how long changes
wait, send a test message, remove the link, and see the last posts with their result."""
import html
import json
import re
import time
import unittest
from dataclasses import asdict

from webapp.notify import NOT_GROUP, Post
from webapp.programs import ProgramBook
from webapp.tests.test_notify_sender import Group
from webapp.tests.test_runs import make_app, sign_in, token

SLACK = "https://hooks.slack.com/services/T0000/B0000/abcdEFGHijkl"
SECRET = "abcdEFGH"  # the part of the link that must never come back


class _Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.group = Group()
        cls.app, cls.store, *_ = make_app(NOTIFY_THREAD=False, NOTIFY_TRANSPORT=cls.group)
        cls.omar = cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)
        programs = ProgramBook(cls.store)
        saks = programs.add_program("SAKS")
        cls.key = programs.add_lob(saks, "NMG Tier 2")
        cls.other = programs.add_lob(saks, "NMG Tier 9")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.nour = sign_in(cls.app, "nour", "Nour-pass-123")

    def text(self, got):
        return html.unescape(got.get_data(as_text=True))

    def page(self, unit=None):
        got = self.client.get("/notifications" + (f"?unit={unit.replace(' ', '+')}" if unit else ""))
        self.assertEqual(got.status_code, 200)
        return self.text(got)

    def save(self, unit=None, client=None, **form):
        client = client or self.client
        data = {"csrf_token": token(client), "unit": unit or self.key, "mode": "on", "hold": "120",
                "kinds": ["break", "added_break", "overtime", "called_in", "channel"], "morning": "",
                "morning_day": "same", **form}
        return client.post("/notifications", data=data, follow_redirects=True)


class TheAccess(_Page):
    def test_only_admins(self):
        for url, method in (("/notifications", "get"), ("/notifications", "post"), ("/notifications/test", "post"),
                            ("/notifications/remove", "post")):
            data = {"csrf_token": token(self.nour), "unit": self.key}
            got = self.nour.get(url) if method == "get" else self.nour.post(url, data=data)
            self.assertEqual(got.status_code, 403, (url, method))
        self.assertNotIn('href="/notifications"', self.text(self.nour.get("/")))
        self.assertIn('href="/notifications"', self.text(self.client.get("/")))


class TheLink(_Page):
    def test_save_a_slack_link_then_it_is_masked(self):
        got = self.save(link=SLACK)
        page = self.text(got)
        self.assertIn("Notifications saved for SAKS, NMG Tier 2.", page)
        self.assertIn("Ends in …ijkl. Saved", page)
        self.assertIn("by Omar Mokhtar. Kept on this server; never shown again in full.", page)
        self.assertNotIn(SECRET, page)
        saved = self.store.get_notify(self.key)
        self.assertEqual((saved["link"], saved["service"], saved["mode"]), (SLACK, "slack", "on"))
        self.assertEqual(saved["site"], "http://localhost/")
        # Final review (Phase AB): the link field is not a password field, so no browser offers to keep the link in
        # its password manager (which syncs it off the server); autocomplete="off" keeps it out of form history.
        field = re.search(r'<input[^>]*name="link"[^>]*>', page).group(0)
        self.assertNotIn('type="password"', field)
        self.assertIn('type="text"', field)
        self.assertIn('autocomplete="off"', field)
        for event in self.store.list_events(0, 4e9):
            self.assertNotIn(SECRET, json.dumps(event))
        said = [e for e in self.store.list_events(0, 4e9) if e["kind"] == "notify_saved"]
        self.assertEqual(said[-1]["subject"], "SAKS, NMG Tier 2")
        exported = self.client.get("/exports/download?kind=record&from=2026-01-01&to=2026-12-31&format=csv")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("Notifications changed", exported.get_data(as_text=True))
        self.assertNotIn(SECRET, exported.get_data(as_text=True))
        # saving again without pasting keeps the link
        self.save(mode="preview")
        self.assertEqual(self.store.get_notify(self.key)["link"], SLACK)

    def test_bad_link_refused_and_nothing_saved(self):
        page = self.text(self.save(unit=self.other, link="https://example.com/hook"))
        self.assertIn(NOT_GROUP, page)
        self.assertIsNone(self.store.get_notify(self.other))
        self.assertNotIn("example.com/hook", page)

    def test_on_without_link_refused(self):
        page = self.text(self.save(unit=self.other))
        self.assertIn("Paste the group link first, or leave posting Off.", page)
        self.assertIsNone(self.store.get_notify(self.other))
        self.save(unit=self.other, mode="off")
        self.assertEqual(self.store.get_notify(self.other)["mode"], "off")


class TheRule(_Page):
    def test_rule_saved(self):
        self.save(link=SLACK, mode="preview", kinds=["break", "aux"], hold="300", morning="07:30",
                  morning_day="before")
        saved = self.store.get_notify(self.key)
        self.assertEqual((saved["mode"], saved["kinds"], saved["hold"], saved["morning"], saved["morning_day"]),
                         ("preview", "break,aux", 300, "07:30", "before"))
        page = self.page(self.key)
        self.assertRegex(page, r'<input type="radio" name="mode" value="preview" checked>')
        self.assertRegex(page, r'<input type="checkbox" name="kinds" value="aux" checked>')
        self.assertRegex(page, r'<input type="checkbox" name="kinds" value="overtime">')
        self.assertIn('<option value="300" selected>5 minutes</option>', page)
        self.assertRegex(page, r'<input type="time" name="morning" value="07:30"')
        self.assertIn('<option value="before" selected>The evening before</option>', page)
        self.assertIn("Never posted: sick and unplanned leave, attendance set back to present, and the why of any aux.",
                      page)
        bad = self.text(self.save(morning="7.30"))
        self.assertIn("Pick a time like 07:30, or leave it empty.", bad)

    def test_every_lob_listed(self):
        page = self.page()
        table = re.search(r'(?s)<table class="nf-lobs".*?</table>', page).group(0)
        self.assertIn("SAKS, NMG Tier 2", table)
        self.assertIn("SAKS, NMG Tier 9", table)


class TheTestMessage(_Page):
    def test_send_test_message(self):
        self.save(link=SLACK)
        before = len(self.group.calls)
        got = self.client.post("/notifications/test", data={"csrf_token": token(self.client), "unit": self.key},
                               follow_redirects=True)
        self.assertIn("Test message posted to Slack.", self.text(got))
        url, body = self.group.calls[-1]
        self.assertEqual((url, len(self.group.calls)), (SLACK, before + 1))
        self.assertIn("SAKS, NMG Tier 2: test from Team Scheduler", json.dumps(body))
        self.group.answers = [(False, 404)]
        got = self.client.post("/notifications/test", data={"csrf_token": token(self.client), "unit": self.key},
                               follow_redirects=True)
        self.assertIn("Test message not posted: Slack says the link no longer works (404); replace the link.",
                      self.text(got))

    def test_no_link_no_test(self):
        got = self.client.post("/notifications/test", data={"csrf_token": token(self.client), "unit": self.other},
                               follow_redirects=True)
        self.assertIn("Save a group link first.", self.text(got))


class TheRemove(_Page):
    def test_remove_link_turns_posting_off(self):
        self.save(link=SLACK)
        got = self.client.post("/notifications/remove", data={"csrf_token": token(self.client), "unit": self.key},
                               follow_redirects=True)
        page = self.text(got)
        self.assertIn("Group link removed for SAKS, NMG Tier 2; posting is off.", page)
        saved = self.store.get_notify(self.key)
        self.assertEqual((saved["link"], saved["mode"]), ("", "off"))
        self.assertNotIn("Ends in", page)


class TheRecentPosts(_Page):
    def test_recent_posts_and_last_post_shown(self):
        self.save(link=SLACK)
        now = time.time()
        post = Post(title="SAKS, NMG Tier 2: changes for Sat 10 Oct",
                    sections=[("", [("Associate 019", "Lunch moved 12:15 to 12:45")])],
                    footer="Changed on the RTA by Omar Mokhtar, 19:19.", url="")
        self.store.add_notify_post(unit=self.key, shift_date="2026-10-10", what="changes", service="slack", count=3,
                                   status="failed", tries=4, reason="Slack had a problem (500)",
                                   body=json.dumps(asdict(post)), made_at=now - 60)
        self.store.add_notify_post(unit=self.key, shift_date="2026-10-10", what="changes", service="slack", count=1,
                                   status="sent", tries=1, sent_at=now, body=json.dumps(asdict(post)), made_at=now)
        page = self.page(self.key)
        card = re.search(r'(?s)<section class="nf-last".*?</section>', page).group(0)
        self.assertIn("SAKS, NMG Tier 2: changes for Sat 10 Oct", card)
        self.assertIn("<b>Associate 019</b>: Lunch moved 12:15 to 12:45", card)
        recent = re.search(r'(?s)<table class="nf-recent".*?</table>', page).group(0)
        self.assertIn("Posted to Slack after 1 retry", recent)
        self.assertIn("Not posted: Slack had a problem (500)", recent)
        lobs = re.search(r'(?s)<table class="nf-lobs".*?</table>', page).group(0)
        self.assertIn("Posted 1 change at", lobs)


if __name__ == "__main__":
    unittest.main()
