# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (owner, 2026-10-20: "the total hours scheduled for each channel per day and on the overall"; sample ap01,
C approved). The hours each channel is staffed come from the channel stretches a day view holds."""
import unittest

from webapp.channel_hours import combine, day_hours, week_hours


def view(runs):
    return {"channels": {"runs": runs, "rows": []}}


class TheChannelHours(unittest.TestCase):
    def test_a_day_adds_each_persons_stretches_by_channel(self):
        v = view({"Associate 01": [(540, 660, "P"), (660, 750, "C")], "Associate 02": [(600, 660, "P")]})
        self.assertEqual(day_hours(v), {"P": 3.0, "C": 1.5})

    def test_a_day_with_no_channel_plan_has_no_hours(self):
        self.assertEqual(day_hours({"channels": None}), {})
        self.assertEqual(day_hours(None), {})

    def test_breaks_are_not_hours_and_a_stretch_with_no_channel_is_its_own_row(self):
        v = view({"Associate 01": [(0, 60, "Break 1"), (60, 120, "No channel planned")]})
        self.assertEqual(day_hours(v), {"No channel planned": 1.0})

    def test_a_stretch_on_all_channels_is_counted_as_its_own_row(self):
        self.assertEqual(day_hours(view({"Associate 01": [(0, 60, "A")]})), {"A": 1.0})

    def test_the_week_sums_per_channel_and_in_an_all_channels_row(self):
        day = view({"Associate 01": [(540, 600, "P")], "Associate 02": [(540, 570, "C")]})
        week = week_hours([day, day, None, day, None, None, view({"x": [(0, 120, "P")]})])
        phone = next(r for r in week["rows"] if r["letter"] == "P")
        self.assertEqual(phone["name"], "Phone")
        self.assertEqual(phone["days"], [1.0, 1.0, 0, 1.0, 0, 0, 2.0])
        self.assertEqual(phone["total"], 5.0)
        self.assertEqual(week["total"]["days"], [1.5, 1.5, 0, 1.5, 0, 0, 2.0])
        self.assertEqual(week["total"]["total"], 6.5)
        self.assertEqual(week["unplanned"], [2, 4, 5])  # days with no channel plan

    def test_a_week_with_no_plan_at_all_has_no_rows(self):
        week = week_hours([None] * 7)
        self.assertEqual(week["rows"], [])
        self.assertEqual(week["unplanned"], [0, 1, 2, 3, 4, 5, 6])

    def test_lobs_weeks_are_added_row_by_row_and_a_day_is_unplanned_only_when_no_lob_has_a_plan(self):
        a = week_hours([view({"x": [(0, 60, "P")]}), None, None, None, None, None, None])
        b = week_hours([view({"y": [(0, 120, "P"), (120, 180, "C")]}), view({"y": [(0, 60, "E")]}),
                        None, None, None, None, None])
        got = combine([a, b])
        phone = next(r for r in got["rows"] if r["letter"] == "P")
        self.assertEqual((phone["days"][0], phone["total"]), (3.0, 3.0))
        self.assertEqual([r["letter"] for r in got["rows"]], ["P", "C", "E"])
        self.assertEqual(got["total"]["days"][:2], [4.0, 1.0])
        self.assertEqual(got["unplanned"], [2, 3, 4, 5, 6])
        self.assertEqual(combine([a]), a)


if __name__ == "__main__":
    unittest.main()
