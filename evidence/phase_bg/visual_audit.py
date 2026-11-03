# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BG: crawl every page a role can reach, in a real browser, at three widths in both looks, and report what is wrong on it:
console errors, CSP violations, failed requests, sideways scroll, things past the edge, broken images, missing names and labels,
duplicate ids, heading problems, small tap targets, low text contrast and focus rings that do not show.
Usage (from the repository root, with the review server running): python visual_audit.py CONFIG.json OUT_DIR [role ...]
Made-up "Associate NN" data only."""
import json
import re
import sys
from collections import defaultdict, deque
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

cfg = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
ROLES = {"admin": ("omar", "Owner-pass-123"), "team_manager": ("tm", "Owner-pass-123"),
         "associate": (cfg["associate"], "Owner-pass-123")}
chosen = sys.argv[3:] or list(ROLES)
WIDTHS = (1440, 768, 360)
BASE = cfg["base"]
SEEDS = ["/", "/?all=1", "/me", "/account/password", "/programs", "/team", "/admin/users", "/exports", "/notifications", "/coach",
         "/roles", "/setup/programs", "/channels", "/news"]
SKIP = re.compile(r"/(logout|theme|static|download|export/download|file|delete|end)\b|\.xlsx$|\.zip$|\.csv$|\.pdf$|/wallboard/stream")

AUDIT_JS = r"""
() => {
  const out = {};
  const vw = window.innerWidth;
  const doc = document.documentElement;
  out.sideways = Math.max(0, doc.scrollWidth - vw);
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const inScroller = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; }
    return false; };
  const name = e => (e.innerText || '').trim().slice(0, 40) || e.getAttribute('aria-label') || e.getAttribute('title') || e.id || e.className.toString().slice(0, 30);
  const sel = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && e.className.toString ? '.' + e.className.toString().trim().split(/\s+/).slice(0, 2).join('.') : '');
  const all = [...document.querySelectorAll('body *')].filter(vis);
  out.past_edge = all.filter(e => { const r = e.getBoundingClientRect(); return r.right > vw + 2 && !inScroller(e) && getComputedStyle(e).position !== 'fixed'; })
    .slice(0, 6).map(e => sel(e) + ' ' + Math.round(e.getBoundingClientRect().right));
  out.broken_images = [...document.images].filter(i => i.complete && i.naturalWidth === 0 && vis(i)).map(i => i.src.slice(-60));
  out.no_alt = [...document.images].filter(i => !i.hasAttribute('alt') && vis(i)).map(i => i.src.slice(-60));
  const labelled = i => i.getAttribute('aria-label') || i.getAttribute('aria-labelledby') || i.getAttribute('title') ||
    (i.id && document.querySelector('label[for="' + CSS.escape(i.id) + '"]')) || i.closest('label') || i.type === 'hidden' ||
    i.type === 'submit' || i.type === 'button' || i.type === 'image';
  out.no_label = [...document.querySelectorAll('input, select, textarea')].filter(i => vis(i) && !labelled(i))
    .slice(0, 8).map(i => sel(i) + '[name=' + (i.name || '') + ']');
  out.no_name = [...document.querySelectorAll('a[href], button, [role=button]')].filter(e => vis(e) &&
    !(e.innerText || '').trim() && !e.getAttribute('aria-label') && !e.getAttribute('title') && !e.getAttribute('aria-labelledby') &&
    !e.querySelector('img[alt]:not([alt=""])')).slice(0, 8).map(sel);
  const ids = {}; document.querySelectorAll('[id]').forEach(e => { ids[e.id] = (ids[e.id] || 0) + 1; });
  out.dup_ids = Object.keys(ids).filter(k => ids[k] > 1).slice(0, 8);
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map(h => +h.tagName[1]);
  out.h1_count = hs.filter(n => n === 1).length;
  out.heading_skips = hs.some((n, i) => i > 0 && n > hs[i - 1] + 1);
  out.title = document.title;
  out.lang = doc.lang;
  out.small_targets = vw <= 400 ? [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button]')]
    .filter(e => { if (!vis(e)) return false; const r = e.getBoundingClientRect(); return (r.width < 24 || r.height < 24) && !(e.tagName === 'A' && getComputedStyle(e).display === 'inline'); })
    .slice(0, 8).map(e => sel(e) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height) + ' "' + name(e) + '"') : [];
  // contrast
  const parse = c => { let m = c.match(/rgba?\(([^)]+)\)/); if (m) { const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    m = c.match(/color\(srgb ([^)]+)\)/); if (m) { const p = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1]; }
    m = c.match(/oklab|oklch|lab|lch/); return null; };
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (fg, bg) => [0, 1, 2].map(i => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat([1]);
  const bgOf = e => { const stack = []; for (let p = e; p; p = p.parentElement) { const s = getComputedStyle(p);
      if (s.backgroundImage !== 'none' && !/^linear-gradient/.test(s.backgroundImage)) return null;
      const c = parse(s.backgroundColor); if (c && c[3] > 0) { stack.push(c); if (c[3] >= 1) break; } }
    let base = [255, 255, 255, 1]; const root = parse(getComputedStyle(document.body).backgroundColor); if (root && root[3] >= 1) base = root;
    for (let i = stack.length - 1; i >= 0; i--) base = blend(stack[i], base); return base; };
  const bad = [];
  const seen = new Set();
  for (const e of all) {
    const direct = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!direct) continue;
    const s = getComputedStyle(e); const fg0 = parse(s.color); const bg = bgOf(e);
    if (!fg0 || !bg) continue;
    const fg = blend([fg0[0], fg0[1], fg0[2], fg0[3] * (parseFloat(s.opacity) || 1)], bg);
    const l1 = lum(fg), l2 = lum(bg); const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const px = parseFloat(s.fontSize); const bold = parseInt(s.fontWeight) >= 700; const large = px >= 24 || (px >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    if (ratio < need - 0.01 && !e.disabled) { const key = sel(e) + Math.round(ratio * 10); if (!seen.has(key)) { seen.add(key);
      bad.push(sel(e) + ' ' + ratio.toFixed(2) + ' (<' + need + ') "' + (e.innerText || '').trim().slice(0, 30) + '"'); } }
  }
  out.low_contrast = bad.slice(0, 8); out.low_contrast_n = bad.length;
  return out;
}
"""

FOCUS_JS = r"""
() => { const bad = []; const els = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex="0"]')]
  .filter(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; }).slice(0, 40);
  for (const e of els) { const before = getComputedStyle(e); const b = [before.outlineStyle, before.outlineWidth, before.boxShadow, before.borderColor, before.backgroundColor].join('|');
    e.focus({ focusVisible: true }); const a = getComputedStyle(e);
    const after = [a.outlineStyle, a.outlineWidth, a.boxShadow, a.borderColor, a.backgroundColor].join('|');
    const shows = after !== b || (a.outlineStyle !== 'none' && parseFloat(a.outlineWidth) > 0);
    if (!shows) bad.push(e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + (e.className.toString().trim().split(/\s+/)[0] || '') + ' "' + (e.innerText || e.value || '').trim().slice(0, 24) + '"');
    e.blur(); }
  return bad.slice(0, 8); }
