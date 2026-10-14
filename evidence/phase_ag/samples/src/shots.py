import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
here = Path(__file__).parent
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
DESK = [("ag00_design_board", "board", 1440, 1000), ("ag01_rta_floor", "rta", 1440, 900), ("ag02_requests", "requests", 1440, 960),
        ("ag03_week", "week", 1440, 900), ("ag04_go_to", "goto", 1440, 900)]
PHONE = [("ag05_my_week_phone", "myweek"), ("ag06_request_leave_phone", "leave"), ("ag07_offer_swap_phone", "swap")]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for theme in ("dark", "light"):
        for shot, name, w, h in DESK:
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto((here / f"{name}.html").as_uri()); pg.evaluate(f"document.documentElement.dataset.theme='{theme}'")
            pg.wait_for_timeout(300); pg.screenshot(path=str(out / f"{shot}{'' if theme == 'dark' else '_light'}.png")); pg.close()
        for shot, name in PHONE:
            pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            pg.goto((here / f"{name}.html").as_uri()); pg.evaluate(f"document.documentElement.dataset.theme='{theme}'")
            pg.wait_for_timeout(300); pg.screenshot(path=str(out / f"{shot}{'' if theme == 'dark' else '_light'}.png")); pg.close()
    b.close()
print("ok")
