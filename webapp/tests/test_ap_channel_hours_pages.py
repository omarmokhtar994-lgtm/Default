# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (sample ap01, C approved): the hours scheduled for each channel per day and for the week are on the RTA's
Timeline, on the Schedules page and in Exports. The made-up Wednesday of test_channel_day: Associate 001 is on Chat
12:00 to 19:00 (7 hours, then blended time), Associate 031 on Phone 12:00 to 14:00 and 14:15 to 19:00 (6.75 hours)."""
import csv
import html
import io
import shutil
import unittest
from datetime import date

from webapp.tests import test_channel_day

WED = date(2026, 10, 14)


class TheChannelHoursOnThePages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)
        cls.run_id = cls.store.list_runs()[0]["id"]

    @classmethod
    def tearDownClass(cls):
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def timeline(self):
        url = f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}"
        return html.unescape(self.admin.get(url).get_data(as_text=True))

    def test_the_rta_timeline_shows_the_days_hours_per_channel_and_the_week(self):
        page = self.timeline()
        self.assertIn('aria-labelledby="chh-h"', page)
        block = page.split('aria-labelledby="chh-h"')[1].split("</section>")[0]
        phone = next(r for r in block.split("<tr>") if ">Phone<" in r)
        chat = next(r for r in block.split("<tr>") if ">Chat<" in r)
        self.assertIn("6.75", phone)
        self.assertIn("7", chat)
        self.assertIn("All channels (blended time)", block)

    def test_a_day_without_a_channel_plan_is_said(self):
        block = self.timeline().split('aria-labelledby="chh-h"')[1].split("</section>")[0]
        self.assertIn("No channel plan", block)  # the other six days of the week

    def test_the_schedules_page_shows_the_week_table(self):
        page = html.unescape(self.admin.get(f"/runs/{self.run_id}/schedules").get_data(as_text=True))
        block = page.split('aria-labelledby="chh-h"')[1].split("</section>")[0]
        self.assertIn("6.75", block)

    def test_exports_has_hours_per_channel_as_a_csv(self):
        got = self.admin.get("/exports/download", query_string={
            "from": "2026-10-11", "to": "2026-10-17", "kind": "channel_hours", "format": "csv", "program": self.key})
        self.assertEqual(got.status_code, 200, got.get_data(as_text=True)[:300])
        rows = list(csv.reader(io.StringIO(got.get_data(as_text=True).lstrip("﻿"))))
        self.assertEqual(rows[0], ["Date", "Program", "Channel", "Hours"])
        self.assertIn(["2026-10-14", self.key, "Phone", "6.75"], rows)


if __name__ == "__main__":
    unittest.main()
