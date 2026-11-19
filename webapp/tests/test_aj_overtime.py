# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AJ item 1 (owner, 2026-10-15: overtime 4 hours before a 20:00 to 05:00 shift was refused with "Overtime has
to start when the shift ends or end when it starts"). Root cause: "+ Add" offered up to 4 h, the server capped
overtime at 2 h and read a start more than 2 h before the shift as the next day. The owner raised the cap to the
longest length "+ Add" offers (4 h, answer of 2026-10-15)."""
import unittest

from webapp.day import OVERTIME_MAX
from webapp.tests.test_overtime_side import NIGHT, LATE, _Overtime


class TheCap(unittest.TestCase):
    def test_the_cap_is_the_longest_length_offered(self):
        self.assertEqual(OVERTIME_MAX, 240)


class FourHours(_Overtime):
    def test_four_hours_before_a_night_shift(self):
        found = self.add(NIGHT, "before", 240)  # 21:00 to 06:00: 17:00 to 21:00
        self.assertEqual((found["lo"], found["hi"]), (1020, 1260))

    def test_three_hours_before_a_night_shift(self):
        found = self.add(NIGHT, "before", 180)
        self.assertEqual((found["lo"], found["hi"]), (1080, 1260))

    def test_four_hours_after_a_day_shift(self):
        found = self.add(LATE, "after", 240)  # 08:00 to 17:00: 17:00 to 21:00
        self.assertEqual((found["lo"], found["hi"]), (1020, 1260))

    def test_more_than_four_hours_is_refused_with_the_cap(self):
        with self.assertRaises(ValueError) as said:
            self.days.add_activity(self.key, self.wed(), LATE, "Overtime", "17:00", "21:05", 1, dry_run=True)
        self.assertEqual(str(said.exception), "Overtime is offered up to 4 hours.")

    def test_the_dialog_note_says_four_hours(self):
        import html
        page = html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date=2026-10-14&view=board&cover=600")
                             .get_data(as_text=True))
        self.assertIn("up to 4 hours", page)
        self.assertNotIn("up to 2 hours", page)

    @staticmethod
    def wed():
        from webapp.tests.test_overtime_side import WED
        return WED


if __name__ == "__main__":
    unittest.main()
