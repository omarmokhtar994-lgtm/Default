"""Phase AC deep review: every route of the website as admin, supervisor, planner, a planner without programs and
signed out; bad values on every query; every POST with nothing and with garbage. Records exceptions, 5xx, slow
responses, access leaks and logged errors. Made-up "Associate NN" data. Run from the repository root."""
import io
import json
import logging
import re
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, ".")
from webapp.programs import ProgramBook  # noqa: E402
from webapp.tests.test_channel_needs import filled  # noqa: E402
from webapp.tests.test_notify_sender import Group  # noqa: E402
from webapp.tests.test_ready import make_ready  # noqa: E402
from webapp.tests.test_runs import REPO, make_app, sign_in, token, upload, wait  # noqa: E402

OUT = Path(sys.argv[1])
work = Path(tempfile.mkdtemp())
EG = timezone(timedelta(hours=3))
today = datetime.now(EG).date()
sunday = today - timedelta(days=(today.weekday() + 1) % 7)
ready = make_ready(work / "ready.xlsx")


class Catch(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.records = []

    def emit(self, record):
        self.records.append((record.name, record.getMessage()[:200],
                             "".join(traceback.format_exception(*record.exc_info))[-600:] if record.exc_info else ""))


catch = Catch()
logging.getLogger().addHandler(catch)

group = Group()
app, store, data, _ = make_app(VALIDATOR_ROOT=str(REPO), NOTIFY_THREAD=False, NOTIFY_TRANSPORT=group)
app.config["PROPAGATE_EXCEPTIONS"] = True
store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
pb = ProgramBook(store)
saks = pb.add_program("SAKS")
key = pb.add_lob(saks, "NMG Tier 2")
key9 = pb.add_lob(saks, "NMG Tier 9")
other = pb.add_program("Cricut")
ck = pb.add_lob(other, "Voice")
sup = store.add_user("sup", "Sup", "Sup-pass-123", must_change=False)
store.update_user(sup, is_supervisor=1)
store.set_user_programs(sup, [saks])
nour = store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)
store.set_user_programs(nour, [saks])
zed = store.add_user("zed", "Zed", "Zed-pass-123", must_change=False)
store.set_user_programs(zed, [])
admin = sign_in(app, "omar", "Owner-pass-123")
runs = {}
for name, week in (("week.xlsx", sunday), ("week_v2.xlsx", sunday), ("week_last.xlsx", sunday - timedelta(days=7)),
                   ("week_next.xlsx", sunday + timedelta(days=7))):
    admin.post("/runs", data={"csrf_token": token(admin), "kind": "ready", "mode": "QUICK", "program": key,
                              "week_start": week.isoformat(), "workbook": (io.BytesIO(ready.read_bytes()), name)},
               content_type="multipart/form-data")
    runs[name] = store.list_runs()[0]["id"]
    wait(store, runs[name], statuses=("DONE", "REJECTED", "FAILED"))
first = app.extensions["schedules"].versions(runs["week.xlsx"])[-1]["id"]
admin.post(f"/schedules/{first}/auto-breaks", data={"csrf_token": token(admin), "use": "1"})
admin.post("/week/target", data={"csrf_token": token(admin), "program": key, "week": sunday.isoformat(), "target": "90"})
needs = filled(work / "needs.xlsx")
admin.post(f"/runs/{runs['week_v2.xlsx']}/channel-needs", data={"csrf_token": token(admin),
           "workbook": (io.BytesIO(needs.read_bytes()), "needs.xlsx")}, content_type="multipart/form-data")
# engine runs (fake runner): a real schedule with validator files, a shortfall, a failure, a rejected input
for name, prog in (("AE_VERSIONED_REAL.xlsx", ck), ("WEEK_SHORTFALL.xlsx", ck), ("WEEK_FAILS.xlsx", ck),
                   ("bad_input.xlsx", ck)):
    got = upload(admin, name=name, data=ready.read_bytes(), program=prog, week_start=sunday.isoformat())
    rid = store.list_runs()[0]["id"]
    runs[name] = rid
    try:
        wait(store, rid, seconds=60)
    except AssertionError as exc:
        print("wait", name, exc)
page = app.extensions["days"].page(key, today)
names = [lane["name"] for lane in page["view"]["lanes"]][:6]
for n in names[:2]:
    admin.post("/day/attendance", data={"csrf_token": token(admin), "program": key, "date": today.isoformat(),
                                        "associate": n, "status": "Sick"})
store.set_notify(key, link="https://hooks.slack.com/services/T0/B0/abcdEFGHijkl", service="slack", mode="on",
                 kinds="break,added_break,overtime,called_in,channel", hold=120, site="http://localhost/")
admin.post("/day/add", data={"csrf_token": token(admin), "program": key, "date": today.isoformat(),
                             "associate": names[3], "what": "VTO", "from": "10:00", "minutes": "30", "view": "board"})
