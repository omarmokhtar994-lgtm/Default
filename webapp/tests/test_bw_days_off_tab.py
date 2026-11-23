# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BW (owner, 2026-11-23: "Add a tab in RTA for all available off days for that day in order to cancel any of them if needed"): the RTA's
Days off tab lists everyone off that day and not called in yet, with their shift the day before and after, and cancels any of them on a Shift
Library shift or typed times through the same "Day off cancelled" record as + Add (same checks, the rest gap kept with a warning)."""
import html
import re
import unittest

from webapp.attendance import CALLED_IN
from webapp.tests.test_overtime_side import WED, _Overtime
from webapp.tests.test_runs import token


class TheTab(_Overtime):
    def setUp(self):
        self.off = self.days.off_today(self.key, WED)
        self.shifts = self.days.shift_library(self.key, WED)
        self.assertGreater(len(self.off), 1, "the made-up week has people off on Wednesday")

    def tearDown(self):
        for r in self.store.list_activities(self.key, [WED.isoformat()]):
            if r["kind"] == CALLED_IN:
                self.store.delete_activity(r["id"])

    def page(self):
        reply = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}&view=daysoff")
        self.assertEqual(reply.status_code, 200)
        return html.unescape(reply.get_data(as_text=True))

    def cancel(self, name, **fields):
        data = {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), "what": "Day off cancelled",
                "associate": name, "view": "daysoff", **fields}
        return self.client.post("/day/add", data=data, follow_redirects=True)

    def test_the_tab_is_in_the_rtas_views(self):
        page = self.page()
        self.assertRegex(page, r'<a href="[^"]*view=daysoff[^"]*" class="on" aria-current="page">Days off</a>')

    def test_it_lists_everyone_off_that_day_with_a_cancel_form_each(self):
        page = self.page()
        self.assertIn(f"{len(self.off)} people off on Wednesday 14 Oct", page)
        for name, _ in self.off:
            row = re.search(rf'(?s)<tr[^>]*>\s*<th scope="row">{name}</th>.*?</tr>', page)
            self.assertIsNotNone(row, name)
            self.assertIn('name="what" value="Day off cancelled"', row.group(0))
            self.assertIn(f'name="associate" value="{name}"', row.group(0))
            self.assertIn("Cancel day off", row.group(0))
            for label, _, _ in self.shifts[:3]:
                self.assertIn(f'<option value="{label}"', row.group(0))

    def test_the_day_before_and_after_are_shown(self):
        row = self.days.days_off_panel(self.key, WED)["off"][0]
        # "tm" added in Phase BX (owner, 2026-11-23: the team manager beside each associate)
        self.assertEqual(set(row), {"name", "language", "before", "after", "tm"})

    def test_cancelling_on_a_library_shift_calls_them_in_and_takes_them_off_the_list(self):
        name = self.off[0][0]
        label, lo, hi = self.shifts[0]
        page = html.unescape(self.cancel(name, shift=label).get_data(as_text=True))
        self.assertIn(f"Recorded: {name}, Day off cancelled", page)
        self.assertEqual([(r["start"], r["end_min"]) for r in self.store.list_activities(self.key, [WED.isoformat()])
                          if r["associate"] == name and r["kind"] == CALLED_IN], [(lo, hi)])
        after = self.page()
        self.assertNotRegex(after, rf'<th scope="row">{name}</th>')
        self.assertIn(f"{len(self.off) - 1} people off", after)
        self.assertRegex(after, rf"(?s)Already called in.*{name}")

    def test_typed_times_win_over_the_shift_pick(self):
        name = self.off[1][0]
        self.cancel(name, shift=self.shifts[0][0], **{"from": "10:30", "to": "16:30"})
        self.assertEqual([(r["start"], r["end_min"]) for r in self.store.list_activities(self.key, [WED.isoformat()])
                          if r["associate"] == name and r["kind"] == CALLED_IN], [(630, 990)])

    def test_no_shift_and_no_times_is_refused_in_words(self):
        page = html.unescape(self.cancel(self.off[0][0]).get_data(as_text=True))
        self.assertIn("Pick a shift from the Shift Library, or type the start and end.", page)
        self.assertEqual([r for r in self.store.list_activities(self.key, [WED.isoformat()]) if r["kind"] == CALLED_IN], [])

    def test_an_unknown_shift_is_refused(self):
        page = html.unescape(self.cancel(self.off[0][0], shift="25:00 - 26:00").get_data(as_text=True))
        self.assertIn("Pick a shift from the Shift Library, or type the start and end.", page)


if __name__ == "__main__":
    unittest.main()
