# © 2026 Omar Mokhtar. All rights reserved.
"""Phase CA (owner, 2026-11-23: "associates by default on present which maybe missed by the RTA to be attentive if they are actually present or not
can we name the default like present default and they change it to present manually?"). Someone with no attendance saved for a shift shows
"Not checked" with an amber edge; picking Present saves it as checked. Until then they still count on the floor as before (the floor's
numbers do not change), and the shift-start and team manager filters say how many are not checked. Made-up people."""
import html
import re
import unittest

from webapp.day import shift_groups, team_groups
from webapp.tests.test_overtime_side import WED, _Overtime


class TheDefault(_Overtime):
    def setUp(self):
        self.addCleanup(self.clear)

    def clear(self):
        with self.store._db() as db:
            db.execute("delete from attendance where program = ?", (self.key,))

    def view(self):
        return self.days.page(self.key, WED)["view"]

    def own(self, name):
        return next(s for l in self.view()["lanes"] if l["name"] == name for s in l["segments"] if s["offset"] == 0)

    def someone(self):
        return next(l["name"] for l in self.view()["lanes"] if any(s["offset"] == 0 for s in l["segments"]))

    def timeline(self):
        return html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}").get_data(as_text=True))

    def select_of(self, page, name):
        return re.search(rf'(?s)<b title="{name}">.*?(<select class="att[^"]*".*?</select>)', page).group(1)

    def test_a_shift_with_nothing_saved_is_not_marked_and_one_saved_as_present_is(self):
        name = self.someone()
        self.assertEqual((self.own(name)["status"], self.own(name)["marked"]), ("Present", False))
        self.days.set_status(self.key, WED, name, "Present", 1)
        self.assertEqual((self.own(name)["status"], self.own(name)["marked"]), ("Present", True))

    def test_the_timeline_says_present_not_checked_until_present_is_picked(self):
        name = self.someone()
        sel = self.select_of(self.timeline(), name)
        self.assertRegex(sel, r'^<select class="att unchecked"')
        self.assertIn('<option value="" selected disabled>Not checked</option>', sel)
        self.assertRegex(sel, r'<option value="Present">Present</option>')
        self.days.set_status(self.key, WED, name, "Present", 1)
        sel = self.select_of(self.timeline(), name)
        self.assertRegex(sel, r'^<select class="att"')
        self.assertNotIn("not checked", sel)
        self.assertIn('<option value="Present" selected>Present</option>', sel)

    def test_another_status_is_marked_too(self):
        name = self.someone()
        self.days.set_status(self.key, WED, name, "Sick", 1)
        self.assertNotIn("not checked", self.select_of(self.timeline(), name))

    def test_the_floor_counts_them_the_same_checked_or_not(self):
        before = [c["now"] for c in self.view()["cells"]]
        for l in self.view()["lanes"]:
            if any(s["offset"] == 0 for s in l["segments"]):
                self.days.set_status(self.key, WED, l["name"], "Present", 1)
        self.assertEqual([c["now"] for c in self.view()["cells"]], before)

    def test_the_filters_count_who_is_not_checked(self):
        view = self.view()
        everyone = sum(g["people"] for g in shift_groups(view))
        self.assertEqual(sum(g["unchecked"] for g in shift_groups(view)), everyone)
        name = self.someone()
        self.days.set_status(self.key, WED, name, "Present", 1)
        view = self.view()
        self.assertEqual(sum(g["unchecked"] for g in shift_groups(view)), everyone - 1)
        team = {l["name"]: {"id": 7, "name": "Team Lead 001"} for l in view["lanes"]}
        self.assertEqual([g["unchecked"] for g in team_groups(view, team)], [everyone - 1])
        page = self.timeline()
        self.assertRegex(page, r"(?s)aria-label=\"Filter by shift start\">.*?, <em class=\"uncheck\">\d+ not checked</em>")


if __name__ == "__main__":
    unittest.main()
