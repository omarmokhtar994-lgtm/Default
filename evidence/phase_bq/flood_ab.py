# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BQ: the flood guard measured (rule: evidence/phase_bq/FLOOD_RULE.txt, written before the first run).

The website runs as production serves it (waitress, 8 threads, one process, ProxyFix as behind Caddy) in its own
process, on made-up data. 200 bots flood the sign-in page (GET, then POST with a made-up wrong username: scrypt, the
most expensive thing a stranger can ask) while one signed-in staff member asks for the home page every 0.5 s.
Run from the repository root with the web venv:  PYTHONPATH=. python evidence/phase_bq/flood_ab.py SECONDS"""
import http.client
import json
import multiprocessing
import re
import statistics
import sys
import threading
import time
import urllib.parse

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
BOTS = 200
PORT = 18790
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
DEFAULTS = {"PER_USER": 600, "PER_ADDRESS": 1200, "ANON_BUSY": 4}


def serve(limits, ready):
    from waitress import create_server
    from werkzeug.middleware.proxy_fix import ProxyFix

    from webapp.serve import CONNECTION_LIMIT, PROXY, THREADS
    from webapp.tests.test_runs import make_app

    app, *_ = make_app(start_worker=False, LIMITS=limits)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    server = create_server(app, host="127.0.0.1", port=PORT, threads=THREADS, connection_limit=CONNECTION_LIMIT, **PROXY)
    ready.set()
    server.run()


class Browser:
    """One client: its own connection, cookie and address (X-Forwarded-For, as Caddy would send it)."""

    def __init__(self, address):
        self.address = address
        self.cookie = ""
        self.conn = None

    def ask(self, method, path, body=None):
        headers = {"X-Forwarded-For": self.address, "Host": "localhost"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            body = urllib.parse.urlencode(body)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        for attempt in (1, 2):
            try:
                if self.conn is None:
                    self.conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
                self.conn.request(method, path, body=body, headers=headers)
                response = self.conn.getresponse()
                text = response.read().decode("utf-8", "replace")
                for name, value in response.getheaders():
                    if name.lower() == "set-cookie" and value.startswith("session="):
                        self.cookie = value.split(";", 1)[0]
                return response.status, text
            except (OSError, http.client.HTTPException):
                if self.conn:
                    self.conn.close()
                self.conn = None
                if attempt == 2:
                    return "error", ""
        return "error", ""

    def sign_in(self, username, password):
        status, text = self.ask("GET", "/login")
        found = TOKEN.search(text) if status == 200 else None
        if not found:
            return status
        return self.ask("POST", "/login", {"username": username, "password": password, "csrf_token": found.group(1)})[0]


def bot_loop(n, one_address, stop, counts, lock):
    bot = Browser("198.51.100.1" if one_address else f"10.{n // 250}.{n % 250}.{1 + n % 200}")
    i = 0
    while not stop.is_set():
        status = bot.sign_in(f"bot{n}x{i}", "Wrong-pass-123")
        with lock:
            counts[str(status)] = counts.get(str(status), 0) + 1
        i += 1
        if status in (429, 503):
            time.sleep(0.05)  # a crude bot: it barely waits


def staff_loop(stop, out, interval=0.5, path="/"):
    staff = Browser("192.0.2.10")
    tries = []  # signing in is not yet signed in: under a flood it may be refused for a moment (recorded)
    while not stop.is_set():
        tries.append(staff.sign_in("sara", "Sara-pass-1"))
        if tries[-1] == 302:
            break
        time.sleep(1)
    out["sign_in"] = tries
    while not stop.is_set():
        started = time.perf_counter()
        status, _ = staff.ask("GET", path)
        out["times"].append(time.perf_counter() - started)
        out["codes"][str(status)] = out["codes"].get(str(status), 0) + 1
        time.sleep(max(0, interval - (time.perf_counter() - started)))


def arm(limits, flood):
    ready = multiprocessing.Event()
    server = multiprocessing.Process(target=serve, args=(limits, ready), daemon=True)
    server.start()
    ready.wait(60)
    time.sleep(1)
    stop, lock, counts = threading.Event(), threading.Lock(), {}
    staff = {"times": [], "codes": {}}
    threads = []
    if flood:
        threads = [threading.Thread(target=bot_loop, args=(n, flood == "one address", stop, counts, lock), daemon=True)
                   for n in range(BOTS)]
        for t in threads:
            t.start()
        time.sleep(3)  # the flood is on before staff start
    staff_thread = threading.Thread(target=staff_loop, args=(stop, staff), daemon=True)
    staff_thread.start()
    time.sleep(SECONDS)
    stop.set()
    staff_thread.join(35)
    for t in threads:
        t.join(35)
    server.terminate()
    server.join(10)
    times = sorted(staff["times"])
    return {"staff_requests": len(times), "staff_codes": staff["codes"], "staff_sign_in": staff["sign_in"],
            "staff_median_s": round(statistics.median(times), 3) if times else None,
            "staff_p95_s": round(times[int(0.95 * (len(times) - 1))], 3) if times else None,
            "staff_max_s": round(times[-1], 3) if times else None, "bot_codes": counts}


def normal_use():
    """Rule check 4: guard on, no flood; one person with 5 tabs polling every 3 s and a page view every 2 s, 60 s."""
    ready = multiprocessing.Event()
    server = multiprocessing.Process(target=serve, args=(DEFAULTS, ready), daemon=True)
    server.start()
    ready.wait(60)
    time.sleep(1)
    stop = threading.Event()
    tabs = [{"times": [], "codes": {}} for _ in range(6)]
    threads = [threading.Thread(target=staff_loop, args=(stop, tabs[i], 3.0 if i < 5 else 2.0), daemon=True) for i in range(6)]
    for t in threads:
        t.start()
    time.sleep(60)
    stop.set()
    for t in threads:
        t.join(10)
    server.terminate()
    codes = {}
    for tab in tabs:
        for k, v in tab["codes"].items():
            codes[k] = codes.get(k, 0) + v
    return {"requests": sum(codes.values()), "codes": codes}


if __name__ == "__main__":
    multiprocessing.set_start_method("fork")
    results = {}
    for flood in ("botnet", "one address"):
        for name, limits in (("A guard off", None), ("B defaults", DEFAULTS)):
            results[f"{flood} / {name}"] = arm(limits, flood)
            print(f"{flood} / {name}: {json.dumps(results[f'{flood} / {name}'])}", flush=True)
    results["normal use, guard on"] = normal_use()
    print(f"normal use, guard on: {json.dumps(results['normal use, guard on'])}", flush=True)
    print(json.dumps(results, indent=1))
