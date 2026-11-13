# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BN samples: the real pages of the review server (made-up "Associate NN" data), each drawn with one of the three sample stylesheets.
Usage: python shoot.py <server details json> <look ...>"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
cfg = json.loads(Path(sys.argv[1]).read_text())
LOOKS = {"a_atelier": "light", "b_lacquer": "dark", "c_platinum": "dark"}
wanted = sys.argv[2:] or list(LOOKS)
key = cfg["key"]
PAGES = [("signin", "/login", False), ("home", "/", True), ("rta", f"/day?program={key}", True), ("week", f"/week?program={key}", True),
         ("overview", f"/overview?program={key}", True)]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for look in wanted:
        css = (HERE / "common.css").read_text() + (HERE / f"{look}.css").read_text()
        for size, (w, h) in (("desktop", (1440, 900)), ("phone", (390, 844))):
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, bypass_csp=True)
            ctx.add_cookies([{"name": "theme", "value": LOOKS[look], "url": cfg["base"]}])
            pg = ctx.new_page()
            for name, path, signed in PAGES:
                if size == "phone" and name not in ("home", "rta"):
                    continue
                if signed and not getattr(ctx, "_in", False):
                    pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
                    pg.press("input[name=password]", "Enter"); pg.wait_for_load_state("networkidle"); ctx._in = True
                pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
                pg.add_style_tag(content=css); pg.wait_for_timeout(250)
                pg.screenshot(path=str(HERE / "shots" / f"{look}_{name}_{size}.png"))
            ctx.close()
    b.close()
print("done")
