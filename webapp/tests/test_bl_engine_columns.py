# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 1 (owner, 2026-11-07): the Schedule sheet may carry four optional columns per associate: ``Shift Length``
(hours, for example 8.5), ``Type`` or ``Employment Type`` (Full time or Part time), ``Off Days`` (a whole number) and ``Breaks``
or ``Breaks Per Day`` (a whole number a day). Blank or absent columns read as "the workbook's default" (None), so every
existing workbook reads exactly as before. A value that cannot be read is refused by name, never replaced by a default.
Made-up "Associate NN" data."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "engine" / "_tools"))
SUNDAY = datetime(2026, 11, 1)


def roster(extra_headers=(), rows=()):
    """A workbook with a Schedule sheet: Slot, Emp ID, Email, SF Name, TL, Language, Sun..Sat dates, then the extra columns."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(["Slot", "Emp ID", "Email", "SF Name", "TL", "Language", *[SUNDAY + timedelta(days=d) for d in range(7)],
               *extra_headers])
    for i, extra in enumerate(rows, 1):
        ws.append([i, f"E{i}", f"a{i}@example.com", f"Associate {i:02d}", "TL 01", "English", *[""] * 7, *extra])
    return wb


def read(wb):
    import l632_universal_scheduler as E
    warnings = []
    associates, _, _ = E._parse_roster(wb, parser_warnings=warnings)
    return associates, warnings


class TheOptionalColumns(unittest.TestCase):
    def test_a_roster_without_the_columns_reads_as_before(self):
        people, warnings = read(roster(rows=[[], []]))
        self.assertEqual([(a.shift_minutes, a.part_time, a.off_days, a.breaks_per_day) for a in people],
                         [(None, False, None, None)] * 2)
        self.assertEqual(warnings, [])

    def test_blank_cells_read_as_the_default(self):
        people, warnings = read(roster(("Shift Length", "Employment Type", "Off Days", "Breaks Per Day"), [["", "", "", ""]]))
        self.assertEqual((people[0].shift_minutes, people[0].part_time, people[0].off_days, people[0].breaks_per_day),
                         (None, False, None, None))
        self.assertEqual(warnings, [])

    def test_a_column_that_is_only_called_type_or_breaks_or_off_is_not_ours(self):
        """A roster that already has a column named Type or Breaks (about something else) is read exactly as before: only the unambiguous
        headers Employment Type and Breaks Per Day mean what this phase says."""
        wb = roster(("Type", "Breaks", "Contract"), [["contractor", "08:00 and 12:00", "FTE"], ["", "x", "?"]])
        people, warnings = read(wb)
        self.assertEqual([(a.shift_minutes, a.part_time, a.off_days, a.breaks_per_day) for a in people], [(None, False, None, None)] * 2)
        self.assertEqual(warnings, [])

    def test_the_columns_are_read_when_present(self):
        wb = roster(("Shift Length", "Employment Type", "Off Days", "Breaks Per Day"),
                    [[8.5, "Part time", 4, 1], [9, "Full time", 2, 3], ["8.5 h", "part-time", "3", "2"]])
        people, warnings = read(wb)
        self.assertEqual([(a.shift_minutes, a.part_time, a.off_days, a.breaks_per_day) for a in people],
                         [(510, True, 4, 1), (540, False, 2, 3), (510, True, 3, 2)])
        self.assertEqual(warnings, [])

    def test_a_value_that_cannot_be_read_is_refused_by_name(self):
        cases = [("Shift Length", "banana", "HARD_INVALID_SHIFT_LENGTH"), ("Shift Length", 2, "HARD_INVALID_SHIFT_LENGTH"),
                 ("Shift Length", 17, "HARD_INVALID_SHIFT_LENGTH"), ("Employment Type", "contractor", "HARD_INVALID_ASSOCIATE_TYPE"),
                 ("Off Days", "x", "HARD_INVALID_OFF_DAYS"), ("Off Days", 7, "HARD_INVALID_OFF_DAYS"),
                 ("Off Days", 2.5, "HARD_INVALID_OFF_DAYS"), ("Breaks Per Day", -1, "HARD_INVALID_BREAKS"),
                 ("Breaks Per Day", "many", "HARD_INVALID_BREAKS"), ("Breaks Per Day", 9, "HARD_INVALID_BREAKS")]
        for header, value, code in cases:
            with self.subTest(header=header, value=value):
                _, warnings = read(roster((header,), [[value]]))
                self.assertTrue([w for w in warnings if w.startswith(code) and "Associate 01" in w], warnings)


if __name__ == "__main__":
    unittest.main()
