# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BF (owner, 2026-11-02: "maximize the security so it can pass any client test ... do some tests if someone tried hacking,
what are the weak areas"). Black-box attacks against the whole site, the way an outsider, a signed-in member of another team
and a person with a text editor would try them. Made-up "Associate NN" style data only. Each test names the attack; a failure
is a weak area."""
import io
import re
import unittest
import zipfile

from webapp.tests import test_ar_walls as fx
from webapp.tests.test_runs import make_app, sign_in, token
from webapp.tests.test_at_security import _Secured, PASSWORD

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
LEAKS = re.compile(r"(?i)traceback \(most recent|sqlite3?\.|operationalerror|werkzeug\.exceptions|File \"/|/home/user|/root/")
OPEN_PATHS = {"login", "static", "logout"}


def rules(app, method):
    return [r for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule)
            if method in r.methods and r.endpoint not in OPEN_PATHS]


def url_of(app, rule, value="1"):
    from flask import url_for
    with app.test_request_context():
        return url_for(rule.endpoint, **{a: value for a in rule.arguments})


class TheOutsider(_Secured):
    """Nobody signed in."""

    def test_no_page_answers_an_outsider_with_content(self):
        client = self.app.test_client()
        bad = []
        for rule in rules(self.app, "GET"):
            got = client.get(url_of(self.app, rule))
            if got.status_code == 200 and rule.endpoint not in ("login",):
                bad.append((rule.rule, got.status_code))
            self.assertLess(got.status_code, 500, rule.rule)
        self.assertEqual(bad, [], f"pages that answer with no sign-in: {bad}")

    def test_no_form_does_anything_for_an_outsider(self):
        client = self.app.test_client()
        before = len(self.store.list_runs())
        for rule in rules(self.app, "POST"):
            got = client.post(url_of(self.app, rule), data={**fx.FORM, "program": self.alpha})
            self.assertIn(got.status_code, (301, 302, 303, 400, 401, 403, 404, 405, 413), (rule.rule, got.status_code))
        self.assertEqual(len(self.store.list_runs()), before)

    def test_odd_methods_are_refused_and_never_crash(self):
        client = self.app.test_client()
        for method in ("PUT", "DELETE", "PATCH", "TRACE", "OPTIONS", "PROPFIND"):
            for path in ("/", "/login", "/runs", "/exports/download"):
                got = client.open(path, method=method)
                self.assertIn(got.status_code, (200, 301, 302, 303, 400, 401, 403, 404, 405), (method, path))
                self.assertNotRegex(got.get_data(as_text=True), LEAKS)
        self.assertEqual([r.rule for r in self.app.url_map.iter_rules()
                          if r.methods & {"PUT", "DELETE", "PATCH"}], [], "a route takes PUT/DELETE/PATCH (no CSRF check there)")

    def test_errors_never_show_the_machine(self):
        client = self.app.test_client()
        for path in ("/nope", "/runs/../../etc/passwd", "/static/../app.py", "/%00", "/runs/999999", "/" + "a" * 5000):
            body = client.get(path).get_data(as_text=True)
            self.assertNotRegex(body, LEAKS, path)


class TheSession(_Secured):
    def login_cookie(self, who="plan_a"):
        client = sign_in(self.app, who, PASSWORD)
        return client, client.get_cookie("session")

    def test_cookie_flags(self):
        client = self.app.test_client()
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        got = client.post("/login", data={"username": "plan_a", "password": PASSWORD, "csrf_token": tok})
        header = "; ".join(got.headers.getlist("Set-Cookie"))
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Lax", header)

    def test_a_cookie_copied_before_sign_out_is_dead_after_it(self):
        client, cookie = self.login_cookie()
        self.assertEqual(client.get("/").status_code, 200)
        client.post("/logout", data={"csrf_token": token(client)})
        replay = self.app.test_client()
        replay.set_cookie("session", cookie.value)
        got = replay.get("/", follow_redirects=False)
        self.assertNotEqual(got.status_code, 200, "a stolen cookie still works after the person signed out")

    def test_the_session_changes_at_sign_in(self):
        anon = self.app.test_client()
        anon.get("/login")
        before = anon.get_cookie("session")
        tok = TOKEN.search(anon.get("/login").get_data(as_text=True)).group(1)
        anon.post("/login", data={"username": "plan_a", "password": PASSWORD, "csrf_token": tok})
        self.assertNotEqual(before.value if before else "", anon.get_cookie("session").value)

    def test_a_forged_cookie_signs_nobody_in(self):
        client = self.app.test_client()
        for value in ("", "x", "eyJ1c2VyX2lkIjoxfQ.AAAAAA.BBBB", "eyJ1c2VyX2lkIjoxfQ"):
            client.set_cookie("session", value)
            self.assertNotEqual(client.get("/").status_code, 200, value)


class TheLoginForm(_Secured):
    def post(self, client, user, password):
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        return client.post("/login", data={"username": user, "password": password, "csrf_token": tok})

    def test_guessing_passwords_locks_the_account_even_for_the_right_one(self):
        client = self.app.test_client()
        for i in range(6):
            self.post(client, "plan_a", f"wrong-{i}-password")
        self.assertNotEqual(self.post(client, "plan_a", PASSWORD).status_code, 302, "the right password worked on a locked account")

    def test_guessing_from_one_address_is_stopped_whoever_it_tries(self):
        client = self.app.test_client()
        codes = [self.post(client, f"nobody_{i}", "wrong-password-1").status_code for i in range(45)]
        self.assertIn(429, codes)
        self.assertEqual(self.post(client, "sup_a", PASSWORD).status_code, 429)

    def test_a_switched_off_account_is_not_named_to_someone_without_its_password(self):
        a = self.app.test_client()
        self.store.set_active(self.users["tm_a"], False)
        try:
            body = self.post(a, "tm_a", "not-the-password").get_data(as_text=True)
        finally:
            self.store.set_active(self.users["tm_a"], True)
        self.assertNotIn("switched off", body)

    def test_a_locked_account_takes_as_long_to_refuse_as_an_unknown_one(self):
        import time
        b = self.app.test_client()
        for i in range(6):
            self.post(self.app.test_client(), "tm_a", f"wrong-{i}-pass-word")
        started = time.perf_counter()
        for _ in range(3):
            self.post(b, "tm_a", "another-wrong-pass-1")
        locked = time.perf_counter() - started
        started = time.perf_counter()
        for _ in range(3):
            self.post(b, "no_such_person", "another-wrong-pass-1")
        unknown = time.perf_counter() - started
        self.assertGreater(locked, unknown * 0.5, f"a locked account answers fast ({locked:.2f}s against {unknown:.2f}s)")

    def test_the_answer_does_not_say_which_usernames_exist(self):
        a, b = self.app.test_client(), self.app.test_client()
        for i in range(4):
            known = self.post(a, "tm_a", f"bad-{i}-pass-word").get_data(as_text=True)
            unknown = self.post(b, "no_such_person", f"bad-{i}-pass-word").get_data(as_text=True)
            self.assertEqual(re.sub(TOKEN.pattern, "", known), re.sub(TOKEN.pattern, "", unknown), i)
        # the fifth wrong password on a real account must not read differently from the fifth on a missing one
        known = self.post(a, "tm_a", "bad-5-pass-word").get_data(as_text=True)
        unknown = self.post(b, "no_such_person", "bad-5-pass-word").get_data(as_text=True)
        self.assertEqual(re.sub(TOKEN.pattern, "", known), re.sub(TOKEN.pattern, "", unknown),
                         "the account-locked message tells an outsider which usernames are real")

    def test_the_next_address_never_leaves_the_site(self):
        for target in ("//evil.test", "/\\evil.test", "https://evil.test", "/\t/evil.test", "javascript:alert(1)",
                       "///evil.test", "/%2f/evil.test", "/..//evil.test", "http:evil.test"):
            client = self.app.test_client()
            tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
            got = client.post("/login?next=" + target, data={"username": "sup_a", "password": PASSWORD, "csrf_token": tok})
            where = got.headers.get("Location", "")
            from urllib.parse import urlsplit
            parts = urlsplit(where)
            self.assertEqual((parts.scheme, parts.netloc), ("", ""), (target, where))  # a path on this site, nothing more


class TheForms(_Secured):
    def test_every_form_without_the_token_does_nothing(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        wrong = []
        for rule in rules(self.app, "POST"):
            if rule.endpoint in ("change_password",):
                continue
            got = client.post(url_of(self.app, rule), data={**fx.FORM, "program": self.alpha})
            if got.status_code not in (400, 403, 404, 405):
                wrong.append((rule.rule, got.status_code))
        self.assertEqual(wrong, [], "forms that act without the CSRF token")

    def test_a_token_from_another_session_is_refused(self):
        a = sign_in(self.app, "plan_a", PASSWORD)
        b = sign_in(self.app, "sup_a", PASSWORD)
        got = a.post("/runs/1/tag", data={"csrf_token": token(b), "program": self.alpha})
        self.assertIn(got.status_code, (400, 403, 404))

    def test_a_json_body_does_not_get_round_the_token(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for rule in rules(self.app, "POST")[:80]:
            got = client.post(url_of(self.app, rule), json={"csrf_token": "x", "program": self.alpha})
            self.assertIn(got.status_code, (400, 403, 404, 405, 415), rule.rule)


class TheInjector(_Secured):
    PAYLOADS = ("' or 1=1 --", "\"; drop table users; --", "1; select sqlite_version()", "%00", "${7*7}", "{{7*7}}",
                "<script>alert(1)</script>", "../../../../etc/passwd", "\\..\\..\\windows\\win.ini", "A" * 3000,
                "' union select username,password_hash from users --")
    NAMES = ("q", "date", "week", "week_start", "program", "name", "associate", "kind", "from", "to", "unit", "tab", "sort",
             "view", "mode", "id", "start", "day", "who", "lang", "channel", "page", "limit", "order", "filter", "search")

    def test_no_query_value_breaks_a_page_or_shows_data_it_should_not(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        broke = []
        for rule in rules(self.app, "GET"):
            base = url_of(self.app, rule)
            for payload in self.PAYLOADS:
                query = {name: payload for name in self.NAMES}
                got = client.get(base, query_string=query)
                body = got.get_data(as_text=True)
                if got.status_code >= 500 or LEAKS.search(body) or "49" == body.strip() or re.search(r"scrypt:\d+:\d+", body):
                    broke.append((rule.rule, payload[:20], got.status_code))
                self.assertNotRegex(body, r"(?i)zorro|bravo", (rule.rule, payload[:20]))
        self.assertEqual(broke, [], f"pages that break or leak under hostile input: {sorted({(r, st) for r, _p, st in broke})}")

    def test_a_path_cannot_climb_out_of_a_download(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for rule in rules(self.app, "GET"):
            if not any(w in rule.rule for w in ("download", "export", "file", "result", "workbook")):
                continue
            for evil in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "%2e%2e/%2e%2e/etc/passwd", "....//....//etc/passwd"):
                try:
                    url = url_of(self.app, rule, evil)
                except ValueError:  # the route wants a number: the address cannot even be built
                    continue
                got = client.get(url)
                self.assertNotIn(b"root:x:", got.data, (rule.rule, evil))
                self.assertLess(got.status_code, 500, (rule.rule, evil))


class TheUploads(_Secured):
    def post(self, data, name="w.xlsx", **extra):
        client = sign_in(self.app, "plan_a", PASSWORD)
        form = {"csrf_token": token(client), "kind": "ready", "program": self.alpha, "week_start": "2026-10-18",
                "workbook": (io.BytesIO(data), name), **extra}
        return client.post("/runs", data=form, content_type="multipart/form-data")

    def test_hostile_workbooks_are_refused_without_a_crash(self):
        bomb = io.BytesIO()
        with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/workbook.xml", "0" * 200_000_000)
        xxe = io.BytesIO()
        with zipfile.ZipFile(xxe, "w") as z:
            z.writestr("[Content_Types].xml", '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>')
            z.writestr("xl/workbook.xml", "<workbook/>")
        cases = {"zip bomb": bomb.getvalue(), "xxe": xxe.getvalue(), "not a zip": b"MZ\x90\x00" * 100,
                 "empty": b"", "html": b"<html><script>alert(1)</script></html>"}
        before = len(self.store.list_runs())
        for label, data in cases.items():
            got = self.post(data)
            self.assertLess(got.status_code, 500, label)
            self.assertNotRegex(got.get_data(as_text=True), LEAKS, label)
        self.assertEqual(len(self.store.list_runs()), before, "a hostile file became a run")

    def test_a_dangerous_name_never_reaches_the_disk_as_a_path(self):
        for name in ("../../evil.xlsx", "..\\..\\evil.xlsx", "/etc/cron.d/x.xlsx", "a\x00b.xlsx", "x" * 400 + ".xlsx", "con.xlsx"):
            got = self.post(b"PK\x03\x04 x", name=name)
            self.assertLess(got.status_code, 500, name)
        import os
        data_dir = self.app.config["DATA_DIR"]
        inside = os.path.realpath(data_dir)
        climbed = [os.path.join(base, "evil.xlsx") for base in (os.path.dirname(inside), os.path.dirname(os.path.dirname(inside)),
                                                                 inside, os.path.join(inside, "runs"))
                   if os.path.exists(os.path.join(base, "evil.xlsx"))]
        self.assertEqual(climbed + [p for p in ("/etc/cron.d/x.xlsx",) if os.path.exists(p)], [],
                         "a file named by the uploader landed outside the run's own folder")

    def test_too_big_a_body_is_refused(self):
        got = self.post(b"PK" + b"0" * (26 * 1024 * 1024))
        self.assertIn(got.status_code, (400, 413))


class TheHeaders(_Secured):
    def test_every_answer_carries_the_headers(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        missing = []
        for rule in rules(self.app, "GET")[:60]:
            got = client.get(url_of(self.app, rule))
            for h in ("Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy",
                      "Permissions-Policy", "Cache-Control"):
                if h not in got.headers:
                    missing.append((rule.rule, h))
        self.assertEqual(missing, [])

    def test_the_policy_allows_no_inline_script_or_style(self):
        csp = self.app.test_client().get("/login").headers["Content-Security-Policy"]
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertNotIn("*", csp)
        for part in ("default-src 'self'", "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors"):
            self.assertIn(part, csp)

    def test_a_cross_site_page_cannot_read_or_embed_these_answers(self):
        got = self.app.test_client().get("/login")
        self.assertEqual(got.headers.get("Cross-Origin-Resource-Policy"), "same-origin",
                         "no Cross-Origin-Resource-Policy: another site can embed these answers")

    def test_the_extra_isolation_headers_are_there(self):
        got = self.app.test_client().get("/login")
        self.assertEqual(got.headers.get("X-Permitted-Cross-Domain-Policies"), "none")

    def test_a_forged_host_is_not_echoed_into_the_page(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for path in ("/", "/login", "/me"):
            got = client.get(path, headers={"Host": "evil.test", "X-Forwarded-Host": "evil.test"})
            self.assertNotIn("evil.test", got.get_data(as_text=True) + str(got.headers.get("Location", "")), path)

    def test_cors_is_closed(self):
        got = self.app.test_client().get("/login", headers={"Origin": "https://evil.test"})
        self.assertNotIn("Access-Control-Allow-Origin", got.headers)
        pre = self.app.test_client().options("/runs", headers={"Origin": "https://evil.test",
                                                               "Access-Control-Request-Method": "POST"})
        self.assertNotIn("Access-Control-Allow-Origin", pre.headers)


if __name__ == "__main__":
    unittest.main()
