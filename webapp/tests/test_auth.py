# © 2026 Omar Mokhtar. All rights reserved.
"""Phase I task 1: per-person logins and the security around them.

Owner, 2026-10-07: "Login per person". Pinned here: login/logout, a forced
password change on first login, lockout after repeated failures, disabled
users, admin-only user management, CSRF on every form, hashed passwords,
cookie flags, and the copyright line on the login page.
"""
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from webapp.app import create_app
from webapp.store import Store

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def make_app(**extra):
    data = Path(tempfile.mkdtemp())
    config = {"DATA_DIR": str(data), "SECRET_KEY": "test-secret", "TESTING": True, "HTTPS": False,
              "START_WORKER": False}
    config.update(extra)
    app = create_app(config)
    store = Store(data / "scheduler.db")
    store.add_user("admin", "Owner", "Admin-pass-1", is_admin=True)
    store.add_user("sara", "Sara", "Sara-pass-1")
    return app, store


def token(client, path="/login"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password,
                                       "csrf_token": token(client)}, follow_redirects=False)


def logged_in(app, username, password):
    client = app.test_client()
    login(client, username, password)
    # First login forces a password change; finish it so the session is usable.
    if client.get("/").status_code == 302 and "/account/password" in client.get("/").headers["Location"]:
        client.post("/account/password", data={"current": password, "new": "Fresh-Secret-42", "confirm": "Fresh-Secret-42",
                                               "csrf_token": token(client, "/account/password")})
    return client


class LoggingIn(unittest.TestCase):
    def test_login_and_logout(self):
        app, _ = make_app()
        client = logged_in(app, "sara", "Sara-pass-1")
        self.assertEqual(client.get("/").status_code, 200)
        client.post("/logout", data={"csrf_token": token(client, "/")})
        self.assertEqual(client.get("/").status_code, 302)

    def test_first_login_forces_password_change(self):
        app, _ = make_app()
        client = app.test_client()
        login(client, "sara", "Sara-pass-1")
        self.assertIn("/account/password", client.get("/").headers["Location"])

    def test_wrong_password_refused(self):
        app, _ = make_app()
        client = app.test_client()
        response = login(client, "sara", "wrong")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Wrong username or password", response.get_data(as_text=True))
        self.assertEqual(client.get("/").status_code, 302)

    def test_login_lockout(self):
        app, _ = make_app()
        client = app.test_client()
        for _ in range(5):
            login(client, "sara", "wrong")
        response = login(client, "sara", "Sara-pass-1")
        self.assertIn("locked", response.get_data(as_text=True).lower())
        self.assertEqual(client.get("/").status_code, 302)

    def test_disabled_user_cannot_log_in(self):
        app, store = make_app()
        uid = next(u["id"] for u in store.list_users() if u["username"] == "sara")
        store.set_active(uid, False)
        client = app.test_client()
        login(client, "sara", "Sara-pass-1")
        self.assertEqual(client.get("/").status_code, 302)


class Administration(unittest.TestCase):
    def test_admin_pages_refuse_members(self):
        app, _ = make_app()
        client = logged_in(app, "sara", "Sara-pass-1")
        self.assertEqual(client.get("/admin/users").status_code, 403)

    def test_admin_adds_and_disables_a_user(self):
        app, store = make_app()
        client = logged_in(app, "admin", "Admin-pass-1")
        page = client.get("/admin/users")
        self.assertEqual(page.status_code, 200)
        client.post("/admin/users", data={"username": "omar2", "display_name": "Omar Two", "password": "Temp-pass-9",
                                          "csrf_token": token(client, "/admin/users")})
        user = next(u for u in store.list_users() if u["username"] == "omar2")
        self.assertTrue(user["must_change"])
        client.post(f"/admin/users/{user['id']}/disable", data={"csrf_token": token(client, "/admin/users")})
        self.assertFalse(next(u for u in store.list_users() if u["username"] == "omar2")["active"])


class Security(unittest.TestCase):
    def test_post_without_csrf_is_refused(self):
        app, _ = make_app()
        client = app.test_client()
        response = client.post("/login", data={"username": "sara", "password": "Sara-pass-1"})
        self.assertEqual(response.status_code, 400)

    def test_passwords_are_hashed(self):
        app, store = make_app()
        with sqlite3.connect(store.path) as db:
            rows = db.execute("select password_hash from users").fetchall()
        for (value,) in rows:
            self.assertNotIn("pass", value)
            self.assertTrue(value.startswith("scrypt:"), value[:20])

    def test_session_cookie_flags(self):
        app, _ = make_app(HTTPS=True)
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])

    def test_copyright_on_login_page(self):
        app, _ = make_app()
        self.assertIn("© 2026 Omar Mokhtar. All rights reserved.", app.test_client().get("/login").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()


class TheAdminTool(unittest.TestCase):
    """deploy/install.sh creates the first admin with this tool; the password
    is typed (twice) at the prompt, never passed on the command line."""

    def test_create_admin_prompts_and_hashes(self):
        from webapp import manage
        data = Path(tempfile.mkdtemp())
        answers = iter(["Owner-pass-123", "Owner-pass-123"])
        rc = manage.main(["--data-dir", str(data), "create-admin", "omar", "--name", "Omar Mokhtar"],
                         ask=lambda prompt: next(answers))
        self.assertEqual(rc, 0)
        user = next(u for u in Store(data / "scheduler.db").list_users() if u["username"] == "omar")
        self.assertTrue(user["is_admin"])
        self.assertFalse(user["must_change"])

    def test_mismatched_passwords_are_refused(self):
        from webapp import manage
        data = Path(tempfile.mkdtemp())
        answers = iter(["Owner-pass-123", "Different-123"])
        self.assertNotEqual(manage.main(["--data-dir", str(data), "create-admin", "omar"],
                                        ask=lambda prompt: next(answers)), 0)
        self.assertEqual(Store(data / "scheduler.db").list_users(), [])
