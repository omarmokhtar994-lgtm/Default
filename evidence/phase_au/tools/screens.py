# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: real screens of the Phase AR, AS and AT pages (made-up "Associate NN" data, the clock stopped on
Wednesday 14 October 2026 at 12:00 Cairo time). Run from the repository root with the web venv:
PYTHONPATH=. python evidence/phase_au/tools/screens.py evidence/phase_au/screens"""
import html
import io
import re
import sys
import threading
from pathlib import Path
from unittest import mock

from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from webapp.bulk_users import HEAD
from webapp.tests.test_as_pages import _Noon
from webapp.tests.test_as_requests import ME, MATE, WED, _Fixture
from webapp.tests.test_runs import sign_in

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


class Setup(_Fixture):
    def runTest(self):
        pass


Setup.setUpClass()
patch = mock.patch("webapp.app.datetime", _Noon)
patch.start()
S = Setup()
S.clear()
app, store, key = Setup.app, Setup.store, Setup.key
uid = store.add_user("tm_only", "Team Manager 07", "Manager-pass-123", must_change=False)
store.update_user(uid, is_team_manager=1)
store.set_user_programs(uid, [Setup.pid])


adm = store.add_user("admin_demo", "Admin 01", "Admin-pass-1234", must_change=False)
store.update_user(adm, is_admin=1)


def post(client, url, **data):
    page = client.get("/", follow_redirects=True).get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    return client.post(url, data={"csrf_token": csrf, **data})


assoc = sign_in(app, "a027", "Associate-pass-1")
page = html.unescape(assoc.get("/me/breaks", query_string={"change": 0}).get_data(as_text=True))
first = re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1)
post(assoc, "/me/breaks", idx=0, to=first, why="Made-up: appointment")
tm = sign_in(app, "tm_only", "Manager-pass-123")
post(tm, "/requests/coaching", program=key, date=WED.isoformat(), names=[ME, MATE], start="14:00", minutes="30",
     dept="Quality", why="Made-up: call review", billable="1")

wb = Workbook()
ws = wb.active
ws.append(HEAD)
ws.append(["associate_01", "Associate 01", "associate", "SAKS", "Associate 006", "", ""])
ws.append(["associate_02", "Associate 02", "associate", "SAKS", "Associate 007", "", ""])
ws.append(["planner_01", "Planner 01", "planner", "SAKS", "", "", ""])
ws.append(["associate_01", "Associate 03", "associate", "SAKS", "Associate 008", "", ""])
ws.append(["associate_04", "Associate 04", "associate", "Nowhere", "Associate 012", "", ""])
buf = io.BytesIO()
wb.save(buf)

server = make_server("127.0.0.1", 0, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"
Q = key.replace(" ", "+")

SHOTS = [  # (file, user, password, path, steps, sizes)
    ("ar1_people", "admin_demo", "Admin-pass-1234", "/admin/users", "made", "d"),
    ("ar2_bulk_choose", "admin_demo", "Admin-pass-1234", "/admin/users/bulk", "", "d"),
    ("ar3_bulk_checked", "admin_demo", "Admin-pass-1234", "/admin/users/bulk", "bulk", "d"),
    ("as1_my_day", "a027", "Associate-pass-1", "/me/breaks", "", "dp"),
    ("au1_my_weeks", "a027", "Associate-pass-1", "/me", "", "dp"),
    ("as2_pick_time", "a027", "Associate-pass-1", "/me/breaks?change=1", "", "dp"),
    ("as3_coaching_form", "tm_only", "Manager-pass-123", "/requests/coaching", "", "d"),
    ("as4_rta_requests", "rta1", "Staff-pass-123", f"/day?program={Q}&date=2026-10-14&view=requests", "", "d"),
    ("as5_measure_setup", "admin_demo", "Admin-pass-1234", "/setup/programs", "", "d"),
    ("at1_sign_in", "", "", "/login", "", "dp"),
]
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for name, user, pw_, path, step, sizes in SHOTS:
        for scheme in ("dark", "light"):
            for size in sizes:
                w, h = (1280, 1300 if step == "made" else 900) if size == "d" else (390, 844)
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, reduced_motion="reduce")
                p = ctx.new_page()
                if user:
                    p.goto(base + "/login")
                    p.fill("input[name=username]", user)
                    p.fill("input[name=password]", pw_)
                    p.click("button.primary")
                    p.wait_for_load_state()
                p.goto(base + path)
                if step == "made":  # make a person with no password: the made-up one is shown once
                    p.fill("input[name=username]", f"associate_{scheme}")
                    p.fill("input[name=display_name]", "Associate 99")
                    p.locator("input[name=programs]").first.check()
                    p.get_by_role("button", name="Add person").click()
                    p.wait_for_selector("#made-h", timeout=8000)
                if step == "bulk":
                    p.set_input_files("input[type=file]", {"name": "People.xlsx", "mimeType": "application/octet-stream",
                                                          "buffer": buf.getvalue()})
                    p.get_by_role("button", name="Check the file").click()
                    p.wait_for_load_state()
                p.screenshot(path=str(OUT / f"{name}_{scheme}_{'phone' if size == 'p' else 'desktop'}.png"), full_page=(step != "made"))
                ctx.close()
    browser.close()
print(sorted(f.name for f in OUT.iterdir()))
