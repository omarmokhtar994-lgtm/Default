# © 2026 Omar Mokhtar. All rights reserved.
"""Phase I task 3: the website in a real browser (Playwright + Chromium).

Skips with a clear message where Playwright or Chromium is missing (the
server needs neither). Screenshots go to evidence/phase_i/screens/."""
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from werkzeug.serving import make_server

from webapp.tests.test_runs import make_app, seed_week

# Phase J (owner-approved control-room redesign): screenshots of the new look.
SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_j" / "screens"
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

    def page(self, width=1280, height=860, scheme="dark"):
        # Phase L: the site follows the device's light or dark setting until the
        # person picks one; headless Chromium reports "light", so say which.
        page = self.browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme)
        self.addCleanup(page.close)
        return page

    def sign_in(self, page, username="omar", password="Owner-pass-123"):
        page.goto(self.base + "/login")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_url(self.base + "/")
        page.wait_for_timeout(600)  # let the page-to-page crossfade finish before any screenshot

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
        # Re-pinned in Phase J: the owner-approved redesign shows the run's stages as a ring
        # on the run page (the thin bar stays in the runs list, checked below).
        expect(page.locator(".progress .ring")).to_be_visible()
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
        expect(page.locator(".ring .arc.active")).to_have_count(1)  # Phase J: ring replaces the run-page bar
        page.screenshot(path=str(SCREENS / "09_run_in_progress.png"), full_page=True)
        expect(page.locator(".status-word")).to_have_text("Approved", timeout=20000)

    def test_run_page_shows_the_week_wall(self):
        page = self.page(height=1100)
        self.sign_in(page)
        real = self.workbook.with_name("REAL_week42.xlsx")
        real.write_bytes(b"PK\x03\x04 real")
        page.locator("input[type=file]").set_input_files(str(real))
        page.get_by_role("button", name="Check and run").click()
        expect(page.locator(".status-word")).to_have_text("Approved", timeout=20000)
        expect(page.locator(".grid.after .cell")).to_have_count(126)
        expect(page.locator(".grid.before")).to_be_hidden()
        page.get_by_text("Before breaks", exact=True).click()
        expect(page.locator(".grid.before")).to_be_visible()
        page.get_by_text("After breaks (published)").click()
        expect(page.get_by_role("heading", name="Headcount suggestions")).to_be_visible()
        page.wait_for_timeout(800)  # let the wall's one-time fade-in finish before the screenshot
        page.screenshot(path=str(SCREENS / "10_run_wall_and_headcount.png"), full_page=True)
        page.goto(self.base + "/")
        expect(page.locator(".latest .grid .cell")).to_have_count(126)
        page.mouse.move(0, 0)
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENS / "11_dashboard_latest_wall.png"), full_page=True)

    def test_light_theme_run_page(self):
        """Phase L: the light look, chosen with the switch in the header."""
        page = self.page(height=1100)
        self.sign_in(page)
        page.get_by_role("button", name="Light look").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        real = self.workbook.with_name("REAL_light.xlsx")
        real.write_bytes(b"PK\x03\x04 real")
        page.locator("input[type=file]").set_input_files(str(real))
        page.get_by_role("button", name="Check and run").click()
        expect(page.locator(".status-word")).to_have_text("Approved", timeout=20000)
        expect(page.locator(".grid.after .cell")).to_have_count(126)
        background = page.evaluate("getComputedStyle(document.body).backgroundColor")
        self.assertEqual(background, "rgb(234, 239, 245)")
        page.wait_for_timeout(800)
        L_SCREENS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(L_SCREENS / "light_run_page.png"), full_page=True)
        page.goto(self.base + "/")
        page.mouse.move(0, 0)
        page.wait_for_timeout(800)
        page.screenshot(path=str(L_SCREENS / "light_home.png"), full_page=True)
        page.get_by_role("button", name="Dark look").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    def drop(self, page, name, data=b"PK\x03\x04 dropped"):
        """Drop a file on the upload area the way a browser does (DataTransfer)."""
        handle = page.evaluate_handle(
            """([name, bytes]) => { const t = new DataTransfer();
                 t.items.add(new File([new Uint8Array(bytes)], name)); return t; }""", [name, list(data)])
        for kind in ("dragenter", "dragover", "drop"):
            page.dispatch_event("[data-drop]", kind, {"dataTransfer": handle})

    def test_drop_a_workbook_onto_the_upload_area(self):
        page = self.page()
        self.sign_in(page)
        self.drop(page, "REAL_dropped.xlsx")
        expect(page.locator("[data-drop] .chosen")).to_have_text("REAL_dropped.xlsx")
        self.assertEqual(page.evaluate("document.querySelector('input[type=file]').files[0].name"), "REAL_dropped.xlsx")
        L_SCREENS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(L_SCREENS / "home_dropped_file.png"))
        page.get_by_role("button", name="Check and run").click()
        expect(page.locator("h1")).to_have_text("REAL_dropped.xlsx")

    def test_drop_rejects_other_files(self):
        page = self.page()
        self.sign_in(page)
        self.drop(page, "REAL_first.xlsx")
        self.drop(page, "notes.pdf")
        expect(page.locator("[data-drop] .chosen")).to_contain_text("notes.pdf is not an Excel workbook")
        self.assertEqual(page.evaluate("document.querySelector('input[type=file]').files[0].name"), "REAL_first.xlsx")

    def upload_as(self, page, name, mode="Quick"):
        page.goto(self.base + "/")
        path = self.workbook.with_name(name)
        path.write_bytes(b"PK\x03\x04 fake")
        page.locator("input[type=file]").set_input_files(str(path))
        page.get_by_label(mode, exact=False).first.check()
        page.get_by_role("button", name="Check and run").click()

    def test_failed_run_says_why_and_what_to_change(self):
        page = self.page(height=1000)
        self.sign_in(page)
        self.upload_as(page, "CONFLICT_English.xlsx")
        expect(page.locator(".status-word")).to_have_text("Can't be scheduled", timeout=20000)
        expect(page.get_by_role("heading", name="What to change in the input workbook")).to_be_visible()
        page.mouse.move(0, 0)
        page.wait_for_timeout(600)
        L_SCREENS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(L_SCREENS / "failed_run_fix_list.png"), full_page=True)
        page.get_by_role("link", name="Upload the corrected workbook").click()
        expect(page.locator("#newrun")).to_be_visible()

    def test_ready_check_starts_the_real_run(self):
        page = self.page(height=900)
        self.sign_in(page)
        self.upload_as(page, "READY_Spanish.xlsx", mode="Readiness check")
        expect(page.locator(".status-word")).to_have_text("Ready to run", timeout=20000)
        expect(page.get_by_role("button", name="Resume")).to_have_count(0)
        page.mouse.move(0, 0)
        page.wait_for_timeout(600)
        page.screenshot(path=str(L_SCREENS / "ready_check_start.png"), full_page=True)
        page.get_by_label("Deep").check()
        page.get_by_role("button", name="Start the run").click()
        expect(page.locator(".byline").first).to_contain_text("Deep run")
        page.get_by_role("link", name="‹ Back").click()
        expect(page.locator(".status-word")).to_have_text("Ready to run")

    def test_advanced_options_fold(self):
        page = self.page()
        self.sign_in(page)
        expect(page.get_by_label("Language working window")).to_be_hidden()
        page.get_by_text("Advanced options").click()
        expect(page.get_by_label("Language working window")).to_be_visible()
        page.screenshot(path=str(SCREENS / "12_advanced_options.png"), full_page=True)

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


