# © 2026 Omar Mokhtar. All rights reserved.
"""Phase Q task 1: programs hold LOBs; people see their programs; supervisors manage their programs' planners.

Every table keeps its `program` text as the key of a schedule unit (a LOB, or a program without LOBs); the
registry says which program and LOB a key belongs to, so adopting an existing name moves no data."""
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp.access import Access, role
from webapp.attendance import DayBook
from webapp.programs import ProgramBook
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED = date(2026, 10, 14)


class TheRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.omar = store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        store.add_run("aaaaaaaaaaaa", cls.omar, "AR_week.xlsx", "QUICK", "DONE", program="AE/AR B2B",
                      week_start="2026-10-11")
        store.add_run("bbbbbbbbbbbb", cls.omar, "NMG_week.xlsx", "QUICK", "DONE", program="NMG",
                      week_start="2026-10-12")
        ScheduleBook(store, cls.base, REPO).ensure(store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.programs = ProgramBook(self.store)
        self.days = DayBook(self.store, ScheduleBook(self.store, self.data, REPO))
        self.programs.sync()

    def program(self, name):
        return next(p for p in self.programs.tree() if p["name"] == name)

    def test_sync_registers_existing_keys(self):
        self.assertEqual(sorted(p["name"] for p in self.programs.tree()), ["AE/AR B2B", "NMG"])
        self.assertEqual(self.programs.sync(), 0)  # once only
        self.assertEqual(self.program("NMG")["units"], ["NMG"])

    def test_add_lob_makes_a_unit(self):
        ae = self.programs.add_program("AE")
        self.assertEqual(self.programs.add_lob(ae, "IT"), "AE IT")
        self.assertEqual(self.programs.unit("AE IT")["label"], "AE, IT")
        with self.assertRaises(ValueError):
            self.programs.add_lob(ae, "IT")  # once per program
        with self.assertRaises(ValueError):
            self.programs.add_program("AE")

    def test_adopt_keeps_the_key_and_its_data(self):
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.omar)
        ae = self.programs.add_program("AE")
        self.programs.adopt("AE/AR B2B", ae, "AR B2B")
        self.assertEqual(sorted(p["name"] for p in self.programs.tree()), ["AE", "NMG"])  # the bare row is gone
        self.assertEqual(self.program("AE")["units"], ["AE/AR B2B"])
        self.assertEqual(self.programs.unit("AE/AR B2B")["label"], "AE, AR B2B")
        page = self.days.page("AE/AR B2B", WED)  # nothing moved: the day still reads its schedule and records
        lane = next(l for l in page["view"]["lanes"] if l["name"] == "Associate 001")
        self.assertEqual(lane["segments"][0]["status"], "Sick")

    def test_program_without_lobs_is_one_unit(self):
        self.assertEqual(self.programs.unit("NMG")["label"], "NMG")
        self.assertIsNone(self.programs.unit("NMG")["lob"])
        self.assertIsNone(self.programs.unit("Nobody"))

    def test_defaults_and_display_names(self):
        nmg = self.program("NMG")["id"]
        self.programs.set_defaults(nmg, 1, "DEEP", {"time_limit": 7200})
        found = self.program("NMG")
        self.assertEqual((found["start_day"], found["run_mode"], found["options"]), (1, "DEEP", {"time_limit": 7200}))
        with self.assertRaises(ValueError):
            self.programs.set_defaults(nmg, 7, "DEEP", {})
        self.programs.rename(nmg, None, "NMG Group")
        self.assertEqual(self.programs.unit("NMG")["label"], "NMG Group")  # the key stays NMG


