# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (sample ap01, B; owner 2026-10-21: edits go through to each person's own LOB, the zone is the one picked
in the RTA view): the RTA's day for every LOB of a program as one page. The made-up program has two LOBs: Tier 1 (the
fixture week, Cairo time) and Tier 2 (the same week with the people renamed "Associate B...", in London time, two
hours behind Cairo in October)."""
import html
import io
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from webapp.merged_day import lob_of, merged_page
from webapp.programs import ProgramBook
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import make_app, sign_in, token, wait
from webapp.tests.test_schedules import REPO

WED = date(2026, 10, 14)
CAIRO, LONDON = "Africa/Cairo", "Europe/London"


def renamed(path: Path) -> Path:
    wb = load_workbook(path)
    ws = wb["Schedule"]
    head = next(r for r in range(1, 10) if "sun" in [str(c.value or "").strip().lower() for c in ws[r]])
    col = next(c.column for c in ws[head] if str(c.value or "").strip().lower() == "sf name")
    for r in range(head + 1, ws.max_row + 1):
        value = ws.cell(r, col).value
        if isinstance(value, str) and value.startswith("Associate "):
            ws.cell(r, col).value = value.replace("Associate ", "Associate B")
    wb.save(path)
    return path


class _TwoLobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        one, two = make_ready(cls.dir / "one.xlsx"), renamed(make_ready(cls.dir / "two.xlsx"))
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.program_id = programs.add_program("SAKS")
        cls.one, cls.two = programs.add_lob(cls.program_id, "Tier 1"), programs.add_lob(cls.program_id, "Tier 2")
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")
        for key, path in ((cls.one, one), (cls.two, two)):
            cls.admin.post("/runs", data={"csrf_token": token(cls.admin), "kind": "ready", "mode": "QUICK",
                                          "program": key, "week_start": "2026-10-11",
                                          "workbook": (io.BytesIO(path.read_bytes()), "week.xlsx")},
                           content_type="multipart/form-data")
            wait(cls.store, cls.store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
        for run in cls.store.list_runs():
            cls.store.update_run(run["id"], tz=CAIRO if run["program"] == cls.one else LONDON)
        cls.days = cls.app.extensions["days"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def zone_of(self, unit, on):
        return CAIRO if unit == self.one else LONDON

    def merged(self, start=0, zone=CAIRO, units=None):
        return merged_page(self.days, self.one, units or [self.one, self.two], WED, "interval", start, zone,
                           self.zone_of)


class TheMergedDayData(_TwoLobs):
    def test_each_person_keeps_their_lob_and_nobody_is_lost(self):
        got = self.merged()["view"]
        alone = [self.days.window_page(self.one, WED, 0)["view"], self.days.window_page(self.two, WED, -120)["view"]]
        names = {l["name"]: l["lob"] for l in got["lanes"]}
        self.assertEqual({n for n, k in names.items() if k == self.one}, {l["name"] for l in alone[0]["lanes"]})
        self.assertEqual({n for n, k in names.items() if k == self.two}, {l["name"] for l in alone[1]["lanes"]})
        self.assertTrue(names and set(names.values()) == {self.one, self.two})

    def test_the_requirement_is_the_sum_of_the_lobs_on_one_clock(self):
        got = self.merged()["view"]
        a = {c["t"]: c for c in self.days.window_page(self.one, WED, 0)["view"]["cells"]}
        b = {c["t"]: c for c in self.days.window_page(self.two, WED, -120)["view"]["cells"]}  # London starts 2 h behind
        for c in got["cells"]:
            t = c["t"]
            self.assertAlmostEqual(c["required"], a[t]["required"] + b[t - 120]["required"], places=3)
            self.assertAlmostEqual(c["now"], a[t]["now"] + b[t - 120]["now"], places=1)

    def test_one_lob_in_the_picked_zone_has_its_times_moved_like_the_single_page(self):
        got = self.merged(start=0, zone="America/New_York", units=[self.one])["view"]
        self.assertEqual(len(got["cells"]), len(self.days.window_page(self.one, WED, 0)["view"]["cells"]))

    def test_a_lob_without_a_schedule_that_day_is_named_and_left_out(self):
        got = merged_page(self.days, self.one, [self.one, self.two], date(2026, 11, 22), "interval", 0, CAIRO,
                          self.zone_of)
        self.assertIsNone(got)

    def test_the_person_is_found_on_their_own_lob(self):
        self.assertEqual(lob_of(self.days, [self.one, self.two], WED, "Associate B027"), self.two)
        self.assertEqual(lob_of(self.days, [self.one, self.two], WED, "associate  027"), self.one)
        self.assertIsNone(lob_of(self.days, [self.one, self.two], WED, "Nobody Here"))


if __name__ == "__main__":
    unittest.main()