# Phase K: the program history pages. Own app, so these weeks stay off the
# Phase J screenshots. The weeks are the real Phase I run's figures varied
# per week (test data; the page draws whatever the runs stored).
K_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_k" / "screens"
L_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_l" / "screens"
HISTORY = [  # week, associates, after, before, at 90%, efficiency, over h, under h, hours, short cells
    ("2026-08-09", 9, 96, 118, 110, 66, 61.0, 6.5, 360, ["Tue 20:30", "Thu 20:30", "Sat 14:00", "Mon 20:30"]),
    ("2026-08-16", 9, 99, 120, 112, 68, 58.5, 5.0, 360, ["Tue 20:30", "Thu 21:00", "Mon 20:30"]),
    ("2026-08-23", 8, 97, 119, 113, 71, 49.0, 5.5, 320, ["Tue 20:30", "Thu 20:30", "Fri 09:00"]),
    ("2026-08-30", 8, 101, 121, 115, 72, 47.5, 4.5, 320, ["Tue 20:30", "Thu 20:30"]),
    ("2026-09-06", 8, 103, 122, 117, 73, 46.0, 4.0, 320, ["Tue 21:00", "Thu 20:30", "Mon 20:30"]),
    ("2026-09-13", 8, 100, 123, 116, 72, 47.0, 4.5, 320, ["Tue 20:30", "Wed 13:00"]),
    ("2026-09-20", 8, 104, 124, 118, 74, 44.5, 3.5, 320, ["Tue 20:30", "Thu 20:30", "Mon 20:30"]),
    ("2026-09-27", 8, 102, 125, 119, 74, 44.0, 3.5, 320, ["Tue 20:30", "Thu 21:00"]),
    ("2026-10-04", 8, 105, 125, 120, 75, 43.0, 3.0, 320, ["Tue 20:30", "Thu 20:30", "Mon 20:30"]),
]


