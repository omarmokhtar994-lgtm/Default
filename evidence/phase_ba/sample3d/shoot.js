const { chromium } = require('playwright'); const path = require('path');
(async () => { const b = await chromium.launch(); const u = 'file://' + path.resolve('index.html');
  for (const [n,w,h] of [['desktop',1360,900],['phone',390,844]]) { const c = await b.newContext({ viewport:{width:w,height:h}, deviceScaleFactor: w<500?2:1 }); const p = await c.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
    await p.goto(u); await p.waitForTimeout(500); if(n==='desktop'){ await p.hover('.tile:nth-child(2)', {position:{x:30,y:20}}); await p.waitForTimeout(300);} await p.screenshot({path:`s3d-${n}.png`}); console.log(n,'overflow',await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth),errs); await c.close(); }
  await b.close(); })();
