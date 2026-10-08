# © 2026 Omar Mokhtar. All rights reserved.
"""Phase N task 2: schedule versions kept on the server.

The tool's own schedules are copied when a run finishes, with the input
workbook, so versions can be edited, checked and downloaded after the run's
files are deleted. Edits land in a draft; the tool's versions and the version
in use never change."""
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from webapp.schedules import KEEP_DAYS, ScheduleBook
from webapp.store import Store

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / "fixtures" / "real_runs" / "week_boundary" / "B3_ARB2B_S30"
AFTER = RUN / "production" / "B3_ARB2B_S30_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
INPUT = RUN / "input_snapshot" / "AE_AR_B2B_SLICE30.xlsx"


class TheVersions(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())
        self.store = Store(self.data / "scheduler.db")
        self.sara = self.store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        self.lina = self.store.add_user("lina", "Lina", "Lina-pass-1", must_change=False)
        self.store.add_run("aaaaaaaaaaaa", self.sara, "AR_week.xlsx", "QUICK", "DONE", program="AE/AR B2B",
                           week_start="2026-10-11")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.versions = self.book.ensure(self.store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None)
        self.tool = self.versions[0]

    def test_finished_run_gets_tool_versions(self):
        self.assertEqual([(v["kind"], v["label"]) for v in self.versions], [("tool_after", "Tool, after breaks")])
        self.assertTrue(self.book.path(self.tool["id"]).is_file())
        self.assertEqual(json.loads(self.tool["checks"])["status"], "PASS")
        self.assertEqual(self.book.ensure(self.store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None), self.versions)  # once

    def test_editing_never_changes_the_tool_or_in_use_version(self):
        before = self.book.path(self.tool["id"]).read_bytes()
        draft = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "swap")
        self.assertNotEqual(draft, self.tool["id"])
        self.assertEqual(self.book.path(self.tool["id"]).read_bytes(), before)
        self.assertEqual(self.book.change(draft, self.sara, "Associate 002", "Sun", "OFF", "leave"), draft)  # same draft
        self.book.set_in_use(draft, self.sara)
        again = self.book.change(draft, self.sara, "Associate 003", "Sun", "OFF", "leave")
        self.assertNotEqual(again, draft)  # the version in use stays as it was
        week = json.loads(self.store.get_schedule(again)["week"])
        days = {a["name"]: a["days"] for a in week["associates"]}
        self.assertEqual((days["Associate 001"][3], days["Associate 002"][0], days["Associate 003"][0]),
                         ("10:00 - 19:00", "OFF", "OFF"))

    def test_change_log_keeps_who_what_why(self):
        draft = self.book.change(self.tool["id"], self.lina, "Associate 001", "Wed", "21:00 - 06:00", "swap requested")
        log = self.store.list_changes(draft)
        self.assertEqual([(c["by_name"], c["associate"], c["day"], c["old"], c["new"], c["reason"], c["severity"]) for c in log],
                         [("Lina", "Associate 001", "Wed", "12:00 - 21:00", "21:00 - 06:00", "swap requested", "red")])
        self.assertEqual(self.store.get_schedule(draft)["label"], "Version 2: Lina's edit")

    def test_check_shows_only_what_the_change_adds(self):
        found = self.book.check(self.tool["id"], "Associate 001", "Wed", "21:00 - 06:00")
        kinds = sorted(p["key"].split("|")[0] for p in found["added"])
        self.assertEqual(kinds, ["BREAK_SEGMENT_COUNT_OR_DURATION", "MAX_SHIFT_VARIETY_VIOLATION", "REST_VIOLATION"])
        self.assertEqual(found["severity"], "red")
        self.assertEqual(self.book.check(self.tool["id"], "Associate 001", "Wed", "12:00 - 21:00")["added"], [])

    def test_swap_checked_then_kept_logged_and_marked(self):
        found = self.book.check_swap(self.tool["id"], "Associate 001", "Associate 002")
        self.assertIn(found["severity"], ("ok", "yellow", "red"))
        self.assertEqual(set(found), {"added", "severity", "problems", "metrics"})
        before = self.book.path(self.tool["id"]).read_bytes()
        draft = self.book.swap(self.tool["id"], self.sara, "Associate 001", "Associate 002", "family reasons")
        self.assertNotEqual(draft, self.tool["id"])
        self.assertEqual(self.book.path(self.tool["id"]).read_bytes(), before)
        slots = {a["slot"]: a["name"] for a in json.loads(self.store.get_schedule(draft)["week"])["associates"]}
        self.assertEqual((slots["1"], slots["2"]), ("Associate 002", "Associate 001"))
        log = [(c["associate"], c["day"], c["old"], c["new"], c["reason"]) for c in self.store.list_changes(draft)]
        self.assertEqual(log, [("Associate 001", "Week", "Slot 1", "Slot 2", "family reasons"),
                               ("Associate 002", "Week", "Slot 2", "Slot 1", "family reasons")])
        edited = self.book.edited_cells(draft)
        self.assertEqual({d for n, d in edited if n == "Associate 001"}, {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"})
        with self.assertRaises(ValueError):
            self.book.check_swap(self.tool["id"], "Associate 001", "Nobody")

    def test_refused_edit_leaves_no_empty_draft(self):
        count = len(self.book.versions("aaaaaaaaaaaa"))
        for bad in (lambda: self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "25:00 - 26:00", "x"),
                    lambda: self.book.change(self.tool["id"], self.sara, "Nobody", "Wed", "OFF", "x"),
                    lambda: self.book.swap(self.tool["id"], self.sara, "Associate 001", "Nobody", "x"),
                    lambda: self.book.swap(self.tool["id"], self.sara, "Associate 001", "Associate 001", "x")):
            with self.assertRaises(ValueError):
                bad()
        self.assertEqual(len(self.book.versions("aaaaaaaaaaaa")), count)

    def test_one_version_in_use_per_program_week(self):
        a = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "x")
        self.book.set_in_use(self.tool["id"], self.sara)
        self.book.set_in_use(a, self.sara)
        in_use = [v["id"] for v in self.book.versions("aaaaaaaaaaaa") if v["in_use"]]
        self.assertEqual(in_use, [a])
        self.assertEqual(self.book.in_use("AE/AR B2B", "2026-10-11")["id"], a)

    def test_versions_survive_run_expiry(self):
        draft = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "x")
        # the run's own files are gone; the copies stay
        self.assertTrue(self.book.path(draft).is_file())
        self.assertIn("added", self.book.check(draft, "Associate 002", "Sun", "OFF"))

    def test_concurrent_edits_both_kept(self):
        draft = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "x")
        threads = [threading.Thread(target=self.book.change, args=(draft, self.sara, name, "Sun", "OFF", "y"))
                   for name in ("Associate 002", "Associate 003")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        days = {a["name"]: a["days"] for a in json.loads(self.store.get_schedule(draft)["week"])["associates"]}
        self.assertEqual((days["Associate 002"][0], days["Associate 003"][0]), ("OFF", "OFF"))
        self.assertEqual(len(self.store.list_changes(draft)), 3)

    def test_versions_deleted_after_13_months(self):
        draft = self.book.change(self.tool["id"], self.sara, "Associate 001", "Wed", "10:00 - 19:00", "x")
        path = self.book.path(draft)
        self.assertEqual(KEEP_DAYS, 395)
        self.assertEqual(self.book.cleanup(now=time.time() + 300 * 86400), 0)
        self.assertEqual(self.book.cleanup(now=time.mktime((2027, 11, 20, 0, 0, 0, 0, 0, -1))), 2)
        self.assertFalse(path.exists())
        self.assertEqual(self.book.versions("aaaaaaaaaaaa"), [])


if __name__ == "__main__":
    unittest.main()
