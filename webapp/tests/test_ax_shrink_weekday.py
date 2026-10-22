# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: intervals down the side, the days of the week across the top, the percentage of in
office, out of office or both): the Shrinkage page's weekday and interval grid. Made-up figures; 11 Oct 2026 is a
Sunday. A slot is [out minutes, scheduled minutes, off-floor minutes, minutes on the floor to count]."""
import unittest

from webapp import shrink_view as sv
from webapp.tests import test_cancel_break as _cb


def grid(per_day, which="out", first=0, last=1440, start_day=0):
    return sv.weekday_grid(per_day, which, first, last, start_day)


SUN1, MON, SUN2 = "2026-10-11", "2026-10-12", "2026-10-18"


class TheWeekdayGrid(unittest.TestCase):
    PER_DAY = {SUN1: {540: [1.0, 4.0, 1.0, 4.0], 570: [0.0, 4.0, 2.0, 4.0]},
               MON: {540: [2.0, 4.0, 0.0, 4.0]},
               SUN2: {540: [3.0, 4.0, 0.0, 4.0]}}

    def test_the_days_run_from_the_week_start_with_their_full_names(self):
        days, _ = grid(self.PER_DAY)
        self.assertEqual(days, ["Sunday", "Monday"])
        days, _ = grid(self.PER_DAY, start_day=1)
        self.assertEqual(days, ["Monday", "Sunday"])

    def test_every_day_of_that_name_in_the_period_is_added_up(self):
        _, rows = grid(self.PER_DAY, "out")
        nine = next(r for r in rows if r["t"] == 540)
        self.assertEqual(nine["cells"], [50.0, 50.0])  # Sundays: (1+3)/(4+4); Monday: 2/4
        _, rows = grid(self.PER_DAY, "inn")
        self.assertEqual(next(r for r in rows if r["t"] == 540)["cells"], [12.5, 0.0])

    def test_a_weekday_with_nobody_scheduled_in_an_interval_is_empty_not_zero(self):
        _, rows = grid(self.PER_DAY, "out")
        self.assertEqual(next(r for r in rows if r["t"] == 570)["cells"], [0.0, None])

    def test_a_weekday_not_in_the_period_has_no_column(self):
        days, rows = grid({MON: self.PER_DAY[MON]})
        self.assertEqual(days, ["Monday"])
        self.assertEqual(len(rows[0]["cells"]), 1)

    def test_the_window_trims_the_rows(self):
        _, rows = grid(self.PER_DAY, first=560, last=600)
        self.assertEqual([r["t"] for r in rows], [570])

    def test_a_shift_past_midnight_lands_on_the_clock_of_its_day(self):
        _, rows = grid({SUN1: {1500: [1.0, 2.0, 0.0, 2.0]}}, "out")  # 25:00 of Sunday is 01:00
        self.assertEqual([r["t"] for r in rows], [60])


class TheWeekdayGridOnThePage(_cb.ThePage):
    def get(self, extra=""):
        unit = self.key.replace(" ", "+")
        return self.client.get(f"/shrinkage?program={unit}&from=2026-10-11&to=2026-10-17&by=interval&step=60{extra}")

    def test_both_draws_an_out_of_office_and_an_in_office_grid(self):
        page = self.get().get_data(as_text=True)
        self.assertIn("Out of office by weekday and interval", page)
        self.assertIn("In office by weekday and interval", page)
        self.assertIn('<th scope="col">Wednesday</th>', page)

    def test_out_only_draws_one_grid(self):
        page = self.get("&show=out").get_data(as_text=True)
        self.assertIn("Out of office by weekday and interval", page)
        self.assertNotIn("In office by weekday and interval", page)

    def test_in_only_draws_one_grid(self):
        page = self.get("&show=in").get_data(as_text=True)
        self.assertIn("In office by weekday and interval", page)
        self.assertNotIn("Out of office by weekday and interval", page)

    def test_the_grid_scrolls_inside_its_panel_and_follows_the_window(self):
        page = self.get("&first=8&last=12").get_data(as_text=True)
        grids = page.split("by weekday and interval", 1)[1].split("by day and interval", 1)[0]
        self.assertIn("tscroll", page)
        self.assertIn(">08:00<", grids)
        self.assertNotIn(">13:00<", grids)

    def test_the_other_views_have_no_weekday_grid(self):
        self.assertNotIn("by weekday and interval", self.client.get(
            f"/shrinkage?program={self.key.replace(' ', '+')}&from=2026-10-11&to=2026-10-17&by=day").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
