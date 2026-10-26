# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: "I think it considers a break as a separator, that's why it kept associates the whole day on the same channel"):
score_day tells a change of channel at a break from one in the middle of a stretch, and with the Balanced tick a change at a break is priced
below one in the middle of a stretch. Rule and acceptance: evidence/phase_bc/REQUESTS.md."""
import unittest

from webapp.channel_plan import score_day
from webapp.tests.test_channel_plan import RULES, WED, setup


def person():
    return {"name": "Associate 001", "language": "English", "start": 480, "end": 1020, "skills": "PCE", "counts_for": {"english"},
            "breaks": [("Break 1", 600, 15), ("Lunch", 750, 30)]}


class TheSplit(unittest.TestCase):
    def test_a_change_at_a_break_and_one_in_the_middle_are_told_apart(self):
        people = [person()]
        plan = {"breaks": {"Associate 001": [600, 750]},
                "blocks": {"Associate 001": [(480, 600, "P"), (615, 750, "C"),   # P to C across Break 1
                                             (780, 900, "C"), (900, 1020, "E")]}}  # C to E in the middle of a stretch
        got = score_day(people, plan, setup(), WED, RULES)
        self.assertEqual((got["moves_at_breaks"], got["moves_mid"]), (1, 1))
        self.assertEqual(got["moves"], 2)  # the old total still counts both

    def test_no_change_no_count(self):
        people = [person()]
        plan = {"breaks": {"Associate 001": [600, 750]}, "blocks": {"Associate 001": [(480, 600, "P"), (615, 750, "P"), (780, 1020, "P")]}}
        got = score_day(people, plan, setup(), WED, RULES)
        self.assertEqual((got["moves_at_breaks"], got["moves_mid"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
