# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV (owner, 2026-10-22: make the site as secure as can be; attack it). Found by evidence/phase_av/security/pentest.py:
a session cookie kept working after its person signed out; an unknown username cost twice a known one to refuse, so
usernames could be found by timing; a very long upload name was a server error. Made-up users."""
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from webapp import store as store_module
from webapp.tests.test_runs import TOKEN, make_app, sign_in


class _Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("sam", "Sam", "Sam-pass-12345", must_change=False)

    def token(self, client):
        return TOKEN.search(client.get("/", follow_redirects=True).get_data(as_text=True)).group(1)


class TheLogout(_Site):
    def test_a_cookie_is_dead_after_its_person_signs_out(self):
        client = sign_in(self.app, "sam", "Sam-pass-12345")
        cookie = client.get_cookie("session").value
        self.assertEqual(client.get("/account/password").status_code, 200)
        client.post("/logout", data={"csrf_token": self.token(client)})
        replay = self.app.test_client()
        replay.set_cookie("session", cookie)
        got = replay.get("/account/password")
        self.assertEqual(got.status_code, 302)
        self.assertIn("/login", got.headers["Location"])

    def test_signing_out_one_device_leaves_the_others(self):
        phone, laptop = sign_in(self.app, "sam", "Sam-pass-12345"), sign_in(self.app, "sam", "Sam-pass-12345")
        phone.post("/logout", data={"csrf_token": self.token(phone)})
        self.assertEqual(laptop.get("/account/password").status_code, 200)

    def test_the_ended_sessions_are_forgotten_after_a_while(self):
        self.store.revoke_session(999, 1.0, now=1000.0)
        self.assertTrue(self.store.session_revoked(999, 1.0))
        self.store.revoke_session(999, 2.0, now=1000.0 + 40 * 86400)  # a later ending sweeps the old one away
        self.assertFalse(self.store.session_revoked(999, 1.0))


class TheSignInCost(_Site):
    def count(self, username, password):
        with mock.patch.object(store_module, "check_password_hash", wraps=store_module.check_password_hash) as check, \
                mock.patch.object(store_module, "generate_password_hash", wraps=store_module.generate_password_hash) as make:
            self.store.authenticate(username, password)
        return check.call_count, make.call_count

    def test_an_unknown_name_costs_one_password_check_like_a_known_name_with_a_wrong_password(self):
        self.assertEqual(self.count("nobody_here", "Wrong-pass-12345"), (1, 0))
        self.assertEqual(self.count("sam", "Wrong-pass-12345"), (1, 0))


class TheLongName(_Site):
    def test_a_very_long_upload_name_is_refused_kindly_not_a_server_error(self):
        client = sign_in(self.app, "sam", "Sam-pass-12345")
        self.store.update_user(self.store.get_user_by_name("sam")["id"], is_admin=1)
        client = sign_in(self.app, "sam", "Sam-pass-12345")
        blank = Path(__file__).resolve().parents[1] / "workbooks" / "Scheduler_Input_Blank.xlsx"
        for name in ("a" * 300 + ".xlsx", "ü" * 200 + ".xlsx"):
            got = client.post("/runs", data={"csrf_token": self.token(client), "kind": "ready", "mode": "QUICK",
                                             "week_start": "2026-10-18", "workbook": (io.BytesIO(blank.read_bytes()), name)},
                              content_type="multipart/form-data", follow_redirects=True)
            self.assertLess(got.status_code, 500, name[:10])


if __name__ == "__main__":
    unittest.main()


class TheWorkbookXml(unittest.TestCase):
    """openpyxl guards against XML entity bombs only with defusedxml; the server's requirements name it and the server
    refuses to start without it, and a workbook that carries one is refused as unreadable."""
    def test_it_is_required_and_active(self):
        from openpyxl.xml import DEFUSEDXML
        self.assertTrue(DEFUSEDXML)
        requirements = (Path(__file__).resolve().parents[2] / "deploy" / "requirements.txt").read_text()
        self.assertRegex(requirements, r"(?m)^defusedxml==")

    def test_a_workbook_with_an_entity_bomb_is_not_read(self):
        import zipfile
        from openpyxl import load_workbook
        path = Path(tempfile.mkdtemp()) / "bomb.xlsx"
        self.addCleanup(shutil.rmtree, path.parent, True)
        src = Path(__file__).resolve().parents[1] / "workbooks" / "Scheduler_Input_Blank.xlsx"
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(path, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item)
                if item.filename == "xl/workbook.xml":  # a declared entity, which an entity bomb is made of
                    data = b'<!DOCTYPE workbook [<!ENTITY a "aaaaaaaaaa">]>' + data
                zout.writestr(item, data)
        with self.assertRaises(Exception) as said:
            load_workbook(path)
        self.assertRegex(type(said.exception).__name__, r"Entit|Forbidden|Parse|Error")
