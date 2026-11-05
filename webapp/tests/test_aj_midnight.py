# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AJ item 3 (owner, 2026-10-15, with a photo of the Timeline from 07:00: "not showing after 00:00 the channel
and phone blue color on the timeline"). Root cause: a day's channel stretches were made only for the shifts that start
that day and only up to midnight, so the part of a night shift after 00:00 had no stretch on either day."""
import unittest
from datetime import date

from webapp.day import window_view
from webapp.tests.test_channel_day import _Day

WED, THU = date(2026, 10, 14), date(2026, 10, 15)
NIGHT = "Associate 016"  # 17:00 to 02:00 on Wednesday, on Email from 21:00


class AfterMidnight(_Day):
    def test_the_next_day_has_the_stretch_after_midnight(self):
        runs = self.days.page(self.key, THU)["view"]["channels"]["runs"][NIGHT]
        self.assertEqual(runs[0], (0, 120, "E"))

    def test_the_24_hours_from_a_start_run_the_channel_past_midnight(self):
        views = {d: self.days.page(self.key, day)["view"] for d, day in ((0, WED), (1, THU))}
        runs = window_view(views, 7 * 60, WED)["channels"]["runs"][NIGHT]
        self.assertEqual(runs[-1], (1260, 1560, "E"))

    def test_the_words_stay_with_the_day_the_shift_starts(self):
        lines = self.days.page(self.key, THU)["view"]["channels"]["timelines"]
        self.assertTrue(lines[NIGHT][0].startswith("18:00 "))  # Thursday's own shift, not last night's


if __name__ == "__main__":
    unittest.main()
