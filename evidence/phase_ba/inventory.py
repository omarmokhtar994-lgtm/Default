# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA: for every page, the tables, lists and containers that are long (rows and pixel height), and the sidebar links with no icon.
Run after evidence/phase_ai/tools/review_server.py wrote its details to argv[1]. Prints JSON lines."""
import json, sys
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1]))
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]; W = cfg["week"]; R = cfg["run_id"]
PAGES = {"home": "/", "day": f"/day?program={Q}&date={D}", "day_board": f"/day?program={Q}&date={D}&view=board",
         "day_adherence": f"/day?program={Q}&date={D}&view=adherence", "day_cover": f"/day?program={Q}&date={D}&view=cover",
         "day_channels": f"/day?program={Q}&date={D}&view=channels", "day_replan": f"/day?program={Q}&date={D}&view=replan",
         "day_bulk": f"/day?program={Q}&date={D}&view=bulk", "day_rescue": f"/day?program={Q}&date={D}&view=rescue", "day_meeting": f"/day?program={Q}&date={D}&view=meeting",
         "overview": f"/overview?program={Q}&date={D}", "wallboard": f"/day/wallboard?program={Q}&date={D}", "handover": f"/day/handover?program={Q}&date={D}",
         "split": f"/day/split?program={Q}&date={D}", "week": f"/week?program={Q}&week={W}", "schedules": f"/schedules?program={Q}", "run": f"/runs/{R}",
         "run_schedules": f"/runs/{R}/schedules", "requests": f"/requests?program={Q}", "incidents": f"/incidents?program={Q}", "shrinkage": f"/shrinkage?program={Q}",
         "notifications": "/notifications", "programs": "/programs", "program": f"/programs/{Q}", "exports": "/exports", "team": "/team", "admin_users": "/admin/users",
         "admin_bulk": "/admin/users/bulk", "roles": "/admin/roles", "setup_with": f"/setup/with?program={Q}", "setup_channels": f"/setup/channels?program={Q}",
         "setup_programs": "/setup/programs", "coach": "/coach", "password": "/account/password"}
JS = """() => {
  const out = [];
  const label = e => (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/).join('.') : '');
  const boxed = e => !!e.closest('.panel-scroll, .tl-scroll, .tscroll.panel-scroll, [data-pager], nav.pager, .pick-list, .who-list, .bp-scroll, .wall-scroll');
  document.querySelectorAll('main table').forEach(t => { if (boxed(t)) return; const rows = t.querySelectorAll('tbody tr').length || t.querySelectorAll('tr').length; const h = Math.round(t.getBoundingClientRect().height);
    if (rows >= 8 || h > 600) out.push({kind: 'table', sel: label(t), rows, h, cols: t.querySelectorAll('tr:first-child > *').length, within: label(t.closest('section,div.card,form,details')||t.parentElement)}); });
  document.querySelectorAll('main ul, main ol').forEach(u => { if (boxed(u)) return; const rows = u.querySelectorAll(':scope > li').length; const h = Math.round(u.getBoundingClientRect().height);
    if (rows >= 8 || h > 600) out.push({kind: 'list', sel: label(u), rows, h, within: label(u.closest('section,div.card,form,details')||u.parentElement)}); });
  const nav = [...document.querySelectorAll('.leftnav nav a')].filter(a => getComputedStyle(a, '::before').maskImage === 'none' && getComputedStyle(a, '::before').webkitMaskImage === 'none').map(a => a.getAttribute('href'));
  return {page_h: document.documentElement.scrollHeight, long: out, noicon: nav};
}"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
    with pg.expect_navigation(): pg.keyboard.press("Enter")
    for name, path in PAGES.items():
        r = pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
        res = pg.evaluate(JS); res.update(page=name, status=r.status); print(json.dumps(res), flush=True)
    b.close()
