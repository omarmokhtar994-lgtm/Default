// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html');
  for (const look of ['a','b']) { const c = await b.newContext({ viewport: { width: 1360, height: 760 } }); const p = await c.newPage();
    await p.goto(`${url}?look=${look}&view=day`); await p.waitForTimeout(300);
    await p.evaluate(() => document.querySelector('.toolrow').scrollIntoView({ block: 'start' })); await p.evaluate(() => window.scrollBy(0, -70)); await p.waitForTimeout(400);
    await p.screenshot({ path: `shots/r5-scroll-${look}.png` });
    await p.click('[data-lane-mode="whole"]'); await p.waitForTimeout(500); await p.mouse.move(5, 5);
    await p.evaluate(() => document.querySelector('.toolrow').scrollIntoView({ block: 'start' })); await p.evaluate(() => window.scrollBy(0, -70)); await p.waitForTimeout(400);
    await p.screenshot({ path: `shots/r5-whole-${look}.png` }); await c.close(); }
  await b.close();
})();
