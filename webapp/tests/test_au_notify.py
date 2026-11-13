# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU (owner, 2026-10-21): a group post says only the latest change to a break, and adds the person's breaks as
they now stand ("Breaks now: Break 1 ..., Lunch ..., Break 3 ...")."""
import json

from webapp.tests.test_notify_daybook import WED, _Tagged, hm


class TheGroupPost(_Tagged):
    def setUp(self):
        with self.store._db() as db:
            db.execute("delete from notify_items")
            db.execute("delete from notify_posts")
        self.notifier = self.app.extensions["notifier"]
        self.store.set_notify(self.key, mode="on", hold=0)

    def lines(self):
        self.notifier.run_once(self.notifier.clock() + 1000)
        post = self.store.notify_posts(unit=self.key, what="changes")[0]
        return json.loads(post["body"])["sections"][0][1]

    def test_two_moves_of_one_break_post_the_last_and_the_breaks_now(self):
        name, idx, kind, start, planned = self.with_breaks()
        first = self.move(name, idx, start)
        second = self.move(name, idx, first)
        mine = [t for n, t in self.lines() if n == name]
        moves = [t for t in mine if t.startswith(kind)]
        self.assertEqual(moves, [f"{kind} moved {hm(first)} to {hm(second)}"])
        final = [t for t in mine if t.startswith("Breaks now: ")]
        self.assertEqual(len(final), 1)
        self.assertIn(f"{kind} {hm(second)}", final[0])
        self.assertNotIn(f"{kind} {hm(first)}", final[0])
