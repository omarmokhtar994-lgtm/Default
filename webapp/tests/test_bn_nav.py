# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BN (owner, 2026-11-12: "the three nav items built"; sample in evidence/phase_bn/nav): the menu's link to the people's accounts reads
Accounts (the group it sits in is People), the top bar keeps one account menu (the name opens Settings and Sign out), and the long pages People,
Weeks and Schedules start with a row of links to their own sections. No URL changes. Made-up people."""
import html
import re
import unittest

from webapp.tests.test_runs import client_for, make_app, seed_week, sign_in


class TheNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        seed_week(cls.store, "NMG", "2026-10-11")
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")

    def page(self, url):
        got = self.admin.get(url)
        self.assertEqual(got.status_code, 200, url)
        return html.unescape(got.get_data(as_text=True))

    def test_the_menu_link_to_the_accounts_reads_accounts(self):
        side = self.page("/").split('class="leftnav"', 1)[1].split("</aside>", 1)[0]
        self.assertRegex(side, r'<p class="navhead">People</p>(?s:.*?)<a href="/admin/users"[^>]*>Accounts</a>')
        self.assertNotIn(">People</a>", side)

    def test_the_accounts_link_is_marked_on_its_page(self):
        side = self.page("/admin/users").split('class="leftnav"', 1)[1].split("</aside>", 1)[0]
        self.assertIn('<a href="/admin/users" class="on" aria-current="page">Accounts</a>', side)

    def test_the_top_bar_has_one_account_menu(self):
        top = self.page("/").split('<header class="top">', 1)[1].split("</header>", 1)[0]
        menu = re.search(r'<details class="acct" data-acct>\s*<summary>(.*?)</summary>(.*?)</details>', top, re.S)
        self.assertIsNotNone(menu)
        self.assertIn("Omar, admin", menu.group(1))
        self.assertIn(">Settings</a>", menu.group(2))
        self.assertRegex(menu.group(2), r'<form method="post" action="/logout">(?s:.*?)Sign out</button>')
        outside = top.replace(menu.group(0), "")
        self.assertNotIn("Sign out", outside)
        self.assertIn('aria-label="Look"', outside)  # the look stays one click away

    def test_the_long_pages_have_a_place_for_the_links_to_their_sections(self):
        # the links are made in the browser from the headings really on the page (sections come and go with the data), so a link never
        # points at nothing; test_ui_playwright (the phone class) checks the links themselves
        for url in ("/admin/users", "/week?program=NMG&week=2026-10-11"):
            got = self.admin.get(url, follow_redirects=True)
            self.assertEqual(got.status_code, 200, url)
            self.assertEqual(got.get_data(as_text=True).count('<nav class="jump" aria-label="On this page" data-jump hidden></nav>'), 1, url)
        from pathlib import Path  # Schedules needs a finished run to draw; its template carries the same one place
        source = (Path(__file__).resolve().parents[1] / "templates" / "schedules.html").read_text()
        self.assertEqual(source.count('<nav class="jump" aria-label="On this page" data-jump hidden></nav>'), 1)
        self.assertNotIn("data-jump", self.page("/"))

if __name__ == "__main__":
    unittest.main()
