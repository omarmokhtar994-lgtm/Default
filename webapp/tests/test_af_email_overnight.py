# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, A2: Email Hours past midnight.

The owner's workbook has Email windows such as 16:00 to 04:00. They were refused ("the window must start before it
ends"), and an evening shift got Email only before midnight. A window whose end is earlier than its start now runs
into the next morning, and the day it starts on holds it (as Channel Setup's windows already do).
"""
import tempfile
import unittest
from pathlib import Path

from webapp.channel_plan import allowed, score_day
from webapp.channels import read_channels
from webapp.tests.test_channel_plan import RULES
from webapp.tests.test_channels import DAYS, HOURS, add_channel_tabs

MON, TUE = 1, 2
OVERNIGHT = [(d, 6, {}, "16:00", "04:00") for d in DAYS[:5]] + [("Fri", 6, {}, "08:00", "22:00"), ("Sat", 0, {}, "", "")]


class OvernightEmailHours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.setup = read_channels(add_channel_tabs(cls.dir / "overnight.xlsx", hours=OVERNIGHT), 60)

    def test_the_window_is_read_into_the_next_morning(self):
        window = self.setup["email_hours"][MON]
        self.assertEqual((window["start"], window["end"]), (16 * 60, 28 * 60))

    def test_an_evening_shift_may_take_email_after_midnight(self):
        person = {"skills": "PCE"}
        self.assertIn("E", allowed(self.setup, MON, person, 25 * 60))      # 01:00 on Tuesday, Monday's window
        self.assertNotIn("E", allowed(self.setup, MON, person, 28 * 60))   # 04:00: the window has closed
        self.assertIn("E", allowed(self.setup, TUE, person, 2 * 60))       # a shift starting Tuesday 02:00

    def test_email_after_midnight_counts_for_the_day(self):
        person = {"name": "Associate 01", "start": 18 * 60, "end": 27 * 60, "breaks": [], "skills": "PCE",
                  "counts_for": {"english"}, "language": "English"}
        plan = {"blocks": {"Associate 01": [(24 * 60, 26 * 60, "E")]}, "breaks": {}}
        self.assertEqual(score_day([person], plan, self.setup, MON, RULES)["email"], 2)

    def test_a_window_that_starts_and_ends_at_the_same_time_is_still_refused(self):
        same = [("Mon", 4, {}, "16:00", "16:00")] + HOURS[2:]
        with self.assertRaisesRegex(ValueError, r"Email Hours, row \d+: .*start"):
            read_channels(add_channel_tabs(self.dir / "same.xlsx", hours=same), 60)


if __name__ == "__main__":
    unittest.main()
