# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "doesn't the site adapt to the time zone changes automatically, so the refusal can work on the day of the change
but the next day should work normally with a difference of 6 hours instead of 7?"): ``rta_window_shift`` is ``rta_shift`` for the 24 hours the RTA
shows (and an hour either side) instead of the day before to 2 days after, so a clock change refuses only the windows it falls in. Pre-registered
rule: a window with no change gives exactly the gap the zones have in it; a window with one gives None; ``rta_shift`` itself is unchanged.
Eastern to Cairo in autumn 2026: Egypt's clocks go back at Cairo midnight on 29/30 Oct, the US's on 1 Nov at 02:00 New York."""
import unittest
from datetime import date

from webapp.clock import noon_gap, rta_shift, rta_window_shift

NY, CAIRO = "America/New_York", "Africa/Cairo"


def gap(day, start):
    """Eastern to Cairo, for the 24 hours from ``start`` minutes of the Cairo clock."""
    return rta_window_shift(date(2026, 10, day) if day <= 31 else date(2026, 11, day - 31), NY, CAIRO, start - noon_gap(
        date(2026, 10, day) if day <= 31 else date(2026, 11, day - 31), NY, CAIRO))


class TheWindowShift(unittest.TestCase):
    def test_midnight_windows_refuse_only_where_a_change_falls_in_them(self):
        self.assertEqual(gap(28, 0), 420)   # 7 h: nothing changes
        self.assertIsNone(gap(29, 0))       # Egypt changes at the end of this Cairo day
        self.assertEqual(gap(30, 0), 360)   # 30 Oct from 00:00 Cairo is already after the change: 6 h
        self.assertEqual(gap(31, 0), 360)   # the next day works, with a 6 h gap
        self.assertIsNone(gap(32, 0))       # 1 Nov: the US changes
        self.assertEqual(gap(33, 0), 420)   # 2 Nov: back to 7 h

    def test_windows_that_start_at_13_00_in_cairo(self):
        self.assertEqual(gap(28, 780), 420)
        self.assertIsNone(gap(29, 780))
        self.assertEqual(gap(30, 780), 360)
        self.assertIsNone(gap(31, 780))
        self.assertEqual(gap(32, 780), 420)

    def test_the_old_wider_check_is_unchanged(self):
        self.assertIsNone(rta_shift(date(2026, 10, 28), NY, CAIRO))
        self.assertEqual(rta_shift(date(2026, 10, 23), NY, CAIRO), 420)

    def test_same_zone_is_zero_and_an_ordinary_day_has_the_ordinary_gap(self):
        self.assertEqual(rta_window_shift(date(2026, 10, 30), CAIRO, CAIRO, 0), 0)
        self.assertEqual(rta_window_shift(date(2026, 10, 14), NY, CAIRO, 0), 420)
        self.assertEqual(noon_gap(date(2026, 10, 14), NY, CAIRO), 420)


if __name__ == "__main__":
    unittest.main()
