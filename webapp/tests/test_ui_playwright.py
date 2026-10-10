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
        # re-pinned (Phase U): the menu also has "Departments and people", so the People link is matched exactly
        page.get_by_role("link", name="People", exact=True).click()
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
        # re-pinned (Phase R): Home also links "Show all my programs", so the menu's link is matched exactly
        page.get_by_role("link", name="Programs", exact=True).click()
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
        # Re-pinned in Phase Q (owner, 2026-10-08): the left menu has its own Program and LOB picker now, so the
        # upload form's field is looked for inside the upload form.
        expect(page.locator("form[action='/runs']").get_by_label("Program and LOB")).to_be_visible()
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
        # re-pinned (Phase T): an aux is kept with who it is with and why (owner, 2026-10-09)
        page.fill("#att-dialog input[name=with_whom]", "Sara")
        page.fill("#att-dialog input[name=why]", "Call quality review")
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
        page.locator("select[name=program]").select_option("NMG")  # NMG starts on Mondays: its Monday is preselected
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
        # re-pinned (Phase R): a program's data moves into a program or LOB picked from the list; typing a new
        # name made stray programs (owner, 2026-10-08). Display names change under LOBs and defaults.
        from webapp.programs import ProgramBook
        book = ProgramBook(self.store)
        target = book.add_lob(book.add_program("AE"), "AR B2B")
        page.reload()
        page.wait_for_load_state("load")
        page.get_by_text("Move this program into another program or LOB").click()
        page.locator("select[name=new]").select_option(target)
        page.get_by_role("button", name="Check what moves").click()
        page.wait_for_load_state("load")
        expect(page.locator("h1")).to_have_text("Move AE/AR B2B into AE, AR B2B")
        page.wait_for_timeout(600)  # let the page-to-page crossfade finish before the screenshot
        page.screenshot(path=str(P_SCREENS / "program_rename.png"), full_page=True)
        self.assertEqual(errors, [])


Q_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_q" / "screens"


