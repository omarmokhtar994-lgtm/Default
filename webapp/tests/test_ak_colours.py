# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK item 1 (owner, 2026-10-15: "Phone and email is very hard to be read on the timeline with those colors";
answer: sample ak01 option D). Phone #1A47A8, Chat #C2549F, Email #A6D96A on a grey bar #9AA1AA when the day has a
channel plan, the channel as tall as the bar, and P, C or E written on stretches of 30 minutes or more, never under
a break (white on Phone and Chat, #1B1F24 on Email).

Re-pinned in Phase AL: the owner did not like the green (2026-10-15) and picked sample al01 option C, Email #2F7D5B with
a white E like the others."""
import re
import unittest
from pathlib import Path

from webapp.day import channel_letters
from webapp.tests import test_ai_fixes as ai

CSS = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")


class TheTokens(unittest.TestCase):
    def test_option_d(self):
        # Re-pinned in Phase BA (owner, 2026-10-25, the three looks): the channel colours are set per look. The light looks
        # (Tide, Drafting table) keep option D's Phone and Email with white text; Chat is #B4468F (was #C2549F, 4.1:1 with white
        # text, 4.5:1 needed). Night watch uses brighter fills with dark text, because the deep set measured under 3:1 on navy.
        for token, value in (("--ch-phone", "#1A47A8"), ("--ch-chat", "#B4468F"), ("--ch-email", "#2F7D5B"), ("--ch-ink", "#FFFFFF")):
            self.assertEqual(CSS.count(f"{token}: {value}"), 3, token)  # Tide's two blocks and Drafting table
        for token, value in (("--ch-phone", "#4C86FF"), ("--ch-chat", "#E070BE"), ("--ch-email", "#3FAE81"), ("--ch-ink", "#06142B")):
            self.assertIn(f"{token}: {value}", CSS)
        self.assertIn("--ch-bar: #9AA1AA", CSS)
        self.assertNotIn("--ch-email-ink", CSS)

    def test_email_text_is_white_like_the_others(self):
        self.assertRegex(CSS, r"\.ch-E \{ background: var\(--ch-email\); color: var\(--ch-ink\); \}")


class TheLetters(unittest.TestCase):
    def test_long_stretches_get_their_letter_at_the_middle(self):
        self.assertEqual(channel_letters([(600, 720, "P"), (720, 740, "C"), (740, 800, "E")], []),
                         [(660, "P"), (770, "E")])

    def test_a_letter_moves_off_a_break(self):
        # a break 650-665 sits on the middle of 600-720: the letter goes to the middle of the longer free piece
        self.assertEqual(channel_letters([(600, 720, "P")], [(650, 15)]), [(692, "P")])

    def test_no_room_no_letter(self):
        self.assertEqual(channel_letters([(600, 640, "C")], [(610, 15)]), [])

    def test_only_channels(self):
        self.assertEqual(channel_letters([(600, 700, "Break 1"), (700, 800, "A")], []), [(750, "A")])


class ThePage(ai.TheChannelsOnTheTimeline):
    def test_bars_are_grey_and_letters_are_drawn(self):
        html = self.client.get(f"/day?program={self.key}&date=2026-10-14").get_data(as_text=True)
        self.assertIn('class="tl-bar has-ch', html)
        self.assertRegex(html, r'<rect class="tl-ch ch-[PCEA]" x="-?\d+" y="8" width="\d+" height="14"')
        self.assertRegex(html, r'<text class="tl-ch-t" x="-?\d+" y="19" data-cx="-?\d+" aria-hidden="true">[PCEA]</text>')


if __name__ == "__main__":
    unittest.main()
