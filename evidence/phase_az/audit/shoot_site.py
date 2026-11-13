# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AZ audit: every real page of the site on made-up "Associate NN" data, desktop dark and light, phone light.
Run after evidence/phase_ai/tools/review_server.py wrote its details to argv[1]; screens go to argv[2]."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]; W = cfg["week"]; R = cfg["run_id"]
PAGES = {
    "login": "/login", "home": "/", "day_timeline": f"/day?program={Q}&date={D}&tz=Africa/Cairo&start=00:00",
    "day_board": f"/day?program={Q}&date={D}&view=board", "day_adherence": f"/day?program={Q}&date={D}&view=adherence",
    "day_cover": f"/day?program={Q}&date={D}&view=cover", "day_channels": f"/day?program={Q}&date={D}&view=channels",
    "day_replan": f"/day?program={Q}&date={D}&view=replan", "overview": f"/overview?program={Q}&date={D}",
    "wallboard": f"/day/wallboard?program={Q}&date={D}", "handover": f"/day/handover?program={Q}&date={D}",
    "week": f"/week?program={Q}&week={W}", "schedules": f"/schedules?program={Q}", "run": f"/runs/{R}",
    "run_schedules": f"/runs/{R}/schedules", "requests": f"/requests?program={Q}", "incidents": f"/incidents?program={Q}",
    "notifications": "/notifications", "programs": "/programs", "exports": "/exports", "team": "/team",
    "shrinkage": f"/shrinkage?program={Q}", "admin_users": "/admin/users", "admin_bulk": "/admin/users/bulk",
    "roles": "/admin/roles", "setup_with": f"/setup/with?program={Q}", "setup_channels": f"/setup/channels?program={Q}",
    "setup_programs": "/setup/programs", "coach": "/coach", "password": "/account/password",
}
RUNS = (("dark", "dark", 1440, 900), ("day", "light", 1440, 900), ("phone", "light", 390, 844))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for tag, scheme, w, h in RUNS:
        ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1)
        pg = ctx.new_page()
        pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for name, path in PAGES.items():
            if name == "login":
                continue
            r = pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
            pg.screenshot(path=str(out / f"{tag}_{name}.png"), full_page=(tag != "dark" or name in ("home", "overview")))
            print(tag, name, r.status, flush=True)
        ctx.close()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); pg = ctx.new_page()
    pg.goto(cfg["base"] + "/login"); pg.screenshot(path=str(out / "dark_login.png"))
    ctx.close()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="light"); pg = ctx.new_page()
    pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", cfg["associate"]); pg.fill("input[name=password]", "Owner-pass-123")
    with pg.expect_navigation(): pg.keyboard.press("Enter")
    for n, path in (("me", "/me"), ("me_breaks", "/me/breaks")):
        pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
        pg.screenshot(path=str(out / f"phone_{n}.png"), full_page=True); print("assoc", n, flush=True)
    b.close()
