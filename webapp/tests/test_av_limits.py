# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: restrict the heavy pages to a limited number of weeks for everyone except admins,
supervisors and the RTA, as a setting; recommend a value). Made-up users."""
import unittest

from webapp.tests import test_cancel_break as _cb
from webapp.tests.test_runs import sign_in, token


class TheLimit(_cb.ThePage):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tm = cls.store.add_user("tm07", "Team Manager 07", "Manager-pass-123", must_change=False)
        cls.store.update_user(cls.tm, is_team_manager=1)
        pid = cls.app.extensions["store"].list_programs()[0]["id"]
        cls.store.set_user_programs(cls.tm, [pid])
        cls.tm_client = sign_in(cls.app, "tm07", "Manager-pass-123")

    def setUp(self):
        self.addCleanup(self.store.set_app_setting, "heavy_weeks", "13")

    def url(self, page, weeks):
        unit = self.key.replace(" ", "+")
        return f"/{page}?program={unit}&from=2026-07-01&to=2026-{'09-30' if weeks > 12 else '08-12'}"

    def test_the_default_is_13_weeks_for_a_team_manager_and_unlimited_for_an_admin(self):
        long = f"/incidents?program={self.key.replace(' ', '+')}&from=2026-01-01&to=2026-10-14"
        self.assertIn("up to 13 weeks", self.tm_client.get(long).get_data(as_text=True))
        self.assertNotIn("up to 13 weeks", self.client.get(long).get_data(as_text=True))

    def test_an_admin_can_set_the_weeks_and_it_applies_to_both_pages_and_exports(self):
        got = self.client.post("/setup/programs", data={"csrf_token": token(self.client), "action": "heavy_pages", "weeks": "6"},
                               follow_redirects=True)
        self.assertIn("up to 6 weeks", got.get_data(as_text=True))
        for page in ("incidents", "shrinkage"):
            text = self.tm_client.get(f"/{page}?from=2026-08-01&to=2026-10-14").get_data(as_text=True)
            self.assertIn("up to 6 weeks", text, page)
        got = self.tm_client.get("/exports/download?from=2026-08-01&to=2026-10-14&kind=attendance&format=xlsx")
        self.assertEqual(got.status_code, 400)
        self.assertIn("up to 6 weeks", got.get_data(as_text=True))
        short = self.tm_client.get("/exports/download?from=2026-10-01&to=2026-10-14&kind=attendance&format=xlsx")
        self.assertEqual(short.status_code, 200)

    def test_the_setting_is_checked_and_the_page_recommends_6(self):
        page = self.client.get("/setup/programs").get_data(as_text=True)
        self.assertIn("Recommended: 6 weeks", page)
        got = self.client.post("/setup/programs", data={"csrf_token": token(self.client), "action": "heavy_pages", "weeks": "0"},
                               follow_redirects=True)
        self.assertIn("whole number of weeks from 1 to 52", got.get_data(as_text=True))
        self.assertEqual(self.store.get_app_setting("heavy_weeks", "13"), "13")

    def test_a_team_manager_cannot_change_it(self):
        got = self.tm_client.post("/setup/programs", data={"csrf_token": token(self.tm_client), "action": "heavy_pages", "weeks": "52"})
        self.assertIn(got.status_code, (302, 403))
        self.assertEqual(self.store.get_app_setting("heavy_weeks", "13"), "13")


if __name__ == "__main__":
    unittest.main()
