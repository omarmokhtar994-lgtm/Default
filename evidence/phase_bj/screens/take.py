# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ: screenshots of the built volumes pages (typed grid, draft, questions, the suggestion built step by step) on the browser tests' fixture
(made-up people and numbers). Run from the repository root with the web venv: python evidence/phase_bj/screens/take.py OUT_DIR"""
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
    nxt = sunday + timedelta(weeks=1)

    def shape(h, wd):
        base = {8: 4, 9: 8, 10: 10, 11: 9, 12: 6, 13: 6, 14: 8, 15: 9, 16: 7, 17: 5, 18: 3, 19: 2}
        return base.get(h, 0) if wd not in (4, 5) or 10 <= h <= 15 else 0

    for channel, scale in (("Phone", 9), ("Chat", 4)):
        rows = []
        for w in range(1, 10):
            for k in range(7):
                day = sunday - timedelta(weeks=w) + timedelta(days=k)
                for h in range(8, 20):
                    for sub in range(60 // step):
                        calls = round(shape(h, day.weekday()) * (scale if day.weekday() in (6, 0) else scale * 0.8) / (60 // step) * rng.uniform(0.94, 1.08)
                                      * (0.35 if w == 3 else 1))
                        rows.append((day.isoformat(), h * 60 + sub * step, calls, round(300 * rng.uniform(0.95, 1.05), 1)))
        store.replace_volume_rows(key, channel, rows, 1)
    program_id = ProgramBook(store).unit(key)["program"]["id"]
    ProgramBook(store).set_measure(program_id, "sl")
    vb.add_driver(key, "events", {"kind": "Promotion", "name": "Autumn sale", "channels": ["Phone", "Chat"], "start": (nxt + timedelta(days=2)).isoformat(),
                                   "end": (nxt + timedelta(days=4)).isoformat(), "change": 25, "after_days": 2, "after_change": -15}, 1)
    vb.add_driver(key, "ai", {"channel": "Phone", "start": nxt.isoformat(), "end": (nxt + timedelta(days=6)).isoformat(), "change": -12,
                              "move_to": "Chat", "move_share": 40}, 1)
    vb.set_growth(key, {"Phone": 6, "Chat": 18}, "measured", 1)
    vb.set_last_year(key, nxt, {"Phone": 14500, "Chat": 6200}, 1)
    for scheme in ("dark", "light"):
        for width in (1280, 360):
            page = C.browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
            page.goto(C.base + "/login")
            page.get_by_label("Username").fill("omar")
            page.get_by_label("Password").fill("Owner-pass-123")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(C.base + "/")
            page.goto(f"{C.base}/volumes?" + urlencode({"program": key, "tab": "actuals"}))
            page.wait_for_load_state("networkidle")
            form = page.locator("form[data-entry-form]")
            form.locator("select[name=week]").select_option(index=form.locator("select[name=week] option").count() - 2)
            for i, v in ((18, "12"), (19, "15"), (20, "18"), (21, "16")):
                form.locator(f'table[data-entry-grid="offered"] input[data-i="{i}"][data-d="2"]').fill(v)
            page.screenshot(path=str(OUT / f"bj_actuals_{scheme}_{width}.png"), full_page=True)
            page.goto(f"{C.base}/volumes?" + urlencode({"program": key, "tab": "forecast", "channel": "Chat", "week": nxt.isoformat()}))
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(OUT / f"bj_forecast_{scheme}_{width}.png"), full_page=True)
            page.evaluate("document.querySelectorAll('main details').forEach(d => { d.open = true; })")
            page.screenshot(path=str(OUT / f"bj_questions_{scheme}_{width}.png"), full_page=True)
            page.close()
finally:
    store.set_volume_drivers(key, {}, 1)
    C.tearDownClass()
print("done", len(list(OUT.glob("*.png"))))
