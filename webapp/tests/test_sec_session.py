# © 2026 Omar Mokhtar. All rights reserved.
"""Owner request, 2026-11-11: "timeout maximum 1 hour and then to be logged out"; the owner chose one hour with no activity.
A signed-in person is signed out after one hour without a page load; every page load starts the hour again; a page's own background requests do not
(so a page left open does not keep itself signed in); one hour is the ceiling. Made-up people; short lifetimes stand for the hour in the behaviour tests."""
import re
import time
import unittest
from datetime import timedelta

from webapp.app import SESSION_IDLE_MINUTES
from webapp.tests import test_ar_walls as fx
from webapp.tests.test_auth import make_app
from webapp.tests.test_runs import sign_in


class TheLimit(unittest.TestCase):
    def test_it_is_one_hour_and_one_hour_is_the_ceiling(self):
        self.assertEqual(SESSION_IDLE_MINUTES, 60)
        app, _ = make_app()
        self.assertEqual(app.permanent_session_lifetime, timedelta(hours=1))
        for asked, want in ((30, 30), (90, 60), (0, 1), (-5, 1)):
            app, _ = make_app(SESSION_IDLE_MINUTES=asked)
            self.assertEqual(app.permanent_session_lifetime, timedelta(minutes=want), asked)

    def test_the_cookie_a_sign_in_sets_expires_within_the_hour(self):
        app, _ = make_app()
        client = app.test_client()
        client.get("/login")
        page = client.get("/login").get_data(as_text=True)
        tok = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        reply = client.post("/login", data={"username": "admin", "password": "Admin-pass-1", "csrf_token": tok})
        cookie = [c for c in reply.headers.getlist("Set-Cookie") if c.startswith("session=")][-1]
        self.assertRegex(cookie, r"(?i)expires=")
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        expires = parsedate_to_datetime(re.search(r"(?i)expires=([^;]+)", cookie).group(1))
        left = (expires - datetime.now(timezone.utc)).total_seconds()
        self.assertTrue(3000 < left <= 3600, left)


class TheBehaviour(fx._Walls):
    """A short lifetime (4 seconds) stands for the hour; the rules are the same."""

    def setUp(self):
        self.was = self.app.permanent_session_lifetime
        self.app.permanent_session_lifetime = timedelta(seconds=4)
        self.addCleanup(setattr, self.app, "permanent_session_lifetime", self.was)
        self.client = sign_in(self.app, "plan_a", fx.PASSWORD)

    def page(self, **headers):
        return self.client.get("/requests", query_string={"program": self.alpha}, headers=headers)

    def test_signed_in_at_first(self):
        self.assertEqual(self.page().status_code, 200)

    def test_idle_for_longer_than_the_limit_signs_out(self):
        time.sleep(5.2)
        reply = self.page()
        self.assertEqual(reply.status_code, 302)
        self.assertIn("/login", reply.headers["Location"])

    def test_every_page_load_starts_the_time_again(self):
        for _ in range(3):                                   # 3 x 2.5 s is 7.5 s in all: more than the 4 s, but never idle that long
            time.sleep(2.5)
            self.assertEqual(self.page().status_code, 200)

    def test_a_pages_own_background_requests_do_not_keep_it_signed_in(self):
        time.sleep(2.5)
        poll = self.client.get("/live/stamp", query_string={"kind": "requests", "program": self.alpha}, headers={"Sec-Fetch-Mode": "cors"})
        self.assertEqual(poll.status_code, 200)             # the page watcher's 30-second question: not a page load
        time.sleep(2.5)
        reply = self.page()
        self.assertEqual(reply.status_code, 302, "5 s since the last page load: signed out, whatever the polls did")
        self.assertIn("/login", reply.headers["Location"])


if __name__ == "__main__":
    unittest.main()
