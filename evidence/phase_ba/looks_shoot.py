# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA: the real pages in the three looks (cookie theme=light, dark, draft). Run after review_server.py; argv[1] its details, argv[2] the output folder,
argv[3] optional comma list of page names, argv[4] optional comma list of looks."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]; W = cfg["week"]; R = cfg["run_id"]
PAGES = {"home": "/", "day": f"/day?program={Q}&date={D}&tz=Africa/Cairo&start=00:00", "week": f"/week?program={Q}&week={W}", "requests": f"/requests?program={Q}",
         "wallboard": f"/day/wallboard?program={Q}&date={D}", "admin_users": "/admin/users", "schedules": f"/schedules?program={Q}", "run": f"/runs/{R}",
         "incidents": f"/incidents?program={Q}", "exports": "/exports", "roles": "/admin/roles", "coach": "/coach", "setup_channels": f"/setup/channels?program={Q}", "run_schedules": f"/runs/{R}/schedules"}
names = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else list(PAGES)
looks = sys.argv[4].split(",") if len(sys.argv) > 4 and sys.argv[4] else ["light", "dark", "draft"]
W_, H_ = (int(x) for x in (sys.argv[5] if len(sys.argv) > 5 else "1440x900").split("x"))
full = len(sys.argv) > 6 and sys.argv[6] == "full"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for look in looks:
        ctx = b.new_context(viewport={"width": W_, "height": H_}, device_scale_factor=1, reduced_motion="reduce")
        ctx.add_cookies([{"name": "theme", "value": look, "url": cfg["base"]}])
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for n in names:
            r = pg.goto(cfg["base"] + PAGES[n]); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
            pg.screenshot(path=str(out / f"{look}_{n}_{W_}.png"), full_page=full); print(look, n, r.status, "errors", errs[-1:] if errs else "-", flush=True)
        ctx.close()
    b.close()
