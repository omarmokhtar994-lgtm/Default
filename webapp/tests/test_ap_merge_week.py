# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (sample ap01, A approved; owner 2026-10-21: only LOBs of the same program): the Week page can show the
LOBs of a program as one grid, in the zone picked, with one target."""
import json
import unittest
from datetime import date

from webapp.programs import ProgramBook
from webapp.tests.test_channel_people import add_version
from webapp.tests.test_runs import make_app, sign_in

WEEK = "2026-10-11"


def rows(*cells):
    return json.dumps({"intervals": [list(c) for c in cells]})


class TheMergedWeek(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        zed = programs.add_program("ZED")
        cls.one, cls.two = programs.add_lob(zed, "One"), programs.add_lob(zed, "Two")
        other = programs.add_program("OTHER")
        cls.x = programs.add_lob(other, "X")
        cls.runs = {}
        # Monday (day 1). One is in Cairo time: 09:00 needs 4, has 3. Two is in London time: 07:00 there is 09:00 in
        # Cairo in October (UK summer time), needs 2, has 2. OTHER's X must never be mixed in.
        for n, (unit, tz, cells) in enumerate(((cls.one, "Africa/Cairo", [(1, "09:00", 4.0, 3.0, 3, 3.0, 3, 0)]),
                                (cls.two, "Europe/London", [(1, "07:00", 2.0, 2.0, 2, 2.0, 2, 0)]),
                                (cls.x, "Africa/Cairo", [(1, "09:00", 50.0, 50.0, 50, 50.0, 50, 0)]))):
            sid = add_version(cls.store, unit, WEEK, [("Associate 01", "English")], run_id=f"00000000000{n}",
                              in_use=True)
            row = cls.store.get_schedule(sid)
            cls.store.update_schedule(sid, checks=rows(*cells))
            cls.store.update_run(row["run_id"], tz=tz)
            cls.runs[unit] = row["run_id"]
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")

    def get(self, **query):
        query = {"program": self.one, "week": WEEK, "tz": "Africa/Cairo", **query}
        return self.admin.get("/week", query_string=query).get_data(as_text=True)

    def test_a_lob_alone_is_unchanged(self):
        page = self.get()
        self.assertIn("75%", page)
        self.assertNotIn("83%", page)

    def test_the_view_pick_offers_the_programs_lobs_only(self):
        page = self.get()
        self.assertIn('name="merge"', page)
        self.assertIn("All LOBs of ZED", page)
        self.assertNotIn("All LOBs of OTHER", page)
        self.assertNotIn('name="merge"', self.get(program=self.x))  # a program with one LOB has nothing to merge

    def test_merged_the_two_lobs_are_one_grid_on_the_cairo_clock(self):
        page = self.get(merge="1")
        self.assertIn("83%", page)       # 5 of the 6 needed at 09:00 Cairo: One's 09:00 and Two's 07:00 London
        self.assertNotIn("75%", page)
        self.assertNotIn("100%</small>", page.split("wkgrid")[1] if "wkgrid" in page else page)
        self.assertIn("ZED, One + Two", page)
        self.assertNotIn(">X<", page)

    def test_the_zone_picked_moves_the_other_lob_to_the_same_hour(self):
        page = self.get(merge="1", tz="Europe/London")  # 09:00 Cairo is 07:00 London
        self.assertIn("83%", page)

    def test_a_person_without_the_program_cannot_merge_it(self):
        other = [p["id"] for p in ProgramBook(self.store).tree() if p["name"] == "OTHER"][0]
        uid = self.store.add_user("planner", "Planner", "Planner-pass-12", is_admin=False, must_change=False)
        self.store.set_user_programs(uid, [other])
        client = sign_in(self.app, "planner", "Planner-pass-12")
        got = client.get("/week", query_string={"program": self.one, "week": WEEK, "merge": "1"})
        self.assertEqual(got.status_code, 403)

    def test_the_schedules_page_offers_the_programs_lobs_together(self):
        page = self.admin.get(f"/runs/{self.runs[self.one]}/schedules").get_data(as_text=True)
        self.assertIn('aria-labelledby="merged-h"', page)
        block = page.split('aria-labelledby="merged-h"')[1].split("</section>")[0]
        self.assertIn("ZED, One + Two", block)
        self.assertIn("merge=1", block)
        self.assertIn("2 of 2 LOBs", block)
        self.assertNotIn("OTHER", block)

    def test_a_program_with_one_lob_has_no_such_panel(self):
        page = self.admin.get(f"/runs/{self.runs[self.x]}/schedules").get_data(as_text=True)
        self.assertNotIn('aria-labelledby="merged-h"', page)


if __name__ == "__main__":
    unittest.main()
