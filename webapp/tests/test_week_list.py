# © 2026 Omar Mokhtar. All rights reserved.
"""Phase Z (owner, 2026-10-10: "The part of multiple schedules for same week this is very very confusing now and i
cant find the one was not used"; approved samples 01 and 02): every schedule of a week in one list, and the menu,
Home and the Week page follow the schedule in use."""
import html
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

WEEK = "2026-10-11"


class TwoSchedulesForOneWeek(unittest.TestCase):
    """SAKS, NMG Tier 2, week of Sun 11 Oct: week_v1.xlsx with its breaks planned automatically and in use, then
    week_v2.xlsx uploaded later and not in use. NMG Tier 1 has one schedule for the same week."""

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.omar = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        saks = programs.add_program("SAKS")
        cls.key = programs.add_lob(saks, "NMG Tier 2")
        cls.alone = programs.add_lob(saks, "NMG Tier 1")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.book = cls.app.extensions["schedules"]
        cls.first = cls.upload("week_v1.xlsx")
        planned = cls.book.versions(cls.first)[0]["id"]
        cls.client.post(f"/schedules/{planned}/auto-breaks", data={"csrf_token": token(cls.client), "use": "1"})
        cls.second = cls.upload("week_v2.xlsx")
        cls.single = cls.upload("tier1.xlsx", program=cls.alone)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    @classmethod
    def upload(cls, name, program=None, week=WEEK):
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                       "program": cls.key if program is None else program, "week_start": week,
                                       "workbook": (io.BytesIO(cls.ready.read_bytes()), name)},
                        content_type="multipart/form-data")
        run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, run_id, statuses=("DONE", "REJECTED", "FAILED"))
        return run_id

    def page(self, url):
        got = self.client.get(url)
        self.assertEqual(got.status_code, 200, url)
        return html.unescape(got.get_data(as_text=True))

    def week_list(self, page):
        found = re.search(r'(?s)<section[^>]*id="week-list".*?</section>', page)
        self.assertIsNotNone(found, "no list of the week's schedules")
        return found.group(0)


class TheWeekList(TwoSchedulesForOneWeek):
    def test_the_menu_opens_the_schedule_in_use(self):
        got = self.client.get("/schedules?program=" + self.key.replace(" ", "+"))
        self.assertEqual(got.status_code, 302)
        self.assertTrue(got.headers["Location"].endswith(f"/runs/{self.first}/schedules"), got.headers["Location"])

    def test_every_schedules_page_lists_the_weeks_schedules(self):
        other_shown = self.book.versions(self.second)[-1]["id"]
        for here, other in ((self.first, self.second), (self.second, self.first)):
            listed = self.week_list(self.page(f"/runs/{here}/schedules"))
            self.assertIn("Schedules for the week of 11 Oct (2)", listed)
            self.assertIn("week_v1.xlsx", listed)
            self.assertIn("week_v2.xlsx", listed)
            self.assertEqual(listed.count(">In use<"), 1)
            self.assertEqual(listed.count(">Not in use<"), 1)
            self.assertEqual(listed.count("You are here"), 1)
            self.assertIn(f'href="/runs/{other}/schedules"', listed)
        listed = self.week_list(self.page(f"/runs/{self.first}/schedules"))
        self.assertRegex(listed, rf'(?s)<form method="post" action="/schedules/{other_shown}/in-use">.*?Set in use</button>')

    def test_a_week_with_one_schedule_has_no_list(self):
        self.assertNotIn('id="week-list"', self.page(f"/runs/{self.single}/schedules"))

    def test_a_run_without_a_week_has_no_list(self):
        loose = self.upload("no_program.xlsx", program="", week="")
        self.assertNotIn('id="week-list"', self.page(f"/runs/{loose}/schedules"))

    def test_the_week_page_links_to_the_other_schedule(self):
        page = self.page(f"/week?program={self.key.replace(' ', '+')}&week={WEEK}")
        self.assertIn(f'This week also has <a href="/runs/{self.second}/schedules">week_v2.xlsx</a> (not in use)', page)
        self.assertIn(f'<a href="/runs/{self.first}/schedules#week-list">See both schedules</a>', page)
        self.assertNotIn("Compare or switch", page)

    def test_a_version_not_in_use_says_so_on_its_week_view(self):
        shown = self.book.versions(self.second)[-1]["id"]
        page = self.page(f"/schedules/{shown}/week")
        self.assertIn("Not in use: the RTA, exports and analysis use week_v1.xlsx for this week.", page)


class TheHomePage(TwoSchedulesForOneWeek):
    """Sample 02: Home shows the schedule in use for the program picked on the left, and the Runs table says which
    run counts for its week."""

    def home(self, key):
        return self.page("/?program=" + key.replace(" ", "+"))

    def rows(self, page):
        table = re.search(r'(?s)<table class="runs">.*?</table>', page).group(0)
        return {re.search(r'>([^<]+\.xlsx)</a>', r).group(1): r for r in re.findall(r"(?s)<tr>.*?</tr>", table)
                if ".xlsx</a>" in r}

    def test_home_shows_the_schedule_in_use_for_the_picked_program(self):
        page = self.home(self.key)
        self.assertIn(f'<h2 id="latest-h">In use for the week of 11 Oct: <a href="/runs/{self.first}">week_v1.xlsx</a></h2>',
                      page)
        self.assertNotIn("Latest schedule: <a", page)

    def test_a_week_with_nothing_in_use_shows_its_latest_schedule(self):
        page = self.home(self.alone)
        self.assertIn(f'<h2 id="latest-h">Latest schedule: <a href="/runs/{self.single}">tier1.xlsx</a></h2>', page)

    def test_the_runs_table_tags_in_use_and_not_in_use(self):
        rows = self.rows(self.home(self.key))
        self.assertIn('<span class="wl-tag use">In use</span>', rows["week_v1.xlsx"])
        self.assertIn('<span class="wl-tag off">Not in use</span>', rows["week_v2.xlsx"])
        self.assertNotIn("wl-tag", rows["tier1.xlsx"])  # the only schedule of its week: nothing to tell apart


if __name__ == "__main__":
    unittest.main()
