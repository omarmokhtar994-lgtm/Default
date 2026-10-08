# © 2026 Omar Mokhtar. All rights reserved.
"""Phase O task 1: actions not already in a log are recorded with who and when
(a version made or set in use here; runs, downloads and people in test_runs)."""
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from webapp.schedules import KEEP_DAYS, ScheduleBook
from webapp.store import Store
from webapp.tests.test_schedules import AFTER, INPUT, REPO


class TheEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        cls.lina = store.add_user("lina", "Lina", "Lina-pass-1", must_change=False)
        store.add_run("aaaaaaaaaaaa", cls.sara, "AR_week.xlsx", "QUICK", "DONE", program="AE/AR B2B",
                      week_start="2026-10-11")
        ScheduleBook(store, cls.base, REPO).ensure(store.get_run("aaaaaaaaaaaa"), INPUT, AFTER, None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.tool = self.book.versions("aaaaaaaaaaaa")[0]

    def events(self, **filters):
        return [(e["kind"], e["by_name"], e["subject"]) for e in self.store.list_events(0, time.time() + 60, **filters)]

    def test_a_new_version_and_set_in_use_are_recorded(self):
        draft = self.book.change(self.tool["id"], self.lina, "Associate 001", "Wed", "10:00 - 19:00", "swap")
        self.book.set_in_use(draft, self.sara)
        self.assertEqual(self.events(), [("version_created", "Lina", "Version 2: Lina's edit"),
                                         ("set_in_use", "Sara", "Version 2: Lina's edit")])
        row = self.store.list_events(0, time.time() + 60, kinds=["set_in_use"])[0]
        self.assertEqual((row["program"], row["week_start"], row["schedule_id"]), ("AE/AR B2B", "2026-10-11", draft))

    def test_filters_by_period_person_and_kind(self):
        self.store.add_event(kind="downloaded", user_id=self.sara, subject="old.zip", at=time.time() - 40 * 86400)
        self.store.add_event(kind="downloaded", user_id=self.lina, subject="new.zip")
        self.store.add_event(kind="run_uploaded", user_id=self.sara, subject="week.xlsx", program="AE/AR B2B")
        now = time.time()
        self.assertEqual([e["subject"] for e in self.store.list_events(now - 86400, now + 60)], ["new.zip", "week.xlsx"])
        self.assertEqual([e["subject"] for e in self.store.list_events(0, now + 60, user_id=self.sara)],
                         ["old.zip", "week.xlsx"])
        self.assertEqual([e["subject"] for e in self.store.list_events(0, now + 60, kinds=["downloaded"],
                                                                       program=None)], ["old.zip", "new.zip"])
        self.assertEqual([e["subject"] for e in self.store.list_events(0, now + 60, program="AE/AR B2B")], ["week.xlsx"])

    def test_events_kept_13_months(self):
        self.store.add_event(kind="downloaded", user_id=self.sara, subject="x.zip")
        self.assertEqual(KEEP_DAYS, 395)
        self.assertEqual(self.store.delete_events_before(time.time() - KEEP_DAYS * 86400), 0)
        self.assertEqual(self.store.delete_events_before(time.time() + 60), 1)


if __name__ == "__main__":
    unittest.main()
