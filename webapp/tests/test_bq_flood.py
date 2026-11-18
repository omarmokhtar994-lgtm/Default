# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BQ (owner, 2026-11-18: "protect against bot attacks that stop the server by a lot of requests or overloading").
A budget of requests per minute: each signed-in person has their own, everyone not signed in is counted by address;
and people who are not signed in can never take every worker thread, so staff always get a page. Made-up users."""
import re
import unittest
from pathlib import Path

from webapp import flood, serve
from webapp.tests.test_runs import TOKEN, make_app

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class TheBudget(unittest.TestCase):
    def test_a_key_gets_its_budget_then_waits_for_the_next_minute(self):
        clock = Clock(1040.0)  # 20 s into a minute (17 x 60 = 1020)
        budget = flood.Budget(3, clock=clock)
        self.assertEqual([budget.hit("a")[0] for _ in range(3)], [0, 0, 0])
        wait, first = budget.hit("a")
        self.assertEqual((wait, first), (40, True))  # the seconds left in this minute
        self.assertEqual(budget.hit("a"), (40, False))  # refused again, but logged once only
        clock.now = 1080.0
        self.assertEqual(budget.hit("a")[0], 0)  # a new minute, a new budget

    def test_keys_do_not_share_a_budget(self):
        budget = flood.Budget(1, clock=Clock())
        self.assertEqual(budget.hit("a")[0], 0)
        self.assertGreater(budget.hit("a")[0], 0)
        self.assertEqual(budget.hit("b")[0], 0)

    def test_the_table_stays_small_whatever_the_number_of_addresses(self):
        clock = Clock()
        budget = flood.Budget(5, size=100, clock=clock)
        for i in range(1000):
            budget.hit(f"10.0.{i // 250}.{i % 250}")
        self.assertLessEqual(len(budget.table), 100)


LIMITS = {"PER_USER": 5, "PER_ADDRESS": 4, "ANON_BUSY": 2}


def client_at(app, address):
    client = app.test_client()
    client.environ_base["REMOTE_ADDR"] = address
    return client


def signed_in_at(app, address, username, password):
    client = client_at(app, address)
    tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"username": username, "password": password, "csrf_token": tok})
    return client


class TheSite(unittest.TestCase):
    def setUp(self):
        self.app, self.store, *_ = make_app(start_worker=False, LIMITS=dict(LIMITS))

    def test_an_address_not_signed_in_is_refused_past_its_budget(self):
        bot = client_at(self.app, "203.0.113.9")
        codes = [bot.get("/login").status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 200, 429])
        refused = bot.get("/login")
        self.assertTrue(refused.headers["Retry-After"].isdigit())
        self.assertIn("Too many requests", refused.get_data(as_text=True))
        self.assertIn("Content-Security-Policy", refused.headers)  # the site's headers still apply
        self.assertEqual(client_at(self.app, "198.51.100.7").get("/login").status_code, 200)  # another address is untouched

    def test_the_site_files_do_not_use_up_an_address(self):
        # a whole office opening the sign-in page at shift start loads the same few files once each
        office = client_at(self.app, "203.0.113.70")
        for _ in range(20):
            self.assertEqual(office.get("/static/app.css").status_code, 200)
        self.assertEqual(office.get("/login").status_code, 200)

    def test_a_signed_in_person_has_their_own_budget_not_the_address(self):
        # an office shares one address: a bot on it uses up the address, the signed-in person still works
        sara = signed_in_at(self.app, "203.0.113.20", "sara", "Sara-pass-1")  # 2 of the address's 4
        bot = client_at(self.app, "203.0.113.20")
        while bot.get("/login").status_code != 429:
            pass
        self.assertEqual(sara.get("/").status_code, 200)

    def test_a_signed_in_person_is_refused_past_their_own_budget(self):
        sara = signed_in_at(self.app, "203.0.113.30", "sara", "Sara-pass-1")
        codes = [sara.get("/").status_code for _ in range(6)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5], 429)

    def test_when_visitors_fill_their_threads_staff_still_get_a_page(self):
        sara = signed_in_at(self.app, "203.0.113.40", "sara", "Sara-pass-1")
        guard = self.app.extensions["flood"]
        guard.anon_busy = LIMITS["ANON_BUSY"]  # two requests from people not signed in are being answered now
        busy = client_at(self.app, "198.51.100.40").get("/login")
        self.assertEqual(busy.status_code, 503)
        self.assertEqual(busy.headers["Retry-After"], "5")
        self.assertEqual(sara.get("/").status_code, 200)

    def test_the_busy_count_goes_back_down_after_each_request(self):
        guard = self.app.extensions["flood"]
        visitor = client_at(self.app, "198.51.100.50")
        visitor.get("/login")
        visitor.get("/no-such-page")
        self.assertEqual(guard.anon_busy, 0)

    def test_a_refusal_is_logged_once_per_address_and_minute(self):
        bot = client_at(self.app, "203.0.113.60")
        with self.assertLogs(self.app.logger, "WARNING") as logs:
            for _ in range(8):
                bot.get("/login")
        lines = [line for line in logs.output if "too many requests" in line]
        self.assertEqual(len(lines), 1)
        self.assertIn("203.0.113.60", lines[0])


class TheAddress(unittest.TestCase):
    """Found while measuring Phase BQ: waitress drops X-Forwarded-For unless told Caddy may send it, so the site saw
    every visitor as 127.0.0.1 and 40 wrong passwords from anyone held sign-in for everyone for 15 minutes."""

    def test_the_server_gets_the_visitors_address_that_caddy_adds(self):
        import http.client
        import threading
        from unittest import mock

        from waitress import create_server
        from werkzeug.middleware.proxy_fix import ProxyFix

        with mock.patch.dict("os.environ", {"SCHEDULER_DATA_DIR": "/tmp/x"}), mock.patch("webapp.app.create_app"), \
                mock.patch("waitress.serve") as run:
            serve.main()
        options = {k: v for k, v in run.call_args.kwargs.items() if k.startswith("trusted_proxy")}
        seen = []

        def app(environ, start):
            seen.append(environ.get("REMOTE_ADDR"))
            start("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        server = create_server(ProxyFix(app, x_for=1, x_proto=1, x_host=1), host="127.0.0.1", port=0, **options)
        threading.Thread(target=server.run, daemon=True).start()
        self.addCleanup(server.close)
        for forwarded in ("203.0.113.5", "9.9.9.9, 203.0.113.6"):  # Caddy adds the real one last
            conn = http.client.HTTPConnection("127.0.0.1", server.effective_port, timeout=10)
            conn.request("GET", "/", headers={"X-Forwarded-For": forwarded})
            conn.getresponse().read()
            conn.close()
        self.assertEqual(seen, ["203.0.113.5", "203.0.113.6"])
        self.assertEqual(options.get("trusted_proxy"), "127.0.0.1")  # only Caddy, on this machine, is believed


class TheSettings(unittest.TestCase):
    BASE = {"SCHEDULER_DATA_DIR": "/var/lib/scheduler"}

    def test_the_server_turns_the_limits_on_by_default(self):
        self.assertEqual(serve.config_from_env(self.BASE)["LIMITS"],
                         {"PER_USER": 600, "PER_ADDRESS": 1200, "ANON_BUSY": 4})

    def test_each_limit_can_be_set_and_a_bad_value_refuses_to_start(self):
        got = serve.config_from_env({**self.BASE, "SCHEDULER_LIMIT_PER_USER": "900", "SCHEDULER_LIMIT_PER_ADDRESS": "1200",
                                     "SCHEDULER_LIMIT_ANON_BUSY": "3"})["LIMITS"]
        self.assertEqual(got, {"PER_USER": 900, "PER_ADDRESS": 1200, "ANON_BUSY": 3})
        for bad in ("0", "-5", "lots"):
            with self.assertRaises(SystemExit, msg=bad):
                serve.config_from_env({**self.BASE, "SCHEDULER_LIMIT_PER_USER": bad})
        with self.assertRaises(SystemExit):  # visitors may not take all 8 threads
            serve.config_from_env({**self.BASE, "SCHEDULER_LIMIT_ANON_BUSY": "8"})

    def test_an_app_built_without_limits_has_none(self):
        app, *_ = make_app(start_worker=False)
        self.assertIsNone(app.extensions.get("flood"))

    def test_caddy_drops_connections_that_trickle_in(self):
        caddy = (DEPLOY / "Caddyfile.template").read_text(encoding="utf-8")
        timeouts = re.search(r"timeouts\s*\{([^}]*)\}", caddy)
        self.assertIsNotNone(timeouts)
        self.assertRegex(timeouts.group(1), r"read_header\s+10s")
        self.assertRegex(timeouts.group(1), r"idle\s+\d+[sm]")


if __name__ == "__main__":
    unittest.main()
