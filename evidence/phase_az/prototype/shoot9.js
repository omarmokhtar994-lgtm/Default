// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html'); const errs = [];
  for (const [v, w, h] of [['day',1360,900],['home',1360,900],['requests',1360,900],['signin',1360,760],['wallboard',1360,760],['week',1360,900]]) {
    const c = await b.newContext({ viewport: { width: w, height: h } }); const p = await c.newPage(); p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
    await p.goto(`${url}?look=c&view=${v}`); await p.waitForTimeout(500);
    if (v === 'day') { await p.click('[data-try]'); await p.waitForTimeout(600); }
    await p.screenshot({ path: `shots/r7-${v}-c.png` }); await c.close(); }
  const m = await b.newContext({ viewport: { width: 390, height: 820 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }); const p = await m.newPage();
  await p.goto(`${url}?look=c&view=home`); await p.waitForTimeout(300); await p.screenshot({ path: 'shots/r7-home-phone-c.png' });
  console.log('phone overflow', await p.evaluate(() => document.documentElement.scrollWidth - innerWidth), 'errors', errs); await b.close();
})();
