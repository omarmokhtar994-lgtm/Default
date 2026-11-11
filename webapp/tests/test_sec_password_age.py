# © 2026 Omar Mokhtar. All rights reserved.
"""Owner request, 2026-11-11: "force password reset after 30 days maximum and a reminder in the last 7 days".

A password older than 30 days must be changed before anything else (the same "Choose your own password" page a temporary password uses). From day 23 on, every page
carries a reminder saying how many days are left. Accounts that exist when this arrives start their 30 days then (nobody is locked out by the update). A
new password, an admin's reset and a new account start the count again. Made-up people."""
import re
import time
import unittest

from webapp.store import PASSWORD_MAX_DAYS, PASSWORD_WARN_DAYS, Store
from webapp.tests import test_ar_walls as fx
from webapp.tests.test_runs import sign_in

PASSWORD = fx.PASSWORD
DAY = 86400


def token(client, path="/account/password"):
    """The form token from a page this person may open (the change page is open to someone whose password is due)."""
    return re.search(r'name="csrf_token" value="([^"]+)"', client.get(path).get_data(as_text=True)).group(1)


class _Aged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx._Walls.setUpClass.__func__(cls)

    def person(self, username, **flags):
        uid = self.store.add_user(username, username.title(), PASSWORD, must_change=False)
        self.store.set_user_programs(uid, [self.alpha_id])
        if flags:
            self.store.update_user(uid, **flags)
        return uid

    def age(self, uid, days):
        with self.store._db() as db:
            db.execute("update users set pw_changed = ? where id = ?", (time.time() - days * DAY, uid))

    def page(self, client, path="/"):
        return client.get(path)


class TheClock(_Aged):
    def test_the_limits_are_thirty_days_and_seven_days_notice(self):
        self.assertEqual((PASSWORD_MAX_DAYS, PASSWORD_WARN_DAYS), (30, 7))

    def test_a_new_account_and_a_new_password_start_the_count(self):
        uid = self.person("age_new")
        self.assertLess(abs(self.store.get_user(uid)["pw_changed"] - time.time()), 5)
        self.age(uid, 20)
        self.store.set_password(uid, "Another-pass-1234")
        self.assertLess(abs(self.store.get_user(uid)["pw_changed"] - time.time()), 5)

    def test_what_exists_when_the_update_arrives_starts_its_thirty_days_then(self):
        uid = self.person("age_old")
        with self.store._db() as db:
            db.execute("alter table users drop column pw_changed")
        reopened = Store(self.store.path)
        row = reopened.get_user(uid)
        self.assertLess(abs(row["pw_changed"] - time.time()), 5)
        self.assertFalse(reopened.password_expired(row))

    def test_exactly_thirty_days_is_expired_and_a_moment_before_is_not(self):
        uid = self.person("age_edge")
        self.age(uid, 29.99)
        self.assertFalse(self.store.password_expired(self.store.get_user(uid)))
        self.assertEqual(self.store.password_days_left(self.store.get_user(uid)), 1)
        self.age(uid, 30.0)
        self.assertTrue(self.store.password_expired(self.store.get_user(uid)))
        self.assertEqual(self.store.password_days_left(self.store.get_user(uid)), 0)


class TheForcedChange(_Aged):
    def test_an_expired_password_sends_every_page_to_the_change_page_and_nowhere_else(self):
        uid = self.person("age_late")
        self.age(uid, 31)
        client = sign_in(self.app, "age_late", PASSWORD)           # signing in still works: the right password is the right password
        for path in ("/", "/programs", "/me/breaks"):
            reply = client.get(path)
            self.assertEqual(reply.status_code, 302, path)
            self.assertIn("/account/password", reply.headers["Location"], path)
        page = client.get("/account/password").get_data(as_text=True)
        self.assertIn("older than 30 days", page)
        self.assertEqual(client.post("/logout", data={"csrf_token": token(client)}).status_code, 302)

    def test_changing_it_frees_the_account_and_starts_a_new_thirty_days(self):
        uid = self.person("age_fix")
        self.age(uid, 40)
        client = sign_in(self.app, "age_fix", PASSWORD)
        same = client.post("/account/password", data={"current": PASSWORD, "new": PASSWORD, "confirm": PASSWORD,
                                                      "csrf_token": token(client)})
        self.assertIn("different from your current one", same.get_data(as_text=True))
        done = client.post("/account/password", data={"current": PASSWORD, "new": "Brand-new-pass-77", "confirm": "Brand-new-pass-77",
                                                      "csrf_token": token(client)})
        self.assertEqual(done.status_code, 302)
        self.assertEqual(client.get("/programs").status_code, 200)
        self.assertFalse(self.store.password_expired(self.store.get_user(uid)))
        self.assertLess(abs(self.store.get_user(uid)["pw_changed"] - time.time()), 5)

    def test_an_associates_account_is_held_to_the_same_limit(self):
        uid = self.person("age_assoc", is_associate=1, roster_name="Alpha Person Two")
        self.age(uid, 35)
        client = sign_in(self.app, "age_assoc", PASSWORD)
        reply = client.get("/me/breaks")
        self.assertEqual(reply.status_code, 302)
        self.assertIn("/account/password", reply.headers["Location"])

    def test_the_forced_page_is_the_same_one_a_temporary_password_gets(self):
        uid = self.person("age_temp")
        with self.store._db() as db:
            db.execute("update users set must_change = 1 where id = ?", (uid,))
        client = sign_in(self.app, "age_temp", PASSWORD)
        page = client.get("/account/password").get_data(as_text=True)
        self.assertIn("temporary password", page)
        self.assertNotIn("older than 30 days", page)


class TheReminder(_Aged):
    def test_nothing_until_day_twenty_three_then_the_days_left_on_every_page(self):
        uid = self.person("age_warn")
        client = sign_in(self.app, "age_warn", PASSWORD)
        self.age(uid, 22.5)
        self.assertNotIn("Your password expires", self.page(client, "/programs").get_data(as_text=True))
        for age, words in ((23.2, "7 days"), (26.5, "4 days"), (29.4, "1 day")):
            self.age(uid, age)
            body = self.page(client, "/programs").get_data(as_text=True)
            self.assertRegex(body, rf"Your password expires in {words}\b", age)
            self.assertIn('href="/account/password"', body)

    def test_it_is_a_link_to_the_change_page_and_not_shown_on_it(self):
        uid = self.person("age_link")
        client = sign_in(self.app, "age_link", PASSWORD)
        self.age(uid, 25)
        self.assertIn("expires in 5 days", self.page(client, "/programs").get_data(as_text=True))
        self.assertNotIn("expires in", client.get("/account/password").get_data(as_text=True))

    def test_nobody_signed_out_sees_it(self):
        self.assertNotIn("Your password expires", self.app.test_client().get("/login").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
