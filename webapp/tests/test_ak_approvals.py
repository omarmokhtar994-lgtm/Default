# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK item 4, approvals (owner, 2026-10-15: assign associates to leaders "so they can approve their requests";
answers: admins and supervisors may approve for an absent team manager, swaps need both team managers, and "to see
where it's pending"). An associate with no team manager is approved by any team manager of the program (ruling)."""
import html
from datetime import date

from webapp.tests import test_ak_team_managers as tmt
from webapp.tests.test_runs import token

THU, TUE = date(2026, 10, 15), date(2026, 10, 13)


class _Requests(tmt._People):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tm3 = cls.add("tm03", "Team Manager 03", "team_manager", [cls.pid])
        cls.planner = cls.add("plan01", "Planner 01", "planner", [cls.pid])
        cls.leave, cls.swaps = cls.app.extensions["leave"], cls.app.extensions["swaps"]
        # a pair who may swap on Thursday, each with an account
        taken = {cls.store.get_user(a)["roster_name"] for a in cls.assoc}
        roster = [n for n, c in cls.days.roster(cls.key, THU) if c[:1].isdigit() and n not in taken]
        cls.pair = next((n, ok[0]) for n in roster
                        for ok in [[c["name"] for c in cls.swaps.candidates(cls.key, THU, n)
                                    if c["ok"] and c["name"] not in taken]] if ok)
        cls.pair_ids = [cls.add(f"swap{i}", name, "associate", [cls.pid], name) for i, name in enumerate(cls.pair)]

    def setUp(self):
        with self.store._db() as db:  # each test asks afresh
            db.execute("delete from leave_requests")
            db.execute("delete from swap_requests")

    def user(self, uid):
        return self.store.get_user(uid)

    def team(self, associate, tm):
        self.store.update_user(associate, team_manager_id=tm)

    def ask_leave(self, associate):
        name = self.user(associate)["roster_name"]
        return self.leave.ask(self.key, name, associate, "Planned leave", THU, THU, "", TUE)

    def offer_swap(self):
        a, b = self.pair
        made = self.swaps.offer(self.key, THU, a, self.pair_ids[0], b, "", TUE)
        self.swaps.answer(made, self.user(self.pair_ids[1]), accept=True)
        return made


class TheLeave(_Requests):
    def test_their_team_manager_approves(self):
        self.team(self.assoc[0], self.tm)
        made = self.ask_leave(self.assoc[0])
        self.assertEqual(self.leave.decide(made, self.user(self.tm), True), "Approved by the TM: the RTA decides next.")

    def test_another_team_manager_is_told_who_decides(self):
        self.team(self.assoc[0], self.tm)
        made = self.ask_leave(self.assoc[0])
        with self.assertRaises(ValueError) as said:
            self.leave.decide(made, self.user(self.tm3), True)
        self.assertEqual(str(said.exception), "Waiting for Team Manager 01, the team manager of Associate 003.")
        self.assertFalse(self.leave.may_decide(self.store.get_leave(made), self.user(self.tm3)))

    def test_an_admin_or_supervisor_approves_in_their_place(self):
        self.team(self.assoc[0], self.tm)
        made = self.ask_leave(self.assoc[0])
        admin = next(u for u in self.store.list_users() if u["is_admin"])
        self.assertTrue(self.leave.may_decide(self.store.get_leave(made), admin))
        self.leave.decide(made, admin, True)

    def test_with_no_team_manager_any_team_manager_of_the_program(self):
        self.team(self.assoc[1], None)
        made = self.ask_leave(self.assoc[1])
        self.assertTrue(self.leave.may_decide(self.store.get_leave(made), self.user(self.tm3)))
        self.assertFalse(self.leave.may_decide(self.store.get_leave(made), self.user(self.planner)))

    def test_where_it_waits(self):
        self.team(self.assoc[2], self.tm)
        made = self.ask_leave(self.assoc[2])
        found = next(r for r in self.leave.waiting(self.key) if r["id"] == made)
        self.assertEqual(found["waiting_on"], "Waiting for Team Manager 01, the team manager of Associate 008")
        self.leave.decide(made, self.user(self.tm), True)
        found = next(r for r in self.leave.waiting(self.key) if r["id"] == made)
        self.assertEqual(found["waiting_on"], "Approved by Team Manager 01, waiting for the RTA")
        mine = next(r for r in self.leave.mine(self.key, "Associate 008") if r["id"] == made)
        self.assertEqual(mine["waiting_on"], "Approved by Team Manager 01, waiting for the RTA")

    def test_the_count_is_their_team(self):
        self.team(self.assoc[0], self.tm)
        self.ask_leave(self.assoc[0])
        self.assertEqual(self.leave.count_for(self.key, self.user(self.tm_away)), 0)
        self.assertGreaterEqual(self.leave.count_for(self.key, self.user(self.tm)), 1)


