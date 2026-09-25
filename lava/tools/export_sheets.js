// Export plan SVG sheets to a multi-page PDF (A2 landscape) and PNG previews using Playwright/Chromium.
// Usage: NODE_PATH=$(npm root -g) node tools/export_sheets.js [plan dir]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const dir = path.resolve(process.argv[2] || path.join(__dirname, '..', 'plan'));
  const sheets = ['lava_A101_planta.svg', 'lava_A102_demolicion.svg', 'lava_A103_flujos.svg'].filter(f => fs.existsSync(path.join(dir, f)));
  // Fonts are cached in tools/fonts (Google Fonts, OFL) and inlined, so the export works offline / behind a proxy.
  const fontDir = path.join(__dirname, 'fonts');
  const fontCss = fs.existsSync(path.join(fontDir, 'fonts.css'))
    ? fs.readFileSync(path.join(fontDir, 'fonts.css'), 'utf8').replace(/url\(([^)]+\.woff2)\)/g, (m, fn) =>
        `url(data:font/woff2;base64,${fs.readFileSync(path.join(fontDir, fn)).toString('base64')})`)
    : '';
  const fonts = `<style>${fontCss}</style>`;
  const pages = sheets.map(f => `<section class="sheet">${fs.readFileSync(path.join(dir, f), 'utf8')}</section>`).join('');
  const html = `<!doctype html><html><head><meta charset="utf-8">${fonts}<style>
    @page { size: 594mm 420mm; margin: 0 }
    html,body{margin:0;padding:0;background:#fff}
    .sheet{width:594mm;height:420mm;page-break-after:always;overflow:hidden}
    .sheet:last-child{page-break-after:auto}
    .sheet svg{width:594mm;height:420mm;display:block}
  </style></head><body>${pages}</body></html>`;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle' }).catch(() => {});
  await page.evaluate(async () => { await document.fonts.ready; return [...document.fonts].filter(f => f.status === 'loaded').length; }).then(n => console.log('fonts loaded:', n));
  const pdf = path.join(dir, 'LAVA_test-fit_planos_A2.pdf');
  await page.pdf({ path: pdf, width: '594mm', height: '420mm', printBackground: true, preferCSSPageSize: true });
  console.log('wrote', pdf);
  for (const f of sheets) {
    const p2 = await browser.newPage({ viewport: { width: 2970, height: 2100 } });
    const svg = fs.readFileSync(path.join(dir, f), 'utf8');
    await p2.setContent(`<!doctype html><html><head><meta charset="utf-8">${fonts}<style>html,body{margin:0}svg{width:2970px;height:2100px;display:block}</style></head><body>${svg}</body></html>`, { waitUntil: 'networkidle' }).catch(() => {});
    await p2.evaluate(() => document.fonts.ready);
    const png = path.join(dir, f.replace('.svg', '.png'));
    await p2.screenshot({ path: png });
    console.log('wrote', png);
    await p2.close();
  }
  await browser.close();
})();
