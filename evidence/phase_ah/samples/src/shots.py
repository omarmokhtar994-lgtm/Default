# © 2026 Omar Mokhtar. All rights reserved.
"""Screenshots of the Phase AH samples: python shots.py <samples dir>"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
out = Path(sys.argv[1])
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for theme in ("dark", "light"):
        pg = b.new_page(viewport={"width": 1320, "height": 900})
        pg.goto((out / f"ah01_hours_needed_{theme}.html").resolve().as_uri()); pg.wait_for_timeout(400)
        pg.screenshot(path=str(out / f"ah01_hours_needed{'' if theme == 'dark' else '_day'}.png"), full_page=True)
        pg.close()
    b.close()
