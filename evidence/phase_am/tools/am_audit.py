# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AM: screens into argv[1], made-up "Associate NN" weeks, the website's clock stopped on Wednesday 14 October
2026 at 10:00 Egypt time: Fix channels on the RTA (button and preview), the Weeks page's Version pick, Home with a
"Before breaks only" run, and a schedule in London time with its download; 1440 px and a phone, dark and light."""
import io
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from webapp.channel_people import ChannelPeople  # noqa: E402
from webapp.programs import ProgramBook  # noqa: E402
from webapp.tests.test_channel_day import ARABIC_SPARE, channel_day, read_week  # noqa: E402
from webapp.tests.test_runs import B3_INPUT, REPO, make_app, run_id_of, sign_in, token, upload as upload_run, wait  # noqa: E402

out = Path(sys.argv[1])
work = Path(tempfile.mkdtemp())
upload = channel_day(work / "upload.xlsx")
app, store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
omar = store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
programs = ProgramBook(store)
pid = programs.add_program("SAKS")
key = programs.add_lob(pid, "NMG Tier 2")
client = sign_in(app, "omar", "Owner-pass-123")
client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK", "program": key,
                           "week_start": "2026-10-11", "workbook": (io.BytesIO(upload.read_bytes()), "week.xlsx")},
            content_type="multipart/form-data")
wait(store, store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
everyone = [a["name"] for a in read_week(upload)["associates"]]
ChannelPeople(store).save(pid, {n: "E" for n in everyone if n not in ("Associate 001", "Associate 031", ARABIC_SPARE)},
                          omar)
from unittest import mock  # noqa: E402
from webapp.tests.test_af_outlook import _Clock  # noqa: E402
book = app.extensions["schedules"]
version = book.versions(store.list_runs()[0]["id"])[0]["id"]
made = book.change_many(version, omar, [(a["name"], "Mon", "OFF") for a in __import__("json").loads(
    book.versions(store.list_runs()[0]["id"])[0]["week"])["associates"][:3]], "a quieter Monday", "a quieter Monday")
assert made != version, "the second version was not made"
app.extensions["days"].set_status(key, __import__("datetime").date(2026, 10, 14), "Associate 031", "Sick", omar)
B1 = REPO / "fixtures" / "real_runs" / "before_break" / "B1_BEFORE" / "input_snapshot" / "AE_FR_Choice.xlsx"
before = run_id_of(upload_run(client, name="BEFOREONLY_week.xlsx", data=B1.read_bytes(), program=key,
                              week_start="2026-10-18"))
wait(store, before)
server = make_server("127.0.0.1", 8770, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:8770"
Q = key.replace(" ", "+")
CHECK = """() => { const ids={}, dup=[]; document.querySelectorAll('[id]').forEach(e=>{ if(ids[e.id]) dup.push(e.id); ids[e.id]=1; });
 const unl=[]; document.querySelectorAll('input:not([type=hidden]),select,textarea,button').forEach(e=>{
   const n=(e.getAttribute('aria-label')||'')+(e.labels&&e.labels.length?e.labels[0].textContent:'')+(e.tagName=='BUTTON'?e.textContent:'')+(e.getAttribute('title')||'');
   if(!n.trim()) unl.push(e.tagName); });
 const nav=performance.getEntriesByType('navigation')[0];
 return {dup:dup.length, unnamed:unl.length, sw:document.documentElement.scrollWidth, vw:document.documentElement.clientWidth,
   ttfb:Math.round(nav.responseStart), load:Math.round(nav.loadEventEnd), nodes:document.getElementsByTagName('*').length}; }"""
with mock.patch("webapp.app.datetime", _Clock), sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for width in (1440, 320):
        pg = b.new_context(viewport={"width": width, "height": 900}).new_page(); errs = []
        pg.on("console", lambda m: m.type in ("error", "warning") and errs.append(m.text[:100]))
        pg.goto(base + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for path in (f"/day?program={Q}&date=2026-10-14&view=channels&fix=1", f"/week?program={Q}&week=2026-10-11&basis=planned",
                     "/", f"/runs/{store.list_runs()[-1]['id']}/schedules?tz=Europe/London"):
            errs.clear(); r = pg.goto(base + path); pg.wait_for_load_state("networkidle")
            print(width, r.status, path.split("?")[0], pg.evaluate(CHECK), "csp" if "content-security-policy" in r.headers else "NO-CSP", errs)
    b.close()
server.shutdown()
