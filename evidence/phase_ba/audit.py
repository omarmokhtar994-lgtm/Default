# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BA: every page in the three looks at 1440 and 390 px. Reports: status, console errors, sideways page scroll, text cut off inside a box that
does not scroll, controls under 24 px (WCAG 2.2 target size), stacked panels closer than 8 px, and pages taller than 4000 px.
Run after review_server.py: python evidence/phase_ba/audit.py /tmp/review_cfg.json [looks]"""
import json, sys
from playwright.sync_api import sync_playwright
cfg = json.load(open(sys.argv[1])); looks = sys.argv[2].split(",") if len(sys.argv) > 2 else ["light", "dark", "draft"]
Q = cfg["key"].replace(" ", "+"); D = cfg["sunday"]; W = cfg["week"]; R = cfg["run_id"]
PAGES = {"home": "/", "day": f"/day?program={Q}&date={D}", "day_board": f"/day?program={Q}&date={D}&view=board", "day_adherence": f"/day?program={Q}&date={D}&view=adherence",
         "day_cover": f"/day?program={Q}&date={D}&view=cover", "day_channels": f"/day?program={Q}&date={D}&view=channels", "day_replan": f"/day?program={Q}&date={D}&view=replan",
         "day_bulk": f"/day?program={Q}&date={D}&view=bulk", "day_rescue": f"/day?program={Q}&date={D}&view=rescue", "day_meeting": f"/day?program={Q}&date={D}&view=meeting",
         "overview": f"/overview?program={Q}&date={D}", "wallboard": f"/day/wallboard?program={Q}&date={D}", "handover": f"/day/handover?program={Q}&date={D}",
         "week": f"/week?program={Q}&week={W}", "schedules": f"/schedules?program={Q}", "run": f"/runs/{R}", "run_schedules": f"/runs/{R}/schedules", "requests": f"/requests?program={Q}",
         "incidents": f"/incidents?program={Q}", "shrinkage": f"/shrinkage?program={Q}", "notifications": "/notifications", "programs": "/programs", "exports": "/exports",
         "team": "/team", "admin_users": "/admin/users", "admin_bulk": "/admin/users/bulk", "roles": "/admin/roles", "setup_with": f"/setup/with?program={Q}",
         "setup_channels": f"/setup/channels?program={Q}", "setup_programs": "/setup/programs", "coach": "/coach", "password": "/account/password"}
JS = """() => {
  const out = {clipped: [], small: [], tight: []};
  const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/)[0] : '');
  document.querySelectorAll('main *').forEach(e => {
    const cs = getComputedStyle(e);
    if (!e.classList.contains('sr-only') && (cs.overflow === 'hidden' || cs.overflowX === 'hidden') && e.scrollWidth > e.clientWidth + 3 && e.clientWidth > 0 && !e.closest('svg') && cs.textOverflow !== 'ellipsis') out.clipped.push(name(e) + ' ' + e.scrollWidth + '>' + e.clientWidth);
    if (/^(BUTTON|INPUT|SELECT)$/.test(e.tagName) && e.type !== 'hidden' && e.type !== 'checkbox' && e.type !== 'radio') { const r = e.getBoundingClientRect(); if (r.width > 0 && (r.height < 24 || r.width < 24)) out.small.push(name(e) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); }
  });
  const ps = [...document.querySelectorAll('main > .panel, main > section.panel')];
  for (let i = 1; i < ps.length; i++) { const gap = ps[i].getBoundingClientRect().top - ps[i - 1].getBoundingClientRect().bottom; if (gap >= 0 && gap < 8) out.tight.push(name(ps[i - 1]) + ' -> ' + name(ps[i]) + ' ' + Math.round(gap)); }
  out.h = document.documentElement.scrollHeight; out.wide = document.scrollingElement.scrollWidth - innerWidth;
  return out;
}"""
bad = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for look in looks:
        for width in (1440, 390):
            ctx = b.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce"); ctx.add_cookies([{"name": "theme", "value": look, "url": cfg["base"]}])
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.goto(cfg["base"] + "/login"); pg.fill("input[name=username]", "omar"); pg.fill("input[name=password]", "Owner-pass-123")
            with pg.expect_navigation(): pg.keyboard.press("Enter")
            for name, path in PAGES.items():
                errs.clear(); r = pg.goto(cfg["base"] + path); pg.wait_for_load_state("networkidle")
                o = pg.evaluate(JS); problems = []
                if r.status >= 400: problems.append(f"status {r.status}")
                if errs: problems.append(f"errors {errs[:2]}")
                if width == 390 and o["wide"] > 1: problems.append(f"sideways {o['wide']}px")
                if o["clipped"]: problems.append("clipped " + "; ".join(sorted(set(o["clipped"]))[:4]))
                if o["small"]: problems.append(f"{len(o['small'])} small controls e.g. " + "; ".join(sorted(set(o["small"]))[:3]))
                if o["tight"]: problems.append("tight " + "; ".join(o["tight"][:2]))
                if o["h"] > 4000 and width == 1440: problems.append(f"tall {o['h']}px")
                if problems: bad += 1; print(f"{look} {width} {name}: " + " | ".join(problems), flush=True)
            ctx.close()
    b.close()
print("pages with findings:", bad)
