# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BG: Tab through ten pages in both looks and report any stop with no visible focus ring. Reads /tmp/bg_cfg.json (the review server).
Made-up data only."""
import json
from playwright.sync_api import sync_playwright
cfg=json.load(open('/tmp/bg_cfg.json')); Q=cfg["key"].replace(" ","+")
paths=["/",f"/day?program={Q}&date={cfg['sunday']}","/admin/users",f"/week?program={Q}&week={cfg['week']}",f"/runs/{cfg['run_id']}","/setup/programs","/me/breaks","/account/password","/programs","/exports"]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for scheme in ("dark","light"):
        ctx=b.new_context(viewport={"width":1440,"height":900},color_scheme=scheme); pg=ctx.new_page()
        pg.goto(cfg["base"]+"/login"); pg.fill("input[name=username]","omar"); pg.fill("input[name=password]","Owner-pass-123")
        with pg.expect_navigation(): pg.keyboard.press("Enter")
        for path in paths:
            r=pg.goto(cfg["base"]+path); pg.wait_for_load_state("networkidle")
            if r.status>=400: continue
            seen=set(); bad=[]
            for i in range(90):
                pg.keyboard.press("Tab")
                info=pg.evaluate("""()=>{const e=document.activeElement; if(!e||e===document.body) return null; const s=getComputedStyle(e);
                  const r=e.getBoundingClientRect(); return {key:e.tagName+'#'+e.id+'.'+e.className+'@'+Math.round(r.x)+','+Math.round(r.y), w:parseFloat(s.outlineWidth)||0, st:s.outlineStyle, sh:s.boxShadow, name:(e.innerText||e.value||e.name||'').trim().slice(0,24), vis:r.width>0&&r.height>0}}""")
                if not info or info['key'] in seen: continue
                seen.add(info['key'])
                if info['vis'] and (info['st']=='none' or info['w']<1) and info['sh']=='none': bad.append((info['key'][:50],info['name']))
            print(scheme,path.split('?')[0],"stops",len(seen),"no-ring",bad[:6])
        ctx.close()
    b.close()
