# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "entry is manual on site per interval or excel sheet to be uploaded and make a draft of sheet can be filled"): the draft
workbook a planner downloads, fills in Excel and uploads. One sheet per channel in the input sheet's layout (intervals down, Sun to Sat across), the week's
start date in a cell, an optional handle-time grid beside the contacts. Made-up numbers."""
import io
import unittest
from datetime import date

from openpyxl import Workbook, load_workbook

from webapp import volumes_draft as V

SUN = date(2026, 10, 25)
MON = date(2026, 10, 26)
TODAY = date(2026, 11, 4)


def filled(week=SUN, step=60, cells=None, sheet="Phone", aht=None):
    """The draft for ``week`` with ``cells`` ({(day column 0-6, row of the interval): value}) typed into the contacts block of ``sheet``."""
    wb = load_workbook(io.BytesIO(V.draft_workbook(week, step)))
    ws = wb[sheet]
    head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
    for (day, slot), value in (cells or {}).items():
        ws.cell(head + 1 + slot, 2 + day).value = value
    for (day, slot), value in (aht or {}).items():
        ws.cell(head + 1 + slot, 10 + day).value = value
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


class TheDraft(unittest.TestCase):
    def setUp(self):
        self.wb = load_workbook(io.BytesIO(V.draft_workbook(SUN, 60)))

    def test_a_read_me_and_a_sheet_per_channel(self):
        self.assertEqual(self.wb.sheetnames, ["Read me", "Phone", "Chat", "Email"])

    def test_the_week_start_is_a_date_in_b2(self):
        for name in ("Phone", "Chat", "Email"):
            v = self.wb[name]["B2"].value
            self.assertEqual((v.date() if hasattr(v, "date") else v), SUN)

    def test_the_layout_is_the_input_sheets(self):
        ws = self.wb["Phone"]
        head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
        self.assertEqual([ws.cell(head, c).value for c in range(2, 9)], ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual([ws.cell(head, c).value for c in range(10, 17)], ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual([ws.cell(head + 1 + i, 1).value for i in (0, 1, 23)], ["00:00", "01:00", "23:00"])
        self.assertIsNone(ws.cell(head + 25, 1).value)

    def test_the_interval_follows_the_program(self):
        ws = load_workbook(io.BytesIO(V.draft_workbook(SUN, 30)))["Chat"]
        head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
        self.assertEqual([ws.cell(head + 1 + i, 1).value for i in (0, 1, 47)], ["00:00", "00:30", "23:30"])

    def test_entries_are_checked_by_excel_itself(self):
        kinds = {dv.type for dv in self.wb["Phone"].data_validations.dataValidation}
        self.assertEqual(kinds, {"whole", "decimal"})

    def test_the_draft_has_no_numbers_in_it_and_no_macros(self):
        ws = self.wb["Phone"]
        head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
        self.assertFalse(any(isinstance(ws.cell(r, c).value, (int, float)) for r in range(head + 1, head + 25) for c in range(2, 17)))

    def test_a_bad_step_is_refused(self):
        for step in (0, 7, 45, 1441):
            with self.assertRaises(ValueError):
                V.draft_workbook(SUN, step)


class TheUpload(unittest.TestCase):
    def test_a_filled_draft_is_read_with_the_right_dates(self):
        data = filled(cells={(0, 9): 40, (1, 9): 55, (1, 10): 60, (6, 9): 12}, aht={(1, 9): 300, (1, 10): 360})
        p = V.parse_draft(data, "draft.xlsx", 60, TODAY)
        self.assertEqual(p.problems, [])
        rows = {(d, m): (o, a) for d, m, o, a in p.rows["Phone"]}
        self.assertEqual(rows[("2026-10-25", 540)], (40.0, None))        # Sunday 25 Oct, 09:00
        self.assertEqual(rows[("2026-10-26", 540)], (55.0, 300.0))
        self.assertEqual(rows[("2026-10-26", 600)], (60.0, 360.0))
        self.assertEqual(rows[("2026-10-31", 540)], (12.0, None))        # Saturday
        self.assertEqual(p.summary["Phone"]["days"], 3)

    def test_a_week_that_starts_on_monday_puts_sunday_last(self):
        p = V.parse_draft(filled(week=MON, cells={(0, 9): 7, (1, 9): 8}), "draft.xlsx", 60, TODAY)
        got = {d for d, _m, _o, _a in p.rows["Phone"]}
        self.assertEqual(got, {"2026-11-01", "2026-10-26"})                # Sun is the 1st of November, Mon the 26th

    def test_the_date_can_be_changed_to_reuse_the_sheet(self):
        wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
        wb["Phone"]["B2"].value = date(2026, 10, 18)
        out = io.BytesIO()
        wb.save(out)
        p = V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)
        self.assertEqual({d for d, *_ in p.rows["Phone"]}, {"2026-10-19"})

    def test_two_channels_are_read_together_and_an_empty_one_is_said(self):
        wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
        wb["Chat"].cell(next(r for r in range(1, 15) if wb["Chat"].cell(r, 1).value == "Interval") + 11, 3).value = 3
        out = io.BytesIO()
        wb.save(out)
        p = V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)
        self.assertEqual(sorted(p.rows), ["Chat", "Phone"])
        self.assertTrue(any("Email" in n and "no numbers" in n for n in p.notes))

    def test_an_empty_draft_is_refused_in_words(self):
        p = V.parse_draft(V.draft_workbook(SUN, 60), "draft.xlsx", 60, TODAY)
        self.assertEqual(p.rows, {})
        self.assertTrue(any("no numbers" in x for x in p.problems))

    def test_one_bad_cell_keeps_every_channel_out(self):
        wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
        ws = wb["Chat"]
        head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
        ws.cell(head + 10, 3).value = "abc"
        out = io.BytesIO()
        wb.save(out)
        p = V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)
        self.assertEqual(p.rows, {})
        self.assertTrue(any(x.startswith("Chat:") for x in p.problems))
        self.assertFalse(any("abc" in x for x in p.problems))              # the text typed is never echoed

    def test_the_bad_values_are_named_by_sheet_and_place(self):
        for bad in (-3, 1.5, 2_000_000, "x"):
            p = V.parse_draft(filled(cells={(1, 9): bad}), "draft.xlsx", 60, TODAY)
            self.assertEqual(p.rows, {}, bad)
            self.assertTrue(p.problems and p.problems[0].startswith("Phone:"), (bad, p.problems))

    def test_a_handle_time_out_of_range_is_refused(self):
        for bad in (0, 9000, "x"):
            p = V.parse_draft(filled(cells={(1, 9): 5}, aht={(1, 9): bad}), "draft.xlsx", 60, TODAY)
            self.assertEqual(p.rows, {}, bad)

    def test_a_week_in_the_future_is_refused(self):
        p = V.parse_draft(filled(week=date(2026, 12, 6), cells={(1, 9): 5}), "draft.xlsx", 60, TODAY)
        self.assertEqual(p.rows, {})
        self.assertTrue(any("outside the range" in x for x in p.problems))

    def test_a_missing_or_wrong_week_start_is_refused(self):
        for value in (None, "next week", 12):
            wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
            wb["Phone"]["B2"].value = value
            out = io.BytesIO()
            wb.save(out)
            p = V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)
            self.assertEqual(p.rows, {}, value)
            self.assertTrue(any("B2" in x for x in p.problems), (value, p.problems))

    def test_intervals_coarser_than_the_program_are_refused(self):
        p = V.parse_draft(filled(step=60, cells={(1, 9): 5}), "draft.xlsx", 30, TODAY)
        self.assertEqual(p.rows, {})
        self.assertTrue(any("60-minute" in x for x in p.problems))

    def test_a_sheet_that_is_not_a_channel_is_refused(self):
        wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
        wb.create_sheet("Fax")
        out = io.BytesIO()
        wb.save(out)
        p = V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)
        self.assertEqual(p.rows, {})
        self.assertTrue(any("Phone, Chat or Email" in x for x in p.problems))
        self.assertFalse(any("Fax" in x for x in p.problems))

    def test_a_sheet_without_the_interval_header_is_refused(self):
        wb = Workbook()
        wb.active.title = "Phone"
        wb.active["B2"] = date(2026, 10, 25)
        wb.active["A5"] = "Time"
        out = io.BytesIO()
        wb.save(out)
        p = V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)
        self.assertEqual(p.rows, {})
        self.assertTrue(any("Interval" in x for x in p.problems))

    def test_only_a_workbook_is_taken(self):
        for name, data in (("draft.csv", b"a,b"), ("draft.xlsx", b"not a workbook"), ("draft.xlsx", b""), ("draft.exe", b"x")):
            with self.assertRaises(ValueError, msg=name):
                V.parse_draft(data, name, 60, TODAY)

    def test_a_card_number_or_outside_link_is_refused(self):
        for text in ("4111 1111 1111 1111", "=cmd|' /C calc'!A0", "=HYPERLINK(\"http://x.example\")"):
            wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
            wb["Phone"]["K3"].value = text
            out = io.BytesIO()
            wb.save(out)
            with self.assertRaises(ValueError, msg=text):
                V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)

    def test_a_giant_sheet_is_not_read_to_the_end(self):
        wb = load_workbook(io.BytesIO(filled(cells={(1, 9): 5})))
        ws = wb["Phone"]
        for r in range(100, 2000):
            ws.cell(r, 1).value = f"{r % 24:02d}:00"
        out = io.BytesIO()
        wb.save(out)
        with self.assertRaises(ValueError):
            V.parse_draft(out.getvalue(), "draft.xlsx", 60, TODAY)

    def test_every_interval_of_a_full_day_round_trips(self):
        cells = {(2, i): i + 1 for i in range(24)}
        p = V.parse_draft(filled(cells=cells), "draft.xlsx", 60, TODAY)
        self.assertEqual(sum(o for _d, _m, o, _a in p.rows["Phone"]), sum(range(1, 25)))
        self.assertEqual(len(p.rows["Phone"]), 24)


if __name__ == "__main__":
    unittest.main()
