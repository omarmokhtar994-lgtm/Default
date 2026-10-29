# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BB: depth on the real Incidents, Shrinkage and Programs pages in the three looks. argv[1] review-server details, argv[2] folder."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
Q = cfg["key"].replace(" ", "+")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for look in ("light", "dark", "draft"):
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.add_cookies([{"name": "theme", "value": look, "url": cfg["base"]}]); pg = ctx.new_page()
        pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for n, path in (("home", "/"), ("incidents", f"/incidents?program={Q}"), ("shrinkage", f"/shrinkage?program={Q}"), ("programs", f"/programs/{Q.replace('+', '%20')}")):
            r = pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
            print(look, n, r.status, "faces:", pg.locator("polygon.face").count(), "charts:", pg.locator("svg.chart").count(), "overflow:", pg.evaluate("document.documentElement.scrollWidth - innerWidth"), flush=True)
            pg.screenshot(path=str(out / f"bb_{look}_{n}.png"), full_page=True)
        ctx.close()
    b.close()
