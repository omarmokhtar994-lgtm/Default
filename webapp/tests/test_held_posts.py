# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD (owner, 2026-10-11: "after bulk moves or fix breaks or emergency button notification shouldn't be sent
automatically instead a button should show up at the top of the page with a send button for the last bulk move if
it's already pressed and someone is pressing it again for the same action should show up a popup that notification
was sent for this move already are u sure u wanna send it again with same data ?"; answer 4: undoing a posted change
offers the correction; samples 05a, 05b): a bulk change waits for Send; Send posts it once; Send again asks first;
an undo before Send posts nothing; an undo after Send offers the correction. Single changes post as before."""
import html
import time
import re

from webapp.tests.test_notify_daybook import SLACK, WED, _Tagged, hm
from webapp.tests.test_runs import token


class _Bulk(_Tagged):
    def setUp(self):
        self.notifier = self.app.extensions["notifier"]
        self.notifier.run_once(time.time() + 3600)  # whatever earlier tests left waiting goes now, so each test starts clean
        self.group.calls.clear()

    def fresh(self, skip=()):
        used = {r["associate"] for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])}
        found = self.with_breaks(skip=set(skip) | used)
        self.addCleanup(self.store.clear_actual_break, self.key, WED.isoformat(), found[0], found[1])
        return found

    def bulk(self, label="Change several breaks: moved 2 breaks"):
        a = self.fresh()
        b = self.fresh(skip=[a[0]])
        with self.days.action(self.key, WED, self.omar, label=label, bulk=True) as act:
            self.move(a[0], a[1], a[3])
            self.move(b[0], b[1], b[3])
        return act.id, (a, b)

    def page(self, extra=""):
        got = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}{extra}")
        return html.unescape(got.get_data(as_text=True))

    def bar(self, extra=""):
        found = re.search(r'(?s)<div class="act-bar[^"]*" id="act-bar">.*?</div>\s*</div>', self.page(extra))
        self.assertIsNotNone(found)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", found.group(0)))

    def send(self, action_id, again="0"):
        return self.client.post("/day/send", data={"csrf_token": token(self.client), "program": self.key,
                                                   "date": WED.isoformat(), "action_id": str(action_id),
                                                   "again": again}, follow_redirects=True)


class TheHold(_Bulk):
    def test_bulk_waits_for_send(self):
        action_id, _ = self.bulk()
        items = self.store.notify_items(action_id=action_id)
        self.assertEqual({i["status"] for i in items}, {"held"})
        self.notifier.run_once(time.time() + 3600)  # long past any hold
        self.assertEqual(self.group.calls, [])
        self.assertEqual({i["status"] for i in self.store.notify_items(action_id=action_id)}, {"held"})

    def test_send_posts_the_bulk_as_one(self):
        action_id, (a, b) = self.bulk()
        got = self.send(action_id)
        self.assertIn("Posting to the Slack group now.", html.unescape(got.get_data(as_text=True)))
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(len(self.group.calls), 1)
        sent = str(self.group.calls[0][1])
        self.assertIn(a[0], sent)
        self.assertIn(b[0], sent)

    def test_send_again_needs_a_yes(self):
        action_id, _ = self.bulk()
        self.send(action_id)
        self.notifier.run_once(time.time() + 3600)
        got = html.unescape(self.send(action_id).get_data(as_text=True))
        self.assertRegex(got, r"Already posted to the Slack group at \d\d:\d\d\.")
        self.assertIn("Send the same post again?", got)  # asked on the page even without the script
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(len(self.group.calls), 1)
        self.send(action_id, again="1")
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(len(self.group.calls), 2)
        self.assertEqual(self.lines(0), self.lines(1))  # the same data

    def lines(self, n):
        return sorted(re.findall(r"Associate \d+", str(self.group.calls[n][1])))

    def test_single_changes_still_post_by_themselves(self):
        name, idx, kind, start, _ = self.fresh()
        self.move(name, idx, start)
        self.assertEqual(self.items()[0]["status"], "waiting")
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(len(self.group.calls), 1)

    def test_bulk_undone_before_send_posts_nothing(self):
        action_id, _ = self.bulk()
        self.days.undo_last(self.key, WED, self.omar)
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(self.group.calls, [])
        statuses = {i["status"] for i in self.store.notify_items(unit=self.key, shift_date=WED.isoformat())
                    if i["log_id"] and i["at"] >= self.store.get_day_action(action_id)["at"]}
        self.assertEqual(statuses, {"skipped"})
        self.assertNotIn("Send", self.bar() if 'id="act-bar"' in self.page() else "")

    def test_undo_after_send_offers_the_correction(self):
        action_id, (a, b) = self.bulk()
        self.send(action_id)
        self.notifier.run_once(time.time() + 3600)
        self.days.undo_last(self.key, WED, self.omar)
        bar = self.bar()
        self.assertIn("You undid Change several breaks: moved 2 breaks at", bar)
        self.assertIn("Send the correction", bar)
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(len(self.group.calls), 1)  # waits for Send too
        undo = self.store.get_day_action(action_id)["undone_by"]
        self.send(undo)
        self.notifier.run_once(time.time() + 3600)
        self.assertEqual(len(self.group.calls), 2)
        self.assertIn("(undone)", str(self.group.calls[1][1]))

    def test_bar_words(self):
        action_id, _ = self.bulk(label="Rescue the day moved 2 breaks")
        bar = self.bar()
        self.assertRegex(bar, r"Rescue the day moved 2 breaks at \d\d:\d\d\. Not posted to the Slack group yet\.")
        self.assertIn("Send to group", bar)
        self.assertIn("Undo", bar)
        self.send(action_id)
        self.notifier.run_once(time.time() + 3600)
        self.assertRegex(self.bar(), r"Posted to the Slack group at \d\d:\d\d\.")
        self.assertIn("Send again", self.bar())


if __name__ == "__main__":
    import unittest
    unittest.main()
