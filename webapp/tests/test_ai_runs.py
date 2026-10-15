# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15): runs are seen by program.

"supervisor see everything based on accounts assigned, not my run if 2 have access for saks for example both can
download anything for saks"; for other programs "they can only see if something is running, count of queued and how
much time they will wait". Admins see every run. Made-up names.
"""
import re
import shutil
import time
import unittest

from webapp.programs import ProgramBook
from webapp.tests.test_runs import make_app, sign_in


class RunsByProgram(unittest.TestCase):
    def setUp(self):
        self.app, self.store, self.data, _ = make_app(start_worker=False)
        self.addCleanup(shutil.rmtree, self.data, True)
        programs = ProgramBook(self.store)
        saks = programs.add_program("SAKS")
        self.saks = programs.add_lob(saks, "NMG Tier 2")
        gdi = programs.add_program("GDI")
        self.gdi = programs.add_lob(gdi, "Chat")
        users = {}
        for name in ("lead1", "lead2", "lead3"):
            users[name] = self.store.add_user(name, name.capitalize(), "Staff-pass-123", must_change=False)
            self.store.update_user(users[name], is_supervisor=1)
        self.store.set_user_programs(users["lead1"], [saks])
        self.store.set_user_programs(users["lead2"], [saks])
        self.store.set_user_programs(users["lead3"], [gdi])
        self.store.add_user("boss", "Boss", "Owner-pass-123", is_admin=True, must_change=False)
        now = time.time()
        self.store.add_run("5a0000000001", users["lead2"], "saks-week.xlsx", "READY", "DONE", program=self.saks,
                           week_start="2026-10-11")
        self.store.add_run("9d0000000001", users["lead3"], "gdi-week.xlsx", "QUICK", "RUNNING", program=self.gdi,
                           week_start="2026-10-11")
        self.store.update_run("9d0000000001", started=now - 120)
        self.store.add_run("9d0000000002", users["lead3"], "gdi-next.xlsx", "QUICK", "QUEUED", program=self.gdi,
                           week_start="2026-10-18")
        self.store.add_run("5a0000000002", users["lead2"], "saks-next.xlsx", "QUICK", "QUEUED", program=self.saks,
                           week_start="2026-10-18")
        self.store.update_run("5a0000000002", created=now + 1)  # in line after GDI's

    def home(self, who, password="Staff-pass-123"):
        return sign_in(self.app, who, password).get("/?all=1").get_data(as_text=True)

    def test_the_programs_runs_whoever_ran_them(self):
        html = self.home("lead1")
        self.assertIn("saks-week.xlsx", html)  # lead2 ran it; lead1 has SAKS too
        client = sign_in(self.app, "lead1", "Staff-pass-123")
        self.assertEqual(client.get("/runs/5a0000000001").status_code, 200)
        self.assertNotIn("gdi-week.xlsx", html)
        self.assertNotIn("gdi-next.xlsx", html)
        self.assertIn(client.get("/runs/9d0000000001").status_code, (403, 404))

    def test_other_programs_only_as_running_queued_and_the_wait(self):
        html = self.home("lead1")
        now = re.search(r'<section class="now".*?</section>', html, re.S).group(0)
        self.assertNotIn("Nothing running", now)
        self.assertIn("A run for another program is running", now)
        self.assertIn("2 waiting", now)
        self.assertIn("A workbook for another program", now)
        self.assertRegex(now, r"A new run would start in about \d")
        self.assertNotIn("Lead3", now)

    def test_admins_see_every_run(self):
        html = self.home("boss", "Owner-pass-123")
        for name in ("saks-week.xlsx", "gdi-week.xlsx", "gdi-next.xlsx", "saks-next.xlsx"):
            self.assertIn(name, html)
        now = re.search(r'<section class="now".*?</section>', html, re.S).group(0)
        self.assertNotIn("another program", now)


if __name__ == "__main__":
    unittest.main()
