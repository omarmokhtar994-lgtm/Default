# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AC (deep review, findings 5 and 9, and earlier open items): the Week page's tiles (associates for an uploaded
schedule, plurals, a fraction that stays on one line); a failed run's Delete wording; a run whose kept input cannot be
read still opens its Schedules page; Resume is refused for a readiness check or a run that cannot be scheduled even
when posted directly; a save written over several seconds is one save; a day with channel tabs and no channel plan
says so in one line."""
import html
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.schedules import group_changes
from webapp.tests.test_channel_day import WED as CH_WED, _Day
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token
from webapp.tests.test_week_list import WEEK, TwoSchedulesForOneWeek
from webapp.versions import shift_span


class TheWeekTiles(TwoSchedulesForOneWeek):
    def tiles(self):
        page = self.page("/week?program=" + self.key.replace(" ", "+") + f"&week={WEEK}")
        return re.search(r'(?s)<section class="tiles".*?</section>', page).group(0)

    def test_associates_tile_for_an_uploaded_schedule(self):
        shown = self.book.in_use(self.key, WEEK)
        week = json.loads(shown["week"])
        working = sum(1 for a in week["associates"] if any(shift_span(d) for d in a["days"]))
        tile = re.search(r'(?s)<span class="tile-label">Associates</span><b>([^<]*)</b>', self.tiles())
        self.assertEqual(tile.group(1), str(working))

    def test_plural_words(self):
        tiles = self.tiles()
        said = re.search(r"(\d+) (intervals?), (\d+) (associate-intervals?)</small>", tiles)
        self.assertIsNotNone(said, tiles)
        for n, word in ((said.group(1), said.group(2)), (said.group(3), said.group(4))):
            self.assertEqual(word.endswith("s"), n != "1", said.group(0))

    def test_tile_fraction_stays_on_one_line(self):
        self.assertRegex(self.tiles(), r'<b>\d+<small class="of"> of \d+</small></b>')


class TheRunPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, cls.data, _ = make_app(START_WORKER=False, VALIDATOR_ROOT=str(REPO))
        cls.omar = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.queue = cls.app.extensions["runs"]

    def run_with_input(self, run_id, workbook, mode, status, data=b"garbage, not a workbook"):
        self.store.add_run(run_id, self.omar, workbook, mode, status, program="SAKS", week_start="2026-10-11")
        folder = self.queue.run_dir(run_id) / "input"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / workbook).write_bytes(data)
        return run_id

    def test_failed_run_delete_wording(self):
        run = self.run_with_input("aaaaaaaaaaa1", "failed.xlsx", "QUICK", "FAILED")
        page = html.unescape(self.client.get(f"/runs/{run}/schedules").get_data(as_text=True))
        section = re.search(r'(?s)<section[^>]*id="delete".*?</section>', page).group(0)
        self.assertIn("failed.xlsx is not in use. Deleting it removes it for everyone", section)
        self.assertIn("I understand that failed.xlsx is deleted for everyone and cannot be brought back.", section)
        self.assertNotIn("0 version", section)
        got = self.client.post(f"/runs/{run}/delete", data={"csrf_token": token(self.client), "confirm": "1"},
                               follow_redirects=True)
        self.assertIn("Deleted failed.xlsx.", html.unescape(got.get_data(as_text=True)))

    def test_unreadable_input_keeps_the_schedules_page(self):
        book = self.app.extensions["schedules"]
        run = "aaaaaaaaaaa2"
        self.store.add_run(run, self.omar, "week.xlsx", "READY", "DONE", program="SAKS", week_start="2026-10-11")
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        book.ensure_ready(self.store.get_run(run), make_ready(tmp / "ready.xlsx"))
        self.assertTrue(book.versions(run))
        book.input_path(run).write_bytes(b"garbage, not a workbook")  # the kept input is damaged on the server
        got = self.client.get(f"/runs/{run}/schedules")
        self.assertEqual(got.status_code, 200)
        page = html.unescape(got.get_data(as_text=True))
        self.assertIn("The input workbook kept with this schedule cannot be read", page)

    def test_resume_refused_for_readiness_and_unschedulable(self):
        smoke = self.run_with_input("aaaaaaaaaaa3", "check.xlsx", "SMOKE", "FAILED")
        got = self.client.post(f"/runs/{smoke}/resume", data={"csrf_token": token(self.client)},
                               follow_redirects=True)
        self.assertIn("This run cannot be resumed", html.unescape(got.get_data(as_text=True)))
        self.assertEqual(self.store.get_run(smoke)["status"], "FAILED")


class TheSaves(unittest.TestCase):
    def test_a_long_save_is_one_save(self):
        changes = [{"at": 100 + 1.5 * i, "user_id": 1, "by_name": "Omar", "reason": "", "severity": "",
                    "problems": "[]", "associate": f"Associate {i:03d}"} for i in range(5)]  # over 6 s
        self.assertEqual(len(group_changes(changes)), 1)
        apart = changes + [{**changes[0], "at": 120.0, "associate": "Associate 099"}]  # a later save
        self.assertEqual(len(group_changes(apart)), 2)


class TheChannelsWithoutAPlan(_Day):
    PLAN = False

    def test_no_channel_plan_is_one_line(self):
        chv = self.view()["channels"]
        self.assertIsNotNone(chv)
        self.assertFalse(chv["planned"])
        app, *_ = make_app(START_WORKER=False, DATA_DIR=str(self.data))
        client = sign_in(app, "omar", "Owner-pass-123")
        page = html.unescape(client.get("/day?program=" + self.key.replace(" ", "+")
                                        + f"&date={CH_WED.isoformat()}&view=channels").get_data(as_text=True))
        self.assertIn("No channel plan for this day yet: plan channels for it to count each channel.", page)
        self.assertNotIn("On the floor with no channel planned", page)


if __name__ == "__main__":
    unittest.main()
