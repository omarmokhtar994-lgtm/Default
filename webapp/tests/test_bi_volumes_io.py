# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI task 3 (owner, 2026-11-03: actuals as input per channel; "same as the input sheet, days and intervals, so it is easy to copy and
paste"): what an uploaded or pasted table of actual volumes is read as, and every reason it is refused. Made-up numbers."""
import csv
import io
import unittest
from datetime import date, time

from openpyxl import Workbook

from webapp import volumes_io as V

TODAY = date(2026, 11, 3)
WEEK = date(2026, 10, 25)  # a Sunday


def table(text):
    return V.parse_pasted(text)


LONG = "Date\tInterval\tChannel\tOffered\tAHT\n2026-10-26\t09:00\tPhone\t12\t300\n2026-10-26\t09:30\tPhone\t15\t310\n2026-10-26\t09:00\tChat\t4\t\n"
GRID = "Interval\tSun\tMon\tTue\tWed\tThu\tFri\tSat\n09:00\t1\t12\t13\t14\t15\t16\t2\n09:30\t3\t15\t16\t17\t18\t19\t4\n"


class ThePaste(unittest.TestCase):
    def test_tabs_commas_and_semicolons(self):
        self.assertEqual(V.parse_pasted("a\tb\n1\t2"), [["a", "b"], ["1", "2"]])
        self.assertEqual(V.parse_pasted("a,b\n1,2"), [["a", "b"], ["1", "2"]])
        self.assertEqual(V.parse_pasted("a;b\n1;2"), [["a", "b"], ["1", "2"]])

    def test_blank_lines_are_dropped_and_cells_trimmed(self):
        self.assertEqual(V.parse_pasted(" a \t b \n\n 1 \t 2 \n"), [["a", "b"], ["1", "2"]])

    def test_too_much_is_refused(self):
        with self.assertRaises(ValueError):
            V.parse_pasted("a\n" * 500_001)


class TheCells(unittest.TestCase):
    def test_times(self):
        for value, minute in (("09:30", 570), ("9:30", 570), ("09:30:00", 570), (time(9, 30), 570), (0.5, 720), ("12:00 AM", 0),
                              ("1:15 PM", 795), ("00:00", 0), ("23:45", 1425)):
            self.assertEqual(V.minute_of(value), minute, value)
        for bad in ("", None, "abc", "25:00", "09:75", -1, 2.5):
            self.assertIsNone(V.minute_of(bad), bad)

    def test_dates(self):
        for value in ("2026-10-26", "26/10/2026", "26-10-2026", date(2026, 10, 26)):
            self.assertEqual(V.date_of(value), date(2026, 10, 26), value)
        for bad in ("", None, "2026-13-40", "yesterday", "10/26/2026"):
            self.assertIsNone(V.date_of(bad), bad)