app.extensions["notifier"].run_once(time.time() + 300)
print("runs", {k: (v, store.get_run(v)["status"]) for k, v in runs.items()})
schedules = sorted({s["id"] for r in runs.values() for s in app.extensions["schedules"].versions(r)})

clients = {"admin": admin, "sup": sign_in(app, "sup", "Sup-pass-123"), "nour": sign_in(app, "nour", "Nour-pass-123"),
           "zed": sign_in(app, "zed", "Zed-pass-123"), "anon": app.test_client()}
K, D, W = key.replace(" ", "+"), today.isoformat(), sunday.isoformat()
person = names[3].replace(" ", "+")
GET = [
    "/", f"/?program={K}", "/account/password", "/admin/users", "/coach", f"/coach?program={K}",
    f"/coach/download?program={K}", f"/day?program={K}&date={D}",
    *[f"/day?program={K}&date={D}&view={v}" for v in ("board", "adherence", "meeting", "cover", "replan", "channels")],
    f"/day?program={K}&date={D}&measure=sl", f"/day?program={K}&date={D}&view=board&add=480",
    f"/day?program={K}&date={D}&view=board&add=480&person={person}", f"/day?program={K}&date={D}&who={person}",
    f"/day?program={K}&date={D}&view=board&cover=600", f"/day/handover?program={K}&date={D}",
    f"/day/wallboard?program={K}&date={D}", "/exports",
    *[f"/exports/download?kind={k}&from={W}&to={D}&format=csv" for k in
      ("attendance", "activities", "activity", "breaks", "changes", "versions", "runs", "worked", "summary",
       "channels", "record")],
    f"/exports/download?kind=summary&from={W}&to={D}&format=xlsx&program={K}",
    "/notifications", f"/notifications?unit={K}", f"/overview?program={K}&date={D}", "/programs",
    f"/programs/{key}", f"/programs/{ck}", f"/runs/week-check?program={K}&week={W}",
    f"/schedules?program={K}", f"/schedules?program={K}&week={W}", "/setup/channels", f"/setup/channels?program={K}",
    "/setup/programs", "/setup/with", f"/setup/with?program={K}", "/team", f"/week?program={K}",
    f"/week?program={K}&week={W}", "/workbooks/Blank_input.xlsx", "/workbooks/Example_input.xlsx",
    "/static/app.css", "/static/app.js",
]
for r in runs.values():
    GET += [f"/runs/{r}", f"/runs/{r}/channel-needs.xlsx", f"/runs/{r}/download", f"/runs/{r}/schedule",
            f"/runs/{r}/schedules", f"/runs/{r}/shortfall", f"/runs/{r}/status.json", f"/runs/{r}/week"]
for s in schedules:
    GET += [f"/schedules/{s}/breaks", f"/schedules/{s}/channels", f"/schedules/{s}/download", f"/schedules/{s}/week"]
BAD = ["/?program=nope", "/?program=../../etc", f"/day?program={K}&date=2026-02-30", f"/day?program={K}&date=abc",
       f"/day?program={K}&date={D}&view=zzz", f"/day?program={K}&date={D}&measure=zzz",
       f"/day?program={K}&date={D}&view=board&add=-5", f"/day?program={K}&date={D}&view=board&add=99999",
       f"/day?program={K}&date={D}&view=board&add=abc", f"/day?program={K}&date={D}&who=%3Cscript%3E",
       f"/day?program={K}&date={D}&view=board&cover=abc", f"/day?program={K}&date=1900-01-01",
       f"/day?program={K}&date=9999-12-31", "/day", "/day?program=", f"/day/handover?program={K}&date=x",
       f"/day/wallboard?program={K}", "/day/wallboard", f"/overview?program={K}&date=zz", "/overview",
       f"/week?program={K}&week=2026-13-01", f"/week?program={K}&week=1999-01-03", "/week", "/schedules",
       f"/schedules?program={K}&week=zz", "/schedules?program=nope", "/programs/nope", "/programs/..%2F..",
       "/runs/zzz", "/runs/000000000000", "/runs/000000000000/week", "/runs/000000000000/schedules",
       "/schedules/999999/breaks", "/schedules/999999/week", "/schedules/0/download", "/workbooks/../app.py",
       "/workbooks/nope.xlsx", "/exports/download?kind=zzz", "/exports/download?kind=runs&from=zz&to=yy",
       "/exports/download?kind=runs&from=2026-12-01&to=2026-01-01", "/exports/download?kind=runs&from=2000-01-01&to=2030-01-01",
       "/exports/download?kind=runs&format=pdf", "/exports/download?pick=group:999", "/exports/download?pick=key:nope",
       "/notifications?unit=nope", "/runs/week-check?program=nope&week=zz", "/runs/week-check",
       "/setup/channels?program=nope", "/setup/with?program=nope", "/coach?program=nope",
       "/coach/download?program=nope", "/admin/users?edit=999999", "/admin/users?edit=abc",
       f"/day?program={K}&date={D}&view=meeting&who={person}&minutes=abc&earliest=zz&latest=yy",
       f"/day?program={K}&date={D}&view=meeting&who={person}&minutes=0", "/static/nope.css"]

