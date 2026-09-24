// Sessão humana real; credenciais efêmeras recebidas por stdin, sem storageState.
const { chromium } = require('playwright');
let stage = "input";
(async () => {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  const human = JSON.parse(input);
  const browser = await chromium.launch({headless: true, ...(process.platform === 'darwin' ? {executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'} : {})});
  const page = await browser.newPage();
  try {
    stage = 'login';
    await page.goto('http://localhost:18080/app/login');
    await page.locator('input[type=text]').fill(human.email);
    await page.locator('input[type=password]').fill(human.password);
    await page.getByRole('button', {name: 'Entrar', exact: true}).click();
    stage = 'dashboard';
    try { await page.waitForURL('**/app/accounts/1/**', {timeout: 20000}); }
    catch (e) { console.error('Caminho: ' + new URL(page.url()).pathname); await page.screenshot({path: '.local/phase42/browser.png'}); throw e; }
    stage = 'pipeline';
    await page.getByText('Pipeline', {exact: true}).first().waitFor({timeout: 30000});
    const item = page.locator('#chatwoot-kanban-menu').getByText('Kanban', {exact: true});
    if (!await item.isVisible()) await page.getByText('Pipeline', {exact: true}).first().click();
    await item.click();
    stage = 'iframe';
    await page.frameLocator('#chatwoot-kanban-panel iframe').locator('[data-stage-id]').first().waitFor({timeout: 30000});
    const text = await page.frameLocator('#chatwoot-kanban-panel iframe').locator('body').innerText();
    if (!text.includes('Novo')) throw new Error('Quadro não carregado');
    console.log('Pipeline e quadro autenticado: ok');
  } catch (error) { await page.screenshot({path: ".local/phase42/browser.png"}); throw error; }
  finally { await browser.close(); }
})().catch(() => { console.error('Navegador: falha na etapa ' + stage + '; credenciais omitidas'); process.exit(1); });
