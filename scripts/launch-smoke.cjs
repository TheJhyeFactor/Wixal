const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');

(async () => {
  const root = path.resolve(__dirname, '..');
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-launch-'));
  const store = new Store(temp);
  store.data.setup = { completed: true, entryCompleted: true };
  store.save();
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: temp };
  delete env.ELECTRON_RUN_AS_NODE;
  let app;
  const open = async () => {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow();
    page.on('pageerror', error => errors.push(error.message));
    return page;
  };
  const errors = [];
  try {
    let page = await open();
    await page.locator('#launch-screen[open]').waitFor();
    await page.waitForFunction(() => document.getElementById('launch-audio').currentTime > 0.05);
    assert.equal(await page.locator('#launch-audio').evaluate(el => el.error), null);
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    await page.locator('.launch-name').evaluate(async el => { await Promise.all(el.getAnimations().map(animation => animation.finished)); });
    await page.screenshot({ path: path.join(root, 'artifacts/launch-intro.png') });
    await page.keyboard.press('Escape');
    await page.locator('#launch-screen').waitFor({ state: 'detached' });
    assert.equal(await page.locator('#launch-audio').evaluate(el => el.paused), true);
    await page.click('#settings-button');
    await page.uncheck('#settings-launch-sound');
    await page.uncheck('#settings-launch-animation');
    await page.waitForFunction(async () => { const { ui } = await window.wixal.state(); return !ui.launchSound && !ui.launchAnimation; });
    const invalid = await page.evaluate(async () => { try { await window.wixal.settings({ launchSound: 'yes' }); return false; } catch { return true; } });
    assert.equal(invalid, true);
    await app.close(); app = null;
    page = await open();
    await page.waitForFunction(() => !!window.wixalLaunch);
    await page.evaluate(() => window.wixalLaunch);
    assert.equal(await page.locator('#launch-screen').count(), 0);
    assert.equal(await page.locator('#launch-audio').evaluate(el => el.currentTime), 0);
    await page.click('#settings-button');
    assert.equal(await page.isChecked('#settings-launch-sound'), false);
    assert.equal(await page.isChecked('#settings-launch-animation'), false);
    // Exercise a silent animated launch and automatic dismissal.
    await page.check('#settings-launch-animation');
    await page.waitForFunction(async () => (await window.wixal.state()).ui.launchAnimation);
    await app.close(); app = null;
    page = await open();
    await page.locator('#launch-screen[open]').waitFor();
    assert.equal(await page.locator('#launch-audio').evaluate(el => el.currentTime), 0);
    await page.locator('#launch-screen').waitFor({ state: 'detached' });
    await page.click('#settings-button');
    await page.check('#settings-motion');
    await page.waitForFunction(async () => (await window.wixal.state()).ui.reduceMotion);
    await app.close(); app = null;
    page = await open();
    await page.waitForFunction(() => !!window.wixalLaunch);
    await page.evaluate(() => window.wixalLaunch);
    assert.equal(await page.locator('#launch-screen').count(), 0);
    assert.deepEqual(errors, []);
    console.log('PASS: visible intro, actual autoplay/decode, Escape skip, automatic dismissal, silent launch, persisted toggles, reduced motion and preference validation');
  } finally {
    if (app) await app.close();
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
