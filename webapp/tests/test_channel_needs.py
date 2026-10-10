# © 2026 Omar Mokhtar. All rights reserved.
"""Phase Z (owner, 2026-10-10: "Associates channels found but i cannot find where i can add the required per channel
and where can it run"; approved sample 03, "Panel + tabs"): channel needs added to a schedule that already exists,
from a workbook made for that week, without a new schedule; every channel reader uses them."""
import html
import io
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook

from webapp.channel_template import add_channel_tabs as needs_tabs
from webapp.channels import read_channels
from webapp.programs import ProgramBook
from webapp.tests.test_channels import add_channel_tabs
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

WEEK = "2026-10-11"
WED = "2026-10-14"
TABS = ["Channels - read me", "Chat 60 Min", "Phone 60 Min", "Email 60 Min", "Email Hours", "Channel Setup"]


def filled(target: Path, step: int = 60) -> Path:
    """A channel needs workbook with Chat 1 and Phone 2 from 08:00 to 22:00 every day."""
    wb = Workbook()
    wb.remove(wb.active)
    needs_tabs(wb, step, ["English"], need=lambda letter, d, t: (0 if not 8 * 60 <= t < 22 * 60 else
                                                                 {"C": 1, "P": 2}[letter]))
    wb.save(target)
    return target


class _Needs(unittest.TestCase):
    """SAKS: NMG Tier 2 has a plain upload that gets channel needs; NMG Tier 3 a plain upload that never does; NMG
    Tier 1 an upload with its own channel tabs that then gets channel needs too. All for the week of Sun 11 Oct."""

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        saks = programs.add_program("SAKS")
        cls.key = programs.add_lob(saks, "NMG Tier 2")
        cls.bare_key = programs.add_lob(saks, "NMG Tier 3")
        cls.tabbed_key = programs.add_lob(saks, "NMG Tier 1")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.book = cls.app.extensions["schedules"]
        cls.plain = cls.upload(cls.ready, "plain.xlsx", cls.key)
        cls.bare = cls.upload(cls.ready, "bare.xlsx", cls.bare_key)
        cls.tabbed = cls.upload(add_channel_tabs(cls.dir / "tabbed.xlsx", src=cls.ready), "tabbed.xlsx",
                                cls.tabbed_key)
        cls.runs_before = len(cls.store.list_runs())
        cls.added = cls.attach(cls.plain, filled(cls.dir / "needs.xlsx"))
        cls.added_tabbed = cls.attach(cls.tabbed, filled(cls.dir / "needs_t1.xlsx"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    @classmethod
    def upload(cls, path, name, program):
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                       "program": program, "week_start": WEEK,
                                       "workbook": (io.BytesIO(path.read_bytes()), name)},
                        content_type="multipart/form-data")
        run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, run_id, statuses=("DONE", "REJECTED", "FAILED"))
        return run_id

    @classmethod
    def attach(cls, run_id, path):
        return cls.client.post(f"/runs/{run_id}/channel-needs",
                               data={"csrf_token": token(cls.client),
                                     "workbook": (io.BytesIO(path.read_bytes()), path.name)},
                               content_type="multipart/form-data", follow_redirects=True)

    def page(self, url):
        got = self.client.get(url)
        self.assertEqual(got.status_code, 200, url)
        return html.unescape(got.get_data(as_text=True))

    def panel(self, page):
        found = re.search(r'(?s)<section[^>]*id="channels".*?</section>', page)
        self.assertIsNotNone(found, "no Channels panel")
        return found.group(0)