class TheSwaps(_Requests):
    def test_two_teams_need_both_team_managers(self):
        a, b = self.pair
        self.team(self.pair_ids[0], self.tm)
        self.team(self.pair_ids[1], self.tm3)
        made = self.offer_swap()
        self.assertEqual(self.swaps.waiting_on(self.store.get_swap(made)),
                         f"Waiting for Team Manager 01 ({a}) and Team Manager 03 ({b})")
        said = self.swaps.decide(made, self.user(self.tm), True)
        self.assertEqual(said, f"Approved for {a}. Waiting for Team Manager 03 ({b}).")
        self.assertEqual(self.store.get_swap(made)["status"], "waiting_tm")
        with self.assertRaises(ValueError):  # the same team manager cannot approve the other side
            self.swaps.decide(made, self.user(self.tm), True)
        self.assertTrue(self.swaps.decide(made, self.user(self.tm3), True).startswith("Approved: "))
        self.assertEqual(self.store.get_swap(made)["status"], "approved")

    def test_one_team_manager_approves_once(self):
        self.team(self.pair_ids[0], self.tm)
        self.team(self.pair_ids[1], self.tm)
        made = self.offer_swap()
        self.assertEqual(self.swaps.waiting_on(self.store.get_swap(made)),
                         f"Waiting for Team Manager 01 ({self.pair[0]} and {self.pair[1]})")
        self.assertTrue(self.swaps.decide(made, self.user(self.tm), True).startswith("Approved: "))

    def test_a_backup_approves_both_sides(self):
        self.team(self.pair_ids[0], self.tm)
        self.team(self.pair_ids[1], self.tm3)
        made = self.offer_swap()
        admin = next(u for u in self.store.list_users() if u["is_admin"])
        self.assertTrue(self.swaps.decide(made, admin, True).startswith("Approved: "))

    def test_a_refusal_by_either_ends_it(self):
        self.team(self.pair_ids[0], self.tm)
        self.team(self.pair_ids[1], self.tm3)
        made = self.offer_swap()
        self.assertEqual(self.swaps.decide(made, self.user(self.tm3), False, "Short that day"), "Refused.")


class ThePage(_Requests):
    def test_the_requests_page_says_where_each_waits(self):
        self.team(self.assoc[0], self.tm)
        self.ask_leave(self.assoc[0])
        body = html.unescape(self.client.get(f"/requests?program={self.key.replace(' ', '+')}").get_data(as_text=True))
        self.assertIn("Waiting for Team Manager 01, the team manager of Associate 003", body)

    def test_a_team_manager_signs_in_and_sees_approve_only_for_their_team(self):
        from webapp.tests.test_runs import sign_in
        self.store.set_password(self.tm3, "Tm-pass-123456", must_change=False)
        self.team(self.assoc[0], self.tm)
        made = self.ask_leave(self.assoc[0])
        client = sign_in(self.app, "tm03", "Tm-pass-123456")
        body = html.unescape(client.get(f"/requests?program={self.key.replace(' ', '+')}").get_data(as_text=True))
        self.assertNotIn(f'action="/requests/leave/{made}"', body)
        got = client.post(f"/requests/leave/{made}", data={"csrf_token": token(client), "decision": "approve"},
                          follow_redirects=True)
        self.assertIn("Waiting for Team Manager 01, the team manager of Associate 003.",
                      html.unescape(got.get_data(as_text=True)))
