# © 2026 Omar Mokhtar. All rights reserved.
"""Render the colour proposals on the review server's pages (an override sheet injected, CSP bypassed for samples only)."""
import json, sys
from pathlib import Path
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright
from palettes import P

def sheet(t, look):
    rgba = lambda h, a: f"rgba({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)}, {a})"
    v = {"--night": t["night"], "--rail-bg": t["rail_bg"], "--console": t["console"], "--console-2": t["console_2"],
         "--rail": t["rail"], "--paper": t["paper"], "--dim": t["dim"], "--edge": t["edge"], "--action": t["paper"],
         "--selected": t["console_2"], "--panel": rgba(t["console"], .9 if look == "night" else .94),
         "--header": rgba(t["night"], .88), "--empty-cell": rgba(t["rail"], .5 if look == "night" else 1),
         "--empty-key": t["rail"], "--code-bg": t["rail_bg"] if look == "night" else t["console_2"]}
    if look == "night":
        v.update({"--on-action": t["night"], "--action-hover": "#FFFFFF", "--well": rgba(t["night"], .6),
                  "--on-covered": t["night"], "--on-short": t["night"], "--on-gap": t["night"], "--on-over": t["night"],
                  "--bg-line": rgba(t["dim"], .045), "--h0": t["console_2"]})
        sel = ":root"
    else:
        v.update({"--on-action": "#FFFFFF", "--well": t["console_2"], "--bg-line": rgba(t["paper"], .045)})
        sel = ':root:not([data-theme="dark"])'
    body = "; ".join(f"{k}: {x}" for k, x in v.items())
    return f"{sel} {{ {body} }}" if look == "night" else f"@media (prefers-color-scheme: light) {{ {sel} {{ {body} }} }}"

cfg = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2]); out.mkdir(exist_ok=True)
key = quote_plus(cfg["key"])
jobs = [("rta", f"/day?program={key}&date={cfg['sunday']}", "omar", 1440, 900, False),
        ("requests", f"/requests?program={key}", "omar", 1440, 900, False),
        ("me", "/me", cfg["associate"], 390, 844, True)]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for name, looks in P.items():
        for look in ("night", "day"):
            if name == "current" and look == "day":
                continue
            css = sheet(looks[look], look) if name != "current" else ""
            for job, url, user, w, h, full in jobs:
                if job == "requests" and look == "day":
                    continue
                ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme="light" if look == "day" else "dark",
                                    bypass_csp=True)
                pg = ctx.new_page()
                pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", user)
                pg.fill("input[name=password]", "Owner-pass-123"); pg.click("form button.primary")
                pg.wait_for_load_state("networkidle")
                pg.goto(cfg["base"] + url); pg.wait_for_load_state("networkidle")
                if css:
                    pg.add_style_tag(content=css)
                pg.screenshot(path=str(out / f"{job}_{name}_{look}.png"), full_page=full)
                ctx.close()
    b.close()
print("done")
