# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV: the Shrinkage page. Made-up "Associate NN" data, Wednesday 14 Oct 2026."""
import unittest

from webapp.tests import test_cancel_break as _cb
from webapp.tests.test_notify_daybook import WED


class TheShrinkagePage(_cb.ThePage):
    def get(self, extra=""):
        unit = self.key.replace(" ", "+")
        return self.client.get(f"/shrinkage?program={unit}&from=2026-10-11&to=2026-10-15{extra}")

    def test_both_by_day_has_two_tiles_and_a_chart(self):
        page = self.get().get_data(as_text=True)
        for text in ("Out of office", "In office", "Day over day", "The numbers"):
            self.assertIn(text, page)
        self.assertIn('<svg class="chart"', page)

    def test_out_only_leaves_in_office_out(self):
        page = self.get("&show=out").get_data(as_text=True)
        body = page.split("<main", 1)[1].split('<form', 1)[1].split("</form>", 1)[1]
        self.assertIn("Out of office", body)
        self.assertNotIn(">In office<", body)

    def test_in_only_leaves_out_of_office_out(self):
        body = self.get("&show=in").get_data(as_text=True).split("</form>", 1)[1]
        self.assertIn("In office", body)
        self.assertNotIn('<span class="tile-label">Out of office', body)

    def test_week_over_week_names_the_week(self):
        self.assertIn("Week of", self.get("&by=week").get_data(as_text=True))

    def test_per_interval_has_the_heat_table_and_a_window(self):
        page = self.get("&by=interval&step=60&first=8&last=12").get_data(as_text=True)
        self.assertIn("by day and interval", page)
        self.assertIn(">08:00<", page)
        self.assertNotIn(">13:00<", page.split("by day and interval", 1)[1])

    def test_the_heat_table_scrolls_inside_its_panel_not_the_page(self):
        # found by the accessibility check: 24 hourly columns made the whole page scroll sideways at 1280 px
        page = self.get("&by=interval&step=60").get_data(as_text=True)
        # re-pinned (Phase BA): the scroll box is now the shared labelled panel-scroll region, same table inside
        self.assertIn('<div class="tscroll panel-scroll" role="region" tabindex="0" aria-label="Table (scrolls)"><table class="ins-heat">', page)

    def test_the_ticks_are_kept_and_changed_by_the_url(self):
        page = self.get("&out=unplanned&inn=breaks").get_data(as_text=True)
        self.assertRegex(page, r'name="out" value="unplanned" checked')
        self.assertNotRegex(page, r'name="out" value="sick" checked')
        self.assertNotRegex(page, r'name="inn" value="aux" checked')

    def test_it_is_in_the_menu_and_clean(self):
        page = self.get().get_data(as_text=True)
        self.assertRegex(page, r'<a [^>]*href="/shrinkage[^"]*"[^>]*>Shrinkage</a>')
        body = page.split("<main", 1)[1]
        self.assertNotRegex(body, r"<script(?![^>]*src=)")
        self.assertNotRegex(body, r' style="')

    def test_the_page_says_which_day_weeks_begin_on(self):
        self.assertIn("Weeks begin on Sunday", self.get("&by=week").get_data(as_text=True))

    def test_a_nonsense_choice_falls_back(self):
        self.assertEqual(self.get("&show=zzz&by=zzz&step=7&first=30&last=2").status_code, 200)


if __name__ == "__main__":
    unittest.main()
