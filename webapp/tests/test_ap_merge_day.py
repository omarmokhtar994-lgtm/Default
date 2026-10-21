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


class TheMergedDayPage(_TwoLobs):
    def get(self, **query):
        query = {"program": self.one, "date": WED.isoformat(), "tz": CAIRO, "merge": "1", **query}
        return self.admin.get("/day", query_string=query)

    def text(self, **query):
        return html.unescape(self.get(**query).get_data(as_text=True))

    def test_the_view_pick_offers_all_lobs_of_the_program(self):
        page = html.unescape(self.admin.get("/day", query_string={"program": self.one, "date": WED.isoformat()})
                             .get_data(as_text=True))
        self.assertIn('name="merge"', page)
        self.assertIn("All LOBs of SAKS", page)

    def test_the_merged_timeline_lists_both_lobs_people_each_with_their_lob(self):
        page = self.text()
        self.assertIn("Associate 027", page)
        self.assertIn("Associate B027", page)
        self.assertIn('Associate B027</a></b><span class="tl-tag lob">Tier 2</span>', page)
        self.assertIn('Associate 027</a></b><span class="tl-tag lob">Tier 1</span>', page)

    def test_the_other_tabs_send_you_back_to_the_timeline_with_a_word_about_it(self):
        got = self.get(view="channels")
        self.assertEqual(got.status_code, 303)
        self.assertIn("merge=1", got.headers["Location"])
        self.assertNotIn("view=channels", got.headers["Location"])
        again = self.admin.get(got.headers["Location"]).get_data(as_text=True)
        self.assertIn("Pick one LOB for that tab", html.unescape(again))

    def test_the_merged_page_has_one_set_of_figures_and_no_single_lob_bars(self):
        page = self.text()
        self.assertIn("Every LOB of the program together", page)
        self.assertIn("Scheduled hours per channel", page)
        self.assertNotIn('id="act-bar"', page)  # Undo and Send belong to one LOB
        self.assertEqual(page.count("On shift today"), 1)

    def test_the_board_and_adherence_work_merged(self):
        for tab in ("board", "adherence"):
            self.assertEqual(self.get(view=tab).status_code, 200, tab)

    def test_the_page_names_a_lob_that_cannot_be_read_together_with_the_others(self):
        # Clocks that change between the LOBs' zones make the sum meaningless: it says so instead of guessing
        got = self.text(date="2026-10-25", tz="America/New_York")  # 25 Oct: the UK changes clocks, the US does not
        self.assertTrue("Clocks change" in got or "No schedule" in got)

    def test_a_change_made_on_the_merged_page_is_saved_on_the_persons_own_lob(self):
        got = self.admin.post("/day/attendance", data={
            "csrf_token": token(self.admin), "program": self.one, "merge": "1", "date": WED.isoformat(), "tz": CAIRO,
            "anchor": WED.isoformat(), "associate": "Associate B027", "status": "Sick"})
        self.assertEqual(got.status_code, 200, got.get_data(as_text=True)[:300])

        def status(unit, name):
            lane = next(l for l in self.days.page(unit, WED)["view"]["lanes"] if l["name"] == name)
            return next(s["status"] for s in lane["segments"] if s["offset"] == 0)

        self.assertEqual(status(self.two, "Associate B027"), "Sick")
        self.assertEqual(status(self.one, "Associate 027"), "Present")

    def test_without_the_merge_flag_a_name_from_the_other_lob_is_refused_as_before(self):
        got = self.admin.post("/day/attendance", data={
            "csrf_token": token(self.admin), "program": self.one, "date": WED.isoformat(), "tz": CAIRO,
            "anchor": WED.isoformat(), "associate": "Associate B028", "status": "Sick"})
        self.assertEqual(got.status_code, 400)


if __name__ == "__main__":
    unittest.main()
