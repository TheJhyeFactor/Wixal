const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
(async () => {
  const root = path.resolve(__dirname, '..'), temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-settings-'));
  const store = new Store(temp); store.addProject(root); store.save();
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: temp }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.locator('#settings-button').click();
    await page.locator('#settings-dialog[open]').waitFor();
    for (const theme of ['midnight', 'forest', 'paper', 'sakura']) {
      await page.click(`[data-theme-choice="${theme}"]`);
      await page.waitForFunction(t => document.documentElement.dataset.theme === t, theme);
      assert.equal(await page.locator(`[data-theme-choice="${theme}"]`).getAttribute('aria-pressed'), 'true');
      await page.screenshot({ path: path.join(root, `artifacts/settings-${theme}.png`) });
    }
    await page.click('[data-theme-choice="paper"]');
    await page.selectOption('#settings-text-size', '17');
    await page.check('#settings-motion');
    await page.uncheck('#settings-summary');
    await page.selectOption('#settings-context', '32768');
    await page.check('#settings-sidebar');
    await page.waitForFunction(async () => { const s = await window.wixal.state(); return s.ui.theme === 'paper' && s.ui.textSize === 17 && s.ui.reduceMotion && s.ui.sidebarCollapsed && !s.autoSummary && s.contextSize === 32768; });
    await page.click('[data-close="settings-dialog"]');
    await page.reload(); await page.waitForFunction(() => document.documentElement.dataset.theme === 'paper');
    await page.keyboard.press('Meta+,'); await page.locator('#settings-dialog[open]').waitFor();
    assert.equal(await page.locator('#settings-text-size').inputValue(), '17');
    assert.equal(await page.locator('#settings-motion').isChecked(), true);
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640));
    await page.screenshot({ path: path.join(root, 'artifacts/settings-compact.png') });
    assert.ok(await page.locator('#settings-dialog').evaluate(el => el.scrollWidth <= el.clientWidth));
    await page.keyboard.press('Escape');
    await page.evaluate(() => document.querySelector('#terminal-button').click());
    await page.locator('.xterm').waitFor();
    assert.equal(await page.evaluate(() => terminal.options.fontSize), 17);
    assert.equal(await page.evaluate(() => terminal.options.theme.background), await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()));
    const invalid = await page.evaluate(async () => { try { await window.wixal.settings({ theme: 'invalid' }); return false; } catch { return true; } });
    assert.equal(invalid, true); assert.deepEqual(errors, []);
    console.log('PASS: four themes, persisted appearance/workspace preferences, shortcut, compact layout, terminal theme and input validation');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
