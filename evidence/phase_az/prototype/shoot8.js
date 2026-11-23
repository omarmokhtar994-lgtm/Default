// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html'); const errs = [];
  async function open(look, view, w, h, mobile) { const c = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: mobile ? 2 : 1, isMobile: !!mobile, hasTouch: !!mobile }); const p = await c.newPage();
    p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
    await p.goto(`${url}?look=${look}&view=${view}`); await p.waitForTimeout(350); return [c, p]; }
  for (const look of ['d','e','f']) {
    let [c, p] = await open(look, 'day', 1360, 900); await p.click('[data-try]'); await p.waitForTimeout(700); await p.screenshot({ path: `shots/r6-day-${look}.png` }); await c.close();
    [c, p] = await open(look, 'signin', 1360, 800); await p.waitForTimeout(600); await p.screenshot({ path: `shots/r6-signin-${look}.png` }); await c.close();
    [c, p] = await open(look, 'requests', 1360, 900); await p.screenshot({ path: `shots/r6-requests-${look}.png` }); await c.close();
  }
  // autofit matrix
  const sizes = [[2560,1300],[1920,1080],[1366,768],[1024,700],[820,1180],[600,900],[390,844],[360,640]];
  for (const [w,h] of sizes) {
    const [c, p] = await open('a', 'week', w, h, w < 700);
    const r = await p.evaluate(() => ({ over: document.documentElement.scrollWidth - innerWidth, rows: document.querySelectorAll('#extra .prow:not([hidden])').length, label: document.querySelector('#extra [data-pager-label]').textContent, tableH: Math.round(document.querySelector('#extra table').getBoundingClientRect().height) }));
    await p.click('[data-view-pick="day"]'); await p.waitForTimeout(150);
    const d = await p.evaluate(() => { const e = document.getElementById('lane-scroll'); return { panelH: e.clientHeight, vh: innerHeight, over: document.documentElement.scrollWidth - innerWidth, tiles: getComputedStyle(document.querySelector('.pulse')).display }; });
    console.log(`${w}x${h}`, 'week', JSON.stringify(r), 'day', JSON.stringify(d)); await c.close();
  }
  console.log('errors', errs); await b.close();
})();
