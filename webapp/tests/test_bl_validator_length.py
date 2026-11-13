# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 2 (owner, 2026-11-07): the independent validator, which re-checks a finished schedule without the solver, also
holds an associate to the Shift Length named on their Schedule row. Fixture: the enforced Voice run of 2026-10-03
(fixtures/real_runs/language_hours), whose input has no Shift Length column; a column is added in a copy of the input."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / "fixtures" / "real_runs" / "language_hours"
INPUT = RUN / "Cricut_Voice_LANGUAGE_HOURS.xlsx"
OUTPUT = RUN / "VOICE_FINAL_SHEET_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"


def validate(book):
    sys.path.insert(0, str(REPO / "engine" / "tools"))
    import independent_validator as V
    return V.validate(Path(book), OUTPUT, REPO / "engine" / "_tools" / "l632_universal_scheduler.py").get("failures", [])


class TheValidatorKeepsTheShiftLength(unittest.TestCase):
    def book_with_length(self, hours):
        """A copy of the input with Shift Length ``hours`` on the first named associate; returns (path, that associate's name)."""
        tmp = Path(tempfile.mkdtemp())
        book = tmp / "in.xlsx"
        shutil.copy(INPUT, book)
        wb = load_workbook(book)
        ws = wb["Schedule"]
        header = next(r for r in range(1, 12) if "Language" in [c.value for c in ws[r]])
        cols = {c.value: c.column for c in ws[header]}
        col = ws.max_column + 1
        ws.cell(header, col, "Shift Length")
        ws.cell(header + 1, col, hours)
        name = ws.cell(header + 1, cols["SF Name"]).value
        wb.save(book)
        return book, name

    def test_a_schedule_that_gives_a_different_length_fails_by_name(self):
        book, name = self.book_with_length(8)  # the run's shifts are 9 hours
        found = [f for f in validate(book) if f.get("type") == "SHIFT_LENGTH_VIOLATION"]
        self.assertTrue(found)
        self.assertEqual({f["associate"] for f in found}, {name})
        self.assertTrue(all(f["expected_minutes"] == 480 and f["actual_minutes"] == 540 for f in found), found)

    def test_a_matching_length_and_a_blank_column_pass(self):
        book, _ = self.book_with_length(9)
        self.assertEqual([f for f in validate(book) if f.get("type") == "SHIFT_LENGTH_VIOLATION"], [])
        self.assertEqual([f for f in validate(INPUT) if f.get("type") == "SHIFT_LENGTH_VIOLATION"], [])


if __name__ == "__main__":
    unittest.main()
