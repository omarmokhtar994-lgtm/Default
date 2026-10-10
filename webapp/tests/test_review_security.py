# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AC (deep review, findings 1 and 3): after signing in, and after picking a look, the website only ever sends
people to its own pages; and a new password ends the sessions opened with the old one (an admin's reset signs the
person out everywhere; changing your own keeps only the device you changed it on)."""
import re
import unittest
from urllib.parse import quote

from webapp.tests.test_runs import TOKEN, make_app, sign_in, token

OFF_SITE = ["/\texample.com", "/\t/example.com", "/\n/example.com", "/\r/example.com", "//example.com",
            "/\\example.com", "/\\\\example.com", "https://example.com", " /\t/example.com"]


class _Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(START_WORKER=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.nour = cls.store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)

    def sign_in_to(self, nxt, user="omar", password="Owner-pass-123"):
        client = self.app.test_client()
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        return client.post("/login?next=" + quote(nxt, safe=""),
                           data={"username": user, "password": password, "csrf_token": tok})


class TheRedirects(_Site):
    def test_sign_in_never_redirects_off_site(self):
        for nxt in OFF_SITE:
            with self.subTest(next=repr(nxt)):
                got = self.sign_in_to(nxt)
                self.assertEqual(got.status_code, 302)
                self.assertEqual(got.headers["Location"], "/")
        kept = self.sign_in_to("/day?program=SAKS+NMG+Tier+2&date=2026-10-14")
        self.assertEqual(kept.headers["Location"], "/day?program=SAKS+NMG+Tier+2&date=2026-10-14")

    def test_theme_never_redirects_off_site(self):
        client = sign_in(self.app, "omar", "Owner-pass-123")
        for nxt in OFF_SITE:
            with self.subTest(next=repr(nxt)):
                got = client.post("/theme", data={"csrf_token": token(client), "theme": "dark", "next": nxt})
                self.assertEqual(got.headers["Location"], "/")
        got = client.post("/theme", data={"csrf_token": token(client), "theme": "dark", "next": "/week?program=X"})
        self.assertEqual(got.headers["Location"], "/week?program=X")


class TheSessions(_Site):
    def signed_in(self, client):
        got = client.get("/")
        return got.status_code == 200 and "/login" not in got.headers.get("Location", "")

    def test_password_reset_ends_other_sessions(self):
        user = self.store.add_user("sami", "Sami", "Sami-pass-123", must_change=False)
        laptop = sign_in(self.app, "sami", "Sami-pass-123")
        self.assertTrue(self.signed_in(laptop))
        admin = sign_in(self.app, "omar", "Owner-pass-123")
        page = admin.get(f"/admin/users?edit={user}").get_data(as_text=True)
        got = admin.post(f"/admin/users/{user}/reset", data={"csrf_token": TOKEN.search(page).group(1)})
        self.assertIn(got.status_code, (200, 302, 303))
        self.assertNotEqual(self.store.authenticate("sami", "Sami-pass-123")[1], "ok")  # the reset happened
        after = laptop.get("/")
        self.assertEqual(after.status_code, 302)
        self.assertIn("/login", after.headers["Location"])

    def test_own_password_change_keeps_this_session(self):
        self.store.add_user("lina", "Lina", "Lina-pass-123", must_change=False)
        phone = sign_in(self.app, "lina", "Lina-pass-123")
        desk = sign_in(self.app, "lina", "Lina-pass-123")
        page = desk.get("/account/password").get_data(as_text=True)
        got = desk.post("/account/password", data={"csrf_token": TOKEN.search(page).group(1),
                                                   "current": "Lina-pass-123", "new": "Blue-river-4567",
                                                   "confirm": "Blue-river-4567"})
        self.assertEqual(got.status_code, 302)
        self.assertTrue(self.signed_in(desk))
        gone = phone.get("/")
        self.assertEqual(gone.status_code, 302)
        self.assertIn("/login", gone.headers["Location"])

    def test_sessions_from_before_the_upgrade_stay(self):
        client = sign_in(self.app, "nour", "Nour-pass-123")
        with client.session_transaction() as s:
            s.pop("pw", None)  # a session opened before Phase AC carries no stamp
        self.assertTrue(self.signed_in(client))
        with client.session_transaction() as s:
            self.assertTrue(s.get("pw"))


if __name__ == "__main__":
    unittest.main()
