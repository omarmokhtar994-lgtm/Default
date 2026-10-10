# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AB (owner, 2026-10-10: "Start the Teams/Slack notifications now", after samples 01 to 04): which group links
are accepted, and the text of a post as Teams and Slack receive it. Made-up "Associate NN" names."""
import json
import unittest
from datetime import datetime, timedelta, timezone

from webapp.notify import (DEFAULT_KINDS, KINDS, Post, body_for, change_post, check_link, link_end, slack_body,
                           teams_body)

EGYPT = timezone(timedelta(hours=3))
SLACK = "https://hooks.slack.com/services/T0000/B0000/abcdEFGHijkl"
TEAMS_OLD = ("https://prod-12.westeurope.logic.azure.com:443/workflows/a1b2/triggers/manual/paths/invoke"
             "?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=Zx9Yk3Vw")
TEAMS_NEW = ("https://default1ab.cd.environment.api.powerplatform.com/powerautomate/automations/direct/workflows/a1b2"
             "/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=Qq7k3Vw")
HOSTS = ("That is not a Teams or Slack group link. Teams links are on logic.azure.com or api.powerplatform.com; "
         "Slack links are on hooks.slack.com.")


def at(hm, day="2026-10-10"):
    return datetime.fromisoformat(f"{day}T{hm}:00").replace(tzinfo=EGYPT).timestamp()


def item(name, text, by="Omar Mokhtar", when="19:19"):
    return {"associate": name, "text": text, "by_name": by, "at": at(when)}


class TheLinks(unittest.TestCase):
    def test_slack_and_teams_links_are_accepted(self):
        self.assertEqual(check_link(SLACK), "slack")
        self.assertEqual(check_link(TEAMS_OLD), "teams")
        self.assertEqual(check_link(TEAMS_NEW), "teams")
        self.assertEqual(check_link("  " + SLACK + "\n"), "slack")  # pasted with spaces around it

    def test_other_links_are_refused(self):
        cases = {
            "": "Paste the group link.",
            "http://hooks.slack.com/services/T0/B0/x": "That is not a Teams or Slack group link: it has to start with "
                                                        "https://.",
            "hooks.slack.com/services/T0/B0/x": "That is not a Teams or Slack group link: it has to start with "
                                                 "https://.",
            "https://example.com/hook": HOSTS,
            "https://hooks.slack.com.evil.io/services/x": HOSTS,
            "https://evil-logic.azure.com.example/x": HOSTS,
            "https://user:pw@hooks.slack.com/services/x": HOSTS,
            "https://hooks.slack.com:8443/services/x": HOSTS,
            "https://127.0.0.1/x": HOSTS,
            "https://logic.azure.com/x": HOSTS,  # the bare domain is no flow's address
            "https://hooks.slack.com/" + "a" * 2000: "That link is too long to be a group link.",
        }
        for url, message in cases.items():
            with self.subTest(url=url[:60]):
                with self.assertRaises(ValueError) as caught:
                    check_link(url)
                self.assertEqual(str(caught.exception), message)

    def test_link_end_is_the_last_four(self):
        self.assertEqual(link_end(SLACK), "ijkl")
        self.assertEqual(link_end(TEAMS_OLD), "k3Vw")


class TheKinds(unittest.TestCase):
    def test_kinds_in_order_and_defaults(self):
        self.assertEqual(list(KINDS), ["break", "added_break", "overtime", "called_in", "channel", "aux", "late"])
        self.assertEqual(KINDS["break"], "Breaks and lunches moved, or put back to plan")
        self.assertEqual(DEFAULT_KINDS, ["break", "added_break", "overtime", "called_in", "channel"])


class ThePost(unittest.TestCase):
    def post(self, items=None, site="https://rta.example/"):
        items = items or [item("Associate 019", "Lunch moved 12:15 to 12:45", when="19:18"),
                          item("Associate 008", "Overtime 17:00 to 18:00")]
        return change_post("SAKS, NMG Tier 2", "2026-10-10", items, site, "SAKS NMG Tier 2")

    def test_change_post_text(self):
        post = self.post()
        self.assertEqual(post.title, "SAKS, NMG Tier 2: changes for Sat 10 Oct")
        self.assertEqual(post.sections, [("", [("Associate 019", "Lunch moved 12:15 to 12:45"),
                                               ("Associate 008", "Overtime 17:00 to 18:00")])])
        self.assertEqual(post.footer, "Changed on the RTA by Omar Mokhtar, 19:19.")
        self.assertEqual(post.url, "https://rta.example/day?program=SAKS+NMG+Tier+2&date=2026-10-10")
        self.assertEqual(self.post(site="").url, "")

    def test_lines_go_in_time_order(self):
        post = self.post([item("Associate 008", "Overtime 17:00 to 18:00", when="19:19"),
                          item("Associate 019", "Lunch moved 12:15 to 12:45", when="19:10")])
        self.assertEqual([n for n, _ in post.sections[0][1]], ["Associate 019", "Associate 008"])

    def test_footer_for_several_people(self):
        post = self.post([item("Associate 001", "Break 1 moved 10:00 to 10:15", by="Sara", when="09:40"),
                          item("Associate 002", "Overtime 17:00 to 18:00", by="Omar Mokhtar", when="09:41"),
                          item("Associate 003", "VTO 15:00 to 16:00", by="Nour", when="09:42")])
        self.assertEqual(post.footer, "Changed on the RTA by Sara, Omar Mokhtar and Nour; last at 09:42.")
        two = self.post([item("Associate 001", "x", by="Sara", when="09:40"), item("Associate 002", "y", when="09:41")])
        self.assertEqual(two.footer, "Changed on the RTA by Sara and Omar Mokhtar; last at 09:41.")

    def test_teams_body_shape(self):
        body = teams_body(self.post())
        self.assertEqual(body["type"], "message")
        att = body["attachments"][0]
        self.assertEqual(att["contentType"], "application/vnd.microsoft.card.adaptive")
        card = att["content"]
        self.assertEqual((card["type"], card["version"]), ("AdaptiveCard", "1.4"))
        text = json.dumps(card)
        self.assertIn('"SAKS, NMG Tier 2: changes for Sat 10 Oct"', text)
        self.assertIn("- **Associate 019**: Lunch moved 12:15 to 12:45", text)
        self.assertIn("Changed on the RTA by Omar Mokhtar, 19:19.", text)
        self.assertEqual(card["actions"], [{"type": "Action.OpenUrl", "title": "Open the RTA",
                                            "url": "https://rta.example/day?program=SAKS+NMG+Tier+2&date=2026-10-10"}])
        self.assertNotIn("actions", teams_body(self.post(site=""))["attachments"][0]["content"])
        self.assertEqual(body_for("teams", self.post()), body)

    def test_slack_body_shape(self):
        body = slack_body(self.post())
        self.assertEqual(body["text"], "SAKS, NMG Tier 2: changes for Sat 10 Oct")
        text = json.dumps(body["blocks"])
        self.assertIn("*SAKS, NMG Tier 2: changes for Sat 10 Oct*", text)
        self.assertIn("\\u2022 *Associate 019*: Lunch moved 12:15 to 12:45", text)
        self.assertIn("<https://rta.example/day?program=SAKS+NMG+Tier+2&date=2026-10-10|Open the RTA>", text)
        self.assertNotIn("Open the RTA", json.dumps(slack_body(self.post(site=""))))
        self.assertEqual(body_for("slack", self.post()), body)

    def test_slack_escapes_control_characters(self):
        post = self.post([item("Associate <1> & *2*", "VTO <!channel> 15:00 to 16:00 @here")])
        text = json.dumps(slack_body(post))
        self.assertIn("Associate &lt;1&gt; &amp; 2", text)
        self.assertIn("VTO &lt;!channel&gt; 15:00 to 16:00", text)
        self.assertNotIn("<!", text)
        self.assertNotIn("<@", text)

    def test_teams_text_cannot_make_a_link(self):
        # Phase AC (Phase AB's open item): text typed on the RTA never becomes a link in a Teams card
        post = self.post([item("Associate 002", "Coaching 14:00 to 14:30 (billable), with [Lina](https://evil.example)")])
        text = json.dumps(teams_body(post))
        self.assertNotIn("](", text)
        self.assertIn("with [Lina] (https://evil.example)", text)

    def test_brackets_stay_readable(self):
        post = self.post([item("Associate 001", "Break [1] moved 10:00 to 10:15")])
        self.assertIn("Break [1] moved 10:00 to 10:15", json.dumps(teams_body(post)))

    def test_long_slack_post_splits(self):
        many = [item(f"Associate {i:03d}", "Break 1 moved 10:00 to 10:15 and a long reason " * 2) for i in range(120)]
        body = slack_body(self.post(many))
        sections = [b["text"]["text"] for b in body["blocks"] if b["type"] == "section"]
        self.assertGreater(len(sections), 2)
        self.assertTrue(all(len(s) <= 2900 for s in sections))
        self.assertLessEqual(len(body["blocks"]), 50)
        self.assertEqual(sum(s.count("•") for s in sections), 120)

    def test_sections_with_headings(self):
        post = Post(title="SAKS, NMG Tier 2: breaks for Sat 10 Oct",
                    sections=[("05:00 to 14:00 (1 person)", [("Associate 019", "Break 1 11:00, Lunch 12:45")])],
                    footer="As planned at 07:30.", url="")
        self.assertIn("**05:00 to 14:00 (1 person)**", json.dumps(teams_body(post)))
        self.assertIn("*05:00 to 14:00 (1 person)*", json.dumps(slack_body(post)))


if __name__ == "__main__":
    unittest.main()
