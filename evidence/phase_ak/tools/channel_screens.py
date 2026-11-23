# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK: screens of the Timeline with a channel plan (the test fixture's made-up "Associate NN" week) in the three
looks at 1440 px and on a phone, into argv[1]."""
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
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait  # noqa: E402

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
server = make_server("127.0.0.1", 8768, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:8768"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for look, scheme in (("dark", "dark"), ("light", "light"), ("ocean", "dark")):
        for width in (1440, 390):
            ctx = b.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
            if look == "ocean":
                ctx.add_cookies([{"name": "theme", "value": "ocean", "url": base}])
            pg = ctx.new_page()
            pg.goto(base + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
            with pg.expect_navigation(): pg.keyboard.press("Enter")
            pg.goto(f"{base}/day?program={key.replace(' ', '+')}&date=2026-10-14&tz=Africa/Cairo&start=07:00")
            pg.wait_for_load_state("networkidle")
            el = pg.locator(".tl").first
            el.scroll_into_view_if_needed()
            el.screenshot(path=str(out / f"timeline_{look}_{width}.png"))
            ctx.close()
    b.close()
server.shutdown()
print("done")
