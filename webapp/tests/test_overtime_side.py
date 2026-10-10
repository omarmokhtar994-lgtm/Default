# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AA (owner, 2026-10-10: "Overtime can be before or after shift"; approved sample 01): the + Add dialog asks
Before the shift or After the shift and a length, and the times are worked out from the person's shift. The rule
itself is unchanged (DayBook.add_activity: overtime ends when the shift starts or starts when it ends)."""
import html
import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

WED = date(2026, 10, 14)
DAY = "Associate 008"      # 08:00 to 17:00 on Wed 14 Oct (starts early on Thursday: no overtime after)
LATE = "Associate 021"     # 08:00 to 17:00, room for overtime after
NIGHT = "Associate 014"    # 21:00 to 06:00
MIDNIGHT = "Associate 033"  # 00:00 to 09:00


class _Overtime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                       "program": cls.key, "week_start": "2026-10-11",
                                       "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                        content_type="multipart/form-data")
        wait(cls.store, cls.store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
        cls.days = cls.app.extensions["days"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def add(self, name, side, minutes, start="10:00", dry_run=True):
        return self.days.add_item(self.key, WED, name, "Overtime", start, minutes, 1, dry_run=dry_run, side=side)

    def form(self, **data):
        return {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), "what": "Overtime",
                "view": "board", "at": "480", **data}


class TheSides(_Overtime):
    def test_after_the_shift_starts_when_it_ends(self):
        found = self.add(LATE, "after", 60)
        self.assertEqual((found["lo"], found["hi"]), (1020, 1080))

    def test_before_the_shift_ends_when_it_starts(self):
        found = self.add(DAY, "before", 60)  # the From time (10:00) is not used
        self.assertEqual((found["lo"], found["hi"]), (420, 480))

    def test_a_shift_ending_after_midnight_gets_overtime_the_next_morning(self):
        found = self.add(NIGHT, "after", 60)
        self.assertEqual((found["lo"], found["hi"]), (1800, 1860))

    def test_before_a_shift_starting_at_midnight_is_refused_clearly(self):
        with self.assertRaises(ValueError) as said:
            self.add(MIDNIGHT, "before", 60)
        self.assertEqual(str(said.exception), f"{MIDNIGHT}'s shift starts at 00:00, so 1 h of overtime before it "
                                              "would start the day before. Pick a shorter length, or After the shift.")


class TheDialog(_Overtime):
    def test_the_dialog_offers_before_and_after(self):
        page = html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}"
                                             f"&view=board&add=480&person={DAY.replace(' ', '+')}")
                             .get_data(as_text=True))
        side = re.search(r'(?s)<fieldset class="ot-side" data-ot-side hidden>.*?</fieldset>', page)
        self.assertIsNotNone(side, "no Before or After choice")
        # disabled until the script shows the choice for Overtime: without it, From works as before
        self.assertRegex(side.group(0), r'<input type="radio" name="side" value="before" checked disabled>')
        self.assertRegex(side.group(0), r'<input type="radio" name="side" value="after" disabled>')
        self.assertIn("Before the shift", side.group(0))
        self.assertIn("After the shift", side.group(0))
        self.assertRegex(page, rf'<option value="{DAY}" data-start="480" data-end="1020"')

    def test_the_person_panel_default_now_records_overtime_before(self):
        got = self.client.post("/day/add", data=self.form(associate=DAY, **{"from": "08:00"}, minutes="60",
                                                          side="before"), follow_redirects=True)
        self.assertIn(f"Recorded: {DAY}, Overtime 07:00 to 08:00.", html.unescape(got.get_data(as_text=True)))

    def test_the_preview_says_the_times(self):
        got = self.client.post("/day/add-preview", data=self.form(associate=LATE, **{"from": "08:00"},
                                                                  minutes="30", side="after"))
        self.assertEqual(got.status_code, 200, got.get_data(as_text=True))
        self.assertIn("17:00 to 17:30", json.loads(got.get_data(as_text=True))["text"])


if __name__ == "__main__":
    unittest.main()
