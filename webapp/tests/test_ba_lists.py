# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA, T3 (owner, 2026-10-25): one rule for long content. Tables and grids people scan or compare scroll inside their own
panel (class panel-scroll, labelled, keyboard reachable); lists that grow over time and are read one by one are pages of 20."""
import re
import unittest
from pathlib import Path

from webapp.tests.test_runs import make_app, sign_in

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
# the tables and grids that are scanned or compared, with the label each panel carries
SCROLL_PANELS = {
    "week.html": ["Achieved every", "Where overtime is needed", "Extra hours available"],
    "day.html": ["By person, lowest first", "Actual shrinkage against your input", "Who is on which channel", "Channels by interval"],
    "coach.html": ["Actual against planned, per weekday"],
    "roles.html": ["What each role may do"],
    "channel_setup.html": ["Who can work which channel"],
    "channels.html": ["Who is on what"],
    "run.html": ["Who and when"],
    "schedules.html": ["Shifts", "Changes in this version"],
    "admin_users_bulk.html": ["People added", "The rows of your file"],
}


class LongTablesScrollInsideAPanel(unittest.TestCase):
    def test_each_long_table_sits_in_a_labelled_scroll_panel(self):
        problems = []
        for name, labels in SCROLL_PANELS.items():
            text = (TEMPLATES / name).read_text()
            for label in labels:
                box = re.search(r'<div class="scroll panel-scroll[^"]*" role="region" tabindex="0" aria-label="' + re.escape(label) + r'[^"]* \(scrolls\)"', text)
                if not box:
                    problems.append(f"{name}: {label}")
        self.assertEqual(problems, [])

    def test_the_panel_has_a_height_a_fixed_header_and_prints_in_full(self):
        css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text()
        self.assertRegex(css, r"\.scroll\.panel-scroll[^{]*\{[^}]*max-height: min\(30rem, 64dvh\)[^}]*overflow: auto")
        self.assertRegex(css, r"\.scroll\.panel-scroll thead th[^{]*\{[^}]*position: sticky; top: 0")
        self.assertRegex(css, r"@media print \{ \.scroll\.panel-scroll[^{]*\{ max-height: none; overflow: visible; \} \}")


class PeopleArePages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        for n in range(1, 46):
            cls.store.add_user(f"associate{n:02d}", f"Associate {n:02d}", "Owner-pass-123", must_change=False)
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.total = len(cls.store.list_users())

    def rows(self, page):
        return re.findall(r"<tr>\s*<td><b>([^<]+)</b>", page)

    def test_the_first_page_has_twenty_people_and_a_pager(self):
        page = self.admin.get("/admin/users").get_data(as_text=True)
        self.assertEqual(len(self.rows(page)), 20)
        self.assertIn('aria-label="People, pages"', page)
        self.assertIn(f"1 to 20 of {self.total}", page)

    def test_the_last_page_has_the_rest(self):
        page = self.admin.get("/admin/users?people_page=3").get_data(as_text=True)
        rest = self.total - 40
        self.assertEqual(len(self.rows(page)), rest)
        self.assertIn(f"41 to {self.total} of {self.total}", page)

    def test_a_page_past_the_end_shows_the_last(self):
        page = self.admin.get("/admin/users?people_page=99").get_data(as_text=True)
        self.assertEqual(len(self.rows(page)), self.total - 40)

    def test_few_people_show_no_pager(self):
        app, store, *_ = make_app(start_worker=False)
        store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        page = sign_in(app, "omar", "Owner-pass-123").get("/admin/users").get_data(as_text=True)
        self.assertNotIn("People, pages", page)


if __name__ == "__main__":
    unittest.main()
