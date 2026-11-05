# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T4: associate accounts (samples ag05 to ag07, owner's approval 2026-10-14).

An admin or a supervisor adds an associate on People, linked to the person's name on the program's schedule (one
account per name). Signed in, an associate reaches only their own pages: anything else sends them to My week (a
page) or is refused (a form). Their menu has My week only, and no Go to.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from webapp.access import role
from webapp.programs import ProgramBook
from webapp.store import Store
from webapp.tests.test_runs import TOKEN, sign_in, token


class Associates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)
        cls.program_id = next(p["id"] for p in ProgramBook(cls.store).tree() if p["name"] == "SAKS")

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def add(self, username, roster_name, client=None, kind="associate"):
        client = client or self.admin
        return client.post("/admin/users", data={
            "csrf_token": token(client), "username": username, "display_name": roster_name,
            "password": "Temporary-pass-1", "role": kind, "roster_name": roster_name,
            "programs": [str(self.program_id)]}, follow_redirects=True).get_data(as_text=True)

    def user(self, username):
        return next((u for u in self.store.list_users() if u["username"] == username), None)

    def signed_in(self, username, roster_name):
        if self.user(username) is None:
            self.add(username, roster_name)
        self.store.set_password(self.user(username)["id"], "Associate-pass-1", must_change=False)
        return sign_in(self.app, username, "Associate-pass-1")

    def test_an_admin_adds_an_associate_linked_to_their_name(self):
        self.add("assoc07", "Associate 007")
        found = self.user("assoc07")
        self.assertEqual((found["is_associate"], found["roster_name"], found["all_programs"]), (1, "Associate 007", 0))
        self.assertEqual(role(found), "Associate")
        self.assertEqual(self.store.user_program_ids(found["id"]), [self.program_id])

    def test_the_name_must_be_on_the_programs_schedule(self):
        page = self.add("ghost", "Associate 999")
        self.assertIn("Associate 999 is not on a schedule of", page)
        self.assertIsNone(self.user("ghost"))
        page = self.add("noname", "")
        self.assertIn("Pick their name on the schedule.", page)
        self.assertIsNone(self.user("noname"))

    def test_one_account_per_name(self):
        self.add("assoc08", "Associate 008")
        page = self.add("assoc08b", "Associate 008")
        self.assertIn("Associate 008 already has an account (assoc08).", page)
        self.assertIsNone(self.user("assoc08b"))

    def test_a_supervisor_adds_associates_for_their_programs(self):
        uid = self.store.add_user("sup", "Sup", "Supervisor-pass-1", must_change=False)
        self.store.update_user(uid, is_supervisor=1)
        self.store.set_user_programs(uid, [self.program_id])
        sup = sign_in(self.app, "sup", "Supervisor-pass-1")
        self.assertIn('<option value="associate">Associate</option>', sup.get("/admin/users").get_data(as_text=True))
        self.add("assoc09", "Associate 009", client=sup)
        self.assertEqual(self.user("assoc09")["roster_name"], "Associate 009")

    def test_the_form_lists_the_names_on_the_schedule(self):
        page = self.admin.get("/admin/users").get_data(as_text=True)
        self.assertIn('<datalist id="roster-names">', page)
        # re-pinned (Phase AO): each name now carries the programs whose schedules hold it (data-programs), so the
        # form can list only the ticked programs' names
        self.assertRegex(page, r'<option value="Associate 013" data-programs="\d+( \d+)*">')

    def test_an_associate_reaches_only_their_own_pages(self):
        me = self.signed_in("assoc10", "Associate 010")
        q = f"program={self.key.replace(' ', '+')}&date=2026-10-14"
        for url in ("/", f"/day?{q}", f"/overview?{q}", f"/week?program={self.key.replace(' ', '+')}",
                    "/admin/users", "/programs", "/exports", "/team", f"/goto?q=a&{q}"):
            with self.subTest(url):
                got = me.get(url)
                self.assertEqual(got.status_code, 302)
                # Re-pinned in Phase AU (owner, 2026-10-21): an associate opens on Today, which is /me/breaks.
                self.assertTrue(got.headers["Location"].endswith("/me/breaks"), got.headers["Location"])
        mine = TOKEN.search(me.get("/me").get_data(as_text=True)).group(1)  # their Home is My week
        refused = me.post("/admin/users", data={"csrf_token": mine, "username": "x", "password": "y" * 12})
        self.assertEqual(refused.status_code, 403)
        self.assertIsNone(self.user("x"))
        for url in ("/me", "/static/app.css", "/account/password"):
            with self.subTest(url):
                # AN followup: close the static-file response after checking access.
                self.assertEqual(me.get(url, buffered=True).status_code, 200)

    def test_their_menu_has_my_week_only(self):
        page = self.signed_in("assoc11", "Associate 011").get("/me").get_data(as_text=True)
        side = page[page.index('class="leftnav"'):page.index("</aside>")]
        self.assertIn('href="/me"', side)
        for gone in ('href="/day', 'href="/programs"', 'href="/exports"', "New schedule", "data-unit-pick"):
            self.assertNotIn(gone, side)
        self.assertNotIn("data-goto-open", page)
        self.assertNotIn('<dialog id="goto"', page)
        self.assertIn("Associate 011", page)

    def test_a_staff_member_never_lands_on_my_week(self):
        self.assertEqual(self.admin.get("/me").status_code, 302)


class TheMigration(unittest.TestCase):
    def test_older_databases_gain_the_columns(self):
        path = Path(tempfile.mkdtemp()) / "old.db"
        with sqlite3.connect(path) as db:
            db.execute("create table users (id integer primary key, username text unique not null, display_name text"
                       " not null, password_hash text not null, is_admin integer not null default 0, active integer"
                       " not null default 1, must_change integer not null default 1, failed integer not null default 0,"
                       " locked_until real not null default 0, created real not null, is_supervisor integer not null"
                       " default 0, all_programs integer not null default 0)")
            db.execute("insert into users (username, display_name, password_hash, created) values ('a', 'A', 'x', 0)")
        Store(path)
        with sqlite3.connect(path) as db:
            row = db.execute("select is_associate, roster_name from users").fetchone()
        self.assertEqual(row, (0, ""))


if __name__ == "__main__":
    unittest.main()
