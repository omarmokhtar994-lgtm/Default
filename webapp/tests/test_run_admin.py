# © 2026 Omar Mokhtar. All rights reserved.
"""Phase P: correcting a run's details, and renaming or merging a program.

A run's schedule versions carry its program and week (copied when it finished),
so they move with it. What a change would do is worked out first: a version
that stops being in use, day records that stay on their dates. Every change is
kept in the record with who, when and why."""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp.attendance import DayBook
from webapp.run_admin import apply_rename, apply_run_change, preview_rename, preview_run_change
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_schedules import AFTER, INPUT, REPO

WED = date(2026, 10, 14)


class TheRunChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Two runs of AE/AR B2B, weeks of 11 and 18 October, each with its tool versions; each test gets a copy."""
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", is_admin=True, must_change=False)
        cls.lina = store.add_user("lina", "Lina", "Lina-pass-12", must_change=False)
        book = ScheduleBook(store, cls.base, REPO)
        for run_id, week in (("aaaaaaaaaaaa", "2026-10-11"), ("bbbbbbbbbbbb", "2026-10-18")):
            store.add_run(run_id, cls.sara, "AR_week.xlsx", "QUICK", "DONE", program="AE/AR B2B", week_start=week)
            book.ensure(store.get_run(run_id), INPUT, AFTER, None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.days = DayBook(self.store, self.book)
        self.a, self.b = self.store.get_run("aaaaaaaaaaaa"), self.store.get_run("bbbbbbbbbbbb")

    def test_versions_move_with_the_run(self):
        found = preview_run_change(self.store, self.a, {"program": "AE AR B2B"})
        self.assertEqual(found["changes"], [("Program", "AE/AR B2B", "AE AR B2B")])
        self.assertFalse(found["needs_check"])
        apply_run_change(self.store, self.a, {"program": "AE AR B2B"}, self.sara, "")
        self.assertEqual({v["program"] for v in self.store.list_schedules(run_id="aaaaaaaaaaaa")}, {"AE AR B2B"})
        self.assertEqual(self.store.get_run("aaaaaaaaaaaa")["program"], "AE AR B2B")
        row, _ = self.days.version("AE AR B2B", WED)
        self.assertEqual(row["run_id"], "aaaaaaaaaaaa")
        self.assertIsNone(self.days.version("AE/AR B2B", WED)[0])  # nothing left behind under the old name

    def test_in_use_at_the_target_wins(self):
        mine, theirs = (self.book.versions(r)[0] for r in ("aaaaaaaaaaaa", "bbbbbbbbbbbb"))
        self.book.set_in_use(mine["id"], self.sara)
        self.book.set_in_use(theirs["id"], self.sara)
        found = preview_run_change(self.store, self.a, {"week_start": "2026-10-18"})
        self.assertEqual([v["label"] for v in found["stop_in_use"]], [mine["label"]])
        self.assertEqual(found["kept_by_target"], theirs["label"])
        self.assertTrue(found["needs_check"])
        apply_run_change(self.store, self.a, {"week_start": "2026-10-18"}, self.sara, "wrong week")
        in_use = [v for v in self.store.list_schedules(program="AE/AR B2B", week_start="2026-10-18") if v["in_use"]]
        self.assertEqual([v["id"] for v in in_use], [theirs["id"]])

    def test_day_records_stay_and_are_listed(self):
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.sara)
        self.days.add_activity("AE/AR B2B", WED, "Associate 008", "Training", "09:00", "10:00", self.sara)
        found = preview_run_change(self.store, self.a, {"week_start": "2026-10-18"})
        self.assertEqual((found["old_records"]["attendance"], found["old_records"]["activities"]), (1, 1))
        self.assertEqual(found["old_records"]["log"], 2)
        self.assertIsNone(found["old_week_after"])  # no other schedule for the week of 11 October
        self.assertTrue(found["needs_check"])
        apply_run_change(self.store, self.a, {"week_start": "2026-10-18"}, self.sara, "wrong week")
        self.assertEqual([r["associate"] for r in self.store.list_attendance("AE/AR B2B", [WED.isoformat()])],
                         ["Associate 001"])

    def test_moving_the_start_a_day_keeps_its_days(self):
        # Sunday 11 to Monday 12: Wednesday stays in the same run (its Wed column), so its records need no check
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.sara)
        found = preview_run_change(self.store, self.a, {"week_start": "2026-10-12"})
        self.assertFalse(found["needs_check"])
        # a record on Sunday 11 is left with no schedule, so that one is shown
        self.days.set_status("AE/AR B2B", date(2026, 10, 11), "Associate 002", "Sick", self.sara)
        found = preview_run_change(self.store, self.a, {"week_start": "2026-10-12"})
        self.assertTrue(found["needs_check"])
        self.assertTrue(found["old_affected"])

    def test_clearing_program_and_week(self):
        apply_run_change(self.store, self.a, {"program": "", "week_start": ""}, self.sara, "")
        self.assertEqual({(v["program"], v["week_start"]) for v in self.store.list_schedules(run_id="aaaaaaaaaaaa")},
                         {("", "")})

    def test_change_is_recorded(self):
        apply_run_change(self.store, self.a, {"program": "AE AR B2B", "user_id": self.lina,
                                              "workbook": "AR week 42.xlsx"}, self.sara, "typo")
        events = [e for e in self.store.list_events(0, 1e12) if e["kind"] == "run_details_changed"]
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["run_id"], events[0]["user_id"]), ("aaaaaaaaaaaa", self.sara))
        self.assertIn("Program: AE/AR B2B → AE AR B2B", events[0]["detail"])
        self.assertIn("Submitted by: Sara → Lina", events[0]["detail"])
        self.assertIn("Workbook: AR_week.xlsx → AR week 42.xlsx", events[0]["detail"])
        self.assertIn("Reason: typo", events[0]["detail"])
        run = self.store.get_run("aaaaaaaaaaaa")
        self.assertEqual((run["user_id"], run["workbook"]), (self.lina, "AR week 42.xlsx"))

    def test_nothing_to_change(self):
        self.assertEqual(preview_run_change(self.store, self.a, {"program": "AE/AR B2B"})["changes"], [])
        with self.assertRaises(ValueError):
            apply_run_change(self.store, self.a, {"program": "AE/AR B2B"}, self.sara, "")


class TheProgramRename(TheRunChange):
    """Renaming a program moves its runs, versions and day records; past events keep the name they had."""
    test_versions_move_with_the_run = test_in_use_at_the_target_wins = test_day_records_stay_and_are_listed = None
    test_clearing_program_and_week = test_change_is_recorded = test_nothing_to_change = None
    test_moving_the_start_a_day_keeps_its_days = None

    def merge_ready(self):
        """Run B becomes AE-AR B2B for the week of 11 October, so both programs hold that week."""
        apply_run_change(self.store, self.b, {"program": "AE-AR B2B", "week_start": "2026-10-11"}, self.sara, "")

    def test_rename_moves_everything(self):
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.sara)
        self.days.move_break("AE/AR B2B", WED, "Associate 008", 1, "13:05", self.sara)
        self.days.add_activity("AE/AR B2B", WED, "Associate 008", "Training", "09:00", "10:00", self.sara)
        self.book.set_in_use(self.book.versions("aaaaaaaaaaaa")[0]["id"], self.sara)
        found = preview_rename(self.store, "AE/AR B2B", "AE-AR B2B")
        self.assertEqual((found["merge"], found["runs"], found["versions"]), (False, 2, 2))  # one version each
        self.assertEqual(found["records"], {"attendance": 1, "breaks": 1, "activities": 1, "log": 3})
        self.assertEqual((found["stop_in_use"], found["clashes"]), ([], []))
        apply_rename(self.store, "AE/AR B2B", "AE-AR B2B", self.sara, "new name")
        self.assertEqual({r["program"] for r in self.store.list_runs()}, {"AE-AR B2B"})
        self.assertEqual({v["program"] for v in self.store.list_schedules()}, {"AE-AR B2B"})
        page = self.days.page("AE-AR B2B", WED)
        lane = next(l for l in page["view"]["lanes"] if l["name"] == "Associate 001")
        self.assertEqual(lane["segments"][0]["status"], "Sick")
        self.assertEqual(len(page["log"]), 3)
        events = {e["kind"]: e for e in self.store.list_events(0, 1e12)}
        self.assertEqual(events["set_in_use"]["program"], "AE/AR B2B")  # history keeps the name it had
        self.assertEqual((events["program_renamed"]["program"], events["program_renamed"]["subject"]),
                         ("AE-AR B2B", "AE/AR B2B"))
        self.assertIn("Reason: new name", events["program_renamed"]["detail"])

    def test_case_only_rename_is_not_a_merge(self):
        found = preview_rename(self.store, "AE/AR B2B", "ae/ar b2b")
        self.assertFalse(found["merge"])
        apply_rename(self.store, "AE/AR B2B", "ae/ar b2b", self.sara, "")
        self.assertEqual({r["program"] for r in self.store.list_runs()}, {"ae/ar b2b"})

    def test_merge_keeps_the_target_in_use(self):
        self.merge_ready()
        mine, theirs = (self.book.versions(r)[0] for r in ("aaaaaaaaaaaa", "bbbbbbbbbbbb"))
        self.book.set_in_use(mine["id"], self.sara)
        self.book.set_in_use(theirs["id"], self.sara)
        found = preview_rename(self.store, "AE/AR B2B", "AE-AR B2B")
        self.assertTrue(found["merge"])
        self.assertEqual([(s["week"], s["label"]) for s in found["stop_in_use"]], [("2026-10-11", mine["label"])])
        apply_rename(self.store, "AE/AR B2B", "AE-AR B2B", self.sara, "one program")
        in_use = [v["id"] for v in self.store.list_schedules(program="AE-AR B2B", week_start="2026-10-11") if v["in_use"]]
        self.assertEqual(in_use, [theirs["id"]])

    def test_merge_refused_on_clashing_records(self):
        self.merge_ready()
        self.days.set_status("AE/AR B2B", WED, "Associate 001", "Sick", self.sara)
        self.days.set_status("AE-AR B2B", WED, "Associate 001", "Late", self.sara, end="13:00")
        found = preview_rename(self.store, "AE/AR B2B", "AE-AR B2B")
        self.assertEqual(len(found["clashes"]), 1)
        self.assertIn("Associate 001", found["clashes"][0])
        self.assertIn("14 Oct", found["clashes"][0])
        with self.assertRaises(ValueError):
            apply_rename(self.store, "AE/AR B2B", "AE-AR B2B", self.sara, "")
        self.assertEqual(self.store.get_run("aaaaaaaaaaaa")["program"], "AE/AR B2B")  # nothing changed

    def test_rename_refusals(self):
        for old, new in (("AE/AR B2B", ""), ("AE/AR B2B", "  "), ("AE/AR B2B", "AE/AR B2B"), ("Nobody", "X"),
                         ("AE/AR B2B", "x" * 81)):
            with self.assertRaises(ValueError, msg=(old, new)):
                preview_rename(self.store, old, new)


if __name__ == "__main__":
    unittest.main()
