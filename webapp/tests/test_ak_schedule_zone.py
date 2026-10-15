# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK item 2 (owner, 2026-10-15: "shedule tab doesn't have times in filter or option"; answer "schedules"): the
schedule a run keeps (/runs/<id>/schedules, opened from the Schedules list) has "Times in". In another zone every
shift is shown in that zone's clock, marked when it starts the day before or the next day; shifts are changed in the
schedule's own zone, so the page links back to it and the shift buttons rest until then."""
import html
import re

from webapp.tests import test_overtime_side as ots


class TheScheduleInAnotherZone(ots._Overtime):
    def page(self, tz=""):
        run = self.store.list_runs()[0]["id"]
        url = f"/runs/{run}/schedules" + (f"?tz={tz}" if tz else "")
        return html.unescape(self.client.get(url).get_data(as_text=True))

    def test_the_page_has_times_in(self):
        body = self.page()
        self.assertRegex(body, r'<label>Times in <select name="tz" data-autosubmit>')
        self.assertIn('<option value="Africa/Cairo" selected>', body)  # the schedule's own zone first

    def test_shifts_move_with_the_zone(self):
        own = self.page()
        moved = self.page("Europe/London")  # Cairo is 2 hours ahead of London on 11 October 2026
        cell = r'data-name="Associate 008" data-day="Wed" data-value="08:00 - 17:00"[^>]*>'
        self.assertRegex(own, cell + "08:00 - 17:00<")
        self.assertRegex(moved, cell + "06:00 - 15:00<")  # the value kept for changes stays in the schedule's time
        self.assertIn("Shifts are changed in Cairo (Egypt) time", moved)

    def test_a_shift_that_moves_across_midnight_says_so(self):
        moved = self.page("America/Los_Angeles")  # 10 hours behind Cairo: a 08:00 start is 22:00 the day before
        self.assertRegex(moved, r'data-name="Associate 008" data-day="Wed"[^>]*>22:00 - 07:00 \(day before\)<')

    def test_shift_buttons_rest_in_another_zone(self):
        moved = self.page("Europe/London")
        self.assertRegex(moved, r'<button type="button" class="ed[^"]*"[^>]* disabled>')
        self.assertNotRegex(self.page(), r'<button type="button" class="ed[^"]*"[^>]* disabled>')
