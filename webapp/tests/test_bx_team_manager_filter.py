# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BX (owner, 2026-11-23: "Add a small filter same as the one per shift start with team manager, and add team manager name next to
associates in smaller text just for reference and easier search"). The team manager is the one on the associate's account (People page), found as
swaps find an account: an active associate account with that roster name that can open the program. On the Timeline the filter sits under the
shift starts and works with them; the name is shown in small text beside the associate on the Timeline and the Days off tab. Made-up people."""
import html
import re
import unittest

from webapp.programs import ProgramBook
from webapp.tests.test_overtime_side import WED, _Overtime

PASS = "Made-up-pass-123"


class _Teams(_Overtime):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        store = cls.store
        pid = ProgramBook(store).unit(cls.key)["program"]["id"]
        page = cls.days.page(cls.key, WED)
        cls.working = [l["name"] for l in page["view"]["lanes"]]
        off = [n for n, _ in cls.days.off_today(cls.key, WED)]

        def person(username, name, **fields):
            uid = store.add_user(username, name, PASS, must_change=False)
            store.update_user(uid, **fields)
            store.set_user_programs(uid, [pid])
            return uid

        cls.tm1 = person("tm01", "Team Manager 01", is_team_manager=1)
        cls.tm2 = person("tm02", "Team Manager 02", is_team_manager=1)
        cls.team1 = cls.working[:3] + off[:1]
        cls.team2 = cls.working[3:5]
        for i, name in enumerate(cls.team1):
            person(f"a1{i}", name, is_associate=1, roster_name=name, team_manager_id=cls.tm1)
        for i, name in enumerate(cls.team2):
            person(f"a2{i}", name, is_associate=1, roster_name=name, team_manager_id=cls.tm2)
        cls.off_with_tm = off[0]

    def timeline(self, **args):
        q = "&".join(f"{k}={v}" for k, v in args.items())
        reply = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}" + (f"&{q}" if q else ""))
        self.assertEqual(reply.status_code, 200)
        return html.unescape(reply.get_data(as_text=True))

    @staticmethod
    def lanes(page):
        return re.findall(r'<div class="tl-who"><b title="([^"]+)">', page)


class TheTeams(_Teams):
    def test_each_linked_associate_has_their_team_manager(self):
        team = self.days.team_of(self.key)
        self.assertEqual({n: t["name"] for n, t in team.items() if n in self.team1 + self.team2},
                         {**{n: "Team Manager 01" for n in self.team1}, **{n: "Team Manager 02" for n in self.team2}})
        self.assertNotIn(self.working[6], team)

    def test_the_name_is_shown_small_next_to_the_associate(self):
        page = self.timeline()
        for name in self.team1[:3]:
            self.assertRegex(page, rf'(?s)<b title="{name}"><a [^>]*>{name}</a><small class="tl-tm">Team Manager 01</small></b>')
        self.assertNotRegex(page, rf'(?s)<b title="{self.working[6]}">.{{0,400}}?class="tl-tm"')

    def test_the_filter_lists_each_team_manager_and_nobody(self):
        page = self.timeline()
        bar = re.search(r'(?s)<div class="shiftbar" role="group" aria-label="Filter by team manager">.*?</div>', page).group(0)
        self.assertIn("<b>All team managers</b>", bar)
        self.assertRegex(bar, rf"<b>Team Manager 01</b><small>3 people")
        self.assertRegex(bar, rf"<b>Team Manager 02</b><small>2 people")
        self.assertRegex(bar, rf"<b>No team manager</b><small>{len(self.working) - 5} people")

    def test_picking_a_team_manager_shows_only_their_people(self):
        self.assertEqual(self.lanes(self.timeline(tm=self.tm1)), self.team1[:3])
        self.assertEqual(set(self.lanes(self.timeline(tm="none"))), set(self.working[5:]))

    def test_it_works_together_with_the_shift_start_filter_and_keeps_it(self):
        who, seg = next((l["name"], s) for l in self.days.page(self.key, WED)["view"]["lanes"] if l["name"] in self.team1
                        for s in l["segments"] if s["offset"] == 0)          # someone of the team with a shift starting today
        shift = f"{seg['start'] // 60:02d}:{seg['start'] % 60:02d}"
        both = self.timeline(tm=self.tm1, shift=shift)
        shown = self.lanes(both)
        self.assertIn(who, shown)
        self.assertTrue(set(shown) <= set(self.team1))
        bar = re.search(r'(?s)aria-label="Filter by shift start">.*?</div>', both).group(0)
        self.assertIn(f"tm={self.tm1}", bar)                      # a shift link keeps the team manager
        tm_bar = re.search(r'(?s)aria-label="Filter by team manager">.*?</div>', both).group(0)
        self.assertIn(f"shift={shift}", tm_bar)                   # and a team manager link keeps the shift

    def test_an_unknown_team_manager_shows_everyone(self):
        self.assertEqual(len(self.lanes(self.timeline(tm="99999"))), len(self.working))

    def test_the_days_off_tab_shows_the_team_manager_too(self):
        page = self.timeline(view="daysoff")
        self.assertRegex(page, rf'<th scope="row">{self.off_with_tm}<small class="tl-tm">Team Manager 01</small></th>')


class NoTeams(_Overtime):
    def test_with_no_team_managers_linked_there_is_no_filter(self):
        page = html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}").get_data(as_text=True))
        self.assertNotIn("Filter by team manager", page)
        self.assertNotIn('class="tl-tm"', page)


if __name__ == "__main__":
    unittest.main()
