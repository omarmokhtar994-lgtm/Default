# © 2026 Omar Mokhtar. All rights reserved.
"""Phase I task 3: the website in a real browser (Playwright + Chromium).

Skips with a clear message where Playwright or Chromium is missing (the
server needs neither). Screenshots go to evidence/phase_i/screens/."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from werkzeug.serving import make_server

from webapp.tests.test_runs import make_app

SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_i" / "screens"
CHROMIUM = "/opt/pw-browsers/chromium"

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover - depends on the machine
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class InTheBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, cls.data, _ = make_app()
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        try:
            cls.browser = cls.pw.chromium.launch(**launch)
        except Exception as exc:  # pragma: no cover
            cls.pw.stop()
            cls.server.shutdown()
            raise unittest.SkipTest(f"Chromium could not start: {exc}")
        SCREENS.mkdir(parents=True, exist_ok=True)
        workbook = Path(tempfile.mkdtemp()) / "week42_NMG.xlsx"
        workbook.write_bytes(b"PK\x03\x04 fake workbook")
        cls.workbook = workbook

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def page(self, width=1280, height=860):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        return page

    def sign_in(self, page, username="omar", password="Owner-pass-123"):
        page.goto(self.base + "/login")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_url(self.base + "/")

    def test_login_page_renders_with_copyright(self):
        page = self.page()
        page.goto(self.base + "/login")
        expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
        expect(page.locator("footer")).to_contain_text("© 2026 Omar Mokhtar. All rights reserved.")
        expect(page.locator(".week")).to_be_visible()  # the week of shift bars
        page.screenshot(path=str(SCREENS / "01_login.png"), full_page=True)

    def test_dashboard_upload_run_flow(self):
        page = self.page()
        self.sign_in(page)
        page.screenshot(path=str(SCREENS / "02_dashboard_empty.png"), full_page=True)
        page.locator("input[type=file]").set_input_files(str(self.workbook))
        page.get_by_label("Quick").check()
        page.get_by_role("button", name="Check and run").click()
        page.wait_for_url(self.base + "/runs/*")
        expect(page.locator(".stagebar")).to_be_visible()
        # The page follows the run by itself, without a reload, until it ends.
        expect(page.locator(".status-word")).to_have_text("Approved", timeout=20000)
        expect(page.get_by_role("link", name="Download the schedule")).to_be_visible()
        expect(page.get_by_role("link", name="Download all results")).to_be_visible()
        page.screenshot(path=str(SCREENS / "03_run_approved.png"), full_page=True)
        page.goto(self.base + "/")
        expect(page.locator(".runs .stagebar").first).to_be_visible()
        page.screenshot(path=str(SCREENS / "04_dashboard_with_runs.png"), full_page=True)

    def test_run_page_follows_a_run_without_reloading(self):
        page = self.page()
        self.sign_in(page)
        slow = self.workbook.with_name("SLOW_week43.xlsx")
        slow.write_bytes(b"PK\x03\x04 slow")
        page.locator("input[type=file]").set_input_files(str(slow))
        page.get_by_role("button", name="Check and run").click()
        page.wait_for_url(self.base + "/runs/*")
        expect(page.locator(".status-word")).to_have_text("Running", timeout=15000)
        expect(page.locator(".stagebar li.active")).to_have_count(1)
        page.screenshot(path=str(SCREENS / "09_run_in_progress.png"), full_page=True)
        expect(page.locator(".status-word")).to_have_text("Approved", timeout=20000)

    def test_rejected_workbook_says_what_to_fix(self):
        page = self.page()
        self.sign_in(page)
        bad = self.workbook.with_name("bad_week.xlsx")
        bad.write_bytes(b"PK\x03\x04 bad")
        page.locator("input[type=file]").set_input_files(str(bad))
        page.get_by_role("button", name="Check and run").click()
        expect(page.locator(".status-word")).to_have_text("Rejected")
        expect(page.locator(".message")).to_contain_text("Schedule!C7: unknown associate 'Zed'")
        page.screenshot(path=str(SCREENS / "05_run_rejected.png"), full_page=True)

    def test_mobile_width_has_no_horizontal_scroll(self):
        page = self.page(width=390, height=844)
        page.goto(self.base + "/login")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        page.screenshot(path=str(SCREENS / "06_login_mobile.png"), full_page=True)
        self.sign_in(page)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        page.screenshot(path=str(SCREENS / "07_dashboard_mobile.png"), full_page=True)

    def test_keyboard_focus_visible(self):
        page = self.page()
        page.goto(self.base + "/login")
        page.get_by_label("Username").focus()
        outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
        width = page.evaluate("parseFloat(getComputedStyle(document.activeElement).outlineWidth)")
        self.assertNotEqual(outline, "none")
        self.assertGreaterEqual(width, 2)

    def test_admin_people_page(self):
        page = self.page()
        self.sign_in(page)
        page.get_by_role("link", name="People").click()
        expect(page.get_by_role("heading", name="People")).to_be_visible()
        page.screenshot(path=str(SCREENS / "08_people.png"), full_page=True)


if __name__ == "__main__":
    unittest.main()
