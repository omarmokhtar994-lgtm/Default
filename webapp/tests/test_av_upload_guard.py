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

    def test_the_requirement_tab_may_have_any_name(self):
        self.assertIsNone(self.look(tabs=("Instructions", "Schedule", "Shift Library", "Demand by hour")))

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


class TheUploadRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import io
        from webapp.tests.test_runs import make_app, sign_in
        cls.io = io
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def upload(self, path, kind="ready"):
        from webapp.tests.test_runs import token
        return self.client.post("/runs", data={"csrf_token": token(self.client), "kind": kind, "mode": "QUICK", "week_start": "2026-10-11",
                                               "workbook": (self.io.BytesIO(Path(path).read_bytes()), "week.xlsx")},
                                content_type="multipart/form-data", follow_redirects=True)

    def incoming(self):
        root = self.app.extensions["runs"].runs_root / "_incoming"
        return list(root.glob("*")) if root.exists() else []

    def test_a_workbook_with_other_tabs_is_deleted_and_said(self):
        before = len(self.store.list_runs())
        got = self.upload(book(self.dir / "p.xlsx", tabs=("Sheet1", "Payroll")))
        text = got.get_data(as_text=True)
        self.assertIn("outsourced", text)
        self.assertEqual(self.incoming(), [])
        self.assertEqual(len(self.store.list_runs()), before)
        self.assertTrue(any(e["kind"] == "upload_refused" for e in self.store.list_events(0, 2 ** 31)))

    def test_a_card_number_is_deleted_and_never_shown_or_logged(self):
        got = self.upload(book(self.dir / "c.xlsx", cells=[("Schedule", "A1", CARD)]))
        self.assertIn("card number", got.get_data(as_text=True))
        self.assertNotIn("4111", got.get_data(as_text=True))
        self.assertEqual(self.incoming(), [])
        for e in self.store.list_events(0, 2 ** 31):
            self.assertNotIn("4111", str(e))

    def test_the_example_template_is_not_refused_by_the_guard(self):
        got = self.upload(REPO / "webapp/workbooks/Scheduler_Input_Example.xlsx", kind="engine")
        self.assertNotIn("outsourced", got.get_data(as_text=True))


class TheNumbersExcelKeeps(unittest.TestCase):
    """Owner, 2026-10-23: "I tried adding credit card information in one of the cells and it was accepted, I just added the card
    number". A number typed into a cell is kept as a number, and Excel keeps 15 digits of it (4111111111111111 is stored as
    4111111111111110), so the check digit no longer fits and the card was not recognised. A whole number of 15 to 19 digits is a
    card (or something as unwanted); shorter numbers are counts, ids and phone numbers, as before."""
    def test_a_card_typed_as_a_number_is_a_card(self):
        for value in (4111111111111110, 4111111111111111, 5500000000000004, 378282246310005, 4.11111111111111e15):
            self.assertEqual(guard.kind_of(value), "card", value)

    def test_the_longest_numbers_too(self):
        self.assertEqual(guard.kind_of(6011000000000000004), "card")  # 19 digits

    def test_counts_ids_phone_numbers_and_measurements_are_not_cards(self):
        for value in (0.9, 12, 1234567890, 201001234567, 20100123456789, 1234.5, 2026.1014, True):
            self.assertIsNone(guard.kind_of(value), value)

    def test_a_card_after_a_colon_or_without_spaces_is_found_in_text(self):
        for text in ("Card:4111 1111 1111 1111", "Visa 4111111111111111", "4111-1111-1111-1111", "paid: 4111111111111111 ok"):
            self.assertEqual(guard.kind_of(text), "card", text)

    def test_times_dates_and_codes_in_text_are_still_not_cards(self):
        for text in ("2026-10-14 12:00:00", "Week 2026-10-11 to 2026-10-17", "ABC-12345678", "12:30 - 21:30"):
            self.assertIsNone(guard.kind_of(text), text)

    def test_a_workbook_with_the_number_in_a_cell_is_refused(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        found = guard.look(book(d / "w.xlsx", cells=[("Schedule", "C3", 4111111111111110)]))
        self.assertEqual(found[0], "personal")
        self.assertIn("card number", found[1])
        self.assertNotIn("4111", found[1])
