const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
(async () => {
 const root = path.resolve(__dirname, '..'), temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-accounts-'));
 const env = { ...process.env, WIXAL_DATA_DIR: temp, WIXAL_RUNTIME_MODE: 'external' }; delete env.ELECTRON_RUN_AS_NODE;
 let app;
 try {
  app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
  const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.locator('#start-page').waitFor({ state: 'visible' });
  assert.equal(await page.locator('.workspace').evaluate(el => el.inert), true);
  const invalid = await page.evaluate(async () => {
    const results = [];
    for (const [name, arg] of [['entry-complete','unknown'], ['entry-complete','account'], ['legal-document','../credentials.enc'], ['legal-document','__proto__'], ['legal-link','https://example.com']]) {
      try { await window.wixal[name](arg); results.push(false); } catch { results.push(true); }
    }
    return results;
  });
  assert.deepEqual(invalid, [true,true,true,true,true]);
  await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/first-start.png') });
  await page.click('#start-page [data-legal="terms"]'); await page.locator('#legal-dialog[open]').waitFor();
  assert.match(await page.locator('#legal-body').innerText(), /Draft for review/);
  assert.match(await page.locator('#legal-body').innerText(), /Australian Consumer Law/);
  await page.click('[data-close="legal-dialog"]');
  await page.click('#start-page [data-legal="privacy"]'); await page.locator('#legal-dialog[open]').waitFor();
  assert.match(await page.locator('#legal-body').innerText(), /omeleyjhye@gmail.com/);
  assert.match(await page.locator('#legal-body').innerText(), /not active in this release/);
  await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/privacy-policy.png') });
  await page.click('[data-close="legal-dialog"]');
  await page.click('#account-create-tab'); assert.equal(await page.locator('#account-name').isVisible(), true);
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640));
  assert.ok(await page.locator('#start-page').evaluate(el => el.scrollWidth <= el.clientWidth));
  await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/first-start-create.png') });
  await page.click('#start-guest');
  await page.locator('#setup-dialog[open]').waitFor();
  await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/setup-account.png') });
  await page.click('[data-setup-theme="forest"]'); await page.waitForFunction(() => document.documentElement.dataset.theme === 'forest');
  await page.click('#setup-account'); await page.locator('#account-dialog[open]').waitFor();
  await page.click('#account-create-tab'); assert.equal(await page.locator('#account-name').isVisible(), true);
  assert.equal(await page.locator('#account-password').getAttribute('autocomplete'), 'new-password');
  await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/account-registration.png') });
  await page.click('[data-close="account-dialog"]'); await page.click('#settings-button'); await page.click('#settings-setup'); await page.click('#setup-finish');
  await page.waitForFunction(async () => (await window.wixal.state()).setup.completed);
  await page.reload(); await page.waitForFunction(() => document.documentElement.dataset.theme === 'forest');
  await page.locator('#start-page').waitFor({ state: 'hidden' });
  assert.equal(await page.locator('#setup-dialog').isVisible(), false);
  assert.equal(await page.locator('#start-page').isVisible(), false);
  assert.equal(await page.locator('.workspace').evaluate(el => el.inert), false);
  assert.equal(await page.locator('#account-label').innerText(), 'Guest');
  const denied = await page.evaluate(async () => { try { await window.wixal['preset-save']('Guest preset'); return false; } catch { return true; } }); assert.equal(denied, true);
  await page.click('#account-button'); await app.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0].setSize(920,640));
  assert.ok(await page.locator('#account-dialog').evaluate(el => el.scrollWidth <= el.clientWidth));
  await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/account-compact.png') });
  assert.deepEqual(errors, []); console.log('PASS: first-start login/create/guest page, readable policy drafts, compact layout, guest setup, persistence, account forms and preset gate');
 } finally { if (app) await app.close(); await fs.rm(temp, { recursive:true, force:true }); }
})().catch(e => { console.error(e); process.exitCode=1; });
