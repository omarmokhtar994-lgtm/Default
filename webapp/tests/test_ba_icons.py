# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA, T1 (owner, 2026-10-25: "add any missing icon"): every link in the menu draws an icon, and the account
links in the top bar do too. Before this phase Shrinkage and Incidents drew a grey square because icons.css had no
rule for their addresses."""
import re
import unittest
from pathlib import Path

from webapp.tests.test_runs import make_app, sign_in

STATIC = Path(__file__).resolve().parents[1] / "static"


class EveryMenuLinkHasAnIcon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")
        cls.icons = (STATIC / "icons.css").read_text()

    def _menu_hrefs(self):
        page = self.admin.get("/").get_data(as_text=True)
        menu = page.split('<aside class="leftnav"', 1)[1].split("</aside>", 1)[0]
        navs = re.findall(r"<nav\b.*?</nav>", menu, re.S)  # the icon rules are for the links inside a nav, not the New schedule button
        return [h for n in navs for h in re.findall(r'<a [^>]*href="([^"]+)"', n)]

    def test_each_menu_address_has_a_rule(self):
        rules = re.findall(r'\.leftnav nav a\[href([\^]?)="([^"]*)"\]::before', self.icons)
        missing = []
        for href in self._menu_hrefs():
            path = href.split("?")[0]
            if not any((path.startswith(v) if op else path == v) for op, v in rules):
                missing.append(path)
        self.assertEqual(missing, [], "menu links with no icon")

    def test_the_new_shapes_are_plain(self):
        for name in ("chart-pie-slice", "warning-circle", "palette"):
            with self.subTest(name):
                self.assertRegex(self.icons, rf'--i-{name}: url\("data:image/svg\+xml,%3Csvg')
        self.assertNotIn("<script", self.icons)

    def test_the_account_links_in_the_top_bar_have_icons(self):
        page = self.admin.get("/").get_data(as_text=True)
        top = page.split('<div class="account">', 1)[1].split("</header>", 1)[0]
        for name in ("gear", "sign-out", "palette"):
            self.assertIn(f"ico i-{name}", top, name)
        self.assertIn('aria-hidden="true"', top)


if __name__ == "__main__":
    unittest.main()
