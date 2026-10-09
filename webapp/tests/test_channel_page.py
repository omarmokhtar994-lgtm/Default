# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V task 6: the "Plan channels" page of a version (owner, 2026-10-09: "assign each associate for a while for
channel based on the requirements ... this can be done on the website only ... automatically plan same as for
breaks").

A grid per day of who is on what in 15-minute steps, coverage per channel and language, and the day's figures.
Suggest plans the day (channels, and breaks inside the break rules); a block can be changed by hand; Copy repeats a
day on days with the same shifts; nothing is kept until Save, which makes a new version checked like any other."""
import html
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.channel_people import ChannelPeople
from webapp.programs import ProgramBook
from webapp.tests.test_channels import add_channel_tabs
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait
from webapp.versions import DAYS, shift_span

WED = 3


class _Page(unittest.TestCase):
    @classmethod
    def start(cls, channels=True):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        book = add_channel_tabs(cls.dir / "channels.xlsx", src=ready) if channels else ready
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.program = programs.add_program("SAKS")
        cls.key = programs.add_lob(cls.program, "NMG Tier 2")
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.admin.post("/runs", data={"csrf_token": token(cls.admin), "kind": "ready", "mode": "QUICK",
                                      "program": cls.key, "week_start": "2026-10-11",
                                      "workbook": (io.BytesIO(book.read_bytes()), "week.xlsx")},
                       content_type="multipart/form-data")
        run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.run_id = run_id
        cls.version = cls.app.extensions["schedules"].versions(run_id)[0]
        cls.week = json.loads(cls.version["week"])
        cls.url = f"/schedules/{cls.version['id']}/channels"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def page(self, day="Wed"):
        got = self.admin.get(f"{self.url}?day={day}")
        return got.status_code, html.unescape(got.get_data(as_text=True))

    def post(self, **data):
        return self.admin.post(self.url, data={"csrf_token": token(self.admin), "day": "Wed", **data})

    def working(self, d=WED):
        return [a for a in self.week["associates"] if shift_span(a["days"][d])]


class TheChannelPage(_Page):
    @classmethod
    def setUpClass(cls):
        cls.start()

    def test_the_page_before_any_plan(self):
        code, page = self.page("Thu")  # no test here plans Thursday
        self.assertEqual(code, 200)
        self.assertIn("SAKS, NMG Tier 2: plan channels", page)
        self.assertIn("Not planned yet: Suggest the day, or set blocks by hand.", page)
        for words in ("Suggest the day", "Move breaks if it helps", "Save as a new version", "Phone", "Chat", "Email",
                      "Break or lunch", self.working(4)[0]["name"]):
            self.assertIn(words, page)

    def test_suggest_fills_a_draft_and_nothing_is_kept_until_saved(self):
        self.assertEqual(self.post(action="suggest", move="1").status_code, 303)
        code, page = self.page()
        self.assertIn("Suggested channels for Wednesday", page)
        self.assertIn("Nothing is kept until you save.", page)
        self.assertRegex(page, r'class="c ch-[PCE]"')
        self.assertRegex(page, r"\d+(\.\d+)? h</b> short on Phone")
        draft = self.store.get_channel_draft(self.version["id"])
        self.assertTrue(draft["Wed"]["blocks"])
        self.assertEqual(json.loads(self.store.get_schedule(self.version["id"])["week"])["channels"], [])
        # a break placed by the suggestion cannot be given a channel
        name = self.working()[0]["name"]
        start = draft["Wed"]["breaks"][name][0]
        self.post(action="edit", who=name, start=f"{start // 60:02d}:{start % 60:02d}",
                  end=f"{(start + 15) // 60:02d}:{(start + 15) % 60:02d}", channel="P")
        self.assertIn(f"{name} is on a break then", self.page()[1])

    def test_a_block_set_by_hand_is_checked_then_kept_in_the_draft(self):
        person = self.working()[1]
        lo, hi = shift_span(person["days"][WED])
        hh = lambda m: f"{(m // 60) % 24:02d}:{m % 60:02d}"  # noqa: E731
        self.post(action="edit", who=person["name"], start="00:00", end="01:00", channel="P") if lo >= 120 else None
        if lo >= 120:
            self.assertIn(f"outside {person['name']}'s shift", self.page()[1])
        self.post(action="edit", who=person["name"], start=hh(lo + 10), end=hh(lo + 70), channel="P")
        self.assertIn("15-minute steps", self.page()[1])
        ChannelPeople(self.store).save(self.program, {person["name"]: "P"}, 1)
        self.post(action="edit", who=person["name"], start=hh(lo), end=hh(lo + 60), channel="C")
        self.assertIn(f"{person['name']} cannot work Chat (see Associate channels).", self.page()[1])
        ChannelPeople(self.store).save(self.program, {person["name"]: "PCE"}, 1)
        self.post(action="edit", who=person["name"], start=hh(lo), end=hh(lo + 60), channel="C")
        self.assertIn(f"{person['name']}: Chat from {hh(lo)} to {hh(lo + 60)}. Nothing is kept until you save.",
                      self.page()[1])
        blocks = self.store.get_channel_draft(self.version["id"])["Wed"]["blocks"][person["name"]]
        self.assertIn([lo, lo + 60, "C"], [list(b) for b in blocks])

    def test_all_channels_times_take_no_single_channel(self):
        evening = [a for a in self.week["associates"] if shift_span(a["days"][5])
                   and shift_span(a["days"][5])[0] <= 20 * 60 < shift_span(a["days"][5])[1]]
        if not evening:
            self.skipTest("nobody works Friday evening in this schedule")
        self.admin.post(self.url, data={"csrf_token": token(self.admin), "day": "Fri", "action": "edit",
                                        "who": evening[0]["name"], "start": "20:00", "end": "21:00", "channel": "P"})
        self.assertIn("is an all-channels time", self.page("Fri")[1])

    def test_the_schedules_page_links_to_it(self):
        page = html.unescape(self.admin.get(f"/runs/{self.run_id}/schedules").get_data(as_text=True))
        self.assertIn(f'href="{self.url}"', page)
        self.assertIn("Plan channels", page)


class TheChannelSave(_Page):
    @classmethod
    def setUpClass(cls):
        cls.start()
        cls.admin.post(cls.url, data={"csrf_token": token(cls.admin), "day": "Wed", "action": "suggest", "move": "1"})
        cls.saved = cls.admin.post(cls.url, data={"csrf_token": token(cls.admin), "day": "Wed", "action": "save",
                                                  "reason": "", "use": "1"})
        cls.new_id = int(re.search(r"/schedules/(\d+)/channels", cls.saved.headers["Location"]).group(1))

    def test_saving_makes_a_checked_version_with_the_plan_and_the_breaks(self):
        self.assertNotEqual(self.new_id, self.version["id"])
        row = self.store.get_schedule(self.new_id)
        week = json.loads(row["week"])
        self.assertTrue([c for c in week["channels"] if c["day"] == "Wed"])
        self.assertTrue([b for b in week["breaks"] if b["day"] == "Wed"])
        added = self.app.extensions["schedules"].view(self.new_id)["added"]
        self.assertEqual([p["text"] for p in added if p["severity"] == "red"], [])
        self.assertEqual(self.store.get_channel_draft(self.version["id"]), {})

    def test_the_change_log_says_channels_planned(self):
        changes = self.app.extensions["schedules"].view(self.new_id)["changes"]
        self.assertTrue(changes)
        self.assertEqual({c["reason"] for c in changes}, {"Channels planned"})
        self.assertTrue(any(re.search(r"(Phone|Chat|Email) \d\d:\d\d to \d\d:\d\d", c["new"]) for c in changes))


class TheProgramWithoutChannels(_Page):
    @classmethod
    def setUpClass(cls):
        cls.start(channels=False)

    def test_the_page_says_there_are_no_channel_tabs(self):
        code, page = self.page()
        self.assertEqual(code, 404)
        self.assertIn("This schedule's input workbook has no channel tabs", page)
        schedules = html.unescape(self.admin.get(f"/runs/{self.run_id}/schedules").get_data(as_text=True))
        self.assertNotIn("Plan channels", schedules)


if __name__ == "__main__":
    unittest.main()
