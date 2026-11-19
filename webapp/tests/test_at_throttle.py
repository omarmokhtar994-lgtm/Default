# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AT (owner, 2026-10-21: yes to a sign-in limit): one account already locks for 15 minutes after 5 wrong passwords.
This adds the other half: one address trying many usernames (password spraying) is held for 15 minutes after 40 wrong
sign-ins, and a right password from that address is not accepted while it is held."""
import re
import unittest

from webapp.tests.test_runs import make_app
from webapp.throttle import SignInThrottle

PASSWORD = "Right-pass-12345"


class TheLimiter(unittest.TestCase):
    def test_it_holds_an_address_after_the_limit_and_frees_it_after_the_window(self):
        t = SignInThrottle(limit=3, seconds=100)
        for _ in range(2):
            t.failed("10.0.0.1", now=0)
        self.assertFalse(t.held("10.0.0.1", now=1))
        t.failed("10.0.0.1", now=2)
        self.assertTrue(t.held("10.0.0.1", now=3))
        self.assertFalse(t.held("10.0.0.2", now=3))      # another address is not held
        self.assertFalse(t.held("10.0.0.1", now=103))    # the window has passed

    def test_old_failures_stop_counting(self):
        t = SignInThrottle(limit=3, seconds=100)
        t.failed("a", now=0)
        t.failed("a", now=1)
        t.failed("a", now=150)
        self.assertFalse(t.held("a", now=151))

    def test_the_table_does_not_grow_without_end(self):
        t = SignInThrottle(limit=3, seconds=100)
        for n in range(5000):
            t.failed(f"10.1.{n // 250}.{n % 250}", now=0)
        t.failed("late", now=1000)
        self.assertLess(len(t._seen), 5)


class ThePage(unittest.TestCase):
    def setUp(self):
        self.app, self.store, *_ = make_app(start_worker=False)
        self.store.add_user("pat", "Pat", PASSWORD, must_change=False)
        self.app.extensions["throttle"].limit = 4

    def attempt(self, user, password, addr="203.0.113.7"):
        client = self.app.test_client()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
        return client.post("/login", data={"username": user, "password": password, "csrf_token": tok},
                           environ_base={"REMOTE_ADDR": addr})

    def test_many_usernames_from_one_address_are_held_and_even_the_right_password_waits(self):
        for n in range(4):
            self.assertEqual(self.attempt(f"nobody{n}", "x").status_code, 200)
        got = self.attempt("pat", PASSWORD)
        self.assertEqual(got.status_code, 429)
        self.assertIn("Too many sign-in attempts", got.get_data(as_text=True))
        self.assertNotIn("Location", got.headers)

    def test_another_address_is_not_held_and_a_right_password_signs_in(self):
        for n in range(4):
            self.attempt(f"nobody{n}", "x")
        self.assertEqual(self.attempt("pat", PASSWORD, addr="203.0.113.99").status_code, 302)

    def test_right_passwords_never_count(self):
        for _ in range(10):
            self.assertEqual(self.attempt("pat", PASSWORD).status_code, 302)


class TheHistory(ThePage):
    """Phase AU: who signed in, who failed and from where, for the admin; never a password, never a typed username that
    is not an account (it may be a password typed in the wrong box)."""
    def events(self, kind):
        return [e for e in self.store.list_events(0, 9e12, None, None) if e["kind"] == kind]

    def test_a_sign_in_a_wrong_password_and_a_held_address_are_recorded_without_secrets(self):
        self.attempt("pat", "Wrong-pass-999")
        self.attempt("not-an-account-Typed-A-Password-1", "x")
        self.attempt("pat", PASSWORD, addr="203.0.113.50")
        self.assertEqual([e["subject"] for e in self.events("sign_in_failed")], ["pat", "(no such username)"])
        self.assertEqual([e["subject"] for e in self.events("signed_in")], ["pat"])
        for _ in range(5):
            self.attempt("nobody", "x")
        self.attempt("pat", PASSWORD)
        self.assertTrue(self.events("sign_in_held"))
        everything = " ".join(str(v) for e in self.store.list_events(0, 9e12, None, None) for v in e.values())
        self.assertNotIn("Wrong-pass-999", everything)
        self.assertNotIn(PASSWORD, everything)
        self.assertNotIn("Typed-A-Password", everything)
        self.assertIn("203.0.113.7", " ".join(e["detail"] for e in self.events("sign_in_failed")))

    def test_the_admin_sees_the_held_addresses_and_lifts_one(self):
        admin = self.store.add_user("boss", "Boss", PASSWORD, must_change=False)
        self.store.update_user(admin, is_admin=1)
        for n in range(4):
            self.attempt(f"nobody{n}", "x")
        client = self.app.test_client()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
        client.post("/login", data={"username": "boss", "password": PASSWORD, "csrf_token": tok},
                    environ_base={"REMOTE_ADDR": "203.0.113.200"})
        page = client.get("/admin/users", environ_base={"REMOTE_ADDR": "203.0.113.200"}).get_data(as_text=True)
        self.assertIn("203.0.113.7", page)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        client.post("/admin/signins/release", data={"csrf_token": csrf, "address": "203.0.113.7"},
                    environ_base={"REMOTE_ADDR": "203.0.113.200"})
        self.assertEqual(self.attempt("pat", PASSWORD).status_code, 302)

    def test_only_an_admin_lifts_a_hold(self):
        self.store.add_user("sup", "Sup", PASSWORD, must_change=False)
        self.store.update_user(self.store.get_user_by_username("sup")["id"] if hasattr(self.store, "get_user_by_username")
                               else next(u for u in self.store.list_users() if u["username"] == "sup")["id"], is_supervisor=1)
        client = self.app.test_client()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
        client.post("/login", data={"username": "sup", "password": PASSWORD, "csrf_token": tok})
        page = client.get("/admin/users").get_data(as_text=True)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        got = client.post("/admin/signins/release", data={"csrf_token": csrf, "address": "203.0.113.7"})
        self.assertEqual(got.status_code, 403)


if __name__ == "__main__":
    unittest.main()