class TheNewLayoutInTheBrowser(unittest.TestCase):
    """Phase Q: the slim top bar and left menu, Home from the programs, Overview apart from RTA, People with
    roles and programs, Programs and LOBs; and no sideways scroll on a phone."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in

    @classmethod
    def setUpClass(cls):
        cls.setUpClass_base()
        Q_SCREENS.mkdir(parents=True, exist_ok=True)
        from datetime import date
        from webapp.programs import ProgramBook
        seed_week(cls.store, "NMG", "2026-10-12")
        book = ProgramBook(cls.store)
        book.sync()
        ae = book.add_program("AE")
        book.adopt("AE/AR B2B", ae, "AR B2B")
        book.add_lob(ae, "IT")
        nmg = next(p["id"] for p in book.tree() if p["name"] == "NMG")
        book.set_defaults(nmg, 1, "QUICK", {})
        sara = next(u for u in cls.store.list_users() if u["username"] == "sara")["id"]
        for name in ("Associate 008", "Associate 021", "Associate 037"):
            cls.app.extensions["days"].set_status("AE/AR B2B", date(2026, 10, 14), name, "Unplanned leave", sara)
        sup = cls.store.add_user("associate.014", "Associate 014", "Sup-pass-1234", must_change=False)
        cls.store.update_user(sup, is_supervisor=1)
        cls.store.set_user_programs(sup, [ae])
        planner = cls.store.add_user("associate.001", "Associate 001", "Plan-pass-1234", must_change=False)
        cls.store.set_user_programs(planner, [ae, nmg])

    def go(self, page, url, errors):
        page.goto(self.base + url)
        page.wait_for_load_state("load")
        page.wait_for_timeout(500)
        self.assertEqual(errors, [])

    def test_the_new_layout(self):
        page = self.page(width=1440, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        top = page.locator("header.top")
        for words in ("Settings", "Sign out"):
            expect(top).to_contain_text(words)
        expect(top.get_by_role("link", name="Exports")).to_have_count(0)
        # re-pinned (Phase R): Home shows the program picked on the left (owner, 2026-10-08), with the others
        # one link away; "Show all my programs" shows both cards
        expect(page.locator("section.programs-home article.pcard")).to_have_count(1)
        expect(page.locator("p.home-scope a.lob")).to_have_count(1)
        page.screenshot(path=str(Q_SCREENS / "home.png"), full_page=True)
        self.go(page, "/overview?program=AE/AR+B2B&date=2026-10-14", errors)
        expect(page.locator("h1")).to_have_text("AE, AR B2B: Wednesday 14 Oct")
        expect(page.locator("aside.leftnav a[aria-current=page]")).to_have_text("Overview")
        page.screenshot(path=str(Q_SCREENS / "overview.png"), full_page=True)
        page.locator("aside.leftnav").get_by_role("link", name="RTA").click()
        page.wait_for_load_state("load")
        page.wait_for_timeout(500)
        expect(page.locator("p.rta-sum")).to_contain_text("On shift today")
        page.screenshot(path=str(Q_SCREENS / "rta.png"))
        self.go(page, "/admin/users", errors)
        expect(page.locator("table.people")).to_contain_text("Supervisor")
        page.screenshot(path=str(Q_SCREENS / "people.png"), full_page=True)
        self.go(page, "/setup/programs", errors)
        expect(page.locator("h1")).to_have_text("Programs and LOBs")
        page.screenshot(path=str(Q_SCREENS / "programs_and_lobs.png"), full_page=True)
        self.go(page, "/", errors)
        page.locator("select[name=program]").select_option("NMG")  # NMG's saved defaults: Monday, Quick
        self.assertEqual(page.locator("select[name=week_start] option:checked").get_attribute("data-day"), "1")

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        for url in ("/", "/overview?program=AE/AR+B2B&date=2026-10-14", "/admin/users", "/setup/programs"):
            self.go(phone, url, errors)
            width = phone.evaluate("document.scrollingElement.scrollWidth")
            self.assertLessEqual(width, 390, url)
        expect(phone.locator("details[data-menu]")).not_to_have_attribute("open", "")
        self.go(phone, "/", errors)
        phone.screenshot(path=str(Q_SCREENS / "phone_home.png"), full_page=True)


R_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_r" / "screens"


class TheRtaActionsInTheBrowser(unittest.TestCase):
    """Phase R task 5: "+ Add" on any interval of the board (with the effect shown first), and one person's
    day with everything recorded and Delete."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in

    @classmethod
    def setUpClass(cls):
        cls.setUpClass_base()
        R_SCREENS.mkdir(parents=True, exist_ok=True)

    def go(self, page, url, errors):
        page.goto(self.base + url)
        page.wait_for_load_state("load")
        page.wait_for_timeout(500)
        self.assertEqual(errors, [])

    def test_add_a_break_from_the_board(self):
        page = self.page(width=1440, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-15&view=board", errors)
        page.locator("#row-900 a.rb-add").click()
        page.wait_for_load_state("load")
        dialog = page.locator("#add-dialog")
        expect(dialog).to_be_visible()
        self.assertTrue(page.evaluate("document.getElementById('add-dialog').matches(':modal')"))
        # re-pinned (Phase S): the dialog also holds the people off that day for "Day off cancelled" (owner,
        # 2026-10-09), a second, disabled "associate" list; this is the working people's
        dialog.locator("select[name=associate]:not([data-off])").select_option("Associate 001")  # Thursday 12:00 - 21:00
        expect(dialog.locator("[data-effect]")).to_contain_text("the floor at its tightest")
        page.wait_for_timeout(300)
        page.screenshot(path=str(R_SCREENS / "board_add.png"))
        dialog.get_by_role("button", name="Add break").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("Recorded: Associate 001, Break 15:00 to 15:15.")
        expect(page.locator("#row-900 a.chip.added", has_text="Associate 001")).to_be_visible()
        self.assertEqual(errors, [])

    def test_delete_overtime_from_the_person_dialog(self):
        from datetime import date
        days = self.app.extensions["days"]
        days.add_activity("AE/AR B2B", date(2026, 10, 16), "Associate 001", "Overtime", "21:00", "22:00", 1)
        page = self.page(width=1440, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-16&view=board&who=Associate+001", errors)
        dialog = page.locator("#person-dialog")
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text("Overtime 21:00 to 22:00")
        page.screenshot(path=str(R_SCREENS / "person.png"))
        dialog.locator("li", has_text="Overtime 21:00 to 22:00").get_by_role("button", name="Delete").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("Cancelled.")
        self.assertEqual(self.store.list_activities("AE/AR B2B", ["2026-10-16"]), [])
        self.assertEqual(errors, [])


class ThePhaseRInTheBrowser(unittest.TestCase):
    """Phase R task 9: every new screen in a real browser, saved for the owner, and no sideways scroll on a phone."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in

    @classmethod
    def setUpClass(cls):
        import io
        from webapp.programs import ProgramBook
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import client_for, run_id_of, token
        cls.setUpClass_base()
        R_SCREENS.mkdir(parents=True, exist_ok=True)
        book = ProgramBook(cls.store)
        book.sync()
        saks = book.add_program("SAKS")
        book.add_lob(saks, "NMG Tier 1")
        cls.tier2 = book.add_lob(saks, "NMG Tier 2")
        book.add_lob(saks, "SAKS Tier 1")
        cls.stray = seed_week(cls.store, "SAKS, NMG Tier 2", "2026-10-18")
        book.sync()
        client = client_for(cls.app)
        ready = make_ready(Path(tempfile.mkdtemp()) / "ready.xlsx").read_bytes()
        cls.ready_run = run_id_of(client.post("/runs", data={
            "csrf_token": token(client), "kind": "ready", "program": cls.tier2, "week_start": "2026-10-11",
            "workbook": (io.BytesIO(ready), "SAKS_week_ready.xlsx")}, content_type="multipart/form-data"))
        cls.ready_version = cls.app.extensions["schedules"].versions(cls.ready_run)[0]

    def go(self, page, url, errors):
        page.goto(self.base + url)
        page.wait_for_load_state("load")
        page.wait_for_timeout(500)
        self.assertEqual(errors, [])

    def test_phase_r_screens(self):
        page = self.page(width=1440, height=900, scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, f"/?program={self.tier2.replace(' ', '+')}", errors)
        expect(page.locator("section.programs-home article.pcard")).to_have_count(1)
        expect(page.locator("section.programs-home h1")).to_have_text("SAKS")
        page.screenshot(path=str(R_SCREENS / "home_picked.png"))
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-16&view=board&cover=1260", errors)
        panel = page.locator("#cover")
        expect(panel.locator("form.ot-offer").first).to_be_visible()
        panel.scroll_into_view_if_needed()
        panel.screenshot(path=str(R_SCREENS / "ot_lengths.png"))
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14&view=cover", errors)
        vto = page.locator("section[aria-labelledby=vto-h]")
        expect(vto.locator("form.vto-offer").first).to_be_visible()
        vto.screenshot(path=str(R_SCREENS / "vto_stretch.png"))
        self.go(page, "/setup/programs", errors)
        stray = page.locator("section.setup-program", has=page.locator("h2", has_text="SAKS, NMG Tier 2"))
        expect(stray).to_contain_text("Move all of it into")
        stray.screenshot(path=str(R_SCREENS / "programs_move_delete.png"))
        self.go(page, f"/runs/{self.stray}", errors)
        page.get_by_text("Edit details").click()
        page.locator("details.tag").screenshot(path=str(R_SCREENS / "edit_details.png"))
        self.go(page, "/", errors)
        page.locator("input[name=kind][value=ready]").check()
        expect(page.locator("fieldset[data-build-only]")).to_be_hidden()
        expect(page.locator("[data-submit-label]")).to_have_text("Check and upload")
        page.locator("#newrun").screenshot(path=str(R_SCREENS / "upload_ready.png"))
        self.go(page, f"/runs/{self.ready_run}", errors)
        expect(page.locator("section.ready-run")).to_contain_text("Ready schedule uploaded")
        page.get_by_role("link", name="Plan breaks").click()
        page.wait_for_load_state("load")
        page.locator(".bp-days").get_by_role("button", name="Wed").click()
        page.wait_for_load_state("load")
        expect(page.locator(".bp-grid")).to_contain_text("Not placed yet")
        page.get_by_role("button", name="Suggest times for the empty ones").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("Suggested times for the empty breaks on Wed")
        expect(page.locator(".bp-grid")).not_to_contain_text("Not placed yet")
        page.wait_for_timeout(500)
        page.screenshot(path=str(R_SCREENS / "plan_breaks.png"), full_page=True)
        self.assertEqual(errors, [])

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        for url in ("/day?program=AE/AR+B2B&date=2026-10-14&view=board&add=600",
                    f"/schedules/{self.ready_version['id']}/breaks?day=Wed", "/setup/programs"):
            self.go(phone, url, errors)
            self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390, url)
        self.go(phone, "/day?program=AE/AR+B2B&date=2026-10-14&view=board&add=600", errors)
        phone.screenshot(path=str(R_SCREENS / "phone_add.png"))



S_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_s" / "screens"


class ThePhaseSInTheBrowser(unittest.TestCase):
    """Phase S: the owner's seven points of 2026-10-09 in a real browser, saved for the owner, and no sideways
    scroll on a phone."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        import io
        from webapp.programs import ProgramBook
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import client_for, run_id_of, token
        cls.setUpClass_base()
        S_SCREENS.mkdir(parents=True, exist_ok=True)
        book = ProgramBook(cls.store)
        book.sync()
        saks = book.add_program("SAKS")
        cls.tier2 = book.add_lob(saks, "NMG Tier 2")
        book.set_defaults(saks, 1, "QUICK", {})  # SAKS starts on Monday
        client = client_for(cls.app)
        ready = make_ready(Path(tempfile.mkdtemp()) / "ready.xlsx").read_bytes()

        def upload(program, week, name):
            return run_id_of(client.post("/runs", data={
                "csrf_token": token(client), "kind": "ready", "program": program, "week_start": week,
                "workbook": (io.BytesIO(ready), name)}, content_type="multipart/form-data"))
        cls.ready_run = upload(cls.tier2, "2026-10-11", "SAKS_week_ready.xlsx")
        cls.unfiled = upload("", "", "Uploaded_without_a_program.xlsx")

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        for url in ("/?all=1", "/day?program=AE/AR+B2B&date=2026-10-14&view=cover",
                    "/day/wallboard?program=AE/AR+B2B&date=2026-10-14&at=12:00", f"/runs/{self.ready_run}",
                    f"/runs/{self.ready_run}/schedules", "/day?program=AE/AR+B2B&date=2026-10-14&view=board&add=600"):
            self.go(phone, url, errors)
            self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390, url)
        dialog = phone.locator("#add-dialog")
        dialog.get_by_label("Day off cancelled").check()
        expect(dialog.locator("select[data-off]")).to_be_visible()
        phone.wait_for_timeout(1500)
        dialog.screenshot(path=str(S_SCREENS / "phone_day_off.png"))

    def test_phase_s_screens(self):
        page = self.page(width=1440, height=900, scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        # 1: the upload form takes the program and LOB picked on the left, and that program's defaults
        self.go(page, f"/?program={self.tier2.replace(' ', '+')}", errors)
        self.go(page, "/", errors)
        expect(page.locator("#newrun select[name=program]")).to_have_value(self.tier2)
        self.assertEqual(page.locator("#newrun select[name=week_start] option:checked").get_attribute("data-day"), "1")
        page.locator("#newrun").screenshot(path=str(S_SCREENS / "upload_picked.png"))
        # 2: a schedule uploaded without a program is listed on Home and filed there
        self.go(page, "/?all=1", errors)
        panel = page.locator("section.unfiled")
        expect(panel).to_contain_text("Uploaded_without_a_program.xlsx")
        panel.screenshot(path=str(S_SCREENS / "home_unfiled.png"))
        panel.locator("select[name=program]").select_option(self.tier2)
        panel.locator("select[name=week_start]").select_option("2026-10-18")
        panel.get_by_role("button", name="File it").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("Details saved.")
        expect(page.locator("section.unfiled")).to_have_count(0)
        # 3: the Schedules page says the name, program and start date, and opens the editor
        self.go(page, f"/runs/{self.ready_run}/schedules", errors)
        expect(page.locator("p.rundetails")).to_contain_text("starts Sunday 11 Oct")
        page.locator("div.phead").screenshot(path=str(S_SCREENS / "schedules_details.png"))
        page.get_by_role("link", name="Edit the name, program or start date").click()
        page.wait_for_load_state("load")
        expect(page.locator("details#edit")).to_have_attribute("open", "")
        page.locator("details#edit").screenshot(path=str(S_SCREENS / "edit_open.png"))
        # 4: Day off cancelled from RTA's + Add, on typed times
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14&view=board&add=600", errors)
        dialog = page.locator("#add-dialog")
        dialog.get_by_label("Day off cancelled").check()
        expect(dialog.locator("select[data-off]")).to_be_visible()
        expect(dialog.locator("button[type=submit]")).to_have_text("Call in")
        dialog.locator("select[data-shift-pick]").select_option("")
        dialog.locator("input[name=from]").fill("10:30")
        dialog.locator("input[name=to]").fill("16:30")
        expect(dialog.locator("[data-effect]")).to_contain_text("called in 10:30 - 16:30", timeout=15000)
        dialog.screenshot(path=str(S_SCREENS / "day_off_add.png"))
        who = dialog.locator("select[data-off]").input_value()
        dialog.locator("button[type=submit]").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text(f"Recorded: {who}, Day off cancelled: called in 10:30 - 16:30.")
        # 5: an uploaded schedule's coverage summary
        self.go(page, f"/runs/{self.ready_run}", errors)
        coverage = page.locator("section.coverage")
        expect(coverage).to_contain_text("Breaks are not planned yet")
        coverage.screenshot(path=str(S_SCREENS / "ready_summary.png"))
        # 6: Find a time for two people lists the times; no person popup
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14&view=meeting", errors)
        for name in ("Associate 001", "Associate 012"):
            page.locator(f"input[name=who][value='{name}']").check()
        # re-pinned (Phase T): Find a time asks who the session is with and why (owner, 2026-10-09)
        page.locator("form.exp-form input[name=with_whom]").fill("Sara")
        page.locator("form.exp-form input[name=why]").fill("Team huddle")
        page.get_by_role("button", name="Find times").click()
        page.wait_for_load_state("load")
        expect(page.locator("#person-dialog")).to_have_count(0)
        expect(page.locator("ol.fit-list li").first).to_be_visible()
        page.locator("section[aria-labelledby=fits-h]").screenshot(path=str(S_SCREENS / "find_a_time.png"))
        # 7: Analysis of a LOB with only uploaded schedules explains, not "Not found"
        self.go(page, f"/programs/{self.tier2}", errors)
        expect(page.locator("main")).to_contain_text("No analysis yet")
        page.screenshot(path=str(S_SCREENS / "analysis_ready_only.png"))
        self.assertEqual(errors, [])



T_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_t" / "screens"


class ThePhaseTInTheBrowser(unittest.TestCase):
    """Phase T: every aux asks who it is with and why, in a real browser (owner, 2026-10-09: "in case of any aux
    being placed like meeting coaching etc we need to specify with who and why in a comment while reserving")."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        cls.setUpClass_base()
        T_SCREENS.mkdir(parents=True, exist_ok=True)

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        self.go(phone, "/day?program=AE/AR+B2B&date=2026-10-13&view=board&add=900", errors)
        phone.locator("#add-dialog").get_by_label("Meeting").check()
        expect(phone.locator("#add-dialog input[name=why]")).to_be_visible()
        self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390)
        self.go(phone, "/day?program=AE/AR+B2B&date=2026-10-13&view=meeting", errors)
        self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390)

    def test_phase_t_screens(self):
        page = self.page(width=1440, height=900, scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        # + Add: an aux shows With and Why, both required; the record and the log carry them
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-15&view=board&add=900", errors)
        dialog = page.locator("#add-dialog")
        expect(dialog.locator("input[name=with_whom]")).to_be_hidden()  # a break asks neither
        dialog.locator("select[name=associate]:not([data-off])").select_option("Associate 001")
        dialog.get_by_label("Coaching").check()
        for name in ("with_whom", "why"):
            expect(dialog.locator(f"input[name={name}]")).to_be_visible()
            self.assertTrue(dialog.locator(f"input[name={name}]").evaluate("e => e.required && !e.disabled"))
        dialog.locator("input[name=with_whom]").fill("Sara")
        dialog.locator("input[name=why]").fill("Monthly quality review")
        expect(dialog.locator("[data-effect]")).to_contain_text("Coaching 15:00 to 15:30", timeout=15000)
        dialog.screenshot(path=str(T_SCREENS / "add_coaching.png"))
        dialog.get_by_role("button", name="Add coaching").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("with Sara: Monthly quality review")
        # the timeline's attendance list: the popup asks both, and the server says what is missing
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14", errors)
        page.select_option('select.att[data-name="Associate 021"]', "Meeting|0")
        att = page.locator("#att-dialog")
        expect(att.locator("input[name=with_whom]")).to_be_visible()
        att.locator("input[name=from]").fill("10:00")
        att.locator("input[name=to]").fill("10:30")
        att.locator("[data-keep]").click()
        expect(att.locator(".dlg-result")).to_have_text("Say who the meeting is with.")
        att.screenshot(path=str(T_SCREENS / "attendance_meeting_refused.png"))
        att.locator("input[name=with_whom]").fill("Ops manager")
        att.locator("input[name=why]").fill("Process update")
        expect(att.locator(".dlg-result")).to_have_text("")  # the message goes once they type
        att.screenshot(path=str(T_SCREENS / "attendance_meeting.png"))
        att.locator("[data-keep]").click()
        expect(page.locator(".log")).to_contain_text("with Ops manager: Process update", timeout=15000)
        # one person's day lists who and why
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14&view=board&who=Associate+021", errors)
        expect(page.locator("#person-dialog")).to_contain_text("with Ops manager: Process update")
        page.locator("#person-dialog").screenshot(path=str(T_SCREENS / "person_with_why.png"))
        # Find a time asks both before the times, and Book carries them
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14&view=meeting", errors)
        for name in ("Associate 001", "Associate 012"):
            page.locator(f"input[name=who][value='{name}']").check()
        page.locator("form.exp-form input[name=with_whom]").fill("IT trainer")
        page.locator("form.exp-form input[name=why]").fill("New CRM release")
        page.get_by_role("button", name="Find times").click()
        page.wait_for_load_state("load")
        page.locator("div.adh").first.screenshot(path=str(T_SCREENS / "find_a_time_with_why.png"))
        page.locator("ol.fit-list li").first.get_by_role("button", name="Book").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("Booked: meeting")
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14&view=cover", errors)
        expect(page.locator("section[aria-labelledby=acts-h]")).to_contain_text("with IT trainer: New CRM release")
        page.locator("section[aria-labelledby=acts-h]").screenshot(path=str(T_SCREENS / "activities_list.png"))
        self.assertEqual(errors, [])


U_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_u" / "screens"


class ThePhaseUInTheBrowser(unittest.TestCase):
    """Phase U: With is picked from the program's departments and people, kept by admins and supervisors (owner,
    2026-10-09: "categorized as well by 2 things department and names ... popup as a drop down list")."""

    setUpClass_base = classmethod(TheSchedulesInTheBrowser.setUpClass.__func__)
    tearDownClass = classmethod(TheSchedulesInTheBrowser.tearDownClass.__func__)
    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        from webapp.contacts import ContactBook
        from webapp.programs import ProgramBook
        cls.setUpClass_base()
        U_SCREENS.mkdir(parents=True, exist_ok=True)
        book = ProgramBook(cls.store)
        book.sync()
        cls.program = next(p["id"] for p in book.tree() if p["key"] == "AE/AR B2B")
        ContactBook(cls.store).add_many(cls.program, "Quality, Lina\nTraining, IT trainer\nWorkforce", 1)

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        for url in ("/setup/with?program=AE/AR+B2B", "/day?program=AE/AR+B2B&date=2026-10-13&view=board&add=900"):
            self.go(phone, url, errors)
            self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390, url)
        phone.locator("#add-dialog").get_by_label("Meeting").check()
        expect(phone.locator("#add-dialog select[name=with_dept]")).to_be_visible()
        phone.locator("#add-dialog").screenshot(path=str(U_SCREENS / "phone_add_department.png"))

    def test_phase_u_screens(self):
        page = self.page(width=1440, height=900, scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        # the lists: an admin (or the program's supervisor) adds a person
        self.go(page, "/setup/with?program=AE/AR+B2B", errors)
        add = page.locator("form.wl-add").first
        add.get_by_label("Department").fill("Quality")
        add.get_by_label("Name").fill("Omar")
        add.get_by_role("button", name="Add").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_have_text("Added Omar to Quality.")
        page.screenshot(path=str(U_SCREENS / "departments_and_people.png"), full_page=True)
        # + Add: the department first, then only its people
        page.set_viewport_size({"width": 1440, "height": 1200})  # the whole dialog in the screen
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-15&view=board&add=900", errors)
        dialog = page.locator("#add-dialog")
        dialog.locator("select[name=associate]:not([data-off])").select_option("Associate 001")
        dialog.get_by_label("Coaching").check()
        dept, who = dialog.locator("select[name=with_dept]"), dialog.locator("select[name=with_whom]")
        expect(dept).to_be_visible()
        dept.select_option("Quality")
        offered = who.evaluate("s => Array.from(s.options).filter(o => o.value && !o.hidden).map(o => o.value)")
        self.assertEqual(offered, ["Lina", "Omar"])  # Training's people are not offered under Quality
        who.select_option("Lina")
        dialog.locator("input[name=why]").fill("Monthly quality review")
        expect(dialog.locator("[data-effect]")).to_contain_text("Coaching 15:00 to 15:30", timeout=15000)
        dialog.screenshot(path=str(U_SCREENS / "add_with_department.png"))
        dialog.get_by_role("button", name="Add coaching").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash")).to_contain_text("with Lina (Quality): Monthly quality review")
        # the attendance popup picks the same way
        self.go(page, "/day?program=AE/AR+B2B&date=2026-10-14", errors)
        page.select_option('select.att[data-name="Associate 021"]', "Training|0")
        att = page.locator("#att-dialog")
        att.locator("input[name=from]").fill("10:00")
        att.locator("input[name=to]").fill("10:30")
        att.locator("select[name=with_dept]").select_option("Training")
        att.locator("select[name=with_whom]").select_option("IT trainer")
        att.locator("input[name=why]").fill("New CRM release")
        att.screenshot(path=str(U_SCREENS / "attendance_with_department.png"))
        att.locator("[data-keep]").click()
        expect(page.locator(".log")).to_contain_text("with IT trainer (Training): New CRM release", timeout=15000)
        self.assertEqual(errors, [])


V_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_v" / "screens"


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class ThePhaseVInTheBrowser(unittest.TestCase):
    """Phase V: Chat, Phone and Email planned per associate (owner, 2026-10-09), in a real browser: the upload's
    channel check, Associate channels, Plan channels (Suggest, Save), booking that warns about a channel, and the
    RTA's Channels tab with a fix applied. The day is test_channel_day's: Associate 001 (Arabic) alone on Chat,
    Associate 031 alone on Phone, Chat and Phone needed from 14:00 to 16:00 and in the 19:00 to 21:00 all-channels
    time."""

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        import io
        import shutil
        from webapp.channel_people import ChannelPeople
        from webapp.programs import ProgramBook
        from webapp.tests.test_channel_day import ARABIC_SPARE, channel_day
        from webapp.tests.test_runs import sign_in as client_sign_in, token, wait
        from webapp.versions import read_week
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        upload = channel_day(cls.dir / "upload.xlsx")
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.omar = cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        program_id = programs.add_program("SAKS")
        cls.key = programs.add_lob(program_id, "NMG Tier 2")
        client = client_sign_in(cls.app, "omar", "Owner-pass-123")
        client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": cls.key,
                                   "week_start": "2026-10-11", "workbook": (io.BytesIO(upload.read_bytes()), "week.xlsx")},
                    content_type="multipart/form-data")
        cls.run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, cls.run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.version = cls.app.extensions["schedules"].versions(cls.run_id)[0]
        everyone = [a["name"] for a in read_week(upload)["associates"]]
        ChannelPeople(cls.store).save(program_id, {n: "E" for n in everyone if n not in
                                                   ("Associate 001", "Associate 031", ARABIC_SPARE)}, cls.omar)
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        V_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def test_phase_v_screens(self):
        page = self.page(width=1440, height=900, scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        q = self.key.replace(" ", "+")
        # the schedules page: the upload's channel check, and the way to plan channels
        self.go(page, f"/runs/{self.run_id}/schedules", errors)
        expect(page.get_by_role("heading", name="Channel tabs")).to_be_visible()
        page.screenshot(path=str(V_SCREENS / "schedules_channel_check.png"), full_page=True)
        # Associate channels: Associate 001 stops working Email
        self.go(page, f"/setup/channels?program={q}", errors)
        page.get_by_label("Associate 001 works Email").uncheck()
        page.get_by_role("button", name="Save", exact=True).click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_have_text("Saved 1 change.")
        page.screenshot(path=str(V_SCREENS / "associate_channels.png"), full_page=True)
        # Plan channels: Thursday suggested, then saved as a new version in use
        self.go(page, f"/schedules/{self.version['id']}/channels?day=Thu", errors)
        page.get_by_role("button", name="Suggest the day").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("Suggested channels for Thursday")
        expect(page.locator("table.cp-grid td.ch-P").first).to_be_visible()
        page.screenshot(path=str(V_SCREENS / "plan_channels.png"), full_page=True)
        page.get_by_role("button", name="Save as a new version").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("Saved as Version 2")
        # booking coaching for the only Arabic speaker on Chat: the dialog says so, and offers a time
        page.set_viewport_size({"width": 1440, "height": 1200})
        self.go(page, f"/day?program={q}&date=2026-10-14&view=board&add=900", errors)
        dialog = page.locator("#add-dialog")
        dialog.locator("select[name=associate]:not([data-off])").select_option("Associate 001")
        dialog.get_by_label("Coaching").check()
        effect = dialog.locator("[data-channel-effect]")
        expect(effect).to_contain_text("nobody on Chat, and no Arabic speaker on Chat")
        expect(dialog.get_by_role("button", name="Use 16:00")).to_be_visible()
        dialog.screenshot(path=str(V_SCREENS / "booking_channel_effect.png"))
        dialog.locator("input[name=with_whom]").fill("Associate 021")
        dialog.locator("input[name=why]").fill("Quality follow-up")
        dialog.get_by_role("button", name="Add coaching").click()
        page.wait_for_load_state("load")
        # the RTA's Channels tab: the warning, its cause, and a fix applied
        self.go(page, f"/day?program={q}&date=2026-10-14&view=channels", errors)
        expect(page.locator(".alert h3").first).to_have_text(
            "15:00 to 16:00: nobody on Chat, and no Arabic speaker on Chat")
        expect(page.locator(".alert").first).to_contain_text("Associate 001 is booked for Coaching, with Associate 021: "
                                                             "Quality follow-up")
        page.screenshot(path=str(V_SCREENS / "rta_channel_warning.png"), full_page=True)
        page.locator("form.fix", has_text="Associate 013: Email → Chat").get_by_role("button", name="Apply").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_have_text("Associate 013: Chat from 15:00 to 16:00.")
        expect(page.locator(".alert")).to_have_count(0)
        page.screenshot(path=str(V_SCREENS / "rta_channel_fixed.png"), full_page=True)
        self.assertEqual(errors, [])

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        q = self.key.replace(" ", "+")
        for url in (f"/setup/channels?program={q}", f"/schedules/{self.version['id']}/channels?day=Wed",
                    f"/day?program={q}&date=2026-10-14&view=channels"):
            self.go(phone, url, errors)
            self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390, url)
        phone.screenshot(path=str(V_SCREENS / "phone_rta_channels.png"), full_page=True)


W_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_w" / "screens"


class ThePhaseWInTheBrowser(unittest.TestCase):
    """Phase W (owner, 2026-10-09), in a real browser: the upload says the week already has a schedule, breaks
    planned automatically, Back after a save leaves the page, the interval target set on the Week page and counted
    on the RTA, the Timeline filtered by shift start through an attendance change, and an export that says Ready.
    The week is this week, so the upload form offers its start date."""

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        import io
        import shutil
        from datetime import date, timedelta
        from webapp.programs import ProgramBook
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import sign_in as client_sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        today = date.today()
        cls.sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        cls.wed = cls.sunday + timedelta(days=3)
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        client = client_sign_in(cls.app, "omar", "Owner-pass-123")
        client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": cls.key,
                                   "week_start": cls.sunday.isoformat(),
                                   "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                    content_type="multipart/form-data")
        cls.run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, cls.run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        W_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def test_phase_w_screens(self):
        page = self.page(width=1440, height=900, scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        q = self.key.replace(" ", "+")
        # the upload form: this LOB already has a schedule for the week
        self.go(page, "/", errors)
        page.locator("select[name=program][data-program-pick]").select_option(self.key)
        page.locator("select[name=week_start]").first.select_option(self.sunday.isoformat())
        warning = page.locator("[data-week-check]")
        expect(warning).to_be_visible()
        expect(warning).to_contain_text("has 1 schedule for the week of")
        warning.scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        page.screenshot(path=str(W_SCREENS / "upload_same_week.png"))
        # plan breaks automatically on the schedules page
        self.go(page, f"/runs/{self.run_id}/schedules", errors)
        page.locator("summary", has_text="Plan breaks automatically").click()
        expect(page.get_by_text("This version has no breaks yet.")).to_be_visible()
        page.wait_for_timeout(700)
        page.screenshot(path=str(W_SCREENS / "plan_breaks_automatically.png"))
        page.get_by_role("button", name="Plan breaks", exact=True).click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("Breaks planned automatically for 7 days")
        expect(page.locator("summary", has_text="Re-plan breaks automatically")).to_be_visible()
        page.wait_for_timeout(700)
        page.screenshot(path=str(W_SCREENS / "breaks_planned.png"))
        made = self.app.extensions["schedules"].versions(self.run_id)[-1]
        # Back after a save on Plan breaks leaves the page (it used to reload the same one)
        self.go(page, f"/schedules/{made['id']}/breaks?day=Wed", errors)
        page.get_by_role("button", name="Suggest times for the empty ones").click()
        page.wait_for_load_state("load")
        page.get_by_role("link", name="‹ Back").click()
        page.wait_for_load_state("load")
        self.assertIn(f"/runs/{self.run_id}/schedules", page.url)
        # the interval target, set on the Week page and counted on the RTA
        self.go(page, f"/week?program={q}&week={self.sunday.isoformat()}", errors)
        page.locator("#target select[name=target]").select_option("90")
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("is now 90%")
        page.wait_for_timeout(700)
        page.locator("#target").screenshot(path=str(W_SCREENS / "week_interval_target.png"))
        self.go(page, f"/day?program={q}&date={self.wed.isoformat()}", errors)
        # Re-pinned in Phase Z: the count moved from the summary line's tile into the achievement block (sample 04).
        expect(page.locator(".achv")).to_contain_text("intervals at 90% or more")
        expect(page.locator(".tl-lbl", has_text="Achieved (target 90%)")).to_be_visible()
        page.wait_for_timeout(700)
        page.locator(".rta-sum").screenshot(path=str(W_SCREENS / "rta_intervals_at_target.png"))
        # the Timeline by shift start, kept through an attendance change
        page.locator(".shiftbar a", has_text="08:00").click()
        page.wait_for_load_state("load")
        lanes = page.locator(".tl-lane select.att")
        expect(lanes).to_have_count(3)
        lanes.first.select_option("Sick")
        page.wait_for_load_state("load")
        expect(page.locator(".shiftbar a[aria-current]")).to_contain_text("1 off")
        expect(page.locator(".tl-lane select.att")).to_have_count(3)
        page.locator(".shiftpick").scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        page.screenshot(path=str(W_SCREENS / "rta_filter_by_shift.png"))
        # an export that says what it is doing, then Ready
        self.go(page, f"/exports?from={self.sunday.isoformat()}&to={self.wed.isoformat()}", errors)
        with page.expect_download() as got:
            page.get_by_role("button", name="Download").click()
        self.assertTrue(got.value.suggested_filename.endswith(".xlsx"))
        expect(page.locator(".exp-ok")).to_contain_text("Ready: Team_Scheduler_")
        page.locator(".exp-ok").scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        page.screenshot(path=str(W_SCREENS / "export_ready.png"))
        self.assertEqual(errors, [])

    def test_an_export_after_signing_out_says_so(self):
        """Final review: with the session gone, the script followed the redirect to the sign-in page and saved
        that page as the export file."""
        page = self.page(width=1280, height=900, scheme="light")
        self.sign_in(page)
        self.go(page, f"/exports?from={self.sunday.isoformat()}&to={self.wed.isoformat()}", [])
        page.context.clear_cookies()
        page.get_by_role("button", name="Download").click()
        expect(page.locator(".alert.bad")).to_contain_text("You were signed out: sign in again, then download.")
        expect(page.locator(".exp-ok")).to_have_count(0)

    def test_a_phone_has_no_sideways_scroll(self):
        phone = self.page(width=390, height=844)
        errors = []
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        q = self.key.replace(" ", "+")
        for url in (f"/day?program={q}&date={self.wed.isoformat()}&shift=08:00",
                    f"/week?program={q}&week={self.sunday.isoformat()}"):
            self.go(phone, url, errors)
            self.assertLessEqual(phone.evaluate("document.scrollingElement.scrollWidth"), 390, url)
        phone.wait_for_timeout(700)
        phone.screenshot(path=str(W_SCREENS / "phone_week_target.png"), full_page=True)


# Phase XY task 6: colours as the browser draws them. Each pair is [foreground, background] in sRGB 0-255; a
# see-through background is laid over what is behind it, up to the page.
PAIRS_JS = """([selector, what]) => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, under) => [0, 1, 2].map(i => top[i] * top[3] + under[i] * (1 - top[3]));
  const behind = (el) => { const layers = [];
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let base = [255, 255, 255]; for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base); return base; };
  return [...document.querySelectorAll(selector)].slice(0, 60).filter(el => el.getClientRects().length).map(el => {
    const s = getComputedStyle(el);
    if (what === "text") { const bg = behind(el), fg = parse(s.color); return [over(fg, bg), bg]; }
    const bg = behind(el.parentElement);
    if (what === "edge") { const fg = parse(s.borderTopColor); return [over(fg, bg), bg]; }
    return [behind(el), bg];  // a filled cell against the panel it sits on
  });
}"""


def parse_colour(text):
    nums = [float(x) for x in re.findall(r"[\d.]+", text)] if "rgb" in text else None
    if nums is None:
        h = text.strip().lstrip("#")
        nums = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return nums


def contrast(fg, bg):
    def lum(c):
        c = [v / 255 for v in c[:3]]
        c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def oklch(rgb):
    """(chroma, hue in degrees) of an sRGB colour, by OKLab."""
    import math
    r, g, b = [v / 255 for v in rgb]
    r, g, b = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in (r, g, b)]
    lc = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)  # the three cone responses
    mc = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    sc = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    a2 = 1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc
    b2 = 0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc
    return math.hypot(a2, b2), math.degrees(math.atan2(b2, a2)) % 360

XY_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_xy" / "screens"


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here; UI tests skipped")
class ThePhaseXYInTheBrowser(unittest.TestCase):
    """Phase XY (the owner approved every review sample and the colour proposal): the review fixes and the new
    colours in a real browser. The Phase W week, plus a schedule still running, a planner with no program and a
    program with ten weeks of history."""

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        import io
        import shutil
        from datetime import date, timedelta
        from webapp.programs import ProgramBook
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import sign_in as client_sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        today = date.today()
        cls.sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        owner = cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.store.add_user("agent", "Agent Seven", "Agent-pass-123", must_change=False)  # a planner with no program
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        client = client_sign_in(cls.app, "omar", "Owner-pass-123")
        client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": cls.key,
                                   "week_start": cls.sunday.isoformat(),
                                   "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                    content_type="multipart/form-data")
        cls.run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, cls.run_id, statuses=("DONE", "REJECTED", "FAILED"))
        cls.version = version = cls.app.extensions["schedules"].versions(cls.run_id)[-1]["id"]
        client.post(f"/schedules/{version}/auto-breaks", data={"csrf_token": token(client), "use": "1"})
        seed_history(cls.store)
        cls.running = "0123456789ab"  # a run id as the queue makes them (12 hex digits)
        cls.store.add_run(cls.running, owner, "week_next_NMG.xlsx", "QUICK", "RUNNING", program=cls.key,
                          week_start=(cls.sunday + timedelta(days=7)).isoformat())
        cls.q = cls.key.replace(" ", "+")
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        XY_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def day(self, page, errors, view=""):
        self.go(page, f"/day?program={self.q}&date={self.sunday.isoformat()}" + (f"&view={view}" if view else ""), errors)

    def present_lane(self, page, skip=0):
        """The attendance box of a lane showing Present (the skip-th one) whose shift starts on the page's day, and
        its person. A shift from the Saturday before belongs to a week with no schedule here, so it cannot be marked."""
        i = page.evaluate("([skip, day]) => [...document.querySelectorAll('.tl-lane select.att')]"
                          ".map((s, k) => s.value === 'Present' && s.dataset.date === day ? k : -1)"
                          ".filter(k => k >= 0)[skip]", [skip, self.sunday.isoformat()])
        box = page.locator(".tl-lane select.att").nth(i)
        return box, box.get_attribute("data-name")

    def watch_posts(self, page):
        posts = []
        page.on("request", lambda r: posts.append(r.url) if r.method == "POST" and "/day/attendance" in r.url else None)
        return posts

    # ---------------------------------------------------------------- Task 4: keyboard moves wait for Enter
    def test_one_arrow_does_not_save_attendance(self):
        page = self.page(scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.day(page, errors)
        posts = self.watch_posts(page)
        box, name = self.present_lane(page)
        box.focus()
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(1500)
        self.assertEqual(posts, [])
        expect(box).to_have_class(re.compile(r"\bpending\b"))
        expect(page.locator("p.pick-note")).to_have_text(
            "Not saved yet. Press Enter to save Unplanned leave, or Esc to keep Present.")
        with page.expect_navigation():
            page.keyboard.press("Enter")
        page.wait_for_load_state("load")
        self.assertEqual(len(posts), 1)
        expect(page.locator(f'.tl-lane select.att[data-name="{name}"]')).to_have_value("Unplanned leave")
        self.assertEqual(errors, [])

    def test_escape_and_tab_put_attendance_back(self):
        page = self.page(scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.day(page, errors)
        posts = self.watch_posts(page)
        box, _ = self.present_lane(page, skip=2)
        for leave in ("Escape", "Tab"):
            box.focus()
            page.keyboard.press("ArrowDown")
            expect(page.locator("p.pick-note")).to_have_count(1)
            page.keyboard.press(leave)
            page.wait_for_timeout(800)
            expect(box).to_have_value("Present")
            expect(page.locator("p.pick-note")).to_have_count(0)
            expect(box).not_to_have_class(re.compile(r"\bpending\b"))
        self.assertEqual(posts, [])
        self.assertEqual(errors, [])

    def test_an_open_list_saves_with_one_enter(self):
        """Review focus 1: a list opened from the keyboard (Alt+Down, Space) and closed with Enter saves once, with no
        second Enter; the wait for Enter is only for arrows on a closed list."""
        for opener in ("Alt+ArrowDown", "Space"):
            page = self.page(scheme="light")
            self.sign_in(page)
            self.day(page, [])
            posts = self.watch_posts(page)
            box, name = self.present_lane(page, skip=6)
            box.focus()
            page.keyboard.press(opener)
            page.keyboard.press("ArrowDown")
            with page.expect_navigation():
                page.keyboard.press("Enter")
            page.wait_for_load_state("load")
            self.assertEqual(len(posts), 1, opener)
            expect(page.locator(f'.tl-lane select.att[data-name="{name}"]')).to_have_value("Unplanned leave")

    def test_a_mouse_pick_still_saves_at_once(self):
        page = self.page(scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.day(page, errors)
        posts = self.watch_posts(page)
        box, name = self.present_lane(page, skip=4)
        with page.expect_navigation():
            box.select_option("Sick")
        page.wait_for_load_state("load")
        self.assertEqual(len(posts), 1)
        expect(page.locator(f'.tl-lane select.att[data-name="{name}"]')).to_have_value("Sick")

    def test_one_arrow_does_not_change_the_measure(self):
        page = self.page(scheme="light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.day(page, errors)
        before = page.url
        pick = page.locator("select[name=measure][data-autosubmit]")
        second = pick.locator("option").nth(1).inner_text()
        pick.focus()
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(1500)
        self.assertEqual(page.url, before)
        expect(page.locator("p.pick-note")).to_have_text(f"Press Enter to show {second}, or Esc to go back.")
        with page.expect_navigation():
            page.keyboard.press("Enter")
        self.assertIn("measure=sl", page.url)

    # ---------------------------------------------------------------- Task 5: Home keeps a form in use
    def home_with_a_clock(self):
        """Home, with the page's timers on a clock the test moves; returns the page and its count of later loads."""
        page = self.page(scheme="light")
        self.sign_in(page)
        page.clock.install()
        page.goto(self.base + "/")
        page.wait_for_load_state("load")
        expect(page.locator(".now .ring")).to_have_count(1)
        loads = []
        page.on("load", lambda: loads.append(page.url))
        return page, loads

    def touch_the_form(self, page):
        page.locator("input[name=kind][value=ready]").check()
        page.locator("#newrun input[type=file]").set_input_files(str(self.dir / "ready.xlsx"))

    def test_home_does_not_reload_over_a_form_in_use(self):
        page, loads = self.home_with_a_clock()
        self.touch_the_form(page)
        page.clock.run_for(65000)
        page.wait_for_timeout(1500)
        self.assertEqual(loads, [])
        expect(page.locator("input[name=kind][value=ready]")).to_be_checked()
        self.assertEqual(page.evaluate("document.querySelector('#newrun input[type=file]').files[0].name"), "ready.xlsx")
        expect(page.locator("#newrun form p.paused")).to_have_text(
            "Updates paused while you fill in this form. They start again when you submit it.")

    def test_home_still_refreshes_when_the_form_is_untouched(self):
        page, loads = self.home_with_a_clock()
        with page.expect_event("load"):
            page.clock.run_for(31000)
        page.wait_for_timeout(800)
        self.assertEqual(len(loads), 1)
        expect(page.locator("#newrun form p.paused")).to_have_count(0)

    def test_a_finished_run_says_so_without_reloading(self):
        page, loads = self.home_with_a_clock()
        self.touch_the_form(page)
        self.store.update_run(self.running, status="DONE")
        self.addCleanup(self.store.update_run, self.running, status="RUNNING")
        page.clock.run_for(31000)
        expect(page.locator(".now")).to_contain_text("This schedule finished.")
        expect(page.locator(".now a", has_text="Open it")).to_have_attribute("href", f"/runs/{self.running}")
        self.assertEqual(loads, [])
        self.assertEqual(page.evaluate("document.querySelector('#newrun input[type=file]').files.length"), 1)

    # ---------------------------------------------------------------- Task 6: colour means state; layout fixes
    def look(self, name, width=1280):
        """A signed-in page in one look: night, day (the device's) or day picked with the switch on a dark device."""
        page = self.page(width=width, scheme="light" if name == "day" else "dark")
        self.sign_in(page)
        if name == "picked":
            with page.expect_navigation():
                page.locator("[data-theme-toggle]").click()
            self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "light")
        return page

    def test_rendered_pairs_pass_in_both_looks(self):
        """The Phase Y pairs as the browser draws them (computed colours, see-through panels laid over the page)."""
        q, s = self.q, self.sunday.isoformat()
        checks = [  # page, elements, what is measured, the least contrast
            (f"/day?program={q}&date={s}", "[data-day] .tc.ok", "text", 4.5),
            (f"/day?program={q}&date={s}&view=board", "[data-day] .chip small", "text", 4.5),
            (f"/week?program={q}&week={s}", ".wk.over", "text", 4.5),
            (f"/week?program={q}&week={s}", ".wk.over small", "text", 4.5),
            (f"/schedules/{self.version}/breaks", ".bp-strip .ok", "text", 4.5),
            (f"/runs/{self.run_id}", "main input[type=text], main select", "edge", 3.0),
            (f"/week?program={q}&week={s}", ".wk.covered", "fill", 3.0),
            (f"/week?program={q}&week={s}", ".wk.short", "fill", 3.0),
        ]
        for name in ("night", "day", "picked"):
            page = self.look(name)
            for url, selector, what, least in checks:
                page.goto(self.base + url)
                page.wait_for_load_state("load")
                pairs = page.evaluate(PAIRS_JS, [selector, what])
                self.assertTrue(pairs, f"{name}: nothing matched {selector} on {url}")
                low = sorted({round(contrast(fg, bg), 2) for fg, bg in pairs if contrast(fg, bg) < least})
                self.assertEqual(low, [], f"{name}: {selector} ({what}) on {url}")
            page.goto(self.base + f"/week?program={q}&week={s}")
            link, teal = page.evaluate("[getComputedStyle(document.querySelector('main p a, main td a, main li a')).color,"
                                       " getComputedStyle(document.documentElement).getPropertyValue('--covered')]")
            (l_c, l_h), (_, t_h) = oklch(parse_colour(link)[:3]), oklch(parse_colour(teal)[:3])
            apart = min(abs(l_h - t_h), 360 - abs(l_h - t_h))
            self.assertTrue(l_c < 0.03 or apart >= 15, f"{name}: links ({link}) wear the covered teal ({teal})")

    def test_ticks_are_ink_and_every_field_has_an_edge(self):
        """Proposal.css made every checkbox and radio ink and gave time fields and text areas the field edge too."""
        for name in ("night", "day"):
            page = self.look(name)
            for url, selector, prop, token in (("/exports", "main input[type=checkbox]", "accentColor", "--action"),
                                               ("/", "main input[type=radio]", "accentColor", "--action"),
                                               (f"/schedules/{self.version}/breaks", "main input[type=time]", "borderTopColor", "--edge"),
                                               (f"/setup/with?program={self.q}", "main textarea", "borderTopColor", "--edge")):
                page.goto(self.base + url)
                page.wait_for_load_state("load")
                got = page.evaluate("""([sel, prop, token]) => {
                  const probe = document.createElement('i'); probe.style.color = `var(${token})`; document.body.append(probe);
                  const want = getComputedStyle(probe).color; probe.remove();
                  return [...document.querySelectorAll(sel)].map(el => [getComputedStyle(el)[prop], want]);
                }""", [selector, prop, token])
                self.assertTrue(got, f"{name}: nothing matched {selector} on {url}")
                self.assertEqual({g for g, _ in got}, {got[0][1]}, f"{name}: {selector} {prop} on {url}")

    def test_focus_never_hides_under_the_top_bar(self):
        for width in (1280, 390):
            page = self.page(width=width, height=700, scheme="light")
            self.sign_in(page)
            page.goto(self.base + f"/runs/{self.run_id}/schedules")
            page.wait_for_load_state("load")
            page.keyboard.press("Tab")  # a keyboard user
            page.evaluate("""() => {
              const cells = [...document.querySelectorAll('button.ed')], target = cells[40], next = cells[41];
              window.scrollTo(0, window.scrollY + target.getBoundingClientRect().top - 10);  // on screen, behind the bar
              next.focus({ preventScroll: true });
            }""")
            page.keyboard.press("Shift+Tab")
            page.wait_for_timeout(400)
            top, bar = page.evaluate("[document.activeElement.getBoundingClientRect().top,"
                                     " document.querySelector('header.top').getBoundingClientRect().bottom]")
            self.assertGreaterEqual(top, bar, f"{width} px wide: the focused cell is under the top bar")

    def test_focus_clears_a_top_bar_that_wraps(self):
        """A long name wraps the top bar to two rows on a narrow desktop (83 px at 960 wide); focus still clears it."""
        page = self.page(width=960, height=700, scheme="light")
        self.sign_in(page)
        page.goto(self.base + f"/runs/{self.run_id}/schedules")
        page.wait_for_load_state("load")
        page.evaluate("document.querySelector('header.top .who').textContent ="
                      " 'Abdelrahman Mohamed Abdelaziz Elsayed Ibrahim, supervisor'")
        page.wait_for_timeout(300)
        self.assertGreater(page.evaluate("document.querySelector('header.top').getBoundingClientRect().height"), 72)
        page.keyboard.press("Tab")
        page.evaluate("""() => {  // the cell's top 8 px under the bar's lower edge: past a fixed padding, still covered
          const cells = [...document.querySelectorAll('button.ed')], target = cells[40], next = cells[41];
          const bar = document.querySelector('header.top').getBoundingClientRect().bottom;
          window.scrollTo(0, window.scrollY + target.getBoundingClientRect().top - (bar - 8));
          next.focus({ preventScroll: true });
        }""")
        page.keyboard.press("Shift+Tab")
        page.wait_for_timeout(400)
        top, bar = page.evaluate("[document.activeElement.getBoundingClientRect().top,"
                                 " document.querySelector('header.top').getBoundingClientRect().bottom]")
        self.assertGreaterEqual(top, bar)

    def test_a_focused_break_shows_its_ring(self):
        for name in ("night", "day"):
            page = self.look(name)
            self.day(page, [])
            brk = page.locator("[data-day] rect.brk").first
            brk.focus()
            page.keyboard.press("Shift+Tab")
            page.keyboard.press("Tab")  # reached with the keyboard, so :focus-visible holds
            style = page.evaluate("""() => { const s = getComputedStyle(document.activeElement);
              return [document.activeElement.tagName, s.outlineStyle, s.outlineWidth, s.outlineColor,
                      getComputedStyle(document.documentElement).getPropertyValue('--action')]; }""")
            tag, outline, width, colour, action = style
            self.assertEqual(tag.lower(), "rect")
            self.assertEqual((outline, width), ("solid", "2px"), name)
            self.assertEqual(parse_colour(colour)[:3], parse_colour(action)[:3], name)

    def test_names_fit_on_a_phone(self):
        page = self.page(width=320, height=700, scheme="light")
        self.sign_in(page)
        self.day(page, [])
        cut = page.evaluate("[...document.querySelectorAll('[data-day] .tl-who b')]"
                            ".filter(b => b.scrollWidth > b.clientWidth).map(b => b.textContent)")
        self.assertEqual(cut, [])
        sizes = page.evaluate("[...document.querySelectorAll('[data-day] select.att')].map(s => parseFloat(getComputedStyle(s).fontSize))")
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 16)

    # ---------------------------------------------------------------- Task 7: the screens for the report
    def test_phase_xy_screens(self):
        errors = []
        q, s = self.q, self.sunday.isoformat()
        shots = [  # look, width, url, file, what to show (None: the screen)
            ("night", 1280, "/", "home_night.png", None),
            ("day", 1280, f"/day?program={q}&date={s}", "rta_timeline_day.png", "section:has(#floor-h)"),
            ("night", 1280, f"/day?program={q}&date={s}", "rta_timeline_night.png", "section:has(#floor-h)"),
            ("day", 1280, f"/day?program={q}&date={s}&view=board", "board_day.png", "section:has(#board-h)"),
            ("day", 1280, f"/week?program={q}&week={s}", "week_day.png", None),
            ("night", 1280, f"/runs/{self.run_id}/schedules", "editor_night.png", None),
            ("day", 1280, "/exports", "exports_day.png", None),
        ]
        for look, width, url, name, part in shots:
            page = self.look(look, width=width)
            page.on("pageerror", lambda e: errors.append(str(e)))
            self.go(page, url, errors)
            page.wait_for_timeout(500)
            if part:
                page.locator(part).first.screenshot(path=str(XY_SCREENS / name))
            else:
                page.screenshot(path=str(XY_SCREENS / name))
        # a program the planner does not have: the page says why and who can fix it
        page = self.page(scheme="light")
        self.sign_in(page, "agent", "Agent-pass-123")
        page.goto(self.base + f"/day?program={q}")
        expect(page.locator("main h1")).to_contain_text("is not one of your programs")
        page.screenshot(path=str(XY_SCREENS / "not_your_program.png"))
        # removing a department asks first
        page = self.look("day")
        self.go(page, f"/setup/with?program={q}", errors)
        add = page.locator("form.wl-add").first
        add.get_by_label("Department").fill("Quality")
        add.get_by_label("Name").fill("Associate 090")
        add.get_by_role("button", name="Add").click()
        page.wait_for_load_state("load")
        page.get_by_role("link", name="Remove the department and its people").first.click()
        page.wait_for_load_state("load")
        expect(page.locator(".check-save h2")).to_contain_text("Remove Quality and its 1 person?")
        page.locator(".check-save").screenshot(path=str(XY_SCREENS / "remove_department_check.png"))
        # the skip link, the first stop for a keyboard
        page = self.look("night")
        self.go(page, "/", errors)
        page.keyboard.press("Tab")
        expect(page.locator("a.skip")).to_be_focused()
        page.screenshot(path=str(XY_SCREENS / "skip_link.png"), clip={"x": 0, "y": 0, "width": 640, "height": 160})
        # a phone: whole names on the timeline
        phone = self.page(width=390, height=844, scheme="dark")
        self.sign_in(phone)
        self.go(phone, f"/day?program={q}&date={s}", errors)
        phone.locator(".tl-lane").first.scroll_into_view_if_needed()
        phone.wait_for_timeout(400)
        phone.screenshot(path=str(XY_SCREENS / "phone_timeline.png"))
        self.assertEqual(errors, [])


