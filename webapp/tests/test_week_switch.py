# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AA (owner, 2026-10-10: "... confirm on which one we will use along with same options in week view as well";
approved sample 04): the Week page switches between the week's schedules, the one not in use says so and offers Set
in use, and a link opens the side-by-side comparison."""
import re
import unittest

from webapp.tests.test_week_list import WEEK, TwoSchedulesForOneWeek


class TheWeekSwitch(TwoSchedulesForOneWeek):
    def switch(self, page):
        found = re.search(r'(?s)<div class="wk-switch" role="group" aria-label="Schedule shown">.*?</div>', page)
        return found.group(0) if found else None

    def test_the_week_page_has_a_schedule_switch(self):
        q = self.key.replace(" ", "+")
        switch = self.switch(self.page(f"/week?program={q}&week={WEEK}"))
        self.assertIsNotNone(switch, "no schedule switch")
        other = self.book.versions(self.second)[-1]["id"]
        self.assertIn(f'<a href="/week?program={q}&week={WEEK}" aria-current="true">week_v1.xlsx<small>in use</small>'
                      "</a>", switch)
        self.assertIn(f'<a href="/schedules/{other}/week">week_v2.xlsx<small>not in use</small></a>', switch)
        self.assertIn(f'<a href="/schedules?program={q}&week={WEEK}">Compare the week\'s schedules</a>', switch)

    def test_the_other_schedule_says_not_in_use_with_set_in_use(self):
        other = self.book.versions(self.second)[-1]["id"]
        page = self.page(f"/schedules/{other}/week")
        switch = self.switch(page)
        self.assertIsNotNone(switch)
        self.assertIn(f'<a href="/schedules/{other}/week" aria-current="true">week_v2.xlsx', switch)
        self.assertIn("Not in use: the RTA, exports and analysis use week_v1.xlsx for this week.", page)
        self.assertRegex(page, rf'(?s)<form method="post" action="/schedules/{other}/in-use">.*?'
                               r'<button class="primary" type="submit">Set week_v2.xlsx in use</button>')

    def test_one_schedule_no_switch(self):
        page = self.page(f"/week?program={self.alone.replace(' ', '+')}&week={WEEK}")
        self.assertIsNone(self.switch(page))


if __name__ == "__main__":
    unittest.main()
