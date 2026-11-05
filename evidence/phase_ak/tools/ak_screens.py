# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK: screens of what changed, from the review server (argv[1]) into argv[2]: Roles, People (team managers),
Leave and swaps (where each request waits, as the admin and as the team manager), a schedule in another zone, and
Fix breaks from 07:00; 1440 px and a phone, dark and light."""
import json, sys
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = sys.argv[2]
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]; R = cfg["run_id"]
SHOTS = [("roles", "/admin/roles"), ("people", "/admin/users"), ("requests", f"/requests?program={Q}"),
         ("schedule_london", f"/runs/{R}/schedules?tz=Europe/London"),
         ("fix_breaks_0700", f"/day?program={Q}&date={D}&view=replan&tz=Africa/Cairo&start=07:00")]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for who, password in (("omar", "Owner-pass-123"), ("tm", "Owner-pass-123")):
        for scheme in ("dark", "light"):
            for width in (1440, 390):
                ctx = b.new_context(viewport={"width": width, "height": 1000}, color_scheme=scheme)
                pg = ctx.new_page()
                pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", who); pg.fill("input[name=password]", password)
                with pg.expect_navigation(): pg.keyboard.press("Enter")
                for name, path in (SHOTS if who == "omar" else [("requests", f"/requests?program={Q}"), ("home", "/")]):
                    pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
                    pg.screenshot(path=f"{out}/{who}_{name}_{scheme}_{width}.png", full_page=True)
                ctx.close()
    b.close()
print("done")
