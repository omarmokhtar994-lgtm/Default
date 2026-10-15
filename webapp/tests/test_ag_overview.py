# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T8 (left from Phase AF): Overview shows the rest of the week too, as the Week page does: each day still to
come with the absences known, the hours short, the overtime needed and the days off to cancel."""
import datetime as dt
import unittest
from unittest import mock


class _Tuesday(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 10, 13, 10, 0, tzinfo=tz)


class TheRestOfTheWeek(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def overview(self, on):
        with mock.patch("webapp.app.datetime", _Tuesday):
            return self.admin.get(f"/overview?program={self.key.replace(' ', '+')}&date={on}").get_data(as_text=True)

    def test_overview_has_the_days_to_come(self):
        page = self.overview("2026-10-13")
        rest = page[page.index('aria-labelledby="out-h"'):]
        # re-pinned in Phase AI: one short row a day, the way in is its "Plan this day" button (owner, 2026-10-15:
        # "rest of week view in overall view is not organized")
        days = __import__("re").findall(r'<th scope="row">([A-Z][a-z]{2} \d\d [A-Z][a-z]{2})</th>.*?'
                                        r'<a class="button" href="/day\?[^"]*">Plan this day</a>', rest)
        self.assertEqual(days, ["Wed 14 Oct", "Thu 15 Oct", "Fri 16 Oct", "Sat 17 Oct"])

    def test_a_week_that_is_over_has_none(self):
        self.assertNotIn('aria-labelledby="out-h"', self.overview("2026-10-04"))


if __name__ == "__main__":
    unittest.main()
