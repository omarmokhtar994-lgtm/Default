// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html'); const errs = [];
  const c = await b.newContext({ viewport: { width: 1360, height: 900 } }); const p = await c.newPage();
  p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
  await p.goto(url + '?look=a&view=day'); await p.waitForTimeout(300);
  const h = () => p.evaluate(() => [document.getElementById('lane-scroll').clientHeight, document.documentElement.scrollHeight, document.getElementById('lane-scroll').getAttribute('data-mode')]);
  console.log('scroll mode', await h());
  await p.click('[data-lane-mode="whole"]'); console.log('whole mode', await h());
  await p.evaluate(() => window.scrollTo(0, 380)); await p.screenshot({ path: 'shots/r5-whole-a.png' });
  await p.reload(); await p.waitForTimeout(200); console.log('after reload (remembered)', await h());
  await p.click('[data-lane-mode="scroll"]'); console.log('back to scroll', await h());
  await p.fill('#lane-find', 'associate 1'); console.log('count', await p.textContent('#lane-count'));
  console.log('errors', errs); await b.close();
})();
