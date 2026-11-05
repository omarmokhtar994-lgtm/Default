# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23, from a Slack post that ended "... and 47 more lines: open the RTA to see them": "post was too long,
those extra 47 lines couldn't be shown on Slack, and associates don't have access to open the tool yet"): a change with more lines than
one Slack message holds goes as several messages, titled "(1 of 3)", "(2 of 3)" and so on, and every line is posted. A message that
fits is posted as before. Made-up "Associate NNN" names."""
import json
import re
import unittest
from dataclasses import asdict

from webapp.notify import SLACK_FLOW_MAX, Post, bodies_for, body_for
from webapp.tests import test_notify_posts as tp
from webapp.tests.test_notify_sender import SLACK, T0, UNIT, _Sender

FLOW = tp.SLACK_FLOWS[0]
DIVIDER = tp.DIVIDER


def long_post(count=120, heading=False):
    lines = [(f"Associate {i:03d}", "Break 1 moved 10:00 to 10:15 and a long reason " * 2) for i in range(count)]
    sections = ([(f"Shift {s}", lines[s * 30:(s + 1) * 30]) for s in range(count // 30)] if heading else [("", lines)])
    return Post(title="SAKS, NMG Tier 2: changes for Sat 10 Oct", sections=sections,
                footer="Changed on the RTA by Omar Mokhtar, 19:19.", url="")


def bullets(text):
    return [line for line in text.split("\n") if line.startswith("• ")]


class TheWorkflowMessage(unittest.TestCase):
    def test_a_long_change_goes_as_several_messages_with_every_line(self):
        bodies = bodies_for("slack", long_post(), FLOW)
        self.assertGreater(len(bodies), 1)
        texts = [b["text"] for b in bodies]
        for i, text in enumerate(texts, 1):
            self.assertLessEqual(len(text), SLACK_FLOW_MAX)
            self.assertEqual(text.split("\n")[0], f"\U0001f4cb SAKS, NMG Tier 2: changes for Sat 10 Oct ({i} of {len(texts)})")
        shown = [line for text in texts for line in bullets(text)]
        self.assertEqual([re.match(r"• (Associate \d+):", s).group(1) for s in shown],
                         [f"Associate {i:03d}" for i in range(120)])  # every line, once, in order
        self.assertNotIn("more lines", json.dumps(texts))
        self.assertNotIn("open the RTA", json.dumps(texts))

    def test_who_changed_it_closes_the_last_message_only(self):
        texts = [b["text"] for b in bodies_for("slack", long_post(), FLOW)]
        footer = "✏️ Changed on the RTA by Omar Mokhtar, 19:19."
        self.assertEqual([t.endswith(footer) for t in texts], [False] * (len(texts) - 1) + [True])

    def test_a_message_that_fits_is_one_message_exactly_as_before(self):
        post = long_post(5)
        self.assertEqual(bodies_for("slack", post, FLOW), [body_for("slack", post, FLOW)])
        text = body_for("slack", post, FLOW)["text"]
        self.assertNotIn(" of ", text.split("\n")[0])
        self.assertEqual(len(bullets(text)), 5)

    def test_a_heading_is_never_left_at_the_end_of_a_message(self):
        texts = [b["text"] for b in bodies_for("slack", long_post(120, heading=True), FLOW)]
        self.assertGreater(len(texts), 1)
        for text in texts:
            lines = [l for l in text.split("\n") if l and l != DIVIDER][1:]  # after the title
            body = [l for l in lines if not l.startswith("✏")]
            self.assertTrue(body[-1].startswith("• "), body[-1])
        self.assertEqual(sum(len(bullets(t)) for t in texts), 120)

    def test_one_line_longer_than_a_message_is_cut_not_lost(self):
        post = Post(title="T", sections=[("", [("Associate 001", "x" * 9000), ("Associate 002", "short")])])
        texts = [b["text"] for b in bodies_for("slack", post, FLOW)]
        self.assertTrue(all(len(t) <= SLACK_FLOW_MAX for t in texts))
        self.assertEqual(sum(len(bullets(t)) for t in texts), 2)


class TheSlackAppMessage(unittest.TestCase):
    def test_more_blocks_than_slack_allows_go_as_several_messages(self):
        lines = [(f"Associate {i:03d}", "y" * 280) for i in range(700)]
        post = Post(title="Big day", sections=[("", lines)], footer="Changed on the RTA by Omar Mokhtar, 19:19.")
        bodies = bodies_for("slack", post, tp.SLACK)
        self.assertGreater(len(bodies), 1)
        for b in bodies:
            self.assertLessEqual(len(b["blocks"]), 50)
        text = json.dumps(bodies)
        self.assertNotIn("more lines", text)
        self.assertEqual(len(re.findall(r"Associate \d{3}", text)), 700)


class TheSender(_Sender):
    def queue_many(self, count):
        for i in range(count):
            self.queue("Break 1 moved 10:00 to 10:15 and a long reason " * 2, who=f"Associate {i:03d}")

    def go(self):
        self.settle(link=FLOW)
        self.queue_many(120)
        self.now += 130
        self.notifier.run_once()

    def test_every_part_is_posted_in_order_and_the_post_is_sent_once(self):
        self.go()
        calls = [body["text"] for _, body in self.group.calls]
        self.assertGreater(len(calls), 1)
        names = [re.match(r"• (Associate \d+):", l).group(1) for t in calls for l in bullets(t)]
        self.assertEqual(names, [f"Associate {i:03d}" for i in range(120)])
        posts = self.store.notify_posts(unit=UNIT)
        self.assertEqual([p["status"] for p in posts], ["sent"])

    def test_a_part_that_fails_is_tried_again_without_repeating_the_ones_already_sent(self):
        self.settle(link=FLOW)
        self.queue_many(120)
        self.group.answers = [(True, 200), (False, 500)]  # part 1 goes, part 2 fails
        self.now += 130
        self.notifier.run_once()
        post = self.store.notify_posts(unit=UNIT)[0]
        self.assertEqual((post["status"], post["tries"]), ("waiting", 1))
        self.assertEqual(len(self.group.calls), 2)
        self.now += 3600
        self.notifier.run_once()
        calls = [body["text"] for _, body in self.group.calls]
        firsts = [t.split("\n")[0].rsplit("(", 1)[1] for t in calls]
        self.assertEqual(firsts[0], f"1 of {firsts[0].split(' of ')[1]}")
        self.assertEqual(calls[1], calls[2])  # part 2 again
        self.assertEqual(sum(1 for t in calls if t.split("\n")[0].endswith("(1 of " + firsts[0].split(' of ')[1])), 1)
        self.assertEqual(self.store.notify_posts(unit=UNIT)[0]["status"], "sent")
        names = [re.match(r"• (Associate \d+):", l).group(1) for t in calls[:1] + calls[2:] for l in bullets(t)]
        self.assertEqual(names, [f"Associate {i:03d}" for i in range(120)])


if __name__ == "__main__":
    unittest.main()
