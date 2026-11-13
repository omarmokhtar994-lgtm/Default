# © 2026 Omar Mokhtar. All rights reserved.
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE = Path(__file__).parent
pages = sorted(HERE.glob("*_day.html")) + sorted(HERE.glob("*_signin.html"))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for f in pages:
        for label, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto(f.as_uri()); pg.wait_for_timeout(1400)
            pg.screenshot(path=str(HERE / "shots" / f"{f.stem}_{label}.png"))
            if "day" in f.stem:
                pg.mouse.wheel(0, 700); pg.wait_for_timeout(500)
                pg.screenshot(path=str(HERE / "shots" / f"{f.stem}_{label}_scrolled.png"))
            pg.close()
    b.close()
print("done")
