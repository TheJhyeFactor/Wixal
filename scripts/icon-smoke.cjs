const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
(async () => {
  const root = path.resolve(__dirname, '..');
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-icons-'));
  const store = new Store(temp);
  store.data.setup = { completed: true, entryCompleted: true };
  store.data.ui.launchAnimation = false;
  store.data.ui.launchSound = false;
  store.save();
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: temp };
  delete env.ELECTRON_RUN_AS_NODE;
  let app;
  const errors = [];
  const open = async () => {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow();
    page.on('pageerror', error => errors.push(error.message));
    await page.click('#settings-button');
    return page;
  };
  try {
    let page = await open();
    assert.equal(await page.isChecked('#settings-icon-theme'), true);
    // Capture the image passed to the real Dock API, leaving the native call intact.
    await app.evaluate(({ app }) => {
      const original = app.dock.setIcon.bind(app.dock);
      app.dock.setIcon = image => { globalThis.lastDockIcon = image.toPNG().toString('base64'); original(image); };
    });
    const verifyDock = async id => assert.equal(await app.evaluate(({ nativeImage }, expected) => {
      return globalThis.lastDockIcon === nativeImage.createFromPath(expected).toPNG().toString('base64');
    }, path.join(root, 'assets/icon-variants', `${id}.png`)), true);
    for (const id of ['sakura', 'midnight', 'pearl', 'copper']) {
      await page.click(`[data-icon-choice="${id}"]`);
      await page.waitForFunction(async id => { const s = await window.wixal.state(); return s.ui.appIcon === id && s.appIcon === id; }, id);
      await page.waitForFunction(id => document.querySelector(`[data-icon-choice="${id}"]`).getAttribute('aria-pressed') === 'true', id);
      assert.equal(await page.isChecked('#settings-icon-theme'), false);
      await verifyDock(id);
      assert.equal(await page.locator(`[data-icon-choice="${id}"] img`).evaluate(img => img.complete && img.naturalWidth === 1024), true);
      assert.ok((await page.locator('#sidebar-app-icon').getAttribute('src')).endsWith(`/${id}.png`));
    }
    await page.click('[data-theme-choice="paper"]');
    await page.waitForFunction(() => document.documentElement.dataset.theme === 'paper');
    assert.equal((await page.evaluate(() => window.wixal.state())).appIcon, 'copper');
    await verifyDock('copper');
    await app.close(); app = null;
    page = await open();
    assert.equal(await page.locator('[data-icon-choice="copper"]').getAttribute('aria-pressed'), 'true');
    await page.check('#settings-icon-theme');
    for (const [theme, icon] of Object.entries({ sakura: 'sakura', midnight: 'midnight', forest: 'copper', paper: 'pearl' })) {
      await page.click(`[data-theme-choice="${theme}"]`);
      await page.waitForFunction(async ({ theme, icon }) => { const s = await window.wixal.state(); return s.ui.theme === theme && s.ui.appIcon === 'theme' && s.appIcon === icon; }, { theme, icon });
      assert.equal(await page.isChecked('#settings-icon-theme'), true);
    }
    await page.locator('#icon-options').scrollIntoViewIfNeeded();
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    await page.screenshot({ path: path.join(root, 'artifacts/icon-settings.png') });
    const rejected = await page.evaluate(async () => { try { await window.wixal.settings({ appIcon: '../../escape' }); return false; } catch { return true; } });
    assert.equal(rejected, true);
    assert.equal((await page.evaluate(() => window.wixal.state())).ui.appIcon, 'theme');
    await app.close(); app = null;
    page = await open();
    assert.equal(await page.isChecked('#settings-icon-theme'), true);
    assert.equal((await page.evaluate(() => window.wixal.state())).appIcon, 'pearl');
    assert.deepEqual(errors, []);
    console.log('PASS: four icon choices, decoded assets, actual Dock API image, independent selection, four theme mappings, restart persistence and invalid input rejection');
  } finally {
    if (app) await app.close();
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
