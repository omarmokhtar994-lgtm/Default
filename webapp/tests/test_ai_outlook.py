# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15): "rest of week view in overall view is not organized". Each day still to come is
one short row: who is away (by kind, the names folded under it), the hours short, the overtime hours and the days off
to cancel that Rescue the day proposes, and one link to that day's Rescue tab for the times and names. Made-up
"Associate NN" data.
"""
import datetime as dt
import re
import unittest
from unittest import mock

from webapp.tests.test_af_outlook import THU, _Clock
from webapp.tests.test_channel_day import WED, _Day


class OneRowADay(_Day):
    def test_the_rows_figures(self):
        self.days.record_absences(self.key, "Associate 001", "Sick", THU, THU, self.omar)
        self.days.record_absences(self.key, "Associate 003", "Exam leave", THU, THU, self.omar)
        row = self.days.outlook(self.key, dt.date(2026, 10, 11), today=WED)[0]
        self.assertEqual(row["absent_text"], "1 sick, 1 exam leave")
        page = self.days.page(self.key, THU)
        plan = self.days.dayoff_plan(page)
        self.assertAlmostEqual(row["overtime_hours"],
                               sum(o["people"] * (o["end"] - o["start"]) for o in plan["overtime"]) / 60)
        self.assertEqual(row["dayoff_people"], sum(p["people"] for p in plan["proposals"]))

    def test_nobody_away(self):
        row = self.days.outlook(self.key, dt.date(2026, 10, 11), today=WED)[0]
        self.assertEqual(row["absent_text"], "Nobody")


class OnOverview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def test_one_short_row_a_day_with_a_way_in(self):
        with mock.patch("webapp.app.datetime", _Clock):
            html = self.admin.get(f"/overview?program={self.key.replace(' ', '+')}&date={WED.isoformat()}"
                                  ).get_data(as_text=True)
        table = re.search(r'<section class="panel" id="outlook".*?</section>', html, re.S).group(0)
        rows = re.findall(r"<tr>(.*?)</tr>", table.split("<tbody>")[1], re.S)
        self.assertEqual(len(rows), 3)  # Thursday, Friday and Saturday
        for row in rows:
            self.assertNotIn("<br>", row)
            self.assertEqual(len(re.findall(r"<t[dh][ >]", row)), 6)
            self.assertRegex(row, r'<a class="button" href="[^"]*view=rescue[^"]*">Plan this day</a>')
        self.assertIn('<th scope="row">Thu 15 Oct</th>', rows[0])


if __name__ == "__main__":
    unittest.main()
