# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BR, Task 3: every tab of the forecast section on a made-up program with 60 weeks of Phone and Chat history, at 1440 px and 390 px wide,
for the review in evidence/phase_br/REVIEW.md. Also lists any console error and any page wider than the window.
Run from the repository root with the web venv:  PYTHONPATH=. python evidence/phase_br/screens.py"""
import random
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accuracy as A  # noqa: E402  (the made-up day shape and counts)

from webapp.programs import ProgramBook  # noqa: E402
from webapp.tests.test_runs import make_app  # noqa: E402

OUT = Path(__file__).resolve().parent / "screens"
CHROMIUM = "/opt/pw-browsers/chromium"


def seed(store, vb, key):
    rng = random.Random(7)
    step = vb.step(key)
    today = date.today()
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    for channel, level in (("Phone", 7000), ("Chat", 2500)):
        rows = []
        for w in range(1, 61):
            grow = 1.0 + 0.003 * (60 - w)
            for k in range(7):
                day = sunday - timedelta(weeks=w) + timedelta(days=k)
                shape = A.day_shape(day.weekday())
                per = [sum(shape[(i * step) // 30:((i + 1) * step) // 30] or [shape[(i * step) // 30] * step / 30]) for i in range(1440 // step)]
                for i, share in enumerate(per):
                    n = A.poisson(rng, level * grow * A.DAY_MIX[day.weekday()] * share)
                    if n:
                        rows.append((day.isoformat(), i * step, n, round(rng.uniform(260, 340), 1)))
        store.replace_volume_rows(key, channel, rows, 1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app, store, *_ = make_app(start_worker=False)
    store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
    programs = ProgramBook(store)
    program_id = programs.add_program("Made-up retail")
    key = programs.add_lob(program_id, "Retail Tier 1")
    programs.set_measure(program_id, "sl")
    vb = app.extensions["volumes"]
    seed(store, vb, key)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    base = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    findings = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM if Path(CHROMIUM).exists() else None)
        for width, name in ((1440, "desktop"), (390, "phone")):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(base + "/login")
            page.get_by_label("Username").fill("omar")
            page.get_by_label("Password").fill("Owner-pass-123")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(base + "/")
            shots = [("actuals", {}), ("forecast", {}), ("forecast_typed", {"total": "7000"}), ("staffing", {"total": "7000"}),
                     ("outlook", {}), ("how", {}), ("settings", {})]
            for tab, extra in shots:
                real = tab.split("_")[0]
                query = "&".join(f"{k}={v}" for k, v in {"program": key, "tab": real, "channel": "Phone"}.items())
                page.goto(f"{base}/volumes?{query}")
                if extra.get("total") and real in ("forecast", "staffing"):
                    page.goto(f"{base}/volumes?{query.replace('tab=staffing', 'tab=forecast')}")
                    page.locator("#total").fill(extra["total"])
                    page.get_by_role("button", name="Work it out").click()
                    page.wait_for_load_state("load")
                    if real == "staffing":
                        page.get_by_role("navigation", name="Volumes").get_by_role("link", name="3. Staffing").click()
                        page.wait_for_load_state("load")
                page.wait_for_timeout(700)
                wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                if wide > 1:
                    findings.append(f"{tab} {name}: page {wide}px wider than the window")
                page.screenshot(path=str(OUT / f"{tab}_{name}.png"), full_page=True)
            findings += [f"{name}: console {e}" for e in errors]
            page.close()
        browser.close()
    server.shutdown()
    print("\n".join(findings) or "no console errors; nothing wider than the window")


if __name__ == "__main__":
    main()
