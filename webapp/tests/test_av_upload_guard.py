# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: an uploaded sheet that does not match the sheets required or the templates, or holds
addresses, card info or anything suspicious, is refused and deleted, without touching normal uploads; phone numbers are
not part of it). Made-up cells only."""
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook

from webapp import upload_guard as guard

REPO = Path(__file__).resolve().parents[2]
CARD = "4111 1111 1111 1111"  # a well-known test number, valid by the Luhn check


def book(path, tabs=("Instructions", "Schedule", "Shift Library", "FT Wise 30 Min"), cells=None):
    wb = Workbook()
    wb.remove(wb.active)
    for name in tabs:
        wb.create_sheet(name)
    for tab, ref, value in cells or []:
        wb[tab][ref] = value
    wb.save(path)
    return path


class TheGuard(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def look(self, **kw):
        return guard.look(book(self.dir / "w.xlsx", **kw))

    def test_the_templates_and_real_inputs_pass(self):
        for f in (REPO / "webapp/workbooks").glob("*.xlsx"):
            self.assertIsNone(guard.look(f), f.name)
        real = REPO / "packages/rc9_2_2_production/inputs"
        for f in sorted(real.glob("*.xlsx"))[:6]:
            self.assertIsNone(guard.look(f), f.name)

    def test_a_workbook_with_other_tabs_is_outsourced_data(self):
        found = self.look(tabs=("Sheet1", "Payroll"))
        self.assertEqual(found[0], "structure")
        self.assertIn("outsourced", found[1])
        self.assertIn("deleted", found[1])
        self.assertIn("Instructions", found[1])

    def test_the_requirement_tab_is_needed(self):
        found = self.look(tabs=("Instructions", "Schedule", "Shift Library"))
        self.assertEqual(found[0], "structure")
        self.assertIn("FT Wise", found[1])

    def test_a_card_number_is_refused_and_never_repeated(self):
        found = self.look(cells=[("Schedule", "A1", f"Paid with {CARD}")])
        self.assertEqual(found[0], "personal")
        self.assertIn("card number", found[1])
        self.assertNotIn("4111", found[1])
        self.assertIn("Schedule", found[1])

    def test_a_number_that_fails_the_check_digit_is_not_a_card(self):
        self.assertIsNone(self.look(cells=[("Schedule", "A1", "4111 1111 1111 1112")]))

    def test_a_street_address_is_refused(self):
        found = self.look(cells=[("Schedule", "B2", "12 Nile Street")])
        self.assertEqual(found[0], "personal")
        self.assertIn("street address", found[1])

    def test_phone_numbers_and_emails_and_plain_numbers_pass(self):
        cells = [("Schedule", "A1", "+20 100 123 4567"), ("Schedule", "A2", "01001234567"),
                 ("Schedule", "A3", "associate.01@example.com"), ("Schedule", "A4", 1.35012310754885),
                 ("Schedule", "A5", "/content/wfm_queue/JOB-20260730-0026-78C323/NMG_EN.xlsx"), ("Schedule", "A6", 12345678)]
        self.assertIsNone(self.look(cells=cells))

    def test_a_formula_that_reaches_outside_is_refused(self):
        found = self.look(cells=[("Schedule", "A1", '=HYPERLINK("http://evil.example/x","go")')])
        self.assertEqual(found[0], "personal")
        self.assertIn("formula", found[1])

    def test_macros_and_embedded_objects_are_refused(self):
        path = book(self.dir / "m.xlsx")
        with zipfile.ZipFile(path, "a") as z:
            z.writestr("xl/vbaProject.bin", b"x")
        found = guard.look(path)
        self.assertEqual(found[0], "active")

    def test_a_file_that_is_not_a_workbook_is_left_to_the_later_checks(self):
        junk = self.dir / "j.xlsx"
        junk.write_bytes(b"PK\x03\x04 not really")
        self.assertIsNone(guard.look(junk))
        text = self.dir / "t.xlsx"
        text.write_text("hello")
        self.assertIsNone(guard.look(text))


if __name__ == "__main__":
    unittest.main()
