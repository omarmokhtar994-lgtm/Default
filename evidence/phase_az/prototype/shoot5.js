// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html'); const errs = [];
  async function page(look, view, w, h, extra) { const c = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: w < 500 ? 2 : 1, isMobile: w < 500, hasTouch: w < 500 }); const p = await c.newPage();
    p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
    await p.goto(`${url}?look=${look}&view=${view}`); await p.waitForTimeout(300); if (extra) await extra(p); return [c, p]; }
  let [c, p] = await page('a', 'day', 1360, 900, async p => { await p.evaluate(() => window.scrollTo(0, 330)); });
  await p.screenshot({ path: 'shots/r4-day-a.png' });
  console.log('lane scroll box', await p.evaluate(() => { const e = document.getElementById('lane-scroll'); return [e.clientHeight, e.scrollHeight]; })); await c.close();
  [c, p] = await page('a', 'week', 1360, 900, async p => { await p.click('[data-day-pick="Tue"]'); await p.click('[data-pager-next]'); });
  await p.screenshot({ path: 'shots/r4-week-a.png', fullPage: true }); console.log('week page height', await p.evaluate(() => document.documentElement.scrollHeight));
  console.log('rows shown', await p.evaluate(() => document.querySelectorAll('#extra .prow:not([hidden])').length), await p.textContent('#extra [data-pager-label]')); await c.close();
  [c, p] = await page('c', 'people', 1360, 900, async p => { await p.fill('[data-pager-search]', 'planner'); });
  await p.screenshot({ path: 'shots/r4-people-c.png', fullPage: true }); console.log('people label', await p.textContent('#view-people [data-pager-label]')); await c.close();
  [c, p] = await page('b', 'week', 1360, 900); await p.screenshot({ path: 'shots/r4-week-b.png', fullPage: true }); await c.close();
  [c, p] = await page('a', 'people', 390, 820); await p.screenshot({ path: 'shots/r4-people-phone.png' });
  console.log('phone overflow', await p.evaluate(() => document.documentElement.scrollWidth - innerWidth)); await c.close();
  console.log('errors', errs); await b.close();
})();
