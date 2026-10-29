# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AM item 4 (owner, 2026-10-16: "not showing percentage of intervals if it's only before breaks ... A it should
show the percentage B in cas i pressed on plan breaks it should show the new percentage after breaks or as per my in
use selection"; answer: the version in use, else the engine's own, as now). Root cause: Home and the run page read an
engine run's figures only from the engine's check of its after-breaks workbook, which a "Before breaks only" run
does not have. Now: the version in use; else the engine's figures; else the version the run shows (said "before
breaks" when it has no breaks)."""
import html
import re
import unittest

from webapp.tests.test_runs import REPO, client_for, make_app, run_id_of, upload, wait

INPUT = REPO / "fixtures" / "real_runs" / "before_break" / "B1_BEFORE" / "input_snapshot" / "AE_FR_Choice.xlsx"


def row_text(body, workbook):
    body = html.unescape(body)
    start = body.index(workbook, body.index("<table class=\"runs\">"))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body[start:body.index("</tr>", start)]))


class TheFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.run_id = run_id_of(upload(cls.client, name="BEFOREONLY_week.xlsx", data=INPUT.read_bytes(),
                                      program="AE/FR", week_start="2026-10-11"))
        wait(cls.store, cls.run_id)
        cls.book = cls.app.extensions["schedules"]

    def test_a_before_breaks_run_shows_its_percentage(self):
        got = row_text(self.client.get("/").get_data(as_text=True), "BEFOREONLY_week.xlsx")
        self.assertNotIn("no data", got)
        self.assertRegex(got, r"\d+% before breaks")
        page = html.unescape(self.client.get(f"/runs/{self.run_id}").get_data(as_text=True))
        self.assertRegex(page, r"\d+ of \d+")

    def test_plan_breaks_in_use_shows_the_new_percentage(self):
        tool = self.book.versions(self.run_id)[0]
        user = self.store.list_users()[0]["id"]
        self.book.auto_breaks(tool["id"], user, use=True)
        planned = next(v for v in self.book.versions(self.run_id) if v["in_use"])
        import json
        from webapp.results import version_summary
        want = version_summary(json.loads(planned["checks"]))["numbers"]
        got = row_text(self.client.get("/").get_data(as_text=True), "BEFOREONLY_week.xlsx")
        self.assertIn(f"{round(100 * want['fully_covered'] / want['active'])}%", got)
        self.assertNotIn("before breaks", got)
        self.book.set_in_use(tool["id"], user)  # back as it was for the other test


if __name__ == "__main__":
    unittest.main()