findings = {"exceptions": [], "5xx": [], "slow": [], "leaks": [], "odd": []}
timing = []
ADMIN_ONLY = ("/admin/users", "/notifications", "/setup/programs")
MANAGER = ("/setup/channels", "/setup/with")


def get(who, url):
    c = clients[who]
    t = time.perf_counter()
    try:
        r = c.get(url)
    except Exception as exc:  # noqa: BLE001
        findings["exceptions"].append((who, "GET", url, f"{type(exc).__name__}: {exc}"[:300],
                                       traceback.format_exc()[-900:]))
        return None
    dt = time.perf_counter() - t
    timing.append((dt, who, url, r.status_code))
    if r.status_code >= 500:
        findings["5xx"].append((who, "GET", url, r.status_code))
    if dt > 1.5:
        findings["slow"].append((round(dt, 2), who, url))
    body = r.get_data(as_text=True) if r.mimetype in ("text/html", "application/json") else ""
    for bad in ("Traceback", "Undefined", "None</", ">None<", "{{", "{%", "nan%", "NaN"):
        if bad in body:
            findings["odd"].append((who, url, bad, body[max(0, body.find(bad) - 80):body.find(bad) + 60]))
    return r


for url in GET:
    for who in clients:
        r = get(who, url)
        if r is None:
            continue
        path = url.split("?")[0]
        if who in ("nour", "zed") and path.startswith(ADMIN_ONLY + MANAGER) and r.status_code == 200:
            findings["leaks"].append((who, url))
        if who == "sup" and path.startswith(ADMIN_ONLY) and r.status_code == 200:
            findings["leaks"].append((who, url))
        if who == "anon" and r.status_code == 200 and not path.startswith(("/static", "/login")):
            findings["leaks"].append((who, url))
        if who in ("zed",) and ck.replace(" ", "+") not in url and K in url and r.status_code == 200 and \
                not path.startswith(("/static", "/account")):
            findings["leaks"].append((who, url))
for url in BAD:
    for who in ("admin", "nour"):
        get(who, url)

# POST: nothing, then garbage, then without the token
POSTS = sorted({r.rule for r in app.url_map.iter_rules() if "POST" in r.methods})
GARB = {"program": "nope", "date": "2026-02-30", "associate": "<b>x</b>", "idx": "x", "at": "99:99", "minutes": "-1",
        "what": "zzz", "kind": "zzz", "status": "zzz", "from": "25:00", "to": "zz", "id": "abc", "week": "zz",
        "target": "abc", "unit": "nope", "mode": "zzz", "hold": "abc", "link": "javascript:alert(1)", "use": "x",
        "action": "zzz", "name": "", "confirm": "1", "first": "x", "second": "y", "value": "zz", "day": "9",
        "channel": "Z", "start": "x", "end": "y", "names": "x", "moves": "[[1,2", "lines": "\x00", "role": "god",
        "username": "a b", "password": "x", "theme": "zzz", "view": "zzz", "span": "a|b", "side": "middle",
        "rows": "{bad json", "kinds": "zzz", "morning": "7.30", "with_whom": "x" * 500, "why": "y" * 5000}
VALID = {"program": key, "date": D}


def fill(rule):
    url = rule
    for var, val in (("<run_id>", runs["week_v2.xlsx"]), ("<int:schedule_id>", str(schedules[-1])),
                     ("<int:user_id>", str(zed)), ("<action>", "zzz"), ("<path:name>", "nope")):
        url = url.replace(var, val)
    return url


def post(who, url, form, csrf=True):
    c = clients[who]
    data = dict(form)
    if csrf:
        data["csrf_token"] = token(c) if who != "anon" else "x"
    try:
        r = c.post(url, data=data)
    except Exception as exc:  # noqa: BLE001
        findings["exceptions"].append((who, "POST", url, str(form)[:120], f"{type(exc).__name__}: {exc}"[:300],
                                       traceback.format_exc()[-900:]))
        return
    if r.status_code >= 500:
        findings["5xx"].append((who, "POST", url, str(form)[:120], r.status_code))


for rule in POSTS:
    if rule in ("/logout",):
        continue
    url = fill(rule)
    for who in ("admin", "nour"):
        post(who, url, {})
        post(who, url, GARB)
        post(who, url, {**GARB, **VALID})
    post("admin", url, VALID, csrf=False)
    post("anon", url, VALID)

timing.sort(reverse=True)
result = {"findings": findings, "slowest": [(round(t, 3), w, u, s) for t, w, u, s in timing[:25]],
          "requests": len(timing), "logged_errors": catch.records[:40], "group_calls": len(group.calls)}
OUT.write_text(json.dumps(result, indent=1, default=str))
print("requests", len(timing), {k: len(v) for k, v in findings.items()}, "logged", len(catch.records))