Z_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_z" / "screens"


class ThePhaseZInTheBrowser(unittest.TestCase):
    """Phase Z (the owner approved samples 01 to 05): a week's schedules in one list, channel needs added to a
    schedule, and today's achievement on the RTA, in a real browser. This week has two uploads for SAKS, NMG Tier 2:
    week.xlsx (breaks planned automatically, in use) and week_v2.xlsx (not in use)."""

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        import io
        import shutil
        from datetime import datetime, timedelta, timezone
        from webapp.programs import ProgramBook
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import sign_in as client_sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        cls.today = datetime.now(timezone(timedelta(hours=3))).date()  # the server's day (Egypt time)
        cls.sunday = cls.today - timedelta(days=(cls.today.weekday() + 1) % 7)
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.q = cls.key.replace(" ", "+")
        cls.client = client = client_sign_in(cls.app, "omar", "Owner-pass-123")
        runs = []
        for name in ("week.xlsx", "week_v2.xlsx"):
            client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK",
                                       "program": cls.key, "week_start": cls.sunday.isoformat(),
                                       "workbook": (io.BytesIO(ready.read_bytes()), name)},
                        content_type="multipart/form-data")
            runs.append(cls.store.list_runs()[0]["id"])
            wait(cls.store, runs[-1], statuses=("DONE", "REJECTED", "FAILED"))
            if name == "week.xlsx":
                first = cls.app.extensions["schedules"].versions(runs[-1])[-1]["id"]
                client.post(f"/schedules/{first}/auto-breaks", data={"csrf_token": token(client), "use": "1"})
        cls.run_id, cls.other = runs
        client.post("/week/target", data={"csrf_token": token(client), "program": cls.key,
                                          "week": cls.sunday.isoformat(), "target": "90"})
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        Z_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    # ---------------------------------------------------------------- Task 6: today's achievement
    def test_the_now_mark_sits_at_the_current_time(self):
        page = self.page(width=1280, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, f"/day?program={self.q}&date={self.today.isoformat()}", errors)
        expect(page.get_by_role("heading", name="Today's achievement")).to_be_visible()
        mark = page.locator(".achv-now")
        expect(mark).to_be_visible()
        strip = page.locator(".achv-strip").bounding_box()
        line = mark.bounding_box()
        minutes = int(page.locator(".achv-strip").get_attribute("data-now"))
        at = (line["x"] + line["width"] / 2 - strip["x"]) / strip["width"]
        self.assertAlmostEqual(at, minutes / 1440, delta=0.01)
        from datetime import timedelta
        other = self.sunday if self.today != self.sunday else self.sunday + timedelta(days=1)  # same week, not today
        self.go(page, f"/day?program={self.q}&date={other.isoformat()}", errors)
        expect(page.get_by_role("heading", name=f"Achievement on {other:%a %d %b}")).to_be_visible()
        expect(page.locator(".achv-now")).to_have_count(0)
        self.assertEqual(errors, [])

    # ---------------------------------------------------------------- Task 7: the screens
    def test_phase_z_screens(self):
        from webapp.tests.test_channel_needs import filled
        page = self.page(width=1440, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        day = self.today.isoformat()
        # Home follows the picked program and the schedule in use; the Runs table tags both uploads
        self.go(page, f"/?program={self.q}", errors)
        expect(page.locator("#latest-h")).to_contain_text("In use for the week of")
        expect(page.locator("table.runs .wl-tag.use")).to_have_count(1)
        expect(page.locator("table.runs .wl-tag.off")).to_have_count(1)
        page.screenshot(path=str(Z_SCREENS / "home_in_use.png"))
        # the week's schedules, from the one not in use
        self.go(page, f"/runs/{self.other}/schedules", errors)
        listed = page.locator("#week-list")
        expect(listed).to_contain_text("Schedules for the week of")
        expect(listed.get_by_role("button", name="Set in use")).to_be_visible()
        page.screenshot(path=str(Z_SCREENS / "schedules_week_list.png"))
        # its Channels panel: three steps, the workbook made for the week, then the needs added
        panel = page.locator("#channels")
        expect(panel).to_contain_text("This schedule has no channel needs yet")
        panel.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        panel.screenshot(path=str(Z_SCREENS / "channels_three_steps.png"))
        with page.expect_download() as got:
            panel.get_by_role("link", name="Download channel needs (.xlsx)").click()
        self.assertTrue(got.value.suggested_filename.startswith("Channel_needs_SAKS_NMG_Tier_2_"))
        panel.get_by_label("Channel needs workbook (.xlsx)").set_input_files(str(filled(self.dir / "needs.xlsx")))
        panel.get_by_role("button", name="Add channel needs").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("Channel needs added to week_v2.xlsx")
        expect(page.locator("#channels")).to_contain_text("From channel needs added on")
        expect(page.locator(".actions").get_by_role("link", name="Plan channels")).to_be_visible()
        page.locator("#channels").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator("#channels").screenshot(path=str(Z_SCREENS / "channels_added.png"))
        # Associate channels says where the needs go
        self.go(page, f"/setup/channels?program={self.q}", errors)
        expect(page.locator(".ch-point")).to_contain_text("open Schedules, then Channels")
        page.screenshot(path=str(Z_SCREENS / "associate_channels_pointer.png"))
        # the Week page links to the other schedule and to the list
        self.go(page, f"/week?program={self.q}&week={self.sunday.isoformat()}", errors)
        # Re-pinned in Phase AA (2026-10-10): approved sample 04 replaced the "See both schedules" sentence with the
        # Week page's Schedule switch, which opens the other schedule and the week's comparison.
        expect(page.get_by_role("group", name="Schedule shown").get_by_role("link", name="week_v2.xlsx")).to_be_visible()
        expect(page.get_by_role("link", name="Compare the week's schedules")).to_be_visible()
        page.screenshot(path=str(Z_SCREENS / "week_page_links.png"))
        # today's achievement on the RTA: the Timeline, then the Interval board, night and day looks
        self.go(page, f"/day?program={self.q}&date={day}", errors)
        expect(page.locator(".achv-now")).to_be_visible()
        expect(page.locator(".tl-row").nth(1)).to_contain_text("Achieved (target 90%)")
        page.screenshot(path=str(Z_SCREENS / "rta_today_achievement.png"))
        self.go(page, f"/day?program={self.q}&date={day}&view=board", errors)
        expect(page.locator(".rb-head")).to_contain_text("Cover (target 90%)")
        expect(page.locator(".rb-c small.ok, .rb-c small.below").first).to_be_visible()
        page.locator(".rb-head").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path=str(Z_SCREENS / "rta_board_at_target.png"))
        light = self.page(width=1440, height=900, scheme="light")
        light.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(light)
        self.go(light, f"/day?program={self.q}&date={day}", errors)
        light.locator(".achv").screenshot(path=str(Z_SCREENS / "rta_today_achievement_day_look.png"))
        # a phone: the block and the schedules list fit without sideways scroll
        phone = self.page(width=390, height=844)
        phone.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(phone)
        for url in (f"/day?program={self.q}&date={day}", f"/runs/{self.other}/schedules",
                    f"/runs/{self.run_id}/schedules"):  # the Channels panel with needs added, then its three steps
            self.go(phone, url, errors)
            self.assertLessEqual(phone.evaluate("document.documentElement.scrollWidth"), 390, url)
        narrow = self.page(width=320, height=700)
        self.sign_in(narrow)
        self.go(narrow, f"/runs/{self.run_id}/schedules", errors)
        self.assertLessEqual(narrow.evaluate("document.documentElement.scrollWidth"), 320)
        self.go(phone, f"/day?program={self.q}&date={day}", errors)
        phone.locator(".achv").scroll_into_view_if_needed()
        phone.wait_for_timeout(300)
        phone.screenshot(path=str(Z_SCREENS / "phone_rta_achievement.png"))
        self.assertEqual(errors, [])


