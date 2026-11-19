# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV: the Incidents page (owner, 2026-10-22). Made-up "Associate NN" data, Wednesday 14 Oct 2026."""
import re
import unittest

from webapp.tests import test_cancel_break as _cb
from webapp.tests.test_notify_daybook import WED, hm

Q = "from=2026-10-14&to=2026-10-14"


class ThePage(_cb.ThePage):
    def get(self, extra="", user=None):
        unit = self.key.replace(" ", "+")
        return (user or self.client).get(f"/incidents?program={unit}&{Q}{extra}")

    def moved_with_a_miss(self):
        name, idx, kind, start, _ = self.with_breaks()
        self.addCleanup(self.store.delete_day_before, "2999-01-01")  # the incident is a record of its own
        self.addCleanup(self.days.move_break, self.key, WED, name, idx, None, self.omar)
        self.days.move_break(self.key, WED, name, idx, hm(start + 5), self.omar, missed=True)
        return name

    def test_the_overview_opens_with_tiles_and_charts(self):
        name = self.moved_with_a_miss()
        got = self.get()
        self.assertEqual(got.status_code, 200)
        page = got.get_data(as_text=True)
        for text in ("Incidents and shrinkage", "Absenteeism", "Shrinkage, in office", "Adherence", "Missed breaks"):
            self.assertIn(text, page)
        self.assertGreaterEqual(page.count('<svg class="chart"'), 3)

    def test_the_associates_level_lists_the_person_and_opens_their_days(self):
        name = self.moved_with_a_miss()
        page = self.get("&view=associates").get_data(as_text=True)
        self.assertIn(name, page)
        self.assertRegex(page, r"data-filter-row")
        one = self.get(f"&view=associates&who={name.replace(' ', '+')}").get_data(as_text=True)
        self.assertIn("Day by day", one)
        self.assertIn("Missed breaks 1", one)

    def test_the_lobs_level_has_a_table_with_every_incident_type(self):
        page = self.get("&view=lobs").get_data(as_text=True)
        for text in ("LOBs side by side", "Unplanned", "Missed", "Adherence"):
            self.assertIn(text, page)

    def test_a_period_with_nothing_says_so(self):
        unit = self.key.replace(" ", "+")
        page = self.client.get(f"/incidents?program={unit}&from=2025-01-01&to=2025-01-03").get_data(as_text=True)
        self.assertIn("Nothing to show", page)

    def test_it_is_in_the_menu_and_has_no_inline_script_or_style(self):
        page = self.get().get_data(as_text=True)
        self.assertRegex(page, r'<a [^>]*href="/incidents[^"]*"[^>]*>Incidents</a>')
        body = page.split("<main", 1)[1]
        self.assertNotRegex(body, r"<script(?![^>]*src=)")
        self.assertNotRegex(body, r' style="')

    def test_it_says_up_or_down_on_the_period_before_and_offers_the_download(self):
        self.moved_with_a_miss()
        page = self.get().get_data(as_text=True)
        self.assertIn("Which days go wrong", page)
        self.assertIn("Download these figures", page)
        self.assertEqual(self.client.get(f"/exports/download?from=2026-10-14&to=2026-10-14&kind=absence&kind=incident_summary&format=xlsx").status_code, 200)

    def test_absenteeism_counts_follow_the_ticks(self):
        both = self.get().get_data(as_text=True)
        self.assertRegex(both, r'name="abs" value="sick" checked')
        suth = self.get("&abs=unplanned").get_data(as_text=True)
        self.assertNotRegex(suth, r'name="abs" value="sick" checked')
        self.assertRegex(suth, r'name="abs" value="unplanned" checked')

    def test_a_long_period_is_cut_and_said(self):
        # re-pinned in Phase AV: the page's own 92-day cap became the setting "weeks at a time" (13 by default) for
        # people who are not admins, supervisors or RTAs; this admin is limited only by the 13 months of records kept
        unit = self.key.replace(" ", "+")
        page = self.client.get(f"/incidents?program={unit}&from=2025-01-01&to=2026-10-14").get_data(as_text=True)
        self.assertIn("Records are kept 13 months; showing the last 400 days", page)


if __name__ == "__main__":
    unittest.main()
