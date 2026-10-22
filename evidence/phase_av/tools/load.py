# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV: a busy-hour load test of the website as production runs it (waitress, 8 threads, one process), on made-up
"Associate NN" data. 5 RTAs, 20 team managers and 475 associates sign in over a ramp and then use their pages with think
times for the run's length. The server runs in its own process; the report gives per-page response times, errors, the
server's memory and CPU. This container is not the Oracle server: read the numbers as relative. Run from the repository
root with the web venv:  PYTHONPATH=. python evidence/phase_av/tools/load.py SECONDS [associates]"""
import multiprocessing
import os
import random
import re
import sys
import threading
import time
from collections import defaultdict
from unittest import mock

import requests
from waitress import create_server

from webapp.tests.test_as_pages import _Noon
from webapp.tests.test_as_requests import WED, _Fixture

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
ASSOCIATES = int(sys.argv[2]) if len(sys.argv) > 2 else 475
RTAS, MANAGERS = 5, 20


class Setup(_Fixture):
    def runTest(self):
        pass


Setup.setUpClass()
Setup().clear()
mock.patch("webapp.app.datetime", _Noon).start()
app, store, key, pid = Setup.app, Setup.store, Setup.key, Setup.pid
roster = [l["name"] for l in Setup.app.extensions["days"].page(key, WED)["view"]["lanes"]]
accounts = {"rta": [], "tm": [], "assoc": []}
for n in range(RTAS):
    uid = store.add_user(f"load_rta{n}", f"RTA {n:02d}", "Staff-pass-123", must_change=False)
    store.set_user_programs(uid, [pid])
    accounts["rta"].append((f"load_rta{n}", "Staff-pass-123"))
for n in range(MANAGERS):
    uid = store.add_user(f"load_tm{n}", f"Team Manager {n:02d}", "Manager-pass-123", must_change=False)
    store.update_user(uid, is_team_manager=1)
    store.set_user_programs(uid, [pid])
    accounts["tm"].append((f"load_tm{n}", "Manager-pass-123"))
for n in range(ASSOCIATES):
    uid = store.add_user(f"load_a{n}", f"Associate L{n:03d}", "Associate-pass-1", must_change=False)
    store.update_user(uid, is_associate=1, roster_name=roster[n % len(roster)])
    store.set_user_programs(uid, [pid])
    accounts["assoc"].append((f"load_a{n}", "Associate-pass-1"))

PORT = 18765


def serve():
    create_server(app, host="127.0.0.1", port=PORT, threads=8, max_request_body_size=26 * 1024 * 1024).run()


server = multiprocessing.get_context("fork").Process(target=serve, daemon=True)
server.start()
BASE = f"http://127.0.0.1:{PORT}"
for _ in range(100):
    try:
        requests.get(BASE + "/login", timeout=2)
        break
    except requests.RequestException:
        time.sleep(0.2)

Q = key.replace(" ", "+")
D = WED.isoformat()
PAGES = {
    "assoc": [("my day", f"/me/breaks", 40), ("my weeks", "/me", 25)],
    "tm": [("leave and swaps", f"/requests?program={Q}", 20), ("weeks", f"/week?program={Q}", 20),
           ("incidents 6 wk", f"/incidents?program={Q}&from=2026-09-03&to=2026-10-14", 14),
           ("shrinkage 6 wk", f"/shrinkage?program={Q}&from=2026-09-03&to=2026-10-14", 14),
           ("RTA timeline", f"/day?program={Q}&date={D}", 14)],
    "rta": [("RTA timeline", f"/day?program={Q}&date={D}", 8), ("RTA board", f"/day?program={Q}&date={D}&view=board", 8),
            ("RTA adherence", f"/day?program={Q}&date={D}&view=adherence", 10),
            ("incidents 13 wk", f"/incidents?program={Q}&from=2026-07-15&to=2026-10-14", 25),
            ("shrinkage per interval", f"/shrinkage?program={Q}&from=2026-10-08&to=2026-10-14&by=interval", 25),
            ("export 2 wk", f"/exports/download?program={Q}&from=2026-10-01&to=2026-10-14&kind=attendance&kind=worked&format=xlsx", 60)],
}
samples, errors, lock = defaultdict(list), defaultdict(int), threading.Lock()
stop = time.time() + SECONDS + 30


def user(role, name, password, delay):
    time.sleep(delay)
    s = requests.Session()
    t0 = time.time()
    try:
        page = s.get(BASE + "/login", timeout=60).text
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        r = s.post(BASE + "/login", data={"username": name, "password": password, "csrf_token": token}, timeout=120)
        ok = r.status_code == 200 and "Sign out" in r.text
    except requests.RequestException:
        ok = False
    with lock:
        samples["sign in"].append(time.time() - t0)
        if not ok:
            errors["sign in"] += 1
    if not ok:
        return
    pages = PAGES[role]
    while time.time() < stop - 30:
        label, path, every = random.choices(pages, weights=[1 / p[2] for p in pages])[0]
        t0 = time.time()
        try:
            r = s.get(BASE + path, timeout=180)
            bad = r.status_code >= 400
        except requests.RequestException:
            bad = True
        with lock:
            samples[label].append(time.time() - t0)
            if bad:
                errors[label] += 1
        time.sleep(random.uniform(0.5, 1.5) * (min(p[2] for p in pages) if role != "assoc" else 30) * (1 if role == "assoc" else 1))


def rss(pid):
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024
    except OSError:
        return 0.0


def cpu(pid):
    try:
        f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
    except OSError:
        return 0.0


threads = []
everyone = [("rta", *a) for a in accounts["rta"]] + [("tm", *a) for a in accounts["tm"]] + [("assoc", *a) for a in accounts["assoc"]]
for role, name, password in everyone:
    t = threading.Thread(target=user, args=(role, name, password, random.uniform(0, 30)), daemon=True)
    t.start()
    threads.append(t)
peak, started, c0 = 0.0, time.time(), cpu(server.pid)
while time.time() < started + SECONDS + 30:
    peak = max(peak, rss(server.pid))
    time.sleep(2)
elapsed = time.time() - started
for t in threads:
    t.join(timeout=60)
print(f"\n{len(everyone)} users ({RTAS} RTAs, {MANAGERS} managers, {ASSOCIATES} associates), {int(elapsed)} s, server memory peak {peak:.0f} MB, "
      f"server CPU {100 * (cpu(server.pid) - c0) / elapsed:.0f}% of one core (this container has {os.cpu_count()} cores)")
print(f"{'page':26}{'calls':>7}{'p50 s':>8}{'p95 s':>8}{'max s':>8}{'errors':>8}")
for label, vals in sorted(samples.items(), key=lambda kv: -len(kv[1])):
    v = sorted(vals)
    print(f"{label:26}{len(v):>7}{v[len(v) // 2]:>8.2f}{v[int(len(v) * 0.95) - 1] if len(v) > 1 else v[0]:>8.2f}{v[-1]:>8.2f}{errors[label]:>8}")
server.terminate()
