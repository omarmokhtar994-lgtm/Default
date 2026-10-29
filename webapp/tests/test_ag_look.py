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
                # AN followup: exhaust and close the streamed file response.
                self.assertEqual(client.get(path, buffered=True).status_code, 200)

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

    def test_hidden_boxes_stay_hidden(self):
        # Phase AG (T9): the timeline's hover box sets its own display, which beat the hidden attribute and left an
        # empty box in the page's top corner
        css = (STATIC / "app.css").read_text()
        self.assertRegex(css, r"\.tl-tip\[hidden\] { display: none; }")

    def test_the_menu_is_grouped_by_job(self):
        page = self.admin.get("/").get_data(as_text=True)
        side = page[page.index('class="leftnav"'):page.index("</aside>")]
        heads = re.findall(r'<p class="navhead">([^<]+)</p>', side)
        self.assertEqual(heads, ["Insights", "Setup"])  # no program picked: Today and This week need one
        self.assertIn('<a href="/" class="on" aria-current="page">Home</a>', side)  # the links keep their markup


class TheThreeLooks(unittest.TestCase):
    """Re-written in Phase BA (owner, 2026-10-25, samples in evidence/phase_az/prototype): the three looks are Tide (light),
    Night watch (dark, the default) and Drafting table (draft). It replaces the Phase AG trio (Graphite night, its day
    version and Deep ocean). The cookie values are light, dark and draft; an old "ocean" cookie is ignored. The status colours
    do not change."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)

    def block(self, selector):
        css = (STATIC / "app.css").read_text()
        start = css.index(selector + " {")
        return css[start:css.index("}", start)]

    def test_the_tokens(self):
        night = self.block(":root")
        self.assertIn("--night: #080F1E;", night)
        self.assertIn("--console: #0F1A31;", night)
        self.assertIn("color-scheme: dark;", night)
        self.assertIn("--night: #E8EFF6;", self.block(':root[data-theme="light"]'))
        draft = self.block(':root[data-theme="draft"]')
        self.assertIn("--night: #F1F3EE;", draft)  # the sheet; the field around it is --page-field
        self.assertIn("--hi: #D7F25A;", draft)  # the marker colour, which never means a status
        self.assertIn("color-scheme: light;", draft)
        for look in (':root[data-theme="light"]', ':root[data-theme="draft"]'):
            self.assertIn("--covered: #06A496;", self.block(look))  # the light looks share the measured status set

    def test_three_looks_are_offered_and_the_one_in_use_is_pressed(self):
        from webapp.tests.test_runs import token
        client = sign_in(self.app, "omar", "Owner-pass-123")
        page = client.get("/").get_data(as_text=True)
        for value, name in (("light", "Tide"), ("dark", "Night watch"), ("draft", "Drafting table")):
            self.assertIn(f'name="theme" value="{value}" data-look="{value}" aria-pressed="false">{name}</button>', page)
        got = client.post("/theme", data={"csrf_token": token(client), "theme": "draft", "next": "/"})
        self.assertIn("theme=draft", got.headers["Set-Cookie"])
        page = client.get("/").get_data(as_text=True)
        self.assertIn('<html lang="en" data-theme="draft">', page)
        self.assertIn('<meta name="theme-color" content="#1B2321">', page)
        self.assertIn('<meta name="color-scheme" content="light">', page)
        self.assertIn('value="draft" data-look="draft" aria-pressed="true">Drafting table</button>', page)
        self.assertIn('value="light" data-look="light" aria-pressed="false">Tide</button>', page)

    def test_an_old_ocean_cookie_is_ignored(self):
        client = sign_in(self.app, "omar", "Owner-pass-123")
        client.set_cookie("theme", "ocean")
        self.assertNotIn("data-theme=", client.get("/").get_data(as_text=True).split("<body", 1)[0].split("<html", 1)[1].split(">", 1)[0])


if __name__ == "__main__":
    unittest.main()
