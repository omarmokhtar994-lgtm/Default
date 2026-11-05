const { chromium } = require('playwright'); const path = require('path');
(async () => { const b = await chromium.launch(); const u = 'file://' + path.resolve('index.html');
  for (const look of ['light','dark','draft']) for (const [n,w,h] of [['desktop',1280,900],['phone',390,844]]) {
    const c = await b.newContext({ viewport:{width:w,height:h}, deviceScaleFactor: w<500?2:1 }); const p = await c.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
    await p.goto(u); await p.evaluate(t=>document.documentElement.dataset.theme=t, look); await p.waitForTimeout(300);
    if(n==='desktop'){ await p.hover('.slab:nth-child(2)', {position:{x:30,y:20}}); await p.waitForTimeout(300); }
    await p.screenshot({path:`dash3d-${look}-${n}.png`, fullPage:true});
    console.log(look,n,'overflow',await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth),errs); await c.close(); }
  await b.close(); })();