class TheAccess(TheRegistry):
    test_sync_registers_existing_keys = test_add_lob_makes_a_unit = test_adopt_keeps_the_key_and_its_data = None
    test_program_without_lobs_is_one_unit = test_defaults_and_display_names = None

    def person(self, username, supervisor=False, programs=()):
        uid = self.store.add_user(username, username.title(), f"{username.title()}-pass-123", must_change=False)
        self.store.update_user(uid, is_supervisor=int(supervisor))
        self.store.set_user_programs(uid, [self.program(p)["id"] for p in programs])
        return self.store.get_user(uid)

    def test_planner_sees_only_their_programs(self):
        lina = self.person("lina", programs=["NMG"])
        seen = Access(self.store, lina)
        self.assertEqual(seen.keys(), {"NMG"})
        self.assertTrue(seen.can_open("NMG"))
        self.assertFalse(seen.can_open("AE/AR B2B"))
        self.assertEqual([p["name"] for p in seen.programs()], ["NMG"])
        self.assertIsNone(Access(self.store, self.store.get_user(self.omar)).keys())  # admins: everything
        self.assertEqual(role(lina), "Planner")

    def test_people_from_before_keep_all_programs(self):
        old = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, old, True)
        db = sqlite3.connect(old / "scheduler.db")
        db.execute("create table users (id integer primary key, username text unique not null, display_name text"
                   " not null, password_hash text not null, is_admin integer not null default 0, active integer"
                   " not null default 1, must_change integer not null default 1, failed integer not null default 0,"
                   " locked_until real not null default 0, created real not null)")
        db.execute("insert into users (username, display_name, password_hash, created) values ('sam', 'Sam', 'x', 0)")
        db.commit()
        db.close()
        store = Store(old / "scheduler.db")
        sam = next(u for u in store.list_users() if u["username"] == "sam")
        self.assertEqual((sam["all_programs"], sam["is_supervisor"]), (1, 0))
        self.assertIsNone(Access(store, sam).keys())
        new = store.get_user(store.add_user("nora", "Nora", "Nora-pass-123", must_change=False))
        self.assertEqual(new["all_programs"], 0)  # people added from now on get the programs chosen for them

    def test_supervisor_manages_their_programs_planners_only(self):
        sup = self.person("sami", supervisor=True, programs=["NMG"])
        mine = self.person("lina", programs=["NMG"])
        theirs = self.person("rana", programs=["AE/AR B2B"])
        other_sup = self.person("hadi", supervisor=True, programs=["NMG"])
        boss = Access(self.store, sup)
        self.assertEqual(role(sup), "Supervisor")
        self.assertTrue(boss.can_manage(mine))
        self.assertFalse(boss.can_manage(theirs))
        self.assertFalse(boss.can_manage(other_sup))
        self.assertFalse(boss.can_manage(self.store.get_user(self.omar)))
        self.assertEqual([p["name"] for p in boss.grantable()], ["NMG"])
        admin = Access(self.store, self.store.get_user(self.omar))
        self.assertTrue(admin.can_manage(other_sup))
        self.assertEqual(sorted(p["name"] for p in admin.grantable()), ["AE/AR B2B", "NMG"])


class TheDeletes(TheRegistry):
    """Phase R task 2: a program or LOB is deleted only once nothing is stored under it; a stray program's
    data is moved into its LOB first (owner, 2026-10-08: move first, then delete)."""
    test_sync_registers_existing_keys = test_add_lob_makes_a_unit = test_adopt_keeps_the_key_and_its_data = None
    test_program_without_lobs_is_one_unit = test_defaults_and_display_names = None

    def lob(self, key):
        return next(l for l in self.store.list_lobs() if l["key"] == key)

    def test_delete_empty_lob(self):
        ae = self.programs.add_program("AE")
        self.programs.add_lob(ae, "IT")
        self.assertEqual(self.programs.delete_lob(self.lob("AE IT")["id"]), "IT")
        self.assertEqual(self.program("AE")["lobs"], [])

    def test_delete_lob_with_data_is_refused_with_counts(self):
        ae = self.programs.add_program("AE")
        self.programs.adopt("AE/AR B2B", ae, "AR B2B")
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.omar)
        self.assertEqual(self.programs.usage("AE/AR B2B")["runs"], 1)
        with self.assertRaises(ValueError) as said:
            self.programs.delete_lob(self.lob("AE/AR B2B")["id"])
        self.assertIn("still has 1 run", str(said.exception))
        self.assertIn("day record", str(said.exception))
        self.assertIn("AE/AR B2B", [l["key"] for l in self.store.list_lobs()])

    def test_delete_program_with_lobs_is_refused(self):
        ae = self.programs.add_program("AE")
        self.programs.add_lob(ae, "IT")
        with self.assertRaises(ValueError) as said:
            self.programs.delete_program(ae)
        self.assertIn("Delete or move its LOBs first.", str(said.exception))

    def test_move_then_delete_stray_program(self):
        from webapp.run_admin import apply_rename
        saks = self.programs.add_program("SAKS")
        key = self.programs.add_lob(saks, "NMG Tier 2")
        self.store.add_run("cccccccccccc", self.omar, "stray.xlsx", "QUICK", "DONE", program="SAKS, NMG Tier 2",
                           week_start="2026-10-18")
        self.programs.sync()
        stray = self.program("SAKS, NMG Tier 2")
        with self.assertRaises(ValueError):
            self.programs.delete_program(stray["id"])  # its run is still filed under it
        apply_rename(self.store, "SAKS, NMG Tier 2", key, self.omar, "into its LOB")
        self.assertEqual(self.programs.delete_program(stray["id"]), "SAKS, NMG Tier 2")
        self.programs.sync()  # nothing is filed under the stray name now, so it does not come back
        self.assertNotIn("SAKS, NMG Tier 2", [p["name"] for p in self.programs.tree()])
        self.assertEqual(self.store.get_run("cccccccccccc")["program"], key)

    def test_deleting_a_program_drops_its_assignments(self):
        gdi = self.programs.add_program("GDI")
        uid = self.store.add_user("lina", "Lina", "Lina-pass-123", must_change=False)
        self.store.set_user_programs(uid, [gdi])
        self.programs.delete_program(gdi)
        self.assertEqual(self.store.user_program_ids(uid), [])


if __name__ == "__main__":
    unittest.main()
