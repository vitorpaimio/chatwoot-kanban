// Prova que uma rota indisponível não prende DOMContentLoaded do Chatwoot.
const { chromium } = require('playwright');
const { readFileSync } = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const source = readFileSync('installer/resources.rb', 'utf8');
  const tag = source.match(/^    loader = '([^']+)'/m)[1];
  const browser = await chromium.launch({
    headless: true,
    ...(process.platform === 'darwin' ? {
      executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    } : {}),
  });
  let release;
  const unavailable = new Promise(resolve => { release = resolve; });
  try {
    const page = await browser.newPage();
    const requested = page.waitForRequest('**/kanban/loader.js');
    await page.route('https://installer.invalid/**', async route => {
      if (route.request().url().endsWith('/kanban/loader.js')) {
        await unavailable;
        await route.abort();
      } else {
        await route.fulfill({ contentType: 'text/html', body:
          `<!doctype html><html><head>${tag}</head><body>Chatwoot</body></html>`,
        });
      }
    });
    await page.goto('https://installer.invalid/', {
      waitUntil: 'domcontentloaded', timeout: 5000,
    });
    await requested;
    assert.equal(await page.evaluate(() => document.readyState), 'interactive');
    console.log('Loader indisponível: DOMContentLoaded liberado.');
  } finally {
    release();
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
