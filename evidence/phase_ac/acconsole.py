"""Phase AC: crawl the signed-in site (up to 120 page kinds) and record console errors and warnings, page errors, CSP
violations, failed sub-requests, response headers of a page, and each page's load time; then exercise the main
interactive controls (pickers, dialogs, tabs) on the RTA and record errors."""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zaudit import BASE, INFO, crawl, sign_in  # noqa: E402

OUT = Path(sys.argv[2])
found = {"console": [], "pageerror": [], "failed": [], "slow": [], "headers": {}, "titles": {}, "dup_ids": [],
         "no_h1": [], "multi_main": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1366, "height": 900})
    page = ctx.new_page()
    here = {"url": ""}
    page.on("console", lambda m: found["console"].append((here["url"], m.type, m.text[:300]))
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: found["pageerror"].append((here["url"], str(e)[:300])))
    page.on("response", lambda r: found["failed"].append((here["url"], r.status, r.url))
            if r.status >= 400 and r.request.resource_type != "document" else None)
    page.on("requestfailed", lambda r: found["failed"].append((here["url"], "failed", r.url, r.failure)))
    sign_in(page)
    urls = crawl(page, limit=120)
    for url in urls:
        here["url"] = url
        t = time.perf_counter()
        resp = page.goto(url)
        page.wait_for_load_state("networkidle")
        dt = time.perf_counter() - t
        if dt > 1.5:
            found["slow"].append((round(dt, 2), url))
        found["titles"][url] = page.title()
        dups = page.evaluate("""() => { const c = {}; document.querySelectorAll('[id]').forEach(e => c[e.id] = (c[e.id] || 0) + 1);
            return Object.entries(c).filter(([k, v]) => v > 1).map(([k, v]) => k + 'x' + v); }""")
        if dups:
            found["dup_ids"].append((url, dups))
        if page.locator("h1").count() == 0:
            found["no_h1"].append(url)
        if page.locator("main").count() != 1:
            found["multi_main"].append(url)
        if not found["headers"] and resp:
            found["headers"] = resp.headers
    # interactive controls on the RTA: open each dialog and tab
    day = f"{BASE}/day?program={INFO['key']}&date={INFO['sunday']}"
    here["url"] = day + " (interactions)"
    page.goto(day)
    page.wait_for_load_state("networkidle")
    for sel in ("rect.brk", "select.att"):
        loc = page.locator(sel).first
        if loc.count():
            try:
                if sel == "rect.brk":
                    loc.focus(); page.keyboard.press("Enter"); page.wait_for_timeout(600)
                    page.locator("#break-dialog [data-step='5']").click(); page.wait_for_timeout(800)
                    page.locator("#break-dialog [data-cancel]").click()
                else:
                    loc.select_option(index=3); page.wait_for_timeout(600)
                    if page.locator("#att-dialog[open]").count():
                        page.locator("#att-dialog [data-cancel]").click()
            except Exception as exc:  # noqa: BLE001
                found["pageerror"].append((here["url"], f"interaction {sel}: {exc}"[:300]))
    b.close()
found["pages"] = len(urls)
OUT.write_text(json.dumps(found, indent=1, default=str))
print({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in found.items()})
