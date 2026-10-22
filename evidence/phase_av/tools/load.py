# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV: a busy-hour load test of the website as production runs it (waitress, 8 threads, one process), on made-up
"Associate NN" data. 5 RTAs, 20 team managers and 475 associates sign in over a ramp and then use their pages with think
times for the run's length. The server runs in its own process; the report gives per-page response times, errors, the
server's memory and CPU. This container is not the Oracle server: read the numbers as relative. Run from the repository
root with the web venv:  PYTHONPATH=. python evidence/phase_av/tools/load.py SECONDS [associates] [action share 0 to 1] [engine]"""
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
ACTION_SHARE = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0  # the share of each role that changes things, not only reads
ENGINE = (sys.argv[4] == "engine") if len(sys.argv) > 4 else False  # a schedule run in parallel: every core busy, 1 GB held
RTAS, MANAGERS = 5, 20
RAMP = 90  # seconds over which everyone signs in (a shift start is not one second)
ASSOCIATE_THINK = 90  # seconds between an associate's page views, on average


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


def burner(seconds):
    """What an engine run does to the server: a busy loop on this core and some memory held."""
    held = bytearray(1024 * 1024 * 1024 // max(1, os.cpu_count() or 1))
    for i in range(0, len(held), 4096):
        held[i] = 1
    end = time.time() + seconds
    while time.time() < end:
        sum(i * i for i in range(20000))


def act(s, role, last, token_of):
    """One change a person makes; returns (label, bad)."""
    token = token_of(last) or token_of(s.get(BASE + "/", timeout=60).text)
    if role == "assoc":
        page = s.get(BASE + "/me/breaks?change=0", timeout=60).text
        found = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page.replace("&#34;", '"'))
        if not found:
            return "ask a break change", False
        r = s.post(BASE + "/me/breaks", data={"csrf_token": token, "idx": 0, "to": found.group(1), "why": "Load test"}, timeout=120)
        return "ask a break change", r.status_code >= 500
    if role == "tm":
        r = s.post(BASE + "/requests/coaching", data={"csrf_token": token, "program": key, "date": D, "names": random.sample(roster, 2),
                                                        "start": "14:00", "minutes": "30", "dept": "Quality", "why": "Load test"}, timeout=120)
        return "ask coaching", r.status_code >= 500
    name = random.choice(roster)
    r = s.post(BASE + "/day/attendance", data={"csrf_token": token, "program": key, "date": D, "associate": name,
                                                 "status": random.choice(["Sick", "Present"])}, timeout=120)
    return "RTA sets attendance", r.status_code >= 500


def token_of(text):
    found = re.search(r'name="csrf_token" value="([^"]+)"', text or "")
    return found.group(1) if found else ""


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
    doer = random.random() < ACTION_SHARE
    last = ""
    while time.time() < stop - 30:
        label, path, every = random.choices(pages, weights=[1 / p[2] for p in pages])[0]
        t0 = time.time()
        try:
            if doer and random.random() < 0.5:  # half of what a person who changes things does is a change
                label, bad = act(s, role, last, token_of)
            else:
                r = s.get(BASE + path, timeout=180)
                last = r.text
                bad = r.status_code >= 400
        except requests.RequestException:
            bad = True
        with lock:
            samples[label].append(time.time() - t0)
            if bad:
                errors[label] += 1
        time.sleep(random.uniform(0.5, 1.5) * (min(p[2] for p in pages) if role != "assoc" else ASSOCIATE_THINK))


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


burners = []
if ENGINE:
    burners = [multiprocessing.get_context("fork").Process(target=burner, args=(SECONDS + 40,), daemon=True)
               for _ in range(os.cpu_count() or 1)]
    for b in burners:
        b.start()
threads = []
everyone = [("rta", *a) for a in accounts["rta"]] + [("tm", *a) for a in accounts["tm"]] + [("assoc", *a) for a in accounts["assoc"]]
for role, name, password in everyone:
    t = threading.Thread(target=user, args=(role, name, password, random.uniform(0, RAMP)), daemon=True)
    t.start()
    threads.append(t)
peak, started, c0 = 0.0, time.time(), cpu(server.pid)
while time.time() < started + SECONDS + 30:
    peak = max(peak, rss(server.pid))
    time.sleep(2)
elapsed = time.time() - started
for t in threads:
    t.join(timeout=60)
print(f"\nchanges by {int(100 * ACTION_SHARE)}% of people; a schedule run in parallel: {'yes, every core busy' if ENGINE else 'no'}")
print(f"{len(everyone)} users ({RTAS} RTAs, {MANAGERS} managers, {ASSOCIATES} associates), {int(elapsed)} s, server memory peak {peak:.0f} MB, "
      f"server CPU {100 * (cpu(server.pid) - c0) / elapsed:.0f}% of one core (this container has {os.cpu_count()} cores)")
print(f"{'page':26}{'calls':>7}{'p50 s':>8}{'p95 s':>8}{'max s':>8}{'errors':>8}")
for label, vals in sorted(samples.items(), key=lambda kv: -len(kv[1])):
    v = sorted(vals)
    print(f"{label:26}{len(v):>7}{v[len(v) // 2]:>8.2f}{v[int(len(v) * 0.95) - 1] if len(v) > 1 else v[0]:>8.2f}{v[-1]:>8.2f}{errors[label]:>8}")
server.terminate()
for b in burners:
    b.terminate()
