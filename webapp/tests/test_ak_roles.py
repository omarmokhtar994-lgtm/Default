# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK item 4 (owner, 2026-10-15: "i need to adjust as i wish the options they can have and supervisor can have
and what they can have access for etc make it adjustable"): the admin sets what Planner, Team manager and Supervisor
may see and do, on Roles. Every check is on the server (a link hidden is not the guard); the defaults keep what
planners and supervisors did before; admins keep everything; Home always opens."""
import html

from webapp.permissions import CATALOGUE, ROLE_NAMES, allowed
from webapp.tests import test_ak_team_managers as tmt
from webapp.tests.test_runs import sign_in, token


class _Roles(tmt._People):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.planner = cls.add("plan01", "Planner 01", "planner", [cls.pid])
        for uid in (cls.planner, cls.tm):
            cls.store.set_password(uid, "Some-pass-12345", must_change=False)

    def setUp(self):
        self.store.set_role_permissions({})  # the defaults

    def as_user(self, username):
        return sign_in(self.app, username, "Some-pass-12345")

    def save(self, allow):
        return self.client.post("/admin/roles", data={"csrf_token": token(self.client), "allow": allow},
                                follow_redirects=True)

    def everything_but(self, role, key):
        return [f"{r}|{k}" for r in ROLE_NAMES for k in CATALOGUE if (r, k) != (role, key)]


class TheDefaults(_Roles):
    def test_planners_and_supervisors_keep_what_they_had(self):
        planner, sup = {"is_admin": 0, "is_supervisor": 0}, {"is_admin": 0, "is_supervisor": 1}
        for key in ("rta_view", "rta_change", "schedules_view", "schedules_change", "runs", "exports", "approve_rta"):
            self.assertTrue(allowed(self.store, planner, key), key)
        for key in ("approve_tm", "people", "setup"):
            self.assertFalse(allowed(self.store, planner, key), key)
            self.assertTrue(allowed(self.store, sup, key), key)

    def test_team_managers_see_and_approve_but_do_not_change_the_day(self):
        tm = self.store.get_user(self.tm)
        self.assertTrue(allowed(self.store, tm, "rta_view"))
        self.assertTrue(allowed(self.store, tm, "approve_tm"))
        self.assertFalse(allowed(self.store, tm, "rta_change"))
        client = self.as_user("tm01")
        got = client.post("/day/attendance", data={"csrf_token": token(client), "program": self.key,
                                                   "date": "2026-10-14", "associate": "Associate 008",
                                                   "status": "Sick"})
        self.assertEqual(got.status_code, 403)

    def test_admins_are_never_blocked(self):
        self.save([])  # every role loses everything
        self.assertEqual(self.client.get("/exports").status_code, 200)
        self.assertTrue(allowed(self.store, {"is_admin": 1}, "people"))


class TheAdminPage(_Roles):
    def test_the_matrix_is_saved_and_enforced(self):
        body = html.unescape(self.client.get("/admin/roles").get_data(as_text=True))
        self.assertIn("Roles", body)
        self.assertRegex(body, r'name="allow" value="Planner\|exports"[^>]* checked>')
        self.save(self.everything_but("Planner", "exports"))
        client = self.as_user("plan01")
        self.assertEqual(client.get("/exports").status_code, 403)
        self.assertEqual(client.get("/exports/download?start=2026-10-14&end=2026-10-14&kind=summary").status_code, 403)
        self.assertNotIn('href="/exports"', client.get("/").get_data(as_text=True))

    def test_a_role_with_nothing_still_opens_home(self):
        self.save([k for k in self.everything_but("Planner", "x") if not k.startswith("Planner|")])
        client = self.as_user("plan01")
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get(f"/day?program={self.key}&date=2026-10-14").status_code, 403)

    def test_approving_can_be_given_to_planners(self):
        self.save(self.everything_but("x", "x") + [])
        planner = self.store.get_user(self.planner)
        self.assertTrue(allowed(self.store, planner, "approve_tm"))

    def test_only_admins_set_roles(self):
        client = self.as_user("plan01")
        self.assertEqual(client.get("/admin/roles").status_code, 403)
        self.assertEqual(client.post("/admin/roles", data={"csrf_token": token(client),
                                                           "allow": ["Planner|people"]}).status_code, 403)
        self.assertFalse(allowed(self.store, self.store.get_user(self.planner), "people"))

    def test_unknown_roles_and_keys_are_ignored(self):
        self.save(["Admin|people", "Planner|delete_everything", "Planner|exports"])
        self.assertTrue(allowed(self.store, self.store.get_user(self.planner), "exports"))
        self.assertFalse(allowed(self.store, self.store.get_user(self.planner), "runs"))

    def test_people_can_be_given_to_team_managers(self):
        client = self.as_user("tm01")
        self.assertEqual(client.get("/admin/users").status_code, 403)
        self.save(self.everything_but("x", "x"))
        self.assertEqual(client.get("/admin/users").status_code, 200)

    def test_back_to_the_defaults_needs_the_tick(self):
        """Review (better-interface, 2026-10-15): putting every role back to the defaults undoes an admin's settings for
        everyone, so it asks for a tick first, as deleting a schedule does."""
        self.save(self.everything_but("Planner", "exports"))
        refused = self.client.post("/admin/roles", data={"csrf_token": token(self.client), "reset": "1"},
                                   follow_redirects=True)
        self.assertIn("Tick the box to put every role back to the defaults.", html.unescape(refused.get_data(as_text=True)))
        self.assertFalse(allowed(self.store, self.store.get_user(self.planner), "exports"))
        self.client.post("/admin/roles", data={"csrf_token": token(self.client), "reset": "1", "confirm": "1"})
        self.assertTrue(allowed(self.store, self.store.get_user(self.planner), "exports"))
        body = self.client.get("/admin/roles").get_data(as_text=True)
        self.assertRegex(body, r'<input type="checkbox" name="confirm" value="1" required>')
