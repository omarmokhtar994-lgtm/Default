// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html'); const errs = [];
  const set = [['a','home'],['a','requests'],['a','schedules'],['b','wallboard'],['b','home'],['c','requests'],['c','schedules']];
  for (const [look, view] of set) {
    const c = await b.newContext({ viewport: { width: 1360, height: 900 } }); const p = await c.newPage();
    p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
    await p.goto(`${url}?look=${look}&view=${view}`); await p.waitForTimeout(400);
    await p.screenshot({ path: `shots/p-${view}-${look}.png`, fullPage: true }); await c.close();
  }
  const m = await b.newContext({ viewport: { width: 390, height: 820 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }); const p = await m.newPage();
  for (const v of ['home','requests']) { await p.goto(`${url}?look=a&view=${v}`); await p.waitForTimeout(300); await p.screenshot({ path: `shots/p-${v}-phone.png`, fullPage: false }); console.log(v, 'overflow', await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth)); }
  console.log('errors', errs); await b.close();
})();
