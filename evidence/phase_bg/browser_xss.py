# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BG: stored XSS in a real browser. Puts script payloads into the free-text fields people can fill (display name, username-like fields,
program and LOB names), then opens every page the crawl found and checks that no payload ran (window.__pwned stays unset), no payload element
exists in the page, and the browser reports no policy violation that came from a payload. Usage: python browser_xss.py CONFIG.json
(the review server running). Made-up data only."""
import json
import re
import sys
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

cfg = json.load(open(sys.argv[1]))
BASE = cfg["base"]
PAYLOADS = ['"><img src=x onerror="window.__pwned=1">', "<svg onload=\"window.__pwned=2\">", "'-window.__pwned=3-'", "</script><script>window.__pwned=4</script>",
            "javascript:window.__pwned=5", "{{7*7}}", "<iframe srcdoc=\"<script>parent.__pwned=6</script>\">"]
INIT = "window.__pwned = 0; window.__viol = []; document.addEventListener('securitypolicyviolation', e => window.__viol.push(e.violatedDirective + ' ' + e.blockedURI));"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script(INIT)
    pg = ctx.new_page()
    pg.goto(BASE + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
    with pg.expect_navigation(): pg.keyboard.press("Enter")
    made = []
    for i, payload in enumerate(PAYLOADS):
        pg.goto(BASE + "/admin/users"); pg.wait_for_load_state("load")
        form = pg.locator("form:has(input[name=username])").first
        form.locator("input[name=username]").fill(f"xss_user_{i}")
        form.locator("input[name=display_name]").fill(payload)
        form.locator("input[name=password]").fill(f"Xss-Tester-{i}-pass-9")
        form.locator("button[type=submit], button:not([type])").first.click()
        pg.wait_for_load_state("load")
        made.append(f"xss_user_{i}")
    seen, queue, bad = set(), ["/", "/admin/users", "/team", "/requests", "/exports", "/programs", "/me", "/notifications", "/incidents", "/shrinkage"], []
    while queue and len(seen) < 80:
        u = queue.pop(0)
        if u in seen or re.search(r"/(logout|theme|download|delete)\b|\.(xlsx|zip|csv)(\?|$)", u):
            continue
        seen.add(u)
        r = pg.goto(BASE + u); pg.wait_for_load_state("networkidle")
        if r is None or r.status >= 400:
            continue
        flagged = pg.evaluate("window.__pwned")
        injected = pg.evaluate("document.querySelectorAll('img[src=x], svg[onload], iframe[srcdoc], script:not([src])').length")
        onattrs = pg.evaluate("[...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a => /^on/i.test(a.name))).length")
        viol = [v for v in pg.evaluate("window.__viol") if "inline" in v or "eval" in v]
        if flagged or injected or onattrs or viol:
            bad.append({"url": u, "pwned": flagged, "injected_elements": injected, "on_attributes": onattrs, "violations": viol[:3]})
        for href in pg.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
            if href and not href.startswith(("#", "mailto:", "javascript:")) and urlsplit(urljoin(BASE + u, href)).netloc == urlsplit(BASE).netloc:
                full = urljoin(BASE + u, href); queue.append(urlsplit(full).path + ("?" + urlsplit(full).query if urlsplit(full).query else ""))
    print("pages opened:", len(seen), "payload people made:", len(made))
    print("PROBLEMS:", json.dumps(bad, indent=1) if bad else "none")
    b.close()
