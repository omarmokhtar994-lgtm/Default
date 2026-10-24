# © 2026 Omar Mokhtar. All rights reserved.
"""Phase Z review server (Phase AJ: the upload with channel needs is in use, and one cover from outside the roster): this week for SAKS, NMG Tier 2 with two uploads (week.xlsx in use with breaks planned
automatically, week_v2.xlsx not in use with channel needs added), a 90% target and three people sick today.
Made-up "Associate NN" names. Run from the repository root with the web venv; serves on 127.0.0.1:8767 and writes its details (base, program key, run ids) to
argv[1] as JSON for page_review.py."""
import io
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, ".")
from werkzeug.serving import make_server  # noqa: E402

from webapp.programs import ProgramBook  # noqa: E402
from webapp.tests.test_channel_needs import filled  # noqa: E402
from webapp.tests.test_ready import make_ready  # noqa: E402
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait  # noqa: E402

OUT = Path(sys.argv[1])
work = Path(tempfile.mkdtemp())
today = datetime.now(timezone(timedelta(hours=3))).date()
sunday = today - timedelta(days=(today.weekday() + 1) % 7)
ready = make_ready(work / "ready.xlsx")
app, store, data, _ = make_app(VALIDATOR_ROOT=str(REPO))
store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
key = ProgramBook(store).add_lob(ProgramBook(store).add_program("SAKS"), "NMG Tier 2")
client = sign_in(app, "omar", "Owner-pass-123")
runs = []
for name in ("week.xlsx", "week_v2.xlsx"):
    client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": key,
                               "week_start": sunday.isoformat(), "workbook": (io.BytesIO(ready.read_bytes()), name)},
                content_type="multipart/form-data")
    runs.append(store.list_runs()[0]["id"])
    wait(store, runs[-1], statuses=("DONE", "REJECTED", "FAILED"))
for name, week in (("week_last.xlsx", sunday - timedelta(days=7)), ("week_next.xlsx", sunday + timedelta(days=7))):
    client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": key,
                               "week_start": week.isoformat(), "workbook": (io.BytesIO(ready.read_bytes()), name)},
                content_type="multipart/form-data")
    wait(store, store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
first = app.extensions["schedules"].versions(runs[0])[-1]["id"]
client.post(f"/schedules/{first}/auto-breaks", data={"csrf_token": token(client), "use": "1"})
client.post("/week/target", data={"csrf_token": token(client), "program": key, "week": sunday.isoformat(), "target": "90"})
needs = filled(work / "needs.xlsx")
client.post(f"/runs/{runs[1]}/channel-needs", data={"csrf_token": token(client),
                                                    "workbook": (io.BytesIO(needs.read_bytes()), "needs.xlsx")},
            content_type="multipart/form-data")
page = app.extensions["days"].page(key, today)
names = [lane["name"] for lane in page["view"]["lanes"]][:3]
for name in names:
    client.post("/day/attendance", data={"csrf_token": token(client), "program": key, "date": today.isoformat(),
                                         "associate": name, "status": "Sick"})
# Phase AH: more people sick today, tomorrow and the day after, as in sample ah01, so Hours needed has work to show
for ahead, count in ((0, 3), (1, 6), (2, 7)):
    on = today + timedelta(days=ahead)
    page = app.extensions["days"].page(key, on)
    if page is None:
        continue
    present = [l["name"] for l in page["view"]["lanes"]
               if any(s["offset"] == 0 and s["status"] == "Present" for s in l["segments"])]
    for name in present[1::max(1, len(present) // count)][:count]:
        try:
            app.extensions["days"].set_status(key, on, name, "Sick", store.list_users()[0]["id"])
        except ValueError:
            pass

# Phase AG: associates, a leave request waiting for the TM, one for the RTA, and a swap waiting for the TM
from webapp.access import Access  # noqa: E402
pid = ProgramBook(store).tree()[0]["id"]
tm = store.add_user("tm", "Team Manager", "Owner-pass-123", must_change=False)
store.update_user(tm, is_supervisor=1); store.set_user_programs(tm, [pid])
leave, swaps, days = app.extensions["leave"], app.extensions["swaps"], app.extensions["days"]
tomorrow = today + timedelta(days=1)
working = [n for n, c in days.roster(key, tomorrow) if c[:1].isdigit()]
pair = None
for n in working:
    ok = [c["name"] for c in swaps.candidates(key, tomorrow, n) if c["ok"]]
    if ok:
        pair = (n, ok[0]); break
people = [n for n in working if not pair or n not in pair][:2]
for n in list(people) + (list(pair) if pair else []):
    uid = store.add_user(n.lower().replace(" ", ""), n, "Owner-pass-123", must_change=False)
    store.update_user(uid, is_associate=1, roster_name=n); store.set_user_programs(uid, [pid])
users = {u["roster_name"]: u for u in store.list_users() if u["is_associate"]}
r1 = leave.ask(key, people[0], users[people[0]]["id"], "Planned leave", tomorrow, tomorrow + timedelta(days=1), "Family visit", today)
r2 = leave.ask(key, people[1], users[people[1]]["id"], "Public holiday", tomorrow, tomorrow, "", today)
leave.decide(r2, store.get_user(tm), approve=True)
if pair:
    sid = swaps.offer(key, tomorrow, pair[0], users[pair[0]]["id"], pair[1], "", today)
    swaps.answer(sid, users[pair[1]], accept=True)
EXTRA = {"associate": people[0].lower().replace(" ", "")}
# Phase AJ: the upload with channel needs in use (channel colours on the Timeline), and one cover from outside the roster
owner = next(u["id"] for u in store.list_users() if u["username"] == "omar")
book = app.extensions["days"].book
book.set_in_use(book.versions(runs[1])[0]["id"], owner)
ch = app.extensions["days"].page(key, today)["view"].get("channels")
letter = next((r["letter"] for r in ch["rows"] if "language" not in r), "") if ch else ""
app.extensions["days"].add_cover(key, today, "Team lead 01", "Team manager", "10:00", "14:00", owner, channel=letter)
server = make_server("127.0.0.1", 8767, app, threaded=True)
OUT.write_text(json.dumps({**EXTRA, "base": "http://127.0.0.1:8767", "key": key, "run_id": runs[0], "other": runs[1],
                           "sunday": today.isoformat(), "week": sunday.isoformat(), "data": str(data)}),
               encoding="utf-8")
print("serving", flush=True)
server.serve_forever()
