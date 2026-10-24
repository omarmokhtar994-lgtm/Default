# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV: real screens of the Incidents page on made-up "Associate NN" data (two LOBs, Sunday 11 to Thursday 15 October
2026, the clock stopped on Wednesday 14 October at 12:00 Cairo time). Run from the repository root with the web venv:
PYTHONPATH=. python evidence/phase_av/tools/screens.py evidence/phase_av/screens"""
import sys
import threading
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from webapp.tests.test_as_pages import _Noon
from webapp.tests.test_notify_daybook import _Tagged, hm

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


class Setup(_Tagged):
    def runTest(self):
        pass


Setup.setUpClass()
patch = mock.patch("webapp.app.datetime", _Noon)
patch.start()
S = Setup()
days, store, app, omar = Setup.days, Setup.store, Setup.app, Setup.omar
SUN = date(2026, 10, 11)


def seed(key, shift):
    """Made-up incidents: a rotation over the people of each day, so every LOB and associate differs."""
    for n in range(5):
        on = SUN + timedelta(days=n)
        page = days.page(key, on)
        if not page:
            continue
        lanes = [(l["name"], s) for l in page["view"]["lanes"] for s in l["segments"] if s["offset"] == 0]
        for i, (name, seg) in enumerate(lanes):
            k = (i * 3 + n * 5 + shift) % 17
            try:
                if k == 0:
                    days.set_status(key, on, name, "Late", omar, end=hm((seg["start"] + 15 + 5 * (i % 7)) % 1440))
                elif k == 1:
                    days.set_status(key, on, name, "Left early", omar, start=hm((seg["end"] - 30 - 5 * (i % 9)) % 1440))
                elif k == 2:
                    days.set_status(key, on, name, "Unplanned leave" if i % 2 else "Sick", omar)
                elif k in (3, 4) and seg["breaks"]:
                    b = seg["breaks"][0]
                    days.move_break(key, on, name, b["idx"], hm((b["start"] + 5 + 5 * (i % 3)) % 1440), omar, missed=True)
                elif k == 5:
                    lo = seg["start"] + 120 + 5 * (i % 6)
                    days.add_activity(key, on, name, "Coaching", hm(lo % 1440), hm((lo + 30) % 1440), omar,
                                      with_whom="Team lead", why="Made-up coaching")
                elif k == 6:
                    lo = seg["start"] + 180
                    days.add_activity(key, on, name, "System issue", hm(lo % 1440), hm((lo + 20) % 1440), omar,
                                      with_whom="IT", why="Made-up outage")
            except ValueError:
                pass


seed(Setup.key, 0)
seed(Setup.quiet, 7)
server = make_server("127.0.0.1", 0, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"
Q = "from=2026-10-11&to=2026-10-15"
who = days.page(Setup.key, SUN)["view"]["lanes"][0]["name"].replace(" ", "+")
SHOTS = [("av1_overview", f"/incidents?{Q}&view=overview"), ("av2_lobs", f"/incidents?{Q}&view=lobs"),
         ("av3_associates", f"/incidents?{Q}&view=associates"), ("av4_one_associate", f"/incidents?{Q}&view=associates&who={who}")]
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for scheme in ("dark", "light"):
        for size, (w, h) in (("desktop", (1280, 900)), ("phone", (390, 844))):
            ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, reduced_motion="reduce")
            p = ctx.new_page()
            p.goto(base + "/login")
            p.fill("input[name=username]", "omar")
            p.fill("input[name=password]", "Owner-pass-123")
            p.click("button.primary")
            p.wait_for_load_state()
            for name, path in SHOTS:
                p.goto(base + path)
                p.screenshot(path=str(OUT / f"{name}_{scheme}_{size}.png"), full_page=True)
            ctx.close()
    browser.close()
print(sorted(f.name for f in OUT.iterdir()))
