# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA: the little 3D on the real pages in the three looks: sign-in, Home, Weeks, Leave and swaps. argv[1] review-server details, argv[2] folder."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
Q = cfg["key"].replace(" ", "+"); W = cfg["week"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for look in ("light", "dark", "draft"):
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.add_cookies([{"name": "theme", "value": look, "url": cfg["base"]}]); pg = ctx.new_page()
        pg.goto(cfg["base"] + "/login"); pg.wait_for_timeout(500); pg.screenshot(path=str(out / f"d3_{look}_login.png"))
        pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for n, path in (("home", "/"), ("week", f"/week?program={Q}&week={W}"), ("requests", f"/requests?program={Q}")):
            pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300); pg.screenshot(path=str(out / f"d3_{look}_{n}.png")); print(look, n, flush=True)
        ctx.close()
    b.close()
