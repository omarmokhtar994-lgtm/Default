# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AB (approved samples 03 and 03b): on the RTA, each line under Changes today says what happened to it in the
group (waiting, posted, or not posted and why), and the break dialog and + Add carry one tick, set by default, to keep
a single change off the group. An LOB that posts nowhere looks exactly as before."""
import html
import re
import time

from webapp.tests.test_notify_daybook import LATE, WED, _Tagged, hm
from webapp.tests.test_runs import token


class _Rta(_Tagged):
    def page(self, program=None, extra=""):
        got = self.client.get(f"/day?program={(program or self.key).replace(' ', '+')}&date={WED.isoformat()}{extra}")
        self.assertEqual(got.status_code, 200)
        return html.unescape(got.get_data(as_text=True))

    def tag(self, page, who, what):
        found = re.search(rf'<li><b>Omar</b>, \d\d:\d\d: {re.escape(who)}, {re.escape(what)} '
                          r'<span class="post-st (\w+)">([^<]+)</span></li>', page)
        self.assertIsNotNone(found, f"no post status for {who}, {what}")
        return found.groups()

    def form(self, **data):
        return {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), **data}


class TheChangesToday(_Rta):
    def test_changes_today_show_their_post(self):
        name, idx, kind, start, _ = self.with_breaks()
        to = self.move(name, idx, start)
        moved = f"{kind} moved {hm(start)} to {hm(to)}"
        state, text = self.tag(self.page(), name, moved)
        self.assertEqual(state, "waiting")
        self.assertRegex(text, r"^Waiting: posts by \d\d:\d\d$")
        self.days.set_status(self.key, WED, "Associate 029", "Sick", self.omar)
        self.assertEqual(self.tag(self.page(), "Associate 029", "Sick"), ("skipped", "Not posted: kept private"))
        self.app.extensions["notifier"].run_once(time.time() + 200)
        state, text = self.tag(self.page(), name, moved)
        self.assertEqual(state, "sent")
        self.assertRegex(text, r"^Posted to Slack, \d\d:\d\d$")
        self.group.answers = [(False, 404)] * 4
        self.days.add_item(self.key, WED, LATE, "Overtime", "", 60, self.omar, side="after")
        later = time.time() + 200
        for wait in (0, 60, 360, 1260):
            self.app.extensions["notifier"].run_once(later + wait)
        self.assertEqual(self.tag(self.page(), LATE, "Overtime 17:00 to 18:00"),
                         ("failed", "Not posted: Slack says the link no longer works (404); replace the link"))

    def test_no_tags_without_notifications(self):
        self.days.add_item(self.quiet, WED, LATE, "Overtime", "", 30, self.omar, side="after")
        page = self.page(self.quiet, "&view=board&add=480")
        self.assertIn("Overtime 17:00 to 17:30", page)
        self.assertNotIn("post-st", page)
        self.assertNotIn('name="post"', page)
        self.assertNotIn("post_asked", page)


class TheTick(_Rta):
    def test_the_dialogs_carry_the_tick(self):
        page = self.page(extra="&view=board&add=480")
        tick = ('<label class="post-tick"><input type="checkbox" name="post" value="1" checked> Post to the Slack group'
                "<small>Untick to keep this one change off the group.</small></label>")
        brk = re.search(r'(?s)<dialog id="break-dialog".*?</dialog>', page).group(0)
        add = re.search(r'(?s)<dialog id="add-dialog".*?</dialog>', page).group(0)
        self.assertIn(tick, brk)
        self.assertIn(tick, add)
        self.assertIn('<input type="hidden" name="post_asked" value="1">', add)

    def test_the_tick_leaves_one_change_out(self):
        self.client.post("/day/add", data=self.form(associate="Associate 037", what="VTO", **{"from": "10:00"},
                                                    minutes="60", view="board", post_asked="1"))
        item = self.items()[0]
        self.assertEqual((item["text"], item["status"], item["reason"]),
                         ("VTO 10:00 to 11:00", "skipped", "left out on the RTA"))
        self.client.post("/day/add", data=self.form(associate="Associate 037", what="VTO", **{"from": "12:00"},
                                                    minutes="30", view="board", post_asked="1", post="1"))
        self.assertEqual((self.items()[0]["text"], self.items()[0]["status"]), ("VTO 12:00 to 12:30", "waiting"))
        self.client.post("/day/add", data=self.form(associate="Associate 037", what="VTO", **{"from": "14:00"},
                                                    minutes="30", view="board"))  # an older page without the tick
        self.assertEqual(self.items()[0]["status"], "waiting")

    def test_the_break_dialog_sends_the_tick(self):
        name, idx, kind, start, _ = self.with_breaks()
        for step in (5, 10, 15, -5, -10, 20):
            got = self.client.post("/day/break", data=self.form(associate=name, idx=str(idx), at=hm(start + step),
                                                                post_asked="1"))
            if got.status_code == 200:
                break
        self.assertEqual(got.status_code, 200)
        item = self.items()[0]
        self.assertEqual((item["kind"], item["status"], item["reason"]), ("break", "skipped", "left out on the RTA"))


if __name__ == "__main__":
    import unittest
    unittest.main()