"""

INIT = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
"""


def pattern(url):
    p = urlsplit(url)
    path = re.sub(r"/[0-9a-f]{8,}|/\d+", "/*", p.path)
    keys = ",".join(sorted(k.split("=")[0] for k in p.query.split("&") if k))
    return path + "?" + keys


def crawl(page, start, limit=90):
    seen, queue, urls = set(), deque(start), []
    per = defaultdict(int)
    while queue and len(urls) < limit:
        u = queue.popleft()
        if u in seen:
            continue
        seen.add(u)
        pat = pattern(u)
        if per[pat] >= 2 or SKIP.search(urlsplit(u).path):
            continue
        r = page.goto(BASE + u, wait_until="load")
        page.wait_for_load_state("networkidle")
        if r is None or r.status >= 400 or urlsplit(page.url).path in ("/login",):
            urls.append(u)
            per[pat] += 1
            continue
        urls.append(u)
        per[pat] += 1
        for href in page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
            if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            full = urljoin(BASE + u, href)
            if urlsplit(full).netloc != urlsplit(BASE).netloc:
                continue
            rel = urlsplit(full).path + ("?" + urlsplit(full).query if urlsplit(full).query else "")
            if rel not in seen:
                queue.append(rel)
    return urls


def sign_in(ctx, user, password):
    pg = ctx.new_page()
    pg.goto(BASE + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", password)
    with pg.expect_navigation():
        pg.keyboard.press("Enter")
    return pg


results, discovered = [], {}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for role in chosen:
        user, password = ROLES[role]
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        pg = sign_in(ctx, user, password)
        start = list(dict.fromkeys(SEEDS + [f"/day?program={cfg['key'].replace(' ', '+')}&date={cfg['sunday']}",
                                           f"/week?program={cfg['key'].replace(' ', '+')}&week={cfg['week']}",
                                           f"/runs/{cfg['run_id']}", f"/runs/{cfg['run_id']}/schedules", "/requests"]))
        discovered[role] = crawl(pg, start)
        ctx.close()
        print(role, "pages", len(discovered[role]), flush=True)
        for scheme in ("dark", "light"):
            for width in WIDTHS:
                ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
                ctx.add_init_script(INIT)
                pg = sign_in(ctx, user, password)
                logs, failed = [], []
                pg.on("console", lambda m: logs.append(m.text[:160]) if m.type in ("error", "warning") else None)
                pg.on("pageerror", lambda e: logs.append("PAGEERROR " + str(e)[:160]))
                pg.on("requestfailed", lambda r: failed.append(r.url[-80:]))
                pg.on("response", lambda r: failed.append(f"{r.status} {r.url[-80:]}") if r.status >= 400 and r.request.resource_type != "document" else None)
                shots = set()
                for u in discovered[role]:
                    logs.clear(); failed.clear()
                    r = pg.goto(BASE + u, wait_until="load")
                    pg.wait_for_load_state("networkidle")
                    row = {"role": role, "scheme": scheme, "width": width, "url": u, "status": r.status if r else None}
                    if r is not None and r.status < 400 and urlsplit(pg.url).path != "/login":
                        row.update(pg.evaluate(AUDIT_JS))
                        row["focus_hidden"] = pg.evaluate(FOCUS_JS) if width == 1440 and scheme == "dark" else []
                        row["csp"] = pg.evaluate("window.__csp")
                    row["console"] = list(logs)[:4]
                    row["failed"] = list(failed)[:4]
                    results.append(row)
                    pat = pattern(u)
                    if pat not in shots and scheme in ("dark", "light") and r is not None and r.status < 400:
                        shots.add(pat)
                        safe = re.sub(r"[^a-z0-9]+", "_", pat.lower()).strip("_")[:60]
                        pg.screenshot(path=f"{OUT}/screens/{role}_{scheme}_{width}_{safe}.png", full_page=True)
                ctx.close()
                print(role, scheme, width, "done", flush=True)
    browser.close()
json.dump({"discovered": discovered, "rows": results}, open(f"{OUT}/audit.json", "w"), indent=1)
print("rows", len(results))
