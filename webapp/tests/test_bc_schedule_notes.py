# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC (owner, 2026-10-26: "in schedule if something is written very big such as the warning for the 29th should be wrapped not to make that
day very long"): in the Shifts table a clock-change warning is a short label under the time, and its full words are said once under the table."""
import unittest

from webapp.tests.test_runs import client_for, make_app, versioned_run, REPO


class TheClockChangeWarning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.client = client_for(cls.app)
        cls.run_id = versioned_run(cls.app, cls.store, cls.client, program="AE/AR B2B", week_start="2026-10-25")
        cls.client.post("/login", data={"username": "omar", "password": "Owner-pass-123"})

    def page(self, zone):
        got = self.client.get(f"/runs/{self.run_id}/schedules?tz={zone}")
        self.assertEqual(got.status_code, 200)
        return got.get_data(as_text=True)

    def test_a_cell_says_clocks_change_in_two_words_and_keeps_the_full_words_in_its_tip(self):
        page = self.page("Africa/Cairo")
        self.assertIn('<span class="ed-warn" title="29 Oct 2026 23:00 occurs twice in Africa/Cairo because the clocks change.', page)
        self.assertIn(">Clocks change</span>", page)
        self.assertNotIn("(invalid source clock time", page)  # the long sentence is not inside a cell any more

    def test_the_full_words_are_said_once_under_the_table_however_many_cells_have_it(self):
        page = self.page("Africa/Cairo")
        self.assertGreaterEqual(page.count('class="ed-warn"'), 2)
        self.assertEqual(page.count("<b>Clocks change:</b>"), 1)
        self.assertIn("The workbook does not identify the occurrence; use the original-zone workbook.</p>", page)

    def test_a_week_without_the_change_has_no_note(self):
        quiet = versioned_run(self.app, self.store, self.client, program="AE/AR B2B", week_start="2026-10-11")
        got = self.client.get(f"/runs/{quiet}/schedules").get_data(as_text=True)
        self.assertNotIn("ed-warn", got)
        self.assertNotIn("Clocks change:", got)


if __name__ == "__main__":
    unittest.main()