class TheLongForm(unittest.TestCase):
    def test_a_good_table(self):
        got = V.parse_long(table(LONG), None, 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertEqual(got.rows["Phone"], [("2026-10-26", 540, 12.0, 300.0), ("2026-10-26", 570, 15.0, 310.0)])
        self.assertEqual(got.rows["Chat"], [("2026-10-26", 540, 4.0, None)])
        self.assertEqual(got.summary["Phone"], {"rows": 2, "days": 1, "first": "2026-10-26", "last": "2026-10-26"})

    def test_headers_in_other_words(self):
        text = "Day\tStart time\tQueue\tCalls offered\tAverage handle time\n26/10/2026\t9:00\tvoice\t12\t300\n"
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertEqual(got.rows["Phone"], [("2026-10-26", 540, 12.0, 300.0)])

    def test_the_channel_can_come_from_the_page(self):
        text = "Date\tInterval\tOffered\n2026-10-26\t09:00\t12\n"
        self.assertEqual(V.parse_long(table(text), "Chat", 30, TODAY).rows["Chat"], [("2026-10-26", 540, 12.0, None)])
        self.assertTrue(V.parse_long(table(text), None, 30, TODAY).problems)

    def test_each_reason_names_its_row(self):
        text = ("Date\tInterval\tChannel\tOffered\tAHT\n"
                "2026-10-26\t09:00\tFax\t5\t300\n"           # row 2: unknown channel
                "2026-10-26\t09:00\tPhone\t-3\t300\n"        # row 3: negative
                "2026-10-26\t09:00\tPhone\t4.5\t300\n"       # row 4: not whole
                "2026-10-26\t09:00\tChat\t5\t300\n"          # row 5: fine (another channel)
                "2026-10-26\t09:30\tPhone\tabc\t300\n"       # row 6: not a number
                "2027-01-01\t09:30\tPhone\t5\t300\n"         # row 7: in the future
                "1999-01-01\t09:30\tPhone\t5\t300\n"         # row 8: too long ago
                "2026-10-26\t09:30\tPhone\t5\t0\n"           # row 9: AHT zero
                "2026-10-26\t09:30\tPhone\t5\t99999\n"       # row 10: AHT absurd
                "2026-10-26\t09:30\tPhone\t2000000\t300\n"   # row 11: absurd volume
                "notadate\t09:30\tPhone\t5\t300\n")          # row 12: date
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertEqual(got.rows, {})
        for row in (2, 3, 4, 6, 7, 8, 9, 10, 11, 12):
            self.assertTrue(any(f"Row {row}" in p for p in got.problems), (row, got.problems))

    def test_times_off_every_grid_are_refused(self):
        text = "Date\tInterval\tChannel\tOffered\n2026-10-26\t09:07\tPhone\t5\n2026-10-26\t09:30\tPhone\t5\n"
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertTrue(got.problems)
        self.assertEqual(got.rows, {})

    def test_one_bad_row_means_nothing_is_taken(self):
        text = LONG + "2026-10-26\t10:00\tPhone\t-1\t300\n"
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertTrue(got.problems)
        self.assertEqual(got.rows, {})

    def test_a_row_given_twice_is_refused(self):
        text = LONG + "2026-10-26\t09:00\tPhone\t99\t300\n"
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertTrue(any("twice" in p.lower() for p in got.problems))

    def test_finer_rows_are_added_up_to_the_programs_interval(self):
        text = ("Date\tInterval\tChannel\tOffered\tAHT\n2026-10-26\t09:00\tPhone\t10\t200\n2026-10-26\t09:15\tPhone\t30\t400\n"
                "2026-10-26\t09:30\tPhone\t5\t300\n2026-10-26\t09:45\tPhone\t5\t300\n")
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertEqual(got.rows["Phone"], [("2026-10-26", 540, 40.0, 350.0), ("2026-10-26", 570, 10.0, 300.0)])

    def test_coarser_rows_that_do_not_divide_are_refused_and_hourly_rows_are_shared(self):
        # re-pinned 2026-11-10 (Phase BM, owner: the history "is hourly"): hourly rows in a 30-minute program used to be refused ("Upload the finer
        # data"); they are now taken and each hour is shared evenly over its intervals. Rows that are not a whole number of intervals are still refused.
        text = "Date\tInterval\tChannel\tOffered\n2026-10-26\t09:00\tPhone\t10\n2026-10-26\t10:00\tPhone\t30\n"
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertEqual([(m, v) for _, m, v, _ in got.rows["Phone"]], [(540, 5.0), (570, 5.0), (600, 15.0), (630, 15.0)])
        twenty = "Date\tInterval\tChannel\tOffered\n2026-10-26\t09:00\tPhone\t10\n2026-10-26\t09:20\tPhone\t30\n"
        refused = V.parse_long(table(twenty), None, 15, TODAY)
        self.assertTrue(any("20-minute" in p for p in refused.problems), refused.problems)

    def test_a_table_without_the_needed_columns_is_refused(self):
        with self.assertRaises(ValueError):
            V.parse_long(table("Name\tValue\nx\t1\n"), None, 30, TODAY)

    def test_formulas_and_long_text_are_never_kept(self):
        text = "Date\tInterval\tChannel\tOffered\n2026-10-26\t09:00\t=HYPERLINK(\"x\")\t5\n"
        got = V.parse_long(table(text), None, 30, TODAY)
        self.assertEqual(got.rows, {})
        self.assertTrue(got.problems)
        self.assertNotIn("HYPERLINK", " ".join(got.problems))  # what was typed is not echoed back


class TheGrid(unittest.TestCase):
    def test_the_input_sheet_layout(self):
        got = V.parse_grid(table(GRID), WEEK, "Phone", None, 30, TODAY)
        self.assertEqual(got.problems, [])
        rows = got.rows["Phone"]
        self.assertEqual(len(rows), 14)
        self.assertIn(("2026-10-25", 540, 1.0, None), rows)   # Sunday of that week
        self.assertIn(("2026-10-26", 570, 15.0, None), rows)  # Monday
        self.assertIn(("2026-10-31", 570, 4.0, None), rows)   # Saturday

    def test_a_monday_week_reads_each_day_in_its_own_column(self):
        got = V.parse_grid(table(GRID), date(2026, 10, 26), "Phone", None, 30, TODAY)  # Monday start
        self.assertIn(("2026-11-01", 540, 1.0, None), got.rows["Phone"])  # the Sunday column is the Sunday that ends the week
        self.assertIn(("2026-10-26", 540, 12.0, None), got.rows["Phone"])

    def test_aht_comes_from_a_second_grid(self):
        aht = "Interval\tSun\tMon\tTue\tWed\tThu\tFri\tSat\n09:00\t300\t301\t302\t303\t304\t305\t306\n09:30\t310\t311\t312\t313\t314\t315\t316\n"
        got = V.parse_grid(table(GRID), WEEK, "Phone", table(aht), 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertIn(("2026-10-26", 540, 12.0, 301.0), got.rows["Phone"])

    def test_a_day_with_nothing_in_it_is_left_out_not_stored_as_zeros(self):
        text = "Interval\tSun\tMon\n09:00\t\t12\n09:30\t\t15\n"
        got = V.parse_grid(table(text), WEEK, "Phone", None, 30, TODAY)
        self.assertEqual({r[0] for r in got.rows["Phone"]}, {"2026-10-26"})

    def test_a_blank_among_numbers_is_zero(self):
        text = "Interval\tMon\n09:00\t12\n09:30\t\n10:00\t7\n"
        got = V.parse_grid(table(text), WEEK, "Phone", None, 30, TODAY)
        self.assertIn(("2026-10-26", 570, 0.0, None), got.rows["Phone"])

    def test_a_grid_for_a_week_in_the_future_is_refused(self):
        got = V.parse_grid(table(GRID), date(2027, 1, 3), "Phone", None, 30, TODAY)
        self.assertTrue(got.problems)

    def test_a_channel_is_needed_and_must_be_known(self):
        with self.assertRaises(ValueError):
            V.parse_grid(table(GRID), WEEK, "Fax", None, 30, TODAY)

    def test_the_header_is_found_even_below_a_title_row(self):
        got = V.parse_grid(table("Phone volumes\n" + GRID), WEEK, "Phone", None, 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertEqual(len(got.rows["Phone"]), 14)

    def test_a_table_that_is_not_a_grid_is_refused(self):
        with self.assertRaises(ValueError):
            V.parse_grid(table("a\tb\n1\t2"), WEEK, "Phone", None, 30, TODAY)


class TheFiles(unittest.TestCase):
    def xlsx(self, rows):
        wb = Workbook()
        ws = wb.active
        for r in rows:
            ws.append(r)
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    def test_a_workbook_with_real_times_and_dates(self):
        data = self.xlsx([["Date", "Interval", "Channel", "Offered", "AHT"], [date(2026, 10, 26), time(9, 0), "Phone", 12, 300]])
        got = V.parse_long(V.read_table(data, "actuals.xlsx"), None, 30, TODAY)
        self.assertEqual(got.problems, [])
        self.assertEqual(got.rows["Phone"], [("2026-10-26", 540, 12.0, 300.0)])

    def test_a_csv_file(self):
        out = io.StringIO()
        csv.writer(out).writerows([["Date", "Interval", "Channel", "Offered"], ["2026-10-26", "09:00", "Phone", 12]])
        got = V.parse_long(V.read_table(out.getvalue().encode(), "actuals.csv"), None, 30, TODAY)
        self.assertEqual(got.rows["Phone"], [("2026-10-26", 540, 12.0, None)])

    def test_a_grid_workbook_with_a_time_column(self):
        rows = [["Interval", "Sun", "Mon"], [time(9, 0), 1, 12], [time(9, 30), 3, 15]]
        got = V.parse_grid(V.read_table(self.xlsx(rows), "grid.xlsx"), WEEK, "Phone", None, 30, TODAY)
        self.assertIn(("2026-10-26", 540, 12.0, None), got.rows["Phone"])

    def test_a_file_that_is_not_a_sheet_is_refused(self):
        with self.assertRaises(ValueError):
            V.read_table(b"PK\x03\x04 not really", "x.xlsx")
        with self.assertRaises(ValueError):
            V.read_table(b"\x00\x01 binary", "x.xls")

    def test_a_workbook_with_a_card_number_is_refused(self):
        data = self.xlsx([["Date", "Interval", "Channel", "Offered", "Note"], [date(2026, 10, 26), time(9, 0), "Phone", 5, "4111 1111 1111 1111"]])
        with self.assertRaises(ValueError):
            V.read_table(data, "x.xlsx")


if __name__ == "__main__":
    unittest.main()