def seed_history(store):
    for week, people, after, before, at90, eff, over, under, hours, cells in HISTORY:
        seed_week(store, "NMG Spanish", week, associates=people, fully_covered=after, before_full=before, at_90=at90,
                  efficiency={"pct": eff, "over_hours": over, "under_hours": under}, productive_hours=hours,
                  slack_hours=hours - 207.4, short_cells=cells)
    seed_week(store, "NMG Spanish", "2026-10-11", outcome="REVIEW")  # the real run's own figures: 7 people, 107 of 126
    seed_week(store, "AE/AR B2B", "2026-10-04", associates=14, fully_covered=118, before_full=126)
    seed_week(store, "AE/AR B2B", "2026-10-11", associates=15, fully_covered=121, before_full=126)


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class TheProgramPagesInTheBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, _, _ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        seed_history(cls.store)
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
        K_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in

    def test_program_analytics_page(self):
        page = self.page(height=900)
        self.sign_in(page)
        page.get_by_role("link", name="Programs").click()
        expect(page.get_by_role("heading", name="Programs")).to_be_visible()
        page.wait_for_timeout(600)  # the page-to-page crossfade
        page.screenshot(path=str(K_SCREENS / "01_programs.png"), full_page=True)
        page.get_by_role("link", name="NMG Spanish").click()
        expect(page.get_by_role("heading", name="What happened")).to_be_visible()
        page.wait_for_timeout(600)
        expect(page.get_by_text("Associates: 7 this week, down 1 from 8 in the week of 04 Oct.")).to_be_visible()
        bar = page.locator("section[aria-labelledby=c-people] rect.hit").last
        bar.hover()
        expect(page.locator(".tip")).to_have_text("11 Oct: 7 associates (down 1)")
        page.screenshot(path=str(K_SCREENS / "06_chart_tip.png"))
        page.mouse.move(1, 1)
        page.evaluate("window.scrollTo(0, 0)")  # the sticky header would otherwise sit mid-page in a full-page shot
        page.screenshot(path=str(K_SCREENS / "02_program_history.png"), full_page=True)
        page.locator("section[aria-labelledby=c-cover] summary").click()
        expect(page.locator("section[aria-labelledby=c-cover] table")).to_be_visible()

    def test_light_theme_pages(self):
        page = self.page(height=900)
        page.context.add_cookies([{"name": "theme", "value": "light", "url": self.base}])
        self.sign_in(page)
        L_SCREENS.mkdir(parents=True, exist_ok=True)
        page.goto(self.base + "/programs/NMG%20Spanish")
        expect(page.get_by_role("heading", name="What happened")).to_be_visible()
        fill = page.evaluate("getComputedStyle(document.querySelector('.chart rect.bar')).fill")
        self.assertEqual(fill, "rgb(42, 120, 214)")  # the light step of the blue series
        page.wait_for_timeout(600)
        page.screenshot(path=str(L_SCREENS / "light_program_history.png"), full_page=True)
        page.goto(self.base + "/programs")
        page.wait_for_timeout(600)
        page.screenshot(path=str(L_SCREENS / "light_programs.png"), full_page=True)
        page.goto(self.base + "/login")

    def test_program_page_on_a_phone(self):
        page = self.page(width=390, height=844)
        self.sign_in(page)
        page.goto(self.base + "/programs/NMG%20Spanish")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        page.screenshot(path=str(K_SCREENS / "03_program_phone.png"), full_page=True)

    def test_team_page_and_upload_fields(self):
        page = self.page()
        self.sign_in(page)
        expect(page.get_by_label("Program")).to_be_visible()
        expect(page.get_by_label("Schedule week")).to_have_value(re.compile(r"\d{4}-\d{2}-\d{2}"))
        page.screenshot(path=str(K_SCREENS / "04_new_run_with_program.png"))
        page.get_by_role("link", name="Team", exact=True).click()
        expect(page.get_by_role("heading", name="Team", exact=True)).to_be_visible()
        page.wait_for_timeout(600)
        page.screenshot(path=str(K_SCREENS / "05_team.png"), full_page=True)


if __name__ == "__main__":
    unittest.main()
