# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: for what people pick by hand, "show only warnings, never stop or disallow"): an associate asking to
move a break is offered every time the shift and their other breaks allow, and a time that is closer to another break than the
minimum gap, further than the normal maximum, or off the default is marked with what it breaks. The RTA sees the same words when
deciding. The made-up night shift of test_as_choices (22:00 to 07:00; Break 1 at 00:30, Lunch at 03:00)."""
import unittest

from webapp.change_requests import break_choices
from webapp.tests.test_as_choices import INPUTS, SHIFT, view


def by_start(words=None):
    got = break_choices(view(), INPUTS, "Associate 014", 0, now=SHIFT[0], words=words)
    return {c["start"]: c for c in got["choices"]}


class TheTimesOfferedToAnAssociate(unittest.TestCase):
    def test_every_quarter_hour_the_shift_and_the_other_breaks_allow_is_offered(self):
        starts = sorted(by_start())
        self.assertEqual(starts[0], SHIFT[0])        # from the shift's start
        self.assertEqual(starts[-1], 1605)           # to the quarter hour before Lunch at 03:00 less the break's own 15 minutes
        self.assertEqual(starts, list(range(starts[0], starts[-1] + 1, 15)))

    def test_a_time_inside_the_gaps_has_no_warning(self):
        self.assertEqual(by_start()[1470]["warnings"], [])
        self.assertEqual(by_start()[1365]["warnings"], [])  # the old earliest: 240 minutes to Lunch

    def test_a_time_past_the_normal_maximum_is_marked_not_removed(self):
        said = " ".join(by_start()[1350]["warnings"])  # 255 minutes before Lunch; the normal maximum is 240
        self.assertIn("normal maximum", said)
        self.assertIn("15 minutes", said)

    def test_a_time_closer_than_the_minimum_is_marked_not_removed(self):
        said = " ".join(by_start()[1560]["warnings"])  # 45 minutes before Lunch; the minimum is 60
        self.assertIn("minimum gap", said)
        self.assertIn("15 minutes", said)

    def test_the_default_words_are_added_when_the_rules_can_be_read(self):
        got = by_start(words=lambda start: ["The first break is normally 2 to 3.5 hours into the shift."] if start < 1400 else [])
        self.assertIn("The first break is normally 2 to 3.5 hours into the shift.", got[1380]["warnings"])
        self.assertNotIn("normally", " ".join(got[1470]["warnings"]))

    def test_the_levels_are_what_they_were(self):
        got = by_start()
        self.assertEqual(got[1380]["level"], "low")
        self.assertEqual(got[1530]["level"], "high")


if __name__ == "__main__":
    unittest.main()
