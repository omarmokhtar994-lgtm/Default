# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AV: an accessibility check of the Incidents, Shrinkage and Booked sessions pages and the new Exports and setup parts, in both looks and at 1280 and 360 px:
text contrast against its real background (4.5, or 3 for large text), a name on every control, one h1 and no skipped
heading level, no sideways scroll on a phone. Made-up data. Run from the repository root with the web venv:
PYTHONPATH=. python evidence/phase_av/tools/a11y.py"""
import json
import re
import sys
import threading
from unittest import mock

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from webapp.tests.test_as_pages import _Noon
from webapp.tests.test_as_requests import ME, MATE, WED, _Fixture
from webapp.tests.test_runs import sign_in, token


class Setup(_Fixture):
    def runTest(self):
        pass


Setup.setUpClass()
mock.patch("webapp.app.datetime", _Noon).start()
Setup().clear()
app, store, key = Setup.app, Setup.store, Setup.key
uid = store.add_user("tm_only", "Team Manager 07", "Manager-pass-123", must_change=False)
store.update_user(uid, is_team_manager=1)
store.set_user_programs(uid, [Setup.pid])
adm = store.add_user("admin_demo", "Admin 01", "Admin-pass-1234", must_change=False)
store.update_user(adm, is_admin=1)


def post(client, url, **data):
    page = client.get("/", follow_redirects=True).get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    return client.post(url, data={"csrf_token": csrf, **data})


assoc = sign_in(app, "a027", "Associate-pass-1")
page = assoc.get("/me/breaks", query_string={"change": 0}).get_data(as_text=True)
post(assoc, "/me/breaks", idx=0, to=re.search(r'name="to" value="([0-9:]+)"(?! disabled)', page).group(1), why="Made-up")
tm = sign_in(app, "tm_only", "Manager-pass-123")
post(tm, "/requests/coaching", program=key, date=WED.isoformat(), start="14:00", minutes="30", dept="Quality",
     why="Made-up", who=[ME, MATE])

server = make_server("127.0.0.1", 0, app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"
Q = key.replace(" ", "+")
PAGES = [("rta1", "Staff-pass-123", f"/incidents?program={Q}&from=2026-10-11&to=2026-10-15"),
         ("rta1", "Staff-pass-123", f"/incidents?program={Q}&from=2026-10-11&to=2026-10-15&view=lobs"),
         ("rta1", "Staff-pass-123", f"/incidents?program={Q}&from=2026-10-11&to=2026-10-15&view=associates"),
         ("rta1", "Staff-pass-123", f"/incidents?program={Q}&from=2026-10-11&to=2026-10-15&view=associates&who=Associate+008"),
         ("rta1", "Staff-pass-123", f"/shrinkage?program={Q}&from=2026-10-11&to=2026-10-15"),
         ("rta1", "Staff-pass-123", f"/shrinkage?program={Q}&from=2026-10-11&to=2026-10-15&by=week"),
         ("rta1", "Staff-pass-123", f"/shrinkage?program={Q}&from=2026-10-11&to=2026-10-15&by=interval&step=60"),
         ("rta1", "Staff-pass-123", f"/day?program={Q}&date=2026-10-14&view=meeting"),
         ("rta1", "Staff-pass-123", f"/day?program={Q}&date=2026-10-14&view=sessions"),
         ("rta1", "Staff-pass-123", f"/day?program={Q}&date=2026-10-14&view=board"),
         ("rta1", "Staff-pass-123", "/exports"),
         ("admin_demo", "Admin-pass-1234", "/setup/programs")]

CHECK = r"""
() => {
  const out = [];
  const lum = (c) => { const [r,g,b] = c.map(v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b; };
  const parse = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(x => parseFloat(x));
    return {rgb: p.slice(0,3), a: p.length > 3 ? p[3] : 1}; };
  const bgOf = (el) => { let stack = [];
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; } }
    let base = [255,255,255]; for (let i = stack.length - 1; i >= 0; i--) { const c = stack[i];
      base = base.map((v, k) => Math.round(c.rgb[k]*c.a + v*(1-c.a))); } return base; };
  const walker = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const n = walker.currentNode; if (!n.textContent.trim()) continue; const el = n.parentElement;
    if (seen.has(el)) continue; seen.add(el);
    const st = getComputedStyle(el); if (st.visibility === 'hidden' || st.display === 'none' || el.closest('[hidden]')) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const fg = parse(st.color); if (!fg) continue; const bg = bgOf(el);
    const f = fg.rgb.map((v, k) => Math.round(v*fg.a + bg[k]*(1-fg.a)));
    const L1 = lum(f), L2 = lum(bg), ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight) >= 700; const large = size >= 24 || (size >= 18.66 && bold);
    if (ratio < (large ? 3 : 4.5) && !el.disabled && !el.closest('[disabled]')) out.push(['contrast', ratio.toFixed(2), el.tagName + '.' + el.className, n.textContent.trim().slice(0, 40)]);
  }
  for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea, button, a[href]')) {
    const r = el.getBoundingClientRect(); if (r.width === 0 && r.height === 0) continue;
    const name = (el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].textContent) || el.textContent || el.getAttribute('title') || el.getAttribute('value') || el.getAttribute('placeholder') || '').trim();
    if (!name) out.push(['no name', el.tagName, el.outerHTML.slice(0, 80)]);
  }
  const h = [...document.querySelectorAll('h1,h2,h3,h4')].map(e => +e.tagName[1]);
  if (document.querySelectorAll('h1').length !== 1) out.push(['h1 count', document.querySelectorAll('h1').length]);
  for (let i = 1; i < h.length; i++) if (h[i] - h[i-1] > 1) out.push(['heading skip', h[i-1] + '->' + h[i]]);
  if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push(['sideways scroll', document.documentElement.scrollWidth + ' > ' + window.innerWidth]);
  return out;
}
"""
found = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for user, pwd, path in PAGES:
        for scheme in ("light", "dark"):
            for w in (1280, 360):
                ctx = browser.new_context(viewport={"width": w, "height": 900}, color_scheme=scheme, reduced_motion="reduce")
                p = ctx.new_page()
                if user:
                    p.goto(base + "/login")
                    p.fill("input[name=username]", user)
                    p.fill("input[name=password]", pwd)
                    p.click("button.primary")
                    p.wait_for_load_state()
                p.goto(base + path)
                p.wait_for_timeout(250)
                for item in p.evaluate(CHECK):
                    found.setdefault((path.split("?")[0], json.dumps(item)), set()).add(f"{scheme}/{w}")
                ctx.close()
    browser.close()
for (path, item), where in sorted(found.items()):
    print(path, item, sorted(where))
print("problems:", len(found))
