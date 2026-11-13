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
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for scheme in ("dark", "light"):
        for width in (1440, 390):
            ctx = b.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
            pg = ctx.new_page()
            pg.goto(base + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
            with pg.expect_navigation(): pg.keyboard.press("Enter")
            pg.goto(f"{base}/day?program={key.replace(' ', '+')}&date=2026-10-14&tz=Africa/Cairo&start=07:00")
            pg.wait_for_load_state("networkidle")
            el = pg.locator(".tl").first
            el.scroll_into_view_if_needed()
            el.screenshot(path=str(out / f"timeline_{scheme}_{width}.png"))
            pg.goto(f"{base}/schedules/{version}/channels?day=Wed"); pg.wait_for_load_state("networkidle")
            pg.locator("section:has(#cp-fair-h)").screenshot(path=str(out / f"fairness_{scheme}_{width}.png"))
            pg.goto(f"{base}/runs/{steady}/schedules"); pg.wait_for_load_state("networkidle")
            pg.screenshot(path=str(out / f"more_consistent_{scheme}_{width}.png"))
            ctx.close()
    b.close()
server.shutdown()
print("done")
