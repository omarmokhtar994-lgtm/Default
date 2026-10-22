# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AX (owner, 2026-10-22: a download option for the charts and tables on Shrinkage and Incidents): each chart can
be saved as a picture (PNG) or as a drawing (SVG), each table as a CSV file Excel opens. Made-up "Associate NN" data."""
import csv
import io
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from webapp.tests import test_cancel_break as _cb

PNG = b"\x89PNG\r\n\x1a\n"


class TheDownloadsInTheBrowser(_cb._Cancel):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, executable_path="/opt/pw-browsers/chromium")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        super().tearDownClass()

    def open(self, path):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        self.addCleanup(page.close)
        page.goto(self.base + "/login")
        page.get_by_label("Username").fill("omar")
        page.get_by_label("Password").fill("Owner-pass-123")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_url(self.base + "/")
        page.goto(self.base + path)
        return page

    def shrinkage(self, extra="&by=day"):
        return f"/shrinkage?program={self.key.replace(' ', '+')}&from=2026-10-11&to=2026-10-15{extra}"

    def saved(self, page, name):
        with page.expect_download() as taken:
            page.get_by_role("button", name=name).first.click()
        return taken.value

    def test_a_table_downloads_as_csv_with_its_headings_and_a_byte_order_mark(self):
        page = self.open(self.shrinkage())
        got = self.saved(page, "Table as CSV")
        self.assertTrue(got.suggested_filename.endswith(".csv"), got.suggested_filename)
        self.assertTrue(got.suggested_filename.startswith("shrinkage"), got.suggested_filename)
        raw = open(got.path(), "rb").read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
        self.assertEqual(rows[0][0], "Day")
        self.assertGreater(len(rows), 2)
        self.assertEqual({len(r) for r in rows}, {len(rows[0])})

    def test_a_chart_downloads_as_a_png_picture(self):
        page = self.open(self.shrinkage())
        got = self.saved(page, "Chart as PNG")
        self.assertTrue(got.suggested_filename.endswith(".png"))
        data = open(got.path(), "rb").read()
        self.assertEqual(data[:8], PNG)
        import base64
        colours = page.evaluate("""async (b64) => {
            const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
            const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
            const x = c.getContext('2d'); x.drawImage(img, 0, 0);
            const d = x.getImageData(0, 0, c.width, c.height).data, seen = new Set();
            for (let i = 0; i < d.length; i += 4 * 97) { seen.add(d[i] + ',' + d[i + 1] + ',' + d[i + 2]); }
            return [img.width, img.height, seen.size];
        }""", base64.b64encode(data).decode())
        self.assertGreater(colours[0], 600)  # drawn at twice its size
        self.assertGreater(colours[2], 2)  # a background, a line and text: not one flat colour

    def test_a_chart_downloads_as_an_svg_drawing_that_keeps_its_look(self):
        page = self.open(self.shrinkage())
        got = self.saved(page, "Chart as SVG")
        text = open(got.path(), encoding="utf-8").read()
        self.assertTrue(text.startswith("<svg") or text.startswith("<?xml"))
        self.assertIn("xmlns=", text)
        self.assertRegex(text, r'stroke="rgb')  # the colours are written into the file, not left to the page's stylesheet

    def test_a_cell_with_a_comma_or_a_quote_stays_one_cell(self):
        page = self.open(self.shrinkage())
        page.evaluate("""() => { const c = document.querySelector('table th[scope=row]'); c.textContent = 'a, "b"'; }""")
        got = self.saved(page, "Table as CSV")
        text = open(got.path(), encoding="utf-8-sig").read()
        self.assertIn('"a, ""b"""', text)

    def test_the_weekday_grid_downloads_too(self):
        page = self.open(self.shrinkage("&by=interval&step=60"))
        self.assertGreaterEqual(page.get_by_role("button", name="Table as CSV").count(), 2)
        page.locator(".dl-row").first.scroll_into_view_if_needed()
        page.wait_for_timeout(700)  # the page-to-page crossfade
        out = Path(__file__).resolve().parents[2] / "evidence" / "phase_ax" / "screens"
        out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out / "shrinkage_downloads.png"))

    def test_the_incidents_page_has_the_buttons(self):
        page = self.open("/incidents?from=2026-10-11&to=2026-10-15")
        self.assertGreaterEqual(page.get_by_role("button", name="Chart as PNG").count(), 1)
        got = self.saved(page, "Chart as PNG")
        self.assertTrue(got.suggested_filename.startswith("incidents"), got.suggested_filename)


if __name__ == "__main__":
    unittest.main()
