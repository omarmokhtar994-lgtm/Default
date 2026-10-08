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

from webapp.tests.test_runs import REPO, make_app, seed_week, versioned_run

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
M_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_m" / "screens"
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

    def test_week_view_page(self):
        page = self.page(height=900)
        self.sign_in(page)
        page.get_by_role("link", name="Weeks", exact=True).click()
        expect(page.locator("h1")).to_contain_text(", week of 11 Oct")
        page.wait_for_load_state("load")  # the picker's script runs after the heading is on screen
        page.select_option("select[name=program]", "NMG Spanish")
        expect(page.locator("h1")).to_have_text("NMG Spanish, week of 11 Oct")
        expect(page.get_by_role("heading", name="Where overtime is needed")).to_be_visible()
        page.locator("td.wk.short").first.hover()
        expect(page.locator(".tip")).to_contain_text("needed for 100%")
        M_SCREENS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(M_SCREENS / "week_view_tip.png"))
        page.mouse.move(1, 1)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        page.screenshot(path=str(M_SCREENS / "week_view.png"), full_page=True)
        page.get_by_role("link", name="Before breaks").click()
        expect(page.locator(".tile b").first).to_have_text("125 of 126")
        phone = self.page(width=390, height=844)
        self.sign_in(phone)
        phone.goto(self.base + "/week?program=NMG%20Spanish&week=2026-10-11")
        self.assertLessEqual(phone.evaluate("document.documentElement.scrollWidth"), 390)
        phone.screenshot(path=str(M_SCREENS / "week_view_phone.png"), full_page=True)

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
        # Re-pinned in Phase P (owner, 2026-10-08): "Schedule week" became the "Schedule starts" dropdown;
        # its value is still the chosen date.
        expect(page.get_by_label("Schedule starts")).to_have_value(re.compile(r"\d{4}-\d{2}-\d{2}"))
        page.screenshot(path=str(K_SCREENS / "04_new_run_with_program.png"))
        page.get_by_role("link", name="Team", exact=True).click()
        expect(page.get_by_role("heading", name="Team", exact=True)).to_be_visible()
        page.wait_for_timeout(600)
        page.screenshot(path=str(K_SCREENS / "05_team.png"), full_page=True)