class TheChannelNeeds(_Needs):
    def test_the_downloaded_workbook_reads_as_empty_needs(self):
        got = self.client.get(f"/runs/{self.bare}/channel-needs.xlsx")
        self.assertEqual(got.status_code, 200)
        self.assertIn("Channel_needs_SAKS_NMG_Tier_3_2026-10-11.xlsx", got.headers["Content-Disposition"])
        path = self.dir / "download.xlsx"
        path.write_bytes(got.data)
        self.assertEqual(load_workbook(path, read_only=True).sheetnames, TABS)
        setup = read_channels(path, 60)
        for letter in "CP":
            self.assertEqual({v for col in setup["need"][letter].values() for v in col.values()}, {0.0})
            self.assertEqual(len(setup["need"][letter][3]), 24)
        self.assertEqual(setup["email_mode"], "none")
        self.assertEqual((setup["languages"], setup["blended"], setup["notes"]), ([], [], []))

    def test_needs_uploaded_to_a_schedule_are_used_without_a_new_run(self):
        self.assertEqual(len(self.store.list_runs()), self.runs_before)
        self.assertTrue((self.book.root / self.plain / "channels.xlsx").is_file())
        said = html.unescape(self.added.get_data(as_text=True))
        self.assertIn("Channel needs added to plain.xlsx", said)
        version = self.book.versions(self.plain)[0]
        page = self.page(f"/runs/{self.plain}/schedules")
        self.assertIn(f'href="/schedules/{version["id"]}/channels">Plan channels</a>', page)
        self.assertEqual(self.client.get(f"/schedules/{version['id']}/channels").status_code, 200)

    def test_the_rta_counts_channels_from_the_attached_needs(self):
        page = self.page(f"/day?program={self.key.replace(' ', '+')}&date={WED}")
        self.assertRegex(page, r'<a href="/day\?[^"]*view=channels"[^>]*>Channels</a>')
        bare = self.page(f"/day?program={self.bare_key.replace(' ', '+')}&date={WED}")
        self.assertNotIn("view=channels", bare)

    def test_a_wrong_interval_file_is_refused_and_nothing_is_attached(self):
        said = html.unescape(self.attach(self.bare, filled(self.dir / "thirty.xlsx", step=30)).get_data(as_text=True))
        self.assertIn("These channel needs were not added:", said)
        self.assertIn("Chat 30 Min does not match the program's 60-minute interval", said)
        self.assertFalse((self.book.root / self.bare / "channels.xlsx").exists())
        self.assertEqual(list((self.book.root / self.bare).glob("channels*")), [])
        self.assertIsNone(self.book.channel_path(self.bare))

    def test_attached_needs_win_over_the_workbooks_own_tabs(self):
        self.assertEqual(self.book.channel_path(self.tabbed), self.book.root / self.tabbed / "channels.xlsx")
        today = datetime.now(timezone(timedelta(hours=3))).strftime("%a %d %b")
        panel = self.panel(self.page(f"/runs/{self.tabbed}/schedules"))
        self.assertIn(f"From channel needs added on {today}", panel)
        self.assertNotIn("Phone 5 = 7", panel)  # the workbook's own Phone tab is no longer read

    def test_the_panel_shows_three_steps_without_needs(self):
        panel = self.panel(self.page(f"/runs/{self.bare}/schedules"))
        self.assertIn("Channels: Chat, Phone and Email", panel)
        self.assertIn("This schedule has no channel needs yet, so its channels cannot be planned.", panel)
        for step in ("Download the channel needs workbook", "Fill in how many people each channel needs",
                     "Upload it here"):
            self.assertIn(step, panel)
        self.assertIn(f'href="/runs/{self.bare}/channel-needs.xlsx"', panel)
        self.assertIn(f'action="/runs/{self.bare}/channel-needs"', panel)
        self.assertIn("Made for SAKS, NMG Tier 3, week of 11 Oct: Chat 60 Min, Phone 60 Min and Email 60 Min", panel)
        self.assertNotIn("Plan channels", self.page(f"/runs/{self.bare}/schedules"))

    def test_associate_channels_points_to_the_schedules(self):
        page = self.page(f"/setup/channels?program={self.key.replace(' ', '+')}")
        self.assertIn("This page says who can work each channel. How many people each channel needs comes with each "
                      "week's schedule: open", page)
        self.assertRegex(page, r'open <a href="/schedules\?program=SAKS[^"]*">Schedules</a>, then Channels, to add the '
                               r'needs and plan the day\.')


if __name__ == "__main__":
    unittest.main()
