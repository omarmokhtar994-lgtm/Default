# © 2026 Omar Mokhtar. All rights reserved.
"""AN review: no guessed workbook occurrence or wrong-offset RTA write.

The wall-clock data format has no occurrence field. These tests cover the
explicit limitation and preserve normal-date edits, permissions and CSRF.
"""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from webapp.clock import converted, rta_shift
from webapp.programs import ProgramBook
from webapp.tests.test_runs import make_app, sign_in, token
from webapp.versions import zoned_copy, zoned_label


class ClockSafety(unittest.TestCase):
    def test_repeated_source_hour_is_not_guessed(self):
        with self.assertRaisesRegex(ValueError, "occurs twice"):
            converted(date(2026, 11, 1), 90, "America/New_York", "UTC")

    def test_missing_source_hour_is_not_normalized(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            converted(date(2026, 3, 8), 150, "America/New_York", "UTC")

    def test_target_repeated_hour_keeps_the_known_instant(self):
        first = converted(date(2026, 11, 1), 330, "UTC", "America/New_York")
        second = converted(date(2026, 11, 1), 390, "UTC", "America/New_York")
        self.assertEqual((first.hour, second.hour), (1, 1))
        self.assertEqual((first.fold, second.fold), (0, 1))
        self.assertNotEqual(first.utcoffset(), second.utcoffset())

    def test_rta_checks_source_and_target_transitions(self):
        for on, source, target in ((date(2026, 11, 1), "America/New_York", "UTC"),
                                   (date(2026, 10, 25), "Africa/Cairo", "Europe/London"),
                                   (date(2026, 3, 8), "UTC", "America/New_York")):
            with self.subTest(on=on, source=source, target=target):
                self.assertIsNone(rta_shift(on, source, target))

    def test_export_labels_distinguish_both_destination_occurrences(self):
        self.assertEqual(zoned_label("05:30 - 06:30", 0, on=date(2026, 11, 1),
                                     from_zone="UTC", to_zone="America/New_York"),
                         "01:30 (UTC-04:00) - 01:30 (UTC-05:00)")

    def test_rta_checks_overnight_tail(self):
        self.assertIsNone(rta_shift(date(2026, 10, 31), "UTC", "America/New_York"))

    def test_normal_dates_and_native_zone_keep_the_existing_offset(self):
        self.assertEqual(rta_shift(date(2026, 10, 14), "Africa/Cairo", "America/New_York"), -420)
        self.assertEqual(rta_shift(date(2026, 11, 1), "America/New_York", "America/New_York"), 0)

    def test_ambiguous_workbook_download_leaves_source_and_destination_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / "source.xlsx", Path(folder) / "copy.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.title = "Schedule"
            sheet.append(["SF Name", "Sun"])
            sheet.append(["Associate 001", "01:30 - 10:30"])
            book.save(source)
            before = source.read_bytes()
            destination.write_bytes(b"existing destination")
            with self.assertRaisesRegex(ValueError, "occurs twice"):
                zoned_copy(source, destination, 0, on=date(2026, 11, 1),
                           from_zone="America/New_York", to_zone="UTC")
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(destination.read_bytes(), b"existing destination")


class RtaClockHTTP(unittest.TestCase):
    def setUp(self):
        self.app, self.store, folder, _ = make_app(start_worker=False)
        self.addCleanup(shutil.rmtree, folder, True)
        self.owner = self.store.add_user("admin", "Administrator", "Admin-pass-123", is_admin=True, must_change=False)
        self.client = sign_in(self.app, "admin", "Admin-pass-123")
        programs = ProgramBook(self.store)
        self.program = programs.add_lob(programs.add_program("Example"), "Support")
        self.data = {"csrf_token": token(self.client), "program": self.program,
                     "date": "2026-10-25", "tz": "Europe/London", "start": "09:00"}

    def test_transition_page_uses_native_zone_and_explains_why(self):
        response = self.client.get("/day", query_string={"program": self.program,
                                                       "date": "2026-10-25", "tz": "Europe/London"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Clocks change in this window", response.get_data(as_text=True))
        self.assertIn('<option value="Africa/Cairo" selected>', response.get_data(as_text=True))

    def test_old_form_cannot_change_operating_start_with_wrong_offset(self):
        response = self.client.post("/day/operating-day", data=self.data)
        self.assertEqual(response.status_code, 303)
        self.assertIn("tz=Africa/Cairo", response.headers["Location"])
        self.assertIsNone(self.store.get_day_start(self.program))

    def test_transition_fallback_keeps_the_operating_day_start(self):
        self.store.set_day_start(self.program, 960, self.owner)
        # re-pinned (Phase AY, owner: only the day the clocks change inside the shown window refuses): the operating day starting at 16:00
        # on 25 Oct is after the UK change (01:00 UTC), so it shows in London time now; 24 Oct's 24 hours from 16:00 contain it
        response = self.client.get("/day", query_string={"program": self.program, "date": "2026-10-24",
                                                       "tz": "Europe/London", "window": "operating"})
        self.assertEqual(response.status_code, 200)
        self.assertIn('<option value="16:00" selected>', response.get_data(as_text=True))
        with self.client.session_transaction() as state:
            self.assertEqual(state["rta"][self.program]["start"], "16:00")

    def test_json_form_receives_actionable_error(self):
        response = self.client.post("/day/operating-day", data=self.data,
                                    headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("schedule's own time zone", response.json["error"])
        self.assertIsNone(self.store.get_day_start(self.program))

    def test_native_zone_save_still_works(self):
        response = self.client.post("/day/operating-day", data={**self.data, "tz": "Africa/Cairo"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.get_day_start(self.program), 540)

    def test_normal_date_cross_zone_save_still_works(self):
        response = self.client.post("/day/operating-day", data={**self.data, "date": "2026-10-14"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.get_day_start(self.program), 660)

    def test_csrf_remains_required(self):
        response = self.client.post("/day/operating-day", data={**self.data, "csrf_token": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.store.get_day_start(self.program))


if __name__ == "__main__":
    unittest.main()
