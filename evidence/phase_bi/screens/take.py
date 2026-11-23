# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: screenshots of the built volumes pages on the browser tests' fixture (made-up people and numbers). Run from the repository root
with the web venv: python evidence/phase_bi/screens/take.py OUT_DIR"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, ".")
from webapp.programs import ProgramBook  # noqa: E402
from webapp.tests import test_ui_playwright as T  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
C = T.ThePhaseVInTheBrowser
C.setUpClass()
try:
    store, key, vb = C.store, C.key, C.app.extensions["volumes"]
    step = vb.step(key)
    rng = random.Random(3)
    today = date.today()
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)

    def shape(h, wd):
        base = {8: 4, 9: 8, 10: 10, 11: 9, 12: 6, 13: 6, 14: 8, 15: 9, 16: 7, 17: 5, 18: 3, 19: 2}
        return base.get(h, 0) if wd not in (4, 5) or 10 <= h <= 15 else 0

    rows = []
    for w in range(0, 9):
        for k in range(7):
            day = sunday - timedelta(weeks=w) + timedelta(days=k)
            if day >= today:
                continue
            for h in range(8, 20):
                for sub in range(60 // step):
                    calls = round(shape(h, day.weekday()) * (9 if day.weekday() in (6, 0) else 7) / (60 // step) * rng.uniform(0.92, 1.1) * (1.08 if w == 1 else 1))
                    rows.append((day.isoformat(), h * 60 + sub * step, calls, round(300 * rng.uniform(0.95, 1.05), 1)))
    store.replace_volume_rows(key, "Phone", rows, 1)
    program_id = ProgramBook(store).unit(key)["program"]["id"]
    ProgramBook(store).set_measure(program_id, "sl")
    vb.save_forecast(key, "Phone", sunday - timedelta(weeks=1), 7000, {}, 1)
    for scheme in ("dark", "light"):
        for width in (1280, 360):
            page = C.browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
            page.goto(C.base + "/login")
            page.get_by_label("Username").fill("omar")
            page.get_by_label("Password").fill("Owner-pass-123")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(C.base + "/")
            for tab, extra in (("actuals", {}), ("forecast", {}), ("how", {"week": (sunday - timedelta(weeks=1)).isoformat()}), ("settings", {})):
                page.goto(f"{C.base}/volumes?" + urlencode({"program": key, "tab": tab, **extra}))
                page.wait_for_load_state("networkidle")
                page.screenshot(path=str(OUT / f"vol_{tab}_{scheme}_{width}.png"), full_page=True)
            page.close()
finally:
    C.tearDownClass()
print("done", len(list(OUT.glob("*.png"))))