N_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_n" / "screens"


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class TheSchedulesInTheBrowser(unittest.TestCase):
    """Phase N: edit a shift, see the warning, keep it, see the marks."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        from webapp.tests.test_runs import client_for
        cls.run_id = versioned_run(cls.app, cls.store, client_for(cls.app), program="AE/AR B2B", week_start="2026-10-11")
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        N_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in

    def test_edit_with_warning_and_marks(self):
        page = self.page(width=1440, height=950)
        self.sign_in(page)
        page.goto(f"{self.base}/runs/{self.run_id}/schedules")
        page.wait_for_load_state("load")
        page.locator('button.ed[data-name="Associate 001"][data-day="Wed"]').click()
        page.select_option("#edit-dialog select[name=value]", "21:00 - 06:00")
        expect(page.locator("#dlg-h")).to_have_text("This change breaks 2 rules", timeout=30000)
        expect(page.locator("#edit-dialog .sevlist li")).to_have_count(3)
        page.screenshot(path=str(N_SCREENS / "edit_warning.png"))
        page.get_by_role("button", name="Yes, keep it").click()
        expect(page.locator("#edit-dialog input[name=reason]")).to_have_attribute("aria-invalid", "true")
        page.fill("#edit-dialog input[name=reason]", "Swap requested by the associate")
        page.get_by_role("button", name="Yes, keep it").click()
        page.wait_for_url("**/schedules?v=*", timeout=30000)
        cell = page.locator('button.ed[data-name="Associate 001"][data-day="Wed"]')
        expect(cell).to_have_class("ed changed sev-red")
        expect(page.locator(".vbar a.cur")).to_contain_text("Version 2")
        page.mouse.move(1, 1)
        page.wait_for_timeout(500)
        page.screenshot(path=str(N_SCREENS / "edit_marked.png"), full_page=True)

    def test_a_change_without_problems_needs_no_reason(self):
        page = self.page(width=1440, height=950)
        self.sign_in(page)
        page.goto(f"{self.base}/runs/{self.run_id}/schedules")
        page.wait_for_load_state("load")
        page.locator('button.ed[data-name="Associate 002"][data-day="Mon"]').click()
        page.select_option("#edit-dialog select[name=value]", "09:00 - 18:00")
        expect(page.locator("#dlg-h")).to_contain_text("This change", timeout=30000)
        page.get_by_role("button", name="No, undo it").click()
        expect(page.locator("#edit-dialog")).not_to_be_visible()


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class TheDayInTheBrowser(unittest.TestCase):
    """Phase N task 4: the day page: attendance, moving a break with its warning, the board, slot swaps."""

    setUpClass = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    url = "/day?program=AE/AR+B2B&date=2026-10-14"

    def test_day_page(self):
        page = self.page(width=1500, height=1000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        page.goto(self.base + self.url)
        page.wait_for_load_state("load")
        expect(page.locator("h1")).to_have_text("AE/AR B2B, Wednesday 14 Oct: the day")
        # attendance: unplanned leave counts at once; a late login asks for the arrival time
        page.select_option('select.att[data-name="Associate 013"]', "Unplanned leave")
        expect(page.locator(".log")).to_contain_text("Associate 013, Unplanned leave", timeout=15000)  # reloaded
        page.wait_for_load_state("load")  # the reloaded page's script is attached
        page.select_option('select.att[data-name="Associate 001"]', "Late")
        expect(page.locator("#att-dialog")).to_be_visible()
        page.fill("#att-dialog input[name=to]", "13:00")
        page.locator("#att-dialog [data-keep]").click()
        expect(page.locator(".log")).to_contain_text("Associate 001, Late, arrived 13:00", timeout=15000)
        page.wait_for_load_state("load")  # the reloaded page's script is attached
        expect(page.locator('select.att[data-name="Associate 001"]')).to_have_value("Late")
        page.select_option('select.att[data-name="Associate 012"]', "Coaching|1")
        page.fill("#att-dialog input[name=from]", "10:00")
        page.fill("#att-dialog input[name=to]", "11:00")
        page.locator("#att-dialog [data-keep]").click()
        expect(page.locator(".log")).to_contain_text("Coaching (billable) 10:00 to 11:00", timeout=15000)
        expect(page.locator('select.att[data-name="Associate 012"]')).to_have_value("Coaching|1")
        page.wait_for_load_state("load")  # the reloaded page's script is attached
        # a break: Enter opens the dialog; a time too close to Break 1 warns before it is kept
        lunch = page.locator('rect.brk[data-name="Associate 008"][data-idx="1"]')
        lunch.focus()
        page.keyboard.press("Enter")
        expect(page.locator("#break-dialog")).to_be_visible()
        page.fill("#break-dialog input[name=at]", "10:30")  # Break 1 ends 10:00: 30 minutes apart
        page.locator("#break-dialog input[name=at]").dispatch_event("change")
        expect(page.locator("#break-dialog .sevlist li").first).to_contain_text("minimum gap between breaks", timeout=15000)
        expect(page.locator("#break-dialog .fits li").first).to_be_visible()
        page.screenshot(path=str(N_SCREENS / "day_break_warning.png"))
        page.locator("#break-dialog [data-keep]").click()
        expect(page.locator('rect.brk.moved[data-name="Associate 008"]')).to_have_count(1, timeout=15000)
        page.wait_for_load_state("load")  # the reloaded page's script is attached
        page.mouse.move(1, 1)
        page.evaluate("window.scrollTo(0, 0)")  # the fixed header stays at the top of a full-page shot
        page.screenshot(path=str(N_SCREENS / "day_timeline.png"), full_page=True)
        # dragging a break on the timeline opens the same dialog with the new time
        other = page.locator('rect.brk[data-name="Associate 021"][data-idx="2"]')
        other.scroll_into_view_if_needed()  # below the fold since Phase O added the tabs and the autopilot button
        box = other.bounding_box()
        page.mouse.move(box["x"] + 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + 40, box["y"] + box["height"] / 2, steps=5)
        page.mouse.up()
        expect(page.locator("#break-dialog")).to_be_visible()
        self.assertNotEqual(page.locator("#break-dialog input[name=at]").input_value(), "15:30")
        page.locator("#break-dialog [data-cancel]").click()
        # the interval board, in service-level terms
        page.goto(self.base + self.url + "&view=board&measure=sl")
        page.wait_for_load_state("load")
        expect(page.locator(".rb-row.rb-head")).to_contain_text("Buffer (h:mm)")
        expect(page.locator('button.chip.moved[data-name="Associate 008"]')).to_be_visible()
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(N_SCREENS / "day_board.png"), full_page=True)
        self.assertEqual(errors, [])

    def test_slot_swap_in_the_browser(self):
        page = self.page(width=1440, height=950)
        self.sign_in(page)
        page.goto(f"{self.base}/runs/{self.run_id}/schedules")
        page.wait_for_load_state("load")
        page.get_by_role("button", name="Swap slots").click()
        page.select_option("#swap-dialog select[name=first]", "Associate 009")
        page.select_option("#swap-dialog select[name=second]", "Associate 010")
        expect(page.locator("#swap-h")).to_contain_text("This swap", timeout=30000)
        page.screenshot(path=str(N_SCREENS / "slot_swap.png"))
        page.fill("#swap-dialog input[name=reason]", "Both asked for it")
        page.get_by_role("button", name="Yes, swap them").click()
        page.wait_for_url("**/schedules?v=*", timeout=30000)
        expect(page.locator(".log")).to_contain_text("Associate 009 moved from Slot 9 to Slot 10 (slot swap)")


O_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_o" / "screens"


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class TheFloorToolsInTheBrowser(unittest.TestCase):
    """Phase O: exports, adherence, find a time, overtime and VTO, the autopilot, the coach, the handover, the wallboard."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    day = "/day?program=AE/AR+B2B&date=2026-10-14"

    @classmethod
    def setUpClass(cls):
        cls.setUpClass_base()
        O_SCREENS.mkdir(parents=True, exist_ok=True)
        from datetime import date
        days = cls.app.extensions["days"]
        omar = next(u for u in cls.store.list_users() if u["username"] == "omar")["id"]
        wed = date(2026, 10, 14)
        week = days.page("AE/AR B2B", wed)["view"]
        everyone = [l["name"] for l in week["lanes"] for s in l["segments"]
                    if s["offset"] == 0 and s["start"] <= 13 * 60 and s["end"] >= 17 * 60]
        afternoon, cls.free = everyone[:9], everyone[9:11]  # nine with records, two left free for a meeting
        for name in afternoon[:7]:
            days.set_status("AE/AR B2B", wed, name, "Unplanned leave", omar)
        days.set_status("AE/AR B2B", wed, afternoon[7], "Late", omar, end="14:20")
        days.add_activity("AE/AR B2B", wed, afternoon[8], "Coaching", "15:00", "15:30", omar, billable=True)

    def go(self, page, url, errors):
        page.goto(self.base + url)
        page.wait_for_load_state("load")
        page.mouse.move(1, 1)
        page.evaluate("window.scrollTo(0, 0)")
        self.assertEqual(errors, [])

    def test_every_floor_tool(self):
        page = self.page(width=1500, height=1000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, "/exports?from=2026-10-11&to=2026-10-17", errors)
        expect(page.locator("h1")).to_have_text("Exports")
        page.screenshot(path=str(O_SCREENS / "exports.png"), full_page=True)
        with page.expect_download() as got:
            page.get_by_role("button", name="Download").click()
        self.assertTrue(got.value.suggested_filename.endswith(".xlsx"))
        self.go(page, self.day + "&view=adherence", errors)
        expect(page.locator(".adh-t").first).to_be_visible()
        page.screenshot(path=str(O_SCREENS / "adherence.png"), full_page=True)
        who = "".join(f"&who={name.replace(' ', '+')}" for name in self.free)
        self.go(page, self.day + "&view=meeting" + who + "&minutes=30&from=12:00&to=19:00", errors)
        expect(page.locator(".fit-list li").first).to_be_visible()
        page.screenshot(path=str(O_SCREENS / "find_a_time.png"), full_page=True)
        self.go(page, self.day + "&view=cover", errors)
        expect(page.locator("#ot-h")).to_be_visible()
        page.screenshot(path=str(O_SCREENS / "overtime_vto.png"), full_page=True)
        self.go(page, self.day + "&view=replan", errors)
        expect(page.locator("#rp-h")).to_have_text("Fix the rest of the day's breaks")
        page.screenshot(path=str(O_SCREENS / "autopilot.png"), full_page=True)
        self.go(page, self.day + "&view=board", errors)
        page.screenshot(path=str(O_SCREENS / "board_with_activities.png"), full_page=True)
        self.go(page, "/coach?program=AE/AR+B2B&from=2026-10-11&to=2026-10-17", errors)
        expect(page.locator(".coach-t")).to_be_visible()
        page.screenshot(path=str(O_SCREENS / "coach.png"), full_page=True)
        self.go(page, "/day/handover?program=AE/AR+B2B&date=2026-10-14", errors)
        expect(page.locator("h1")).to_contain_text("Handover")
        page.screenshot(path=str(O_SCREENS / "handover.png"), full_page=True)
        wall = self.page(width=1600, height=900)
        self.sign_in(wall)
        wall.goto(self.base + "/day/wallboard?program=AE/AR+B2B&date=2026-10-14&at=14:10")
        wall.wait_for_load_state("load")
        expect(wall.locator(".wall-row")).to_have_count(4)
        wall.screenshot(path=str(O_SCREENS / "wallboard.png"))

    def test_the_board_adds_cover(self):  # runs after test_every_floor_tool, so its screenshots stay as they were
        page = self.page(width=1500, height=1000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, self.day + "&view=board", errors)
        row = page.locator(".rb-row[data-t='900']")  # 15:00, short: seven are on unplanned leave
        row.get_by_role("link", name="Add cover").click()
        page.wait_for_load_state("load")
        panel = page.locator("#cover")
        expect(panel.locator("h3")).to_contain_text("Cover 15:00 to 16:00")
        expect(panel.get_by_role("heading", name="Day off cancelled")).to_be_visible()
        offer = panel.locator("form:has(input[name='kind'][value='Called in']) button").first
        expect(offer).to_be_visible()
        top = page.locator("header.top").bounding_box()["height"]
        self.assertGreater(row.bounding_box()["y"], top - 1)  # the row lands below the header, its panel under it
        self.assertGreater(panel.bounding_box()["y"], row.bounding_box()["y"])
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(O_SCREENS / "board_add_cover.png"))  # the panel below the header, the board under it
        who, shift = offer.inner_text().split(":", 1)
        shift = shift.split("·")[0].strip()
        offer.click()
        page.wait_for_load_state("load")
        self.assertIn("cover=900", page.url)
        expect(page.locator(".flash, .flashes").first).to_contain_text(f"Recorded: {who}, day off cancelled (called in).")
        self.go(page, self.day, errors)
        expect(page.locator(".tl-tag.called")).to_have_attribute("title", f"Day off cancelled: called in {shift}")
        expect(page.get_by_text(f"Day off cancelled: called in {shift}").first).to_be_visible()
        page.screenshot(path=str(O_SCREENS / "called_in_timeline.png"), full_page=True)


