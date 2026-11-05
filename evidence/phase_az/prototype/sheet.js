// © 2026 Omar Mokhtar. All rights reserved.
const { chromium } = require('playwright'); const path = require('path'); const fs = require('fs');
const LOOKS = [['a','1','Tide','light, sky gradient, soft cards'],['b','2','Night watch','navy, hairline cards'],['c','3','Drafting table','dark field, hatched sheet, highlighter'],
               ['d','4','Meadow','friendly, sage and green'],['e','5','Ink','white, black frames, square'],['f','6','Dusk','warm dark, peach action']];
(async () => {
  const b = await chromium.launch(); const url = 'file://' + path.resolve('index.html');
  const c = await b.newContext({ viewport: { width: 1300, height: 820 } }); const p = await c.newPage();
  for (const [k] of LOOKS) for (const v of ['day', 'requests']) {
    await p.goto(`${url}?look=${k}&view=${v}`); await p.addStyleTag({ content: '.protobar{display:none!important}' }); await p.waitForTimeout(350);
    await p.screenshot({ path: `sheet/${k}-${v}.png` });
  }
  const col = ([k, n, name, d]) => `<section><h2><b>${n}</b> ${k.toUpperCase()} ${name}<small>${d}</small></h2><img src="${k}-day.png"><p>RTA, real-time view</p><img src="${k}-requests.png"><p>Leave and swaps</p></section>`;
  for (const [i, set] of [[1, LOOKS.slice(0, 3)], [2, LOOKS.slice(3)]]) {
    fs.writeFileSync(`sheet/sheet-${i}.html`, `<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:28px;background:#ECEEF2;font:16px/1.4 system-ui,sans-serif;color:#111}.g{display:grid;grid-template-columns:repeat(3,620px);gap:28px}section{background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 12px #0002}h2{margin:0 0 12px;font-size:24px}h2 b{display:inline-grid;place-items:center;width:38px;height:38px;border-radius:50%;background:#111;color:#fff;margin-right:8px}h2 small{display:block;font-weight:400;font-size:14px;color:#555;margin-top:2px}img{width:100%;display:block;border:1px solid #0003;border-radius:8px}p{margin:6px 0 16px;color:#555;font-size:14px}</style><div class="g">${set.map(col).join('')}</div>`);
    const q = await c.newPage({ viewport: { width: 1980, height: 1000 } }); await q.setViewportSize({ width: 1980, height: 1000 });
    await q.goto('file://' + path.resolve(`sheet/sheet-${i}.html`)); await q.waitForTimeout(400); await q.screenshot({ path: `sheet/looks-${i === 1 ? '1-3' : '4-6'}.png`, fullPage: true }); await q.close();
  }
  await b.close();
})();
