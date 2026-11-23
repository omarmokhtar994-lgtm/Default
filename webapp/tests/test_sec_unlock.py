# © 2026 Omar Mokhtar. All rights reserved.
"""Security hardening (owner, 2026-11-11: "adding unlock button to admin and supervisor to unlock locked account or IP"). The owner chose: admins unlock
any account and release a held address; supervisors unlock the accounts of people in their own programs only, and releasing an address stays with admins.

After five wrong passwords an account is locked for 15 minutes. The People page now shows who is locked and for how long, with an Unlock button where the
person may manage that account. Unlocking clears the lock and the count of wrong tries, never touches or shows a password, is recorded (who, whom), and
needs the form's token. Made-up people."""
import html
import re
import unittest

from webapp.store import LOCK_AFTER_FAILURES
from webapp.tests import test_ar_walls as fx
from webapp.tests.test_runs import sign_in, token

PASSWORD = fx.PASSWORD


class _Locked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx._Walls.setUpClass.__func__(cls)
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")

    def person(self, username, program=None, **flags):
        uid = self.store.add_user(username, username.title(), PASSWORD, must_change=False)
        self.store.set_user_programs(uid, [program or self.alpha_id])
        if flags:
            self.store.update_user(uid, **flags)
        return uid

    def lock(self, username):
        for _ in range(LOCK_AFTER_FAILURES):
            self.store.authenticate(username, "Wrong-pass-999")
        self.assertEqual(self.store.authenticate(username, PASSWORD)[1], "locked")

    def unlock(self, client, uid, with_token=True):
        data = {"csrf_token": token(client)} if with_token else {}
        return client.post(f"/admin/users/{uid}/unlock", data=data, follow_redirects=False)

    def page(self, client):
        return html.unescape(client.get("/admin/users").get_data(as_text=True))

    def events(self, kind):
        return [e for e in self.store.list_events(0, 9e12, None, None) if e["kind"] == kind]

    def locked(self, uid):
        return self.store.get_user(uid)["locked_until"] > 0


class TheAdmin(_Locked):
    def test_the_page_says_who_is_locked_and_for_how_long_with_a_button_for_only_them(self):
        uid = self.person("lock_a")
        self.person("lock_free")
        self.lock("lock_a")
        page = self.page(self.admin)
        row = re.search(r"<tr>\s*<td><b>Lock_A</b>.*?</tr>", page, re.S).group(0)
        self.assertRegex(row, r"Locked, about \d+ min left")
        self.assertIn(f"/admin/users/{uid}/unlock", row)
        free = re.search(r"<tr>\s*<td><b>Lock_Free</b>.*?</tr>", page, re.S).group(0)
        self.assertNotIn("/unlock", free)
        self.assertNotIn("Locked", free)

    def test_unlocking_lets_them_in_with_the_password_they_have_and_clears_the_count(self):
        uid = self.person("lock_b")
        self.lock("lock_b")
        self.assertEqual(self.unlock(self.admin, uid).status_code, 302)
        self.assertFalse(self.locked(uid))
        self.assertEqual(self.store.authenticate("lock_b", PASSWORD)[1], "ok")
        self.assertEqual(self.store.get_user(uid)["password_hash"] and self.store.authenticate("lock_b", PASSWORD)[0]["id"], uid)
        # the count of wrong tries starts again: four wrong passwords do not lock it
        for _ in range(LOCK_AFTER_FAILURES - 1):
            self.store.authenticate("lock_b", "Wrong-pass-999")
        self.assertEqual(self.store.authenticate("lock_b", PASSWORD)[1], "ok")

    def test_it_is_recorded_with_who_and_whom_and_no_password(self):
        uid = self.person("lock_c")
        self.lock("lock_c")
        before = len(self.events("user_unlocked"))
        self.unlock(self.admin, uid)
        found = self.events("user_unlocked")
        self.assertEqual(len(found), before + 1)
        self.assertIn("lock_c", str(found[-1]))
        self.assertNotIn(PASSWORD, str(found[-1]))

    def test_an_account_that_is_not_locked_is_left_alone_and_said_so(self):
        uid = self.person("lock_d")
        before = len(self.events("user_unlocked"))
        reply = self.unlock(self.admin, uid)
        self.assertEqual(reply.status_code, 302)
        self.assertIn("is not locked", html.unescape(self.admin.get("/admin/users").get_data(as_text=True)))
        self.assertEqual(len(self.events("user_unlocked")), before)

    def test_it_needs_the_forms_token(self):
        uid = self.person("lock_e")
        self.lock("lock_e")
        self.assertEqual(self.unlock(self.admin, uid, with_token=False).status_code, 400)
        self.assertTrue(self.locked(uid))

    def test_an_admin_does_not_unlock_themselves(self):
        me = self.store.get_user_by_name("omar")
        reply = self.unlock(self.admin, me["id"])
        self.assertEqual(reply.status_code, 302)
        self.assertIn("Change your own account", html.unescape(self.admin.get("/admin/users").get_data(as_text=True)))

    def test_the_held_address_panel_and_its_button_are_the_admins_alone(self):
        sup = sign_in(self.app, "sup_a", PASSWORD)
        self.assertNotIn("Addresses held", self.page(sup))
        self.assertEqual(sup.post("/admin/signins/release", data={"csrf_token": token(sup), "address": "203.0.113.9"}).status_code, 403)


class TheSupervisor(_Locked):
    def setUp(self):
        self.sup = sign_in(self.app, "sup_a", PASSWORD)

    def test_they_unlock_a_person_in_their_own_program(self):
        uid = self.person("lock_mine", program=self.alpha_id)
        self.lock("lock_mine")
        self.assertIn(f"/admin/users/{uid}/unlock", self.page(self.sup))
        self.assertEqual(self.unlock(self.sup, uid).status_code, 302)
        self.assertFalse(self.locked(uid))
        self.assertEqual(self.store.authenticate("lock_mine", PASSWORD)[1], "ok")

    def test_not_a_person_in_another_program_not_an_admin_not_another_supervisor(self):
        other = self.person("lock_theirs", program=self.bravo_id)
        self.lock("lock_theirs")
        self.assertEqual(self.unlock(self.sup, other).status_code, 403)
        self.assertTrue(self.locked(other))
        boss = self.person("lock_boss", program=self.alpha_id, is_supervisor=1)
        self.lock("lock_boss")
        self.assertEqual(self.unlock(self.sup, boss).status_code, 403)
        self.assertTrue(self.locked(boss))

    def test_they_do_not_see_a_button_for_people_they_cannot_unlock(self):
        self.person("lock_seen", program=self.alpha_id)
        self.lock("lock_seen")
        other = self.person("lock_hidden", program=self.bravo_id)
        self.lock("lock_hidden")
        page = self.page(self.sup)
        self.assertNotIn(f"/admin/users/{other}/unlock", page)
        self.assertNotIn("Lock_Hidden", page)

    def test_a_person_without_the_right_to_manage_people_cannot(self):
        uid = self.person("lock_plain")
        self.lock("lock_plain")
        planner = sign_in(self.app, "plan_a", PASSWORD)
        reply = self.unlock(planner, uid)
        self.assertIn(reply.status_code, (302, 403))
        self.assertTrue(self.locked(uid))

    def test_nothing_in_the_unlock_shows_or_changes_a_password(self):
        uid = self.person("lock_pw", program=self.alpha_id)
        before = self.store.get_user(uid)["password_hash"]
        self.lock("lock_pw")
        self.unlock(self.sup, uid)
        self.assertEqual(self.store.get_user(uid)["password_hash"], before)


if __name__ == "__main__":
    unittest.main()