P_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_p" / "screens"


class TheRunDetailsInTheBrowser(unittest.TestCase):
    """Phase P: the start-date dropdown, Edit details with its check before saving, and Rename or merge."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in

    @classmethod
    def setUpClass(cls):
        cls.setUpClass_base()
        P_SCREENS.mkdir(parents=True, exist_ok=True)
        from datetime import date
        sara = next(u for u in cls.store.list_users() if u["username"] == "sara")["id"]
        cls.store.add_run("0123456789ab", sara, "NMG_week.xlsx", "QUICK", "DONE", program="NMG", week_start="2026-10-12")
        cls.app.extensions["days"].set_status("AE/AR B2B", date(2026, 10, 14), "Associate 001", "Sick", sara)
        seed_week(cls.store, "AE/AR B2B", "2026-10-04", associates=14, fully_covered=118, before_full=126)  # a page

    def test_start_date_edit_and_rename(self):
        page = self.page(width=1280, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        starts = page.locator("select[name=week_start]")
        page.locator("input[name=program]").fill("NMG")  # NMG starts on Mondays: its Monday is preselected
        self.assertEqual(starts.locator("option:checked").get_attribute("data-day"), "1")
        starts.scroll_into_view_if_needed()
        page.locator("form:has(select[name=week_start])").screenshot(path=str(P_SCREENS / "upload_start_date.png"))
        page.goto(self.base + f"/runs/{self.run_id}")
        page.wait_for_load_state("load")
        page.get_by_text("Edit details").click()
        expect(page.locator("select[name=user_id]")).to_be_visible()
        page.locator("details.tag").screenshot(path=str(P_SCREENS / "run_edit_details.png"))
        page.locator("details.tag select[name=week_start]").select_option("2026-10-18")
        page.locator("details.tag").get_by_role("button", name="Save").click()
        page.wait_for_load_state("load")
        panel = page.locator("#check")
        expect(panel.locator("h2")).to_have_text("Check before saving")
        expect(panel).to_contain_text("Sun 11 Oct 2026 → Sun 18 Oct 2026")
        expect(panel).to_contain_text("stay on their dates")
        panel.scroll_into_view_if_needed()
        page.wait_for_timeout(600)
        panel.screenshot(path=str(P_SCREENS / "run_check_before_saving.png"))
        panel.get_by_role("link", name="No, keep as it was").click()
        page.wait_for_load_state("load")
        self.assertEqual(self.store.get_run(self.run_id)["week_start"], "2026-10-11")  # nothing changed
        page.get_by_role("link", name="AE/AR B2B").first.click()
        page.wait_for_load_state("load")
        page.get_by_text("Rename or merge this program").click()
        page.locator("input[name=new]").fill("AE-AR B2B")
        page.get_by_role("button", name="Check what moves").click()
        page.wait_for_load_state("load")
        expect(page.locator("h1")).to_have_text("Rename AE/AR B2B to AE-AR B2B")
        page.wait_for_timeout(600)  # let the page-to-page crossfade finish before the screenshot
        page.screenshot(path=str(P_SCREENS / "program_rename.png"), full_page=True)
        self.assertEqual(errors, [])
