# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: "add in the insights breaks missed count, coaching count, meeting, tasks etc, and remove out
of adherence"): the Incidents page shows a count and the time for every kind of incident, for everyone in the period and
for one associate when one is open."""
import unittest

from webapp import insights, insights_page
from webapp.tests import test_av_insights as _ins


class TheCountsByType(_ins.TheInsights):
    def test_the_counts_name_every_kind_with_its_count_and_time(self):
        got = insights_page.build(self.facts, "overview", "", _ins.WED, _ins.THU)["counts"]
        self.assertEqual([c["label"] for c in got], [label for _, label in insights.KINDS])
        by = {c["label"]: c for c in got}
        self.assertEqual(by["Missed breaks"]["n"], 1)
        self.assertGreater(by["Missed breaks"]["min"], 0)
        self.assertEqual((by["Late logins"]["n"], by["Late logins"]["min"]), (1, 60))
        self.assertEqual(by["Sick"]["n"], 1)
        self.assertEqual(by["Coaching"]["n"], 0)  # a kind with none is still listed: a zero is information
        for label in ("Coaching", "Meetings", "Tasks", "Training", "System issues", "Bio breaks"):
            self.assertIn(label, by)
        self.assertNotIn("Out of adherence", by)

    def test_one_associate_has_their_own_counts(self):
        found = insights_page.build(self.facts, "associates", "Associate 008", _ins.WED, _ins.THU)
        mine = {c["label"]: c["n"] for c in found["person_counts"]}
        self.assertEqual(mine["Missed breaks"], 1)
        self.assertEqual(mine["Late logins"], 0)

    def test_the_grid_cells_carry_the_time_as_well_as_the_count(self):
        heat = insights_page.build(self.facts, "overview", "", _ins.WED, _ins.THU)["heat"]
        row = heat[0]
        kinds = [k for k, _ in insights.KINDS]
        late = row["cells"][kinds.index("late")]
        self.assertEqual((late[0], late[2]), (1, 60))  # count, level, minutes
        sick = row["cells"][kinds.index("sick")]
        self.assertEqual(sick[2], 540)
        self.assertEqual(row["cells"][kinds.index("coaching")][2], 0)

    def test_the_incidents_tile_no_longer_names_out_of_adherence(self):
        tiles = insights_page.build(self.facts, "overview", "", _ins.WED, _ins.THU)["tiles"]
        self.assertNotIn("adherence", next(t for t in tiles if t["label"] == "Incidents")["note"].replace("Adherence", ""))


from webapp.tests import test_cancel_break as _cb  # noqa: E402


class TheCountsOnThePage(_cb.ThePage):
    def get(self, extra=""):
        return self.client.get(f"/incidents?program={self.key.replace(' ', '+')}&from=2026-10-11&to=2026-10-17{extra}"
                               ).get_data(as_text=True)

    def test_every_kind_is_listed_and_out_of_adherence_is_not(self):
        page = self.get()
        self.assertIn("Counts by type", page)
        for label in ("Missed breaks", "Coaching", "Meetings", "Tasks", "Training", "System issues", "Bio breaks"):
            self.assertIn(f'aria-label="{label}"', page)
        self.assertNotIn("Out of adherence", page)

    def test_the_grid_shows_a_duration_under_a_count(self):
        from webapp.tests.test_notify_daybook import WED, hm
        name, idx, kind, start, _ = self.with_breaks()
        self.addCleanup(self.store.delete_day_before, "2999-01-01")
        self.addCleanup(self.days.move_break, self.key, WED, name, idx, None, self.omar)
        self.days.move_break(self.key, WED, name, idx, hm(start + 5), self.omar, missed=True)
        page = self.get("&view=lobs")
        grid = page.split('class="ins-heat"', 1)[1].split("</table>", 1)[0]
        self.assertRegex(grid, r'<td class="lv\d">\d+<small>[^<]*(min|h)[^<]*</small></td>')

    def test_the_adherence_percentage_is_still_there(self):
        self.assertIn('aria-label="Adherence"', self.get())


if __name__ == "__main__":
    unittest.main()
