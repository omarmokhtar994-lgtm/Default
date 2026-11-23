# © 2026 Omar Mokhtar. All rights reserved.
"""The audit must reject private data while accepting the established AM routes."""
import unittest

from tools.review_website_routes import ODD_MARKERS, access_leak


class TheRouteAudit(unittest.TestCase):
    def leak(self, who, url, body="", status=200):
        return access_leak(who, url, status, body, "SAKS+NMG", "Other+Program", ["private-run"], 1)

    def test_home_without_programs_is_accessible_but_must_not_expose_runs(self):
        self.assertFalse(self.leak("zed", "/?program=SAKS+NMG", "No runs"))
        self.assertTrue(self.leak("zed", "/?program=SAKS+NMG", '<a href="/runs/private-run">Private</a>'))

    def test_supervisors_may_manage_planners_but_not_the_owner(self):
        self.assertFalse(self.leak("sup", "/admin/users", '<a href="/admin/users?edit=2">Planner</a>'))
        self.assertTrue(self.leak("sup", "/admin/users", '<a href="/admin/users?edit=1">Owner</a>'))

    def test_planners_cannot_get_the_people_page(self):
        self.assertTrue(self.leak("nour", "/admin/users"))
        self.assertFalse(self.leak("nour", "/admin/users", status=403))

    def test_private_day_and_anonymous_home_still_fail(self):
        self.assertTrue(self.leak("zed", "/day?program=SAKS+NMG"))
        self.assertTrue(self.leak("anon", "/"))
        self.assertFalse(self.leak("anon", "/static/app.css"))

    def test_empty_state_text_is_valid_but_template_and_error_text_are_not(self):
        self.assertFalse(any(marker in "Language gaps <b>None</b>" for marker in ODD_MARKERS))
        for body in ("Traceback", "{{ broken }}", "Undefined", "NaN", "nan%"):
            with self.subTest(body=body):
                self.assertTrue(any(marker in body for marker in ODD_MARKERS))


if __name__ == "__main__":
    unittest.main()
