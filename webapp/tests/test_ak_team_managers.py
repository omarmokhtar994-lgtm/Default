# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK item 4 (owner, 2026-10-15: "We need to create accounts under Team Manager role and i need a way to assign
associates to specific leaders so they can approve their requests"; answers: a new role next to Supervisor, a pick
per associate on the People page and many at once). A team manager is offered and kept only when they share one of
the associate's programs."""
import html
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.store import Store
from webapp.tests import test_overtime_side as ots
from webapp.tests.test_runs import token


class _People(ots._Overtime):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        book = ProgramBook(cls.store)
        cls.pid = next(p["id"] for p in book.tree() if p["name"] == "SAKS")
        cls.other = book.add_program("Other")
        cls.tm = cls.add("tm01", "Team Manager 01", "team_manager", [cls.pid])
        cls.tm_away = cls.add("tm02", "Team Manager 02", "team_manager", [cls.other])
        cls.assoc = [cls.add(f"assoc{n:02d}", f"Associate {n:03d}", "associate", [cls.pid], f"Associate {n:03d}")
                     for n in (3, 5, 8)]

    @classmethod
    def add(cls, username, name, kind, programs, roster=""):
        cls.client.post("/admin/users", data={"csrf_token": token(cls.client), "username": username,
                                              "display_name": name, "password": "Temp-pass-1234", "role": kind,
                                              "roster_name": roster, "programs": [str(p) for p in programs]})
        return next(u["id"] for u in cls.store.list_users() if u["username"] == username)

    def people(self):
        return html.unescape(self.client.get("/admin/users").get_data(as_text=True))

    def set_one(self, who, tm):
        return self.client.post(f"/admin/users/{who}/team", data={"csrf_token": token(self.client),
                                                                   "team_manager": str(tm)}, follow_redirects=True)


class TheRole(_People):
    def test_a_team_manager_account(self):
        user = self.store.get_user(self.tm)
        self.assertEqual((user["is_team_manager"], user["is_supervisor"], user["is_admin"]), (1, 0, 0))
        self.assertIn('<span class="role role-team-manager">Team manager</span>', self.people())


class TheAssigning(_People):
    def test_one_associate_gets_a_team_manager(self):
        got = html.unescape(self.set_one(self.assoc[0], self.tm).get_data(as_text=True))
        self.assertIn("Associate 003's team manager is Team Manager 01.", got)
        self.assertEqual(self.store.get_user(self.assoc[0])["team_manager_id"], self.tm)

    def test_several_at_once(self):
        got = self.client.post("/admin/users/team", data={"csrf_token": token(self.client), "team_manager": str(self.tm),
                                                          "who": [str(a) for a in self.assoc]}, follow_redirects=True)
        self.assertIn("3 associates now have Team Manager 01 as their team manager.",
                      html.unescape(got.get_data(as_text=True)))
        self.assertEqual({self.store.get_user(a)["team_manager_id"] for a in self.assoc}, {self.tm})

    def test_only_a_team_manager_of_their_programs(self):
        got = html.unescape(self.set_one(self.assoc[1], self.tm_away).get_data(as_text=True))
        self.assertIn("Team Manager 02 has none of Associate 005's programs.", got)
        self.assertIsNone(self.store.get_user(self.assoc[1])["team_manager_id"])

    def test_cleared(self):
        self.set_one(self.assoc[2], self.tm)
        self.set_one(self.assoc[2], "")
        self.assertIsNone(self.store.get_user(self.assoc[2])["team_manager_id"])

    def test_the_pick_offers_only_team_managers_of_their_programs(self):
        body = self.people()
        form = body[body.index(f'action="/admin/users/{self.assoc[0]}/team"'):]
        form = form[:form.index("</form>")]
        self.assertIn("Team Manager 01", form)
        self.assertNotIn("Team Manager 02", form)
        # review (better-interface): the row has another Save (programs and role), so this one says what it saves
        self.assertIn(">Save team manager</button>", form)

    def test_not_for_staff(self):
        got = self.set_one(self.tm_away, self.tm)
        self.assertIn("Only an associate has a team manager.", html.unescape(got.get_data(as_text=True)))


class TheUpgrade(unittest.TestCase):
    def test_a_database_from_before_gets_both_columns(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        Store(folder / "scheduler.db")
        db = sqlite3.connect(folder / "scheduler.db")
        db.execute("alter table users drop column is_team_manager")
        db.execute("alter table users drop column team_manager_id")
        db.commit()
        db.close()
        store = Store(folder / "scheduler.db")
        uid = store.add_user("someone", "Someone", "Some-pass-12345")
        self.assertEqual((store.get_user(uid)["is_team_manager"], store.get_user(uid)["team_manager_id"]), (0, None))


if __name__ == "__main__":
    unittest.main()
