# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF defect X3: a break in a shift's first cell (owner's photo: the second UK associate's row starts with a
break).

When the workbook leaves Break Edge Margin Minutes blank, the engine derives one per shift: max(2, min(4,
quarters // 10)) quarter-hours, 30 to 60 minutes (l632_universal_scheduler.py, "Derived per shift"). The website's
planners read the blank as no margin at all, so Plan channels and Plan breaks could put a break in the shift's
first quarter-hour. They now derive the same margin.
"""
import unittest

from webapp.break_plan import check_row, edge_margin
from webapp.channel_plan import _candidates
from webapp.tests.test_channel_plan import RULES


class TheDerivedMargin(unittest.TestCase):
    def test_as_the_engine_derives_it(self):
        self.assertEqual(edge_margin(RULES, 5 * 60), 30)   # 20 quarters: 2
        self.assertEqual(edge_margin(RULES, 9 * 60), 45)   # 36 quarters: 3
        self.assertEqual(edge_margin(RULES, 12 * 60), 60)  # 48 quarters: 4
        self.assertEqual(edge_margin(RULES, 2 * 60), 30)   # never under 2 quarters

    def test_a_margin_in_the_workbook_wins(self):
        self.assertEqual(edge_margin({**RULES, "edge_margin": 15}, 9 * 60), 15)
        self.assertEqual(edge_margin({**RULES, "edge_margin": 0}, 9 * 60), 0)


class NoBreakInTheFirstCell(unittest.TestCase):
    def test_plan_channels_starts_breaks_after_the_margin(self):
        person = {"start": 10 * 60, "end": 19 * 60}
        first = min(_candidates(RULES, person, "Break 1", 15))
        self.assertEqual(first, 10 * 60 + 45)
        self.assertLessEqual(max(_candidates(RULES, person, "Break 2", 15)), 19 * 60 - 45 - 15)

    def test_a_break_at_the_shift_start_is_flagged(self):
        level, text = check_row(RULES, "10:00 - 19:00", [10 * 60, 13 * 60, 16 * 60])
        self.assertEqual(level, "warn")
        self.assertIn("within 45 minutes of the shift's start or end", text)


if __name__ == "__main__":
    unittest.main()
