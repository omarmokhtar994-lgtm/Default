// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  const url = 'file://' + path.resolve('index.html');
  const errs = [];
  for (const look of ['a','b','c']) {
    const ctx = await b.newContext({ viewport: { width: 1360, height: 900 } });
    const p = await ctx.newPage();
    p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type()==='error') errs.push(m.text()); });
    await p.goto(url + '?look=' + look);
    await p.waitForTimeout(300);
    await p.click('[data-try]'); await p.waitForTimeout(900);
    await p.screenshot({ path: `shots/day-${look}.png` });
    await p.click('#note-act'); await p.waitForTimeout(500);
    await p.click('[data-id="0"] [data-act="approve"]'); await p.waitForTimeout(700);
    await p.screenshot({ path: `shots/approved-${look}.png` });
    await p.goto(url + `?look=${look}&view=signin`); await p.waitForTimeout(900);
    await p.screenshot({ path: `shots/signin-${look}.png` });
    await ctx.close();
  }
  const m = await b.newContext({ viewport: { width: 390, height: 820 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true, reducedMotion: 'reduce' });
  const p = await m.newPage(); p.on('pageerror', e => errs.push(String(e)));
  await p.goto(url + '?look=a'); await p.click('[data-try]'); await p.waitForTimeout(700);
  await p.screenshot({ path: 'shots/phone-a-reduced.png' });
  const over = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  console.log('phone horizontal overflow px:', over, 'errors:', errs);
  await b.close();
})();
