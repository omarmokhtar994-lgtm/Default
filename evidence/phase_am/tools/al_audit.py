# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AL: screens into argv[1], made-up "Associate NN" weeks: the Timeline with Email in deep green, the Fairness
section of Plan channels after Suggest the week, and a run's Schedules list with "Tool, more consistent"; 1440 px and a
phone, dark and light."""
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
version = app.extensions["schedules"].versions(store.list_runs()[0]["id"])[0]["id"]
client.post(f"/schedules/{version}/channels", data={"csrf_token": token(client), "day": "Wed", "action": "suggest_week"})
steady = run_id_of(upload_run(client, name="VERSIONED_CONSISTENT_week.xlsx", data=B3_INPUT.read_bytes(),
                          program=key, week_start="2026-10-18"))
wait(store, steady)
server = make_server("127.0.0.1", 8769, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:8769"
CHECK = """() => { const ids={}, dup=[]; document.querySelectorAll('[id]').forEach(e=>{ if(ids[e.id]) dup.push(e.id); ids[e.id]=1; });
 const unl=[]; document.querySelectorAll('input:not([type=hidden]),select,textarea,button').forEach(e=>{
   const n=(e.getAttribute('aria-label')||'')+(e.labels&&e.labels.length?e.labels[0].textContent:'')+(e.tagName=='BUTTON'?e.textContent:'')+(e.getAttribute('title')||'');
   if(!n.trim()) unl.push(e.tagName); });
 const nav=performance.getEntriesByType('navigation')[0];
 return {dup:dup.length, unnamed:unl.length, sw:document.documentElement.scrollWidth, vw:document.documentElement.clientWidth,
   ttfb:Math.round(nav.responseStart), load:Math.round(nav.loadEventEnd), nodes:document.getElementsByTagName('*').length}; }"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for width in (1440, 320):
        pg = b.new_context(viewport={"width": width, "height": 900}).new_page(); errs = []
        pg.on("console", lambda m: m.type in ("error", "warning") and errs.append(m.text[:100]))
        pg.goto(base + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for path in (f"/schedules/{version}/channels?day=Wed", f"/runs/{steady}/schedules",
                     f"/day?program={key.replace(' ', '+')}&date=2026-10-14&tz=Africa/Cairo&start=07:00"):
            errs.clear(); r = pg.goto(base + path); pg.wait_for_load_state("networkidle")
            print(width, r.status, path.split("?")[0], pg.evaluate(CHECK), "csp" if "content-security-policy" in r.headers else "NO-CSP", errs)
    b.close()
server.shutdown()
