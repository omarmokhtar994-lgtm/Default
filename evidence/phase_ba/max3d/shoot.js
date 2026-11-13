const { chromium } = require('playwright'); const path = require('path');
(async () => { const b = await chromium.launch(); const u = 'file://' + path.resolve('index.html');
  for (const [n,w,h,full] of [['desktop',1360,900,true],['phone',390,844,false]]) { const c = await b.newContext({ viewport:{width:w,height:h}, deviceScaleFactor: w<500?2:1 }); const p = await c.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
    await p.goto(u); await p.waitForTimeout(600); await p.screenshot({path:`max3d-${n}.png`, fullPage: full}); console.log(n,'overflow',await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth),errs); await c.close(); }
  await b.close(); })();
