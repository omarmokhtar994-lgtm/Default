# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15): the reported defects.

- "when i choose different program i still csn dee same departments and names": the RTA's With suggestions listed
  every user on the site; they list the people who can open the program.
- "no back button in wallboard".
- "chsnnels not coloredd here": the Timeline draws each person's channel stretches and the channel rows, and says
  when the day has no channel plan.
- "howlong is he logged in": the hover counts from when the RTA has them in (a late login), and the whole row
  answers it.
Made-up "Associate NN" data."""
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.day import day_view, hover_tips
from webapp.programs import ProgramBook
from webapp.tests.test_day import INPUTS, WED as DWED, WEEK
from webapp.tests.test_notify_daybook import WED, _Tagged


class TheNamesAndTheWallboard(_Tagged):
    def test_with_suggestions_are_the_programs_own_people(self):
        gdi = ProgramBook(self.store).add_program("GDI")
        uid = self.store.add_user("gdi.lead", "Associate 88 Lead", "Owner-pass-123", must_change=False)
        self.store.set_user_programs(uid, [gdi])
        html = self.client.get(f"/day?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        names = re.search(r'<datalist id="team-names">(.*?)</datalist>', html, re.S).group(1)
        self.assertNotIn("Associate 88 Lead", names)
        self.assertIn("Omar", names)  # an admin opens every program

    def test_the_wallboard_has_a_way_back(self):
        html = self.client.get(f"/day/wallboard?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        back = re.search(r'<a class="wall-back" href="([^"]+)">([^<]+)</a>', html)
        self.assertIsNotNone(back, "no Back link on the wallboard")
        self.assertIn("/day?", back.group(1).replace("&amp;", "&"))

    def test_a_day_without_channels_says_so_on_the_timeline(self):
        html = self.client.get(f"/day?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        self.assertIn("no channel needs yet", html)


class TheChannelsOnTheTimeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.channel_people import ChannelPeople
        from webapp.tests.test_channel_day import ARABIC_SPARE, channel_day, read_week
        from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        upload = channel_day(cls.dir / "upload.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        omar = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        program_id = programs.add_program("SAKS")
        cls.key = programs.add_lob(program_id, "NMG Tier 2")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                       "program": cls.key, "week_start": "2026-10-11",
                                       "workbook": (io.BytesIO(upload.read_bytes()), "week.xlsx")},
                        content_type="multipart/form-data")
        wait(cls.store, cls.store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
        everyone = [a["name"] for a in read_week(upload)["associates"]]
        ChannelPeople(cls.store).save(program_id, {n: "E" for n in everyone if n not in
                                                   ("Associate 001", "Associate 031", ARABIC_SPARE)}, omar)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def test_each_bar_shows_its_channels_and_the_rows_follow(self):
        html = self.client.get(f"/day?program={self.key}&date=2026-10-14").get_data(as_text=True)
        page = self.app.extensions["days"].page(self.key, __import__("datetime").date(2026, 10, 14))
        runs = page["view"]["channels"]["runs"]
        name, stretches = next((n, r) for n, r in runs.items() if any(c in ("P", "C", "E") for _, _, c in r))
        lane = re.search(r'aria-label="' + re.escape(name) + r': .*?</svg>', html, re.S).group(0)
        for a, b, c in stretches:
            if c in ("P", "C", "E", "A"):
                self.assertRegex(lane, rf'<rect class="tl-ch ch-{c}" x="{a}" y="\d+" width="{b - a}"')
        for row in page["view"]["channels"]["rows"]:
            self.assertIn(f'<span class="tl-lbl">{row["name"]}</span>', html)


class TheHover(unittest.TestCase):
    def test_a_late_login_counts_from_when_they_came_in(self):
        base = day_view(WEEK, INPUTS, DWED, {}, {})
        lane, seg = next((lane, s) for lane in base["lanes"] for s in lane["segments"]
                         if s["offset"] == 0 and s["end"] - s["start"] >= 480)
        came = seg["start"] + 60
        view = day_view(WEEK, INPUTS, DWED, {(0, lane["name"]): {"status": "Late", "from": None, "to": came}}, {})
        lines = hover_tips(view, seg["start"] + 200)[(lane["name"], 0)]["shift"]
        self.assertIn(f"Logged in at {came // 60:02d}:{came % 60:02d}", lines)
        self.assertIn("Logged in for 2 h 20 min", lines)

    def test_before_the_login(self):
        view = day_view(WEEK, INPUTS, DWED, {}, {})
        lane, seg = next((lane, s) for lane in view["lanes"] for s in lane["segments"] if s["offset"] == 0)
        lines = hover_tips(view, seg["start"] - 30)[(lane["name"], 0)]["shift"]
        self.assertIn(f"Logs in at {seg['start'] // 60 % 24:02d}:{seg['start'] % 60:02d}", lines)


class TheWholeRowAnswers(_Tagged):
    def test_each_lane_carries_the_shift_card(self):
        html = self.client.get(f"/day?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        lanes = re.findall(r'<div class="tl-row tl-lane"([^>]*)>', html)
        self.assertTrue(lanes)
        self.assertTrue(all("data-tip=" in attrs for attrs in lanes), lanes[:2])


if __name__ == "__main__":
    unittest.main()
