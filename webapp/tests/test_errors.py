# © 2026 Omar Mokhtar. All rights reserved.
"""Phase XY (review finding 6, owner-approved sample 6): an error page says why and what to do next."""
import html
import unittest

from webapp.programs import ProgramBook


class TheErrorPages(unittest.TestCase):
    def setUp(self):
        from webapp.tests.test_runs import make_app, sign_in
        self.app, self.store, *_ = make_app(start_worker=False)
        self.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(self.store)
        self.saks = programs.add_program("SAKS")
        self.tier2 = programs.add_lob(self.saks, "NMG Tier 2")
        nour = self.store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)
        self.store.update_user(nour, is_supervisor=1)
        self.store.set_user_programs(nour, [self.saks])
        self.store.add_user("lina", "Lina", "Lina-pass-123", must_change=False)  # a planner with no program
        self.sup = sign_in(self.app, "nour", "Nour-pass-123")
        self.planner = sign_in(self.app, "lina", "Lina-pass-123")

    def get(self, client, url):
        got = client.get(url)
        return got.status_code, html.unescape(got.get_data(as_text=True))

    def test_a_program_you_do_not_have_says_so_and_who_can_fix_it(self):
        code, page = self.get(self.planner, "/day?program=" + self.tier2.replace(" ", "+"))
        self.assertEqual(code, 403)
        self.assertIn("SAKS, NMG Tier 2 is not one of your programs", page)
        self.assertIn("Ask an admin to add this one to your programs.", page)
        self.assertNotIn("This page is for admins.", page)

    def test_a_made_up_program_is_not_repeated_back(self):
        """Final review: the heading names only a real program or LOB, so a crafted link cannot put its own words
        in the site's heading."""
        code, page = self.get(self.planner, "/day?program=Your+password+expired.+Call+IT+on+0100")
        self.assertEqual(code, 403)
        self.assertIn("This program is not one of your programs", page)
        self.assertNotIn("Your password expired", page)

    def test_a_page_for_admins_and_supervisors_says_so(self):
        code, page = self.get(self.planner, "/admin/users")
        self.assertEqual(code, 403)
        self.assertIn("Only admins and supervisors can open this page.", page)

    def test_a_page_for_admins_says_so(self):
        code, page = self.get(self.sup, "/setup/programs")
        self.assertEqual(code, 403)
        self.assertIn("Only admins can open this page.", page)

    def test_a_missing_page_says_so_and_offers_home(self):
        code, page = self.get(self.planner, "/nothing-here")
        self.assertEqual(code, 404)
        self.assertIn("This page does not exist.", page)
        self.assertIn("The link may be old, or the page moved.", page)
        self.assertRegex(page, r'<a [^>]*href="/"[^>]*>Go to Home</a>')
        self.assertNotIn("Back to runs", page)


if __name__ == "__main__":
    unittest.main()
