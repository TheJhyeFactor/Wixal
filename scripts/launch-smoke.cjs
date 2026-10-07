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
    assert.equal(await page.locator('.launch-name').getAttribute('aria-label'), 'Wixal');
    assert.equal(await page.locator('.launch-version').textContent(), `v${require('../package.json').version}`);
    await page.locator('#launch-screen').evaluate(el => {
      window.launchTestTemplate = el.cloneNode(true);
      el.querySelector('.launch-scene').getAnimations({ subtree: true }).forEach(animation => { animation.pause(); animation.currentTime = 1500; });
    });
    await page.screenshot({ path: path.join(root, 'artifacts/launch-intro.png') });
    await page.keyboard.press('Escape');
    await page.locator('#launch-screen').waitFor({ state: 'detached' });
    assert.equal(await page.locator('#launch-audio').evaluate(el => el.paused), true);
    // Exercise the original wordmark reveal with the actual Electron CSS and themes.
    for (const theme of ['sakura', 'midnight', 'forest', 'paper']) {
      const result = await page.evaluate(theme => {
        document.documentElement.dataset.theme = theme;
        const screen = window.launchTestTemplate.cloneNode(true);
        screen.removeAttribute('open');
        document.body.append(screen); screen.showModal();
        const scene = screen.querySelector('.launch-scene');
        const animations = window.WixalLaunchMotion.play(scene, { exit: false });
        const widths = [0, 650, 1500].map(time => {
          animations.forEach(animation => { animation.pause(); animation.currentTime = time; });
          return parseFloat(getComputedStyle(screen.querySelector('.launch-name-window')).width);
        });
        const name = screen.querySelector('.launch-name'), logo = screen.querySelector('.launch-logo');
        const rect = name.getBoundingClientRect(), below = screen.querySelector('.launch-version').getBoundingClientRect();
        const probe = document.createElement('span'); probe.style.color = 'var(--pink)'; screen.append(probe);
        const result = {
          background: getComputedStyle(screen).backgroundColor,
          expected: getComputedStyle(document.body).backgroundColor,
          below: below.top > rect.bottom,
          visible: getComputedStyle(name).opacity === '1', widths,
          shadow: getComputedStyle(logo).filter,
          ink: getComputedStyle(logo).color,
          expectedInk: getComputedStyle(document.body).color,
          accent: getComputedStyle(screen.querySelector('.launch-fold')).fill,
          expectedAccent: getComputedStyle(probe).color,
          sceneBackground: getComputedStyle(scene).backgroundColor,
          sceneShadow: getComputedStyle(scene).boxShadow,
          paperElements: screen.querySelectorAll('.launch-paper, .launch-sheet, .launch-ribbon, .launch-orbit').length
        };
        screen.close(); screen.remove(); animations.forEach(animation => animation.cancel());
        return result;
      }, theme);
      assert.equal(result.background, result.expected);
      assert.equal(result.ink, result.expectedInk);
      assert.equal(result.accent, result.expectedAccent);
      assert.equal(result.sceneBackground, 'rgba(0, 0, 0, 0)');
      assert.equal(result.sceneShadow, 'none');
      assert.equal(result.paperElements, 0);
      assert(result.shadow.startsWith('drop-shadow('));
      assert(result.below && result.visible);
      assert.equal(result.widths[0], 0);
      assert(result.widths[1] > 0 && result.widths[1] < 285);
      assert.equal(result.widths[2], 285);
    }
    // Restore the saved theme after transient visual checks.
    await page.evaluate(async () => { document.documentElement.dataset.theme = (await window.wixal.state()).ui.theme; });
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
    console.log('PASS: original Wixal vector reveal in four themes, transparent wordmark with drop shadow, dynamic version, autoplay/decode, Escape, automatic dismissal, saved toggles and reduced motion');
  } finally {
    if (app) await app.close();
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
