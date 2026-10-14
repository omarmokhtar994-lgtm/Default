# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AG, T1: the v4 look ("Shift desk", owner's blanket approval, 2026-10-14).

- Fonts are served by the site itself (Archivo for headings and figures, Atkinson Hyperlegible Next for text), with
  their licence; no page asks Google for anything, so the CSP allows this site only.
- Icons are Phosphor's shapes (MIT, with its licence) inside the site's own icons.css, drawn by the stylesheet: the
  menu's links keep their markup.
- The menu is grouped by job: Today, This week, Insights, then Setup for managers; the page labels stay.
"""
import re
import unittest
from pathlib import Path

from webapp.tests.test_runs import make_app, sign_in

STATIC = Path(__file__).resolve().parents[1] / "static"


class TheLook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")

    def test_no_page_asks_google(self):
        for url in ("/login", "/"):
            page = (self.admin if url == "/" else self.app.test_client()).get(url).get_data(as_text=True)
            self.assertNotIn("googleapis", page)
            self.assertNotIn("gstatic", page)

    def test_the_csp_allows_this_site_only(self):
        csp = self.app.test_client().get("/login").headers["Content-Security-Policy"]
        self.assertNotIn("https:", csp)
        self.assertIn("font-src 'self'", csp)
        self.assertIn("style-src 'self'", csp)

    def test_fonts_and_icons_are_served_with_their_licences(self):
        client = self.app.test_client()
        for path in ("/static/fonts/archivo.woff2", "/static/fonts/atkinson-hyperlegible-next.woff2",
                     "/static/fonts/OFL", "/static/icons.css", "/static/LICENSE-phosphor"):
            with self.subTest(path):
                self.assertEqual(client.get(path).status_code, 200)

    def test_the_stylesheet_uses_them(self):
        css = (STATIC / "app.css").read_text()
        self.assertRegex(css, r'@font-face\s*{[^}]*"Archivo"[^}]*fonts/archivo\.woff2')
        self.assertRegex(css, r'@font-face\s*{[^}]*"Atkinson Hyperlegible Next"[^}]*fonts/atkinson-hyperlegible-next\.woff2')
        self.assertNotIn("Saira", css)
        icons = (STATIC / "icons.css").read_text()
        self.assertIn("Phosphor", icons.splitlines()[0])
        self.assertRegex(icons, r'a\[href\^="/day"\]::before { --i: var\(--i-pulse\); }')  # the RTA's menu icon
        self.assertRegex(icons, r'--i-pulse: url\("data:image/svg\+xml,')
        self.assertIn('icons.css', self.admin.get("/").get_data(as_text=True))

    def test_the_menu_is_grouped_by_job(self):
        page = self.admin.get("/").get_data(as_text=True)
        side = page[page.index('class="leftnav"'):page.index("</aside>")]
        heads = re.findall(r'<p class="navhead">([^<]+)</p>', side)
        self.assertEqual(heads, ["Insights", "Setup"])  # no program picked: Today and This week need one
        self.assertIn('<a href="/" class="on" aria-current="page">Home</a>', side)  # the links keep their markup


if __name__ == "__main__":
    unittest.main()
