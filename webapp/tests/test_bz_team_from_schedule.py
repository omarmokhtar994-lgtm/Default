# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BZ (owner, 2026-11-23: "Why not taken from the schedule uploaded already?"): the RTA's team manager comes from the Schedule tab's TL column
of the schedule in use for that day when nothing else names one. Order: the associate's account (People page), then the team managers sheet (a
correction), then the TL column. A TL that is a team manager's account joins it. This made-up schedule's TL is "Team Lead 001" for everyone."""
import unittest

from webapp.day import team_groups
from webapp.programs import ProgramBook
from webapp.tests.test_overtime_side import WED, _Overtime


class TheScheduleColumn(_Overtime):
    def setUp(self):
        self.lanes = [l["name"] for l in self.days.page(self.key, WED)["view"]["lanes"]]
        self.addCleanup(self.days.set_team_sheet, self.key, {})

    def test_everyone_gets_the_tl_of_the_schedule_in_use_that_day(self):
        team = self.days.team_of(self.key, WED)
        self.assertEqual({team[n]["name"] for n in self.lanes}, {"Team Lead 001"})

    def test_without_a_day_the_column_is_not_read(self):
        self.assertEqual(self.days.team_of(self.key), {})

    def test_the_sheet_corrects_the_column(self):
        self.days.set_team_sheet(self.key, {self.lanes[0]: "Team Lead 002"})
        team = self.days.team_of(self.key, WED)
        self.assertEqual((team[self.lanes[0]]["name"], team[self.lanes[1]]["name"]), ("Team Lead 002", "Team Lead 001"))

    def test_a_tl_that_is_a_team_manager_account_joins_it(self):
        store = self.store
        tm = store.add_user("bz_tl01", "Team Lead 001", "Made-up-pass-123", must_change=False)
        store.update_user(tm, is_team_manager=1)
        store.set_user_programs(tm, [ProgramBook(store).unit(self.key)["program"]["id"]])
        try:
            team = self.days.team_of(self.key, WED)
            self.assertEqual(team[self.lanes[0]], {"id": tm, "name": "Team Lead 001"})
            groups = team_groups(self.days.page(self.key, WED)["view"], team)
            self.assertEqual([(g["key"], g["people"]) for g in groups], [(str(tm), len(self.lanes))])
        finally:
            store.update_user(tm, is_team_manager=0)

    def test_the_days_off_tab_has_it_too(self):
        off = self.days.days_off_panel(self.key, WED)["off"]
        self.assertTrue(off)
        self.assertEqual({p["tm"] for p in off}, {"Team Lead 001"})


if __name__ == "__main__":
    unittest.main()
