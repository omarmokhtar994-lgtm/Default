# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL audit: the parts of the website that read a roster or a workbook's break rules cope with the new Schedule columns.

- A ready-schedule upload (shifts made, breaks still to plan) with the new columns is accepted: they are the engine's to read, the upload check only
  looks at names, days and shifts.
- The break rules the website's planner and checker use come from the engine's own parser, so a row's Breaks Per Day reaches them as the break set of
  its shift length, and a shift length with none has an empty set that the planner handles.
- A workbook where the new headers hold nothing, or hold values this phase refuses, is still read for its shifts by the upload check.
Made-up data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from webapp import break_plan as BP
from webapp.break_rules_cli import rules as break_rules
from webapp.ready import check_ready
from webapp.tests.test_bl_engine_parttime import EXAMPLE, workbook
from webapp.tests.test_ready import make_ready

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "engine" / "_tools" / "l632_universal_scheduler.py"


def with_columns(source, path, headers):
    wb = load_workbook(source)
    ws = wb["Schedule"]
    head = next(r for r in range(1, 10) if "sun" in [str(c.value or "").strip().lower() for c in ws[r]])
    col = ws.max_column + 1
    for j, (header, value) in enumerate(headers.items()):
        ws.cell(head, col + j, header)
        ws.cell(head + 1, col + j, value)
    wb.save(path)
    return path


class TheReadyUploadAndTheNewColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.ready = make_ready(cls.dir / "ready.xlsx")

    def test_the_new_columns_do_not_stop_a_ready_schedule(self):
        path = with_columns(self.ready, self.dir / "cols.xlsx", {"Shift Length": 9, "Employment Type": "Part time", "Off Days": 3, "Breaks Per Day": 1})
        self.assertEqual(check_ready(path), [])

    def test_columns_with_values_the_engine_would_refuse_are_not_the_upload_checks_business(self):
        path = with_columns(self.ready, self.dir / "odd.xlsx", {"Employment Type": "contractor", "Off Days": "x"})
        self.assertEqual(check_ready(path), [])

    def test_a_column_called_type_or_breaks_is_ignored_by_both(self):
        path = with_columns(self.ready, self.dir / "type.xlsx", {"Type": "FTE", "Breaks": "12:00"})
        self.assertEqual(check_ready(path), [])


class TheBreakRulesTheWebsiteUses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()

    def rules(self, **columns):
        return break_rules(Path(workbook(self.dir, columns=columns, durations="9, 5")), ENGINE)

    def test_without_the_columns_the_rules_are_the_workbooks(self):
        got = self.rules()
        # The example workbook carries its own break set for long shifts; with no new columns the rules are exactly its own, nothing added.
        self.assertEqual(got["by_length"], break_rules(EXAMPLE, ENGINE)["by_length"])
        self.assertEqual(BP.slots_for(got, 300), BP.slots_for(got, 540))

    def test_a_rows_breaks_per_day_is_the_break_set_of_its_shift_length(self):
        got = self.rules(**{"Shift Length": {1: 5}, "Breaks Per Day": {1: 1}})
        self.assertEqual(BP.slots_for(got, 300), [("Break 1", 15)])
        self.assertEqual([label for label, _ in BP.slots_for(got, 540)], ["Break 1", "Lunch", "Break 2"])

    def test_zero_breaks_is_an_empty_set_the_planner_can_use(self):
        got = self.rules(**{"Shift Length": {1: 5}, "Breaks Per Day": {1: 0}})
        self.assertEqual(BP.slots_for(got, 300), [])
        self.assertEqual(BP.break_minutes(got), (15, 30))                  # the other lengths still give a short break and a lunch
        self.assertEqual(BP.slots_of(got, "Associate 003", 300), [])

    def test_the_rules_are_valid_json_for_the_command_line_tool(self):
        got = self.rules(**{"Shift Length": {1: 5}, "Breaks Per Day": {1: 1}})
        self.assertEqual(json.loads(json.dumps(got)), got)


if __name__ == "__main__":
    unittest.main()
