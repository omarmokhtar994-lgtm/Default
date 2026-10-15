# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AJ: screens of what changed, from the review server (argv[1]) into argv[2]: the cover panel on the Overtime
and VTO tab, the board's cover panel note, and the Timeline from 07:00 (channel colours past midnight)."""
import json, sys
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = sys.argv[2]
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for scheme in ("dark", "light"):
        for width in (1440, 360):
            ctx = b.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
            pg = ctx.new_page()
            pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
            with pg.expect_navigation(): pg.keyboard.press("Enter")
            pg.goto(f"{cfg['base']}/day?program={Q}&date={D}&view=cover"); pg.wait_for_load_state("networkidle")
            pg.locator("#outside-h").scroll_into_view_if_needed()
            pg.locator("section[aria-labelledby=outside-h]").screenshot(path=f"{out}/cover_panel_{scheme}_{width}.png")
            if width == 1440:
                pg.goto(f"{cfg['base']}/day?program={Q}&date={D}&tz=Africa/Cairo&start=07:00"); pg.wait_for_load_state("networkidle")
                pg.screenshot(path=f"{out}/timeline_0700_{scheme}.png", full_page=True)
                pg.goto(f"{cfg['base']}/day?program={Q}&date={D}&view=board"); pg.wait_for_load_state("networkidle")
                pg.screenshot(path=f"{out}/board_{scheme}.png", full_page=False)
            ctx.close()
    b.close()
print("done")
