# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: a merge of an Eastern LOB with an Egypt LOB "says different timezones and refuses"): LOBs whose intervals
differ in length (one 30 minutes, one 60) were refused with a line about clocks. The line now says what it is: different interval
lengths, naming each LOB. Two LOBs of the same interval length, one raised in Eastern time, still merge as far as the check goes."""
import unittest
from datetime import date

from webapp.merged_day import merged_page

ON = date(2026, 10, 23)
ZONES = {"SAKS/Tier 1": "Africa/Cairo", "SAKS/Tier 2": "America/New_York"}


class _Days:
    def __init__(self, lengths):
        self.lengths = lengths

    def version(self, unit, on):
        return ({"id": 1}, None)

    def page(self, unit, on, measure):
        return {"view": {"interval": self.lengths[unit]}}


class TheMessage(unittest.TestCase):
    def merge(self, lengths):
        return merged_page(_Days(lengths), "SAKS/Tier 1", list(ZONES), ON, "interval", 780, "Africa/Cairo", lambda unit, on: ZONES[unit])

    def test_different_interval_lengths_are_said_as_that_and_name_each_lob(self):
        with self.assertRaises(ValueError) as said:
            self.merge({"SAKS/Tier 1": 30, "SAKS/Tier 2": 60})
        text = str(said.exception)
        self.assertIn("different interval lengths", text)
        self.assertIn("SAKS/Tier 1: 30 minutes", text)
        self.assertIn("SAKS/Tier 2: 60 minutes", text)
        self.assertNotIn("clocks", text.lower())


if __name__ == "__main__":
    unittest.main()
