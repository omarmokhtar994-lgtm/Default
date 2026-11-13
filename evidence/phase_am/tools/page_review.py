# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI T12 (Phase AK: Roles, a schedule in another zone and the RTA tools from 07:00 added): every page at 360 and 1440 px in the dark and light looks: status, console errors, sideways
scroll on a phone. Screens of the RTA views go to argv[2]."""
import json, sys
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = sys.argv[2]
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]; W = cfg["week"]; R = cfg["run_id"]
PAGES = ["/", "/?all=1", f"/day?program={Q}&date={D}&tz=Africa/Cairo&start=00:00",
         f"/day?program={Q}&date={D}&view=board", f"/day?program={Q}&date={D}&view=adherence",
         f"/day?program={Q}&date={D}&view=meeting", f"/day?program={Q}&date={D}&view=cover",
         f"/day?program={Q}&date={D}&view=channels", f"/day?program={Q}&date={D}&view=rescue",
         f"/day?program={Q}&date={D}&view=replan", f"/day?program={Q}&date={D}&view=bulk",
         f"/day?program={Q}&date={D}&tz=America/New_York&start=16:00",
         f"/day?program={Q}&date={D}&view=board", f"/day?program={Q}&date={D}&view=adherence",
         f"/day?program={Q}&date={D}&view=cover", f"/day?program={Q}&date={D}&tz=Africa/Cairo&start=00:00",
         f"/overview?program={Q}&date={D}", f"/day/wallboard?program={Q}&date={D}", f"/day/handover?program={Q}&date={D}",
         f"/week?program={Q}&week={W}", f"/schedules?program={Q}", f"/runs/{R}", f"/runs/{R}/schedules",
         f"/requests?program={Q}", "/notifications", "/programs", "/exports", "/team", "/admin/users",
         f"/setup/with?program={Q}", f"/setup/channels?program={Q}", "/setup/programs", "/coach", "/account/password",
         "/admin/roles", f"/runs/{R}/schedules?tz=Europe/London", f"/day?program={Q}&date={D}&view=replan&start=07:00",
         f"/day?program={Q}&date={D}&view=rescue&start=07:00", f"/day?program={Q}&date={D}&view=bulk&start=07:00"]
found = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for scheme in ("dark", "light"):
        for width in (1440, 360):
            ctx = b.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
            pg = ctx.new_page()
            errors = []
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
            with pg.expect_navigation(): pg.keyboard.press("Enter")
            for i, path in enumerate(PAGES):
                errors.clear()
                r = pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
                wide = pg.evaluate("document.scrollingElement.scrollWidth - window.innerWidth")
                if r.status >= 400 or errors or (width == 360 and wide > 1):
                    found.append({"scheme": scheme, "width": width, "path": path, "status": r.status,
                                  "errors": errors[:3], "sideways": wide})
                if scheme == "dark" and "day?" in path:
                    pg.screenshot(path=f"{out}/t12_{width}_{i:02d}.png", full_page=False)
            ctx.close()
    # the associate's own pages
    ctx = b.new_context(viewport={"width": 360, "height": 800}); pg = ctx.new_page()
    errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", cfg["associate"]); pg.fill("input[name=password]", "Owner-pass-123")
    with pg.expect_navigation(): pg.keyboard.press("Enter")
    for path in ("/me", f"/me?swap={D}"):
        r = pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
        wide = pg.evaluate("document.scrollingElement.scrollWidth - window.innerWidth")
        if r.status >= 400 or errors or wide > 1:
            found.append({"who": "associate", "path": path, "status": r.status, "errors": errors[:3], "sideways": wide})
    b.close()
print(json.dumps(found, indent=1))
print("problems:", len(found))
