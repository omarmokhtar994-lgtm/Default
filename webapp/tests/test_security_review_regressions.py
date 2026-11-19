# © 2026 Omar Mokhtar. All rights reserved.
"""Run in the real deployment/test venv after applying the proposed patch.

The original four HTTP regressions and the missing-file cases below require the real test venv.
These HTTP tests have NOT been executed in the assessment workspace because
Flask/Werkzeug and the pinned solver dependencies are unavailable there.
"""
import unittest
from webapp.app import password_problem
from webapp.tests.test_auth import make_app, logged_in, token


class PasswordNormalization(unittest.TestCase):
    def test_padding_cannot_make_a_short_password_pass(self):
        for padding in (' ', '\t', '\u200b', '\ufeff', '\u00a0'):
            value = 'Riv7!' + padding*8
            self.assertTrue(password_problem(value, value, 'someone'))

    def test_real_password_with_paste_padding_remains_valid(self):
        value = ' Blue.harbour.7412 '
        self.assertEqual(password_problem(value, value, 'someone'), '')

    def test_short_temporary_password_is_refused_when_adding_account(self):
        app, store = make_app()
        client = logged_in(app, 'admin', 'Admin-pass-1')
        response = client.post('/admin/users', data={
            'username': 'paddedcandidate', 'display_name': 'Synthetic candidate',
            'role': 'admin', 'password': 'Riv7!' + '\u200b'*8,
            'csrf_token': token(client, '/admin/users')})
        self.assertLess(response.status_code, 500)
        self.assertIsNone(store.get_user_by_name('paddedcandidate'))


class PasswordFloorEverywhere(unittest.TestCase):
    """Audit (Claude, 2026-11-11): the first fix guarded the call sites; these pin the other ones and the store itself, so a new caller cannot
    store a password that is short once the paste padding is stripped."""

    def test_the_bulk_people_sheet_refuses_a_padded_short_password(self):
        import re
        from webapp.tests.test_ar_users import TheBulkUpload, sheet
        from openpyxl import Workbook  # noqa: F401  (the sheet helper builds the workbook)
        case = TheBulkUpload("test_the_template_has_the_columns_and_one_example")
        TheBulkUpload.setUpClass()
        try:
            before = len(case.store.list_users())
            data = sheet(("pad_short", "Pad Short", "planner", "ALPHA", "", "", "Riv7!" + "\u200b" * 8),
                         ("pad_ok", "Pad Ok", "planner", "ALPHA", "", "", "  Blue.harbour.7412 "))
            page = case.check(data).get_data(as_text=True)
            self.assertIn("at least 10", page)
            self.assertIn("Add 1 person", page)                          # only the real password's row is good
            case.confirm(page)
            self.assertEqual(len(case.store.list_users()), before + 1)
            self.assertIsNone(case.store.get_user_by_name("pad_short"))
            self.assertTrue(case.can_sign_in("pad_ok", "Blue.harbour.7412"))
        finally:
            TheBulkUpload.tearDownClass()

    def test_the_store_itself_refuses_what_is_short_once_cleaned(self):
        from webapp.store import MIN_PASSWORD_LENGTH, hash_password
        with self.assertRaises(ValueError):
            hash_password("Riv7!" + "\u200b" * 8)
        with self.assertRaises(ValueError):
            hash_password(" " * 12)
        self.assertTrue(hash_password("a" * MIN_PASSWORD_LENGTH).startswith("scrypt:"))


class MalformedCsrf(unittest.TestCase):
    def test_unicode_csrf_returns_400_instead_of_server_error(self):
        app, _ = make_app()
        client = app.test_client()
        client.get('/login')
        response = client.post('/login', data={'username': 'nobody', 'password': 'irrelevant', 'csrf_token': 'é'})
        self.assertEqual(response.status_code, 400)



from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook, load_workbook
from webapp.tests.test_at_security import _Secured, PASSWORD
from webapp.tests.test_runs import sign_in, token as page_token
import io


class MissingScheduleFiles(_Secured):
    def test_missing_schedule_download_returns_404(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        source = self.app.extensions["schedules"].path(self.sched[self.alpha])
        source.unlink(missing_ok=True)
        with self.assertNoLogs(self.app.logger, level="ERROR"):
            response = client.get(f"/schedules/{self.sched[self.alpha]}/download", buffered=True)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("/tmp/", response.get_data(as_text=True))
        response.close()

    def test_missing_schedule_edit_endpoints_return_404_without_mutation(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        source = self.app.extensions["schedules"].path(self.sched[self.alpha])
        source.unlink(missing_ok=True)
        before = len(self.store.list_schedules())
        data = {"csrf_token": page_token(client), "first": "Alpha Person One", "second": "Alpha Person Two",
                "associate": "Alpha Person One", "day": "Sun", "value": "Leave", "reason": "Synthetic check"}
        for action in ("check", "change", "swap-check", "swap"):
            with self.subTest(action=action), self.assertNoLogs(self.app.logger, level="ERROR"):
                response = client.post(f"/schedules/{self.sched[self.alpha]}/{action}", data=data)
                self.assertEqual(response.status_code, 404)
                self.assertIn("unavailable", response.get_json()["error"])
        self.assertEqual(len(self.store.list_schedules()), before)

    def test_a_missing_schedule_file_is_a_logged_warning_never_a_silent_404(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.app.extensions["schedules"].path(self.sched[self.alpha]).unlink(missing_ok=True)
        with self.assertLogs(self.app.logger, level="WARNING") as seen:
            response = client.get(f"/schedules/{self.sched[self.alpha]}/download", buffered=True)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(any("schedule file missing" in line and "/download" in line for line in seen.output), seen.output)
        response.close()

    def test_existing_schedule_file_download_still_succeeds(self):
        source = self.app.extensions["schedules"].path(self.sched[self.alpha])
        source.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        wb.active["A1"] = "Synthetic download fixture"
        wb.save(source)
        wb.close()
        self.addCleanup(source.unlink, missing_ok=True)
        client = sign_in(self.app, "plan_a", PASSWORD)
        response = client.get(f"/schedules/{self.sched[self.alpha]}/download", buffered=True)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response.headers["Content-Disposition"])
            got = load_workbook(io.BytesIO(response.data))
            try:
                self.assertEqual(got.active["A1"].value, "Synthetic download fixture")
            finally:
                got.close()
        finally:
            response.close()

    def test_invalid_wallboard_input_returns_controlled_400(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        with patch.object(self.app.extensions["days"], "page", side_effect=ValueError("Missing synthetic inputs")), \
                self.assertNoLogs(self.app.logger, level="ERROR"):
            response = client.get("/day/wallboard", query_string={"program": self.alpha, "date": "2026-10-14"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_the_wallboard_refusal_is_logged_with_its_cause(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        with patch.object(self.app.extensions["days"], "page", side_effect=ValueError("Missing synthetic inputs")), \
                self.assertLogs(self.app.logger, level="WARNING") as seen:
            client.get("/day/wallboard", query_string={"program": self.alpha, "date": "2026-10-14"})
        self.assertTrue(any("Missing synthetic inputs" in line for line in seen.output), seen.output)

    def test_file_error_handling_preserves_authentication_and_authorization(self):
        url = f"/schedules/{self.sched[self.alpha]}/download"
        response = self.app.test_client().get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        foreign = sign_in(self.app, "plan_b", PASSWORD)
        self.assertEqual(foreign.get(url).status_code, 403)


if __name__ == '__main__':
    unittest.main()