AA_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_aa" / "screens"


class ThePhaseAAInTheBrowser(unittest.TestCase):
    """Phase AA (the owner approved samples 01 to 04): overtime before or after the shift, deleting a schedule that is
    not needed, the Schedules page by week, and the Week page's schedule switch, in a real browser. This week for
    SAKS, NMG Tier 2 has week.xlsx (breaks planned, in use), week_v2.xlsx and week_v3.xlsx; next week has one."""

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go

    @classmethod
    def setUpClass(cls):
        import io
        import shutil
        from datetime import datetime, timedelta, timezone
        from webapp.programs import ProgramBook
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import sign_in as client_sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        today = datetime.now(timezone(timedelta(hours=3))).date()
        cls.sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        cls.wed = cls.sunday + timedelta(days=3)
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.q = cls.key.replace(" ", "+")
        client = client_sign_in(cls.app, "omar", "Owner-pass-123")
        runs = {}
        for name, week in (("week.xlsx", cls.sunday), ("week_v2.xlsx", cls.sunday), ("week_v3.xlsx", cls.sunday),
                           ("week_next.xlsx", cls.sunday + timedelta(days=7))):
            client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK",
                                       "program": cls.key, "week_start": week.isoformat(),
                                       "workbook": (io.BytesIO(ready.read_bytes()), name)},
                        content_type="multipart/form-data")
            runs[name] = cls.store.list_runs()[0]["id"]
            wait(cls.store, runs[name], statuses=("DONE", "REJECTED", "FAILED"))
        first = cls.app.extensions["schedules"].versions(runs["week.xlsx"])[-1]["id"]
        client.post(f"/schedules/{first}/auto-breaks", data={"csrf_token": token(client), "use": "1"})
        cls.runs = runs
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        AA_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def test_overtime_before_or_after_the_shift(self):
        page = self.page(width=1280, height=1000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        self.go(page, f"/day?program={self.q}&date={self.wed.isoformat()}&view=board&add=480&person=Associate+021",
                errors)
        dialog = page.locator("#add-dialog")
        dialog.get_by_label("Overtime").check()
        expect(dialog.locator("[data-from-label]")).to_be_hidden()
        expect(dialog.locator("[data-ot-shift]")).to_have_text("Associate 021's shift today: 08:00 to 17:00.")
        expect(dialog.locator("[data-ot-time=before]")).to_have_text("07:00 to 08:00")
        dialog.locator("select[name=minutes]").select_option("30")
        expect(dialog.locator("[data-ot-time=before]")).to_have_text("07:30 to 08:00")
        dialog.get_by_label("After the shift").check()
        expect(dialog.locator("[data-ot-time=after]")).to_have_text("17:00 to 17:30")
        expect(dialog.locator("[data-effect]")).to_contain_text("Overtime 17:00 to 17:30")
        dialog.screenshot(path=str(AA_SCREENS / "overtime_before_or_after.png"))
        dialog.get_by_role("button", name="Add overtime").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("Recorded: Associate 021, Overtime 17:00 to 17:30.")
        self.assertEqual(errors, [])

    def test_phase_aa_screens(self):
        page = self.page(width=1440, height=900)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        week = self.sunday.isoformat()
        # the menu's Schedules: the week picker and the week's schedules side by side
        self.go(page, f"/schedules?program={self.q}&week={week}", errors)
        expect(page.locator("nav.weekpick a[aria-current]")).to_contain_text("3 schedules")
        expect(page.locator("table.cmp thead th b")).to_have_count(3)
        expect(page.locator("table.cmp thead th b").first).to_have_text("week.xlsx")
        page.screenshot(path=str(AA_SCREENS / "schedules_by_week.png"), full_page=True)
        # the Week page's switch, then the other schedule's week with Set in use
        self.go(page, f"/week?program={self.q}&week={week}", errors)
        switch = page.get_by_role("group", name="Schedule shown")
        expect(switch.locator("a[aria-current]")).to_contain_text("week.xlsx")
        page.locator("div.phead").screenshot(path=str(AA_SCREENS / "week_switch.png"))
        switch.get_by_role("link", name="week_v2.xlsx").click()
        page.wait_for_load_state("load")
        expect(page.get_by_role("button", name="Set week_v2.xlsx in use")).to_be_visible()
        page.locator("div.phead").screenshot(path=str(AA_SCREENS / "week_switch_not_in_use.png"))
        # delete: the tick is required, then the week's page opens without it
        self.go(page, f"/runs/{self.runs['week_v3.xlsx']}/schedules#delete", errors)
        section = page.locator("#delete")
        section.scroll_into_view_if_needed()
        section.screenshot(path=str(AA_SCREENS / "delete_section.png"))
        section.get_by_role("button", name="Delete schedule").click()
        page.wait_for_timeout(400)
        self.assertIn(f"/runs/{self.runs['week_v3.xlsx']}/schedules", page.url)  # the browser asks for the tick
        self.assertIsNotNone(self.store.get_run(self.runs["week_v3.xlsx"]))
        section.locator("input[name=confirm]").check()
        section.get_by_role("button", name="Delete schedule").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_contain_text("Deleted week_v3.xlsx and its 1 version.")
        expect(page.locator("table.cmp thead th b")).to_have_count(2)
        page.screenshot(path=str(AA_SCREENS / "after_delete.png"))
        # phones: no sideways scroll
        for width in (390, 320):
            phone = self.page(width=width, height=800)
            phone.on("pageerror", lambda e: errors.append(str(e)))
            self.sign_in(phone)
            for url in (f"/schedules?program={self.q}&week={week}", f"/week?program={self.q}&week={week}",
                        f"/runs/{self.runs['week_v2.xlsx']}/schedules"):
                self.go(phone, url, errors)
                self.assertLessEqual(phone.evaluate("document.documentElement.scrollWidth"), width, f"{width} {url}")
            if width == 390:
                self.go(phone, f"/schedules?program={self.q}&week={week}", errors)
                phone.screenshot(path=str(AA_SCREENS / "phone_schedules_by_week.png"))
        self.assertEqual(errors, [])


AB_SCREENS = Path(__file__).resolve().parents[2] / "evidence" / "phase_ab" / "screens"


class ThePhaseABInTheBrowser(unittest.TestCase):
    """Phase AB (the owner approved samples 01 to 04 and said "Start the Teams/Slack notifications now"): the
    Notifications page, and RTA changes reaching a Slack group, in a real browser. The group is a fake that records
    what it receives; the link is a made-up Slack link."""

    page = InTheBrowser.page
    sign_in = InTheBrowser.sign_in
    go = ThePhaseRInTheBrowser.go
    SLACK = "https://hooks.slack.com/services/T0000/B0000/abcdEFGHijkl"

    @classmethod
    def setUpClass(cls):
        import io
        import shutil
        from datetime import datetime, timedelta, timezone
        from webapp.programs import ProgramBook
        from webapp.tests.test_notify_sender import Group
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import sign_in as client_sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        cls.today = datetime.now(timezone(timedelta(hours=3))).date()
        sunday = cls.today - timedelta(days=(cls.today.weekday() + 1) % 7)
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.group = Group()
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO), NOTIFY_THREAD=False, NOTIFY_TRANSPORT=cls.group)
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.q = cls.key.replace(" ", "+")
        client = client_sign_in(cls.app, "omar", "Owner-pass-123")
        client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": cls.key,
                                   "week_start": sunday.isoformat(),
                                   "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                    content_type="multipart/form-data")
        run = cls.store.list_runs()[0]["id"]
        wait(cls.store, run, statuses=("DONE", "REJECTED", "FAILED"))
        first = cls.app.extensions["schedules"].versions(run)[-1]["id"]
        client.post(f"/schedules/{first}/auto-breaks", data={"csrf_token": token(client), "use": "1"})
        cls.server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        launch = {"headless": True}
        if os.path.exists(CHROMIUM):
            launch["executable_path"] = CHROMIUM
        cls.browser = cls.pw.chromium.launch(**launch)
        AB_SCREENS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def move_a_break(self, page, errors, tick):
        """Open the first break of someone not moved yet, set the tick, move it 5 minutes later; the log line."""
        day = f"/day?program={self.q}&date={self.today.isoformat()}"
        done = {e["associate"] for e in self.store.list_day_log(self.key, self.today.isoformat())}
        for rect in page.locator(f'rect.brk[data-date="{self.today.isoformat()}"]').all():
            name = rect.get_attribute("data-name")
            if name in done:
                continue
            rect.focus()
            page.keyboard.press("Enter")
            dialog = page.locator("#break-dialog")
            expect(dialog).to_be_visible()
            box = dialog.locator("input[name=post]")
            expect(box).to_be_checked()
            if not tick:
                box.uncheck()
            dialog.locator("[data-step='5']").click()
            dialog.locator("[data-keep]").click()
            try:
                expect(page.locator("#daylog-h + ul.log")).to_contain_text(name, timeout=8000)
                page.wait_for_load_state("load")  # the reloaded page's script is attached
                return name
            except AssertionError:
                self.go(page, day, errors)
        self.fail("no break could be moved")

    def test_notifications_page_and_rta_posts(self):
        import time as clock
        page = self.page(width=1440, height=1000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.sign_in(page)
        # the page before any link
        self.go(page, "/notifications", errors)
        expect(page.locator("h1")).to_have_text("Notifications")
        expect(page.locator("table.nf-lobs")).to_contain_text("No group link yet")
        page.screenshot(path=str(AB_SCREENS / "notifications_empty.png"), full_page=True)
        # save a Slack link: shown again only by its end
        page.fill("input[name=link]", self.SLACK)
        page.get_by_label("On", exact=False).first.check()
        page.get_by_role("button", name="Save").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_have_text("Notifications saved for SAKS, NMG Tier 2.")
        expect(page.locator("#nf-link-said")).to_contain_text("Ends in …ijkl.")
        self.assertEqual(page.locator("input[name=link]").input_value(), "")
        self.assertNotIn("abcdEFGH", page.content())
        # the test message reaches the group, and says so
        page.get_by_role("button", name="Send test message").click()
        page.wait_for_load_state("load")
        expect(page.locator("p.flash").first).to_have_text("Test message posted to Slack.")
        expect(page.locator("table.nf-recent")).to_contain_text("Posted to Slack")
        self.assertEqual(self.group.calls[-1][0], self.SLACK)
        page.screenshot(path=str(AB_SCREENS / "notifications_saved.png"), full_page=True)
        # on the RTA: one break move posted, one left out with the tick
        day = f"/day?program={self.q}&date={self.today.isoformat()}"
        self.go(page, day, errors)
        posted = self.move_a_break(page, errors, tick=True)
        left = self.move_a_break(page, errors, tick=False)
        expect(page.locator("#daylog-h + ul.log .post-st.waiting").first).to_contain_text("Waiting: posts by")
        calls = len(self.group.calls)
        self.app.extensions["notifier"].run_once(clock.time() + 200)
        self.assertEqual(len(self.group.calls), calls + 1)
        sent = str(self.group.calls[-1][1])
        self.assertIn(posted, sent)
        self.assertNotIn(left, sent)
        self.go(page, day, errors)
        log = page.locator("#daylog-h + ul.log")
        expect(log.locator("li", has_text=posted).locator(".post-st.sent")).to_contain_text("Posted to Slack, ")
        expect(log.locator("li", has_text=left).locator(".post-st.skipped")).to_have_text(
            "Not posted: left out on the RTA")
        page.locator("section[aria-labelledby=daylog-h]").screenshot(path=str(AB_SCREENS / "changes_today.png"))
        # the break dialog with its tick
        page.locator(f'rect.brk[data-date="{self.today.isoformat()}"]').first.focus()
        page.keyboard.press("Enter")
        page.locator("#break-dialog").screenshot(path=str(AB_SCREENS / "break_dialog_tick.png"))
        page.locator("#break-dialog [data-cancel]").click()
        # the last post, as the group saw it
        self.go(page, "/notifications", errors)
        expect(page.locator("section.nf-last")).to_contain_text(posted)
        expect(page.locator("table.nf-lobs")).to_contain_text("Posted 1 change at")
        page.screenshot(path=str(AB_SCREENS / "notifications_last_post.png"), full_page=True)
        # phones: no sideways scroll
        for width in (390, 320):
            phone = self.page(width=width, height=800)
            phone.on("pageerror", lambda e: errors.append(str(e)))
            self.sign_in(phone)
            for url in ("/notifications", day):
                self.go(phone, url, errors)
                self.assertLessEqual(phone.evaluate("document.documentElement.scrollWidth"), width, f"{width} {url}")
            if width == 390:
                self.go(phone, "/notifications", errors)
                phone.screenshot(path=str(AB_SCREENS / "phone_notifications.png"), full_page=True)
        self.assertEqual(errors, [])
