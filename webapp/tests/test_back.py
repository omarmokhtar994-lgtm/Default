# © 2026 Omar Mokhtar. All rights reserved.
"""Phase W task 2: Back (owner, 2026-10-09: "back button is not working to do anything").

Measured: Back went to the browser's previous page, and after any save (a form that reloads the same page) that
previous page is the same page, so Back looked dead. The script now goes to the last page that was a different
page; when there is none (the page was opened directly), the link itself goes up one level, never just Home."""
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

BACK = re.compile(r'<a href="([^"]*)" data-back>')


class TheBackLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                       "program": key, "week_start": "2026-10-11",
                                       "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                        content_type="multipart/form-data")
        cls.run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, cls.run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.version = cls.app.extensions["schedules"].versions(cls.run_id)[0]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def back(self, url):
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        found = BACK.search(page.get_data(as_text=True))
        self.assertIsNotNone(found, "the page has no Back link")
        return html.unescape(found.group(1))

    def test_plan_breaks_goes_up_to_its_schedule(self):
        mine = f"/runs/{self.run_id}/schedules?v={self.version['id']}"
        self.assertEqual(self.back(f"/schedules/{self.version['id']}/breaks?day=Wed"), mine)
        self.assertEqual(self.back(f"/schedules/{self.version['id']}/week"), mine)

    def test_a_run_schedules_page_goes_up_to_the_run(self):
        self.assertEqual(self.back(f"/runs/{self.run_id}/schedules"), f"/runs/{self.run_id}")


if __name__ == "__main__":
    unittest.main()
