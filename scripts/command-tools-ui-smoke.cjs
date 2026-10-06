const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-command-ui-'));
  const store = new Store(path.join(temp, 'state')); store.addProject(temp);
  store.data.setup = { completed: true, entryCompleted: true };
  store.session().messages = [{ role: 'user', content: 'Review command output' }, { role: 'tool', tool_name: 'command_read', content: JSON.stringify({ state: 'completed', exitCode: 0, output: 'Visible command evidence in this conversation', next_offset: 46 }) }]; store.save();
  const env = { ...process.env, WIXAL_DATA_DIR: path.join(temp, 'state'), WIXAL_RUNTIME_MODE: 'external' }; delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ args: [path.resolve(__dirname, '..')], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
  try {
    const page = await app.firstWindow(), errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.locator('.turn-activity').waitFor();
    assert.equal(await page.locator('.turn-activity').evaluate(element => element.open), false);
    await page.click('.turn-activity > summary');
    await page.click('[data-inspect-action]');
    await page.locator('#activity-dock .tool-content').first().waitFor({ state: 'visible' });
    assert.match(await page.locator('#activity-dock').innerText(), /Visible command evidence/);
    assert.equal(await page.locator('#activity-dock').evaluate(element => element.open), true);
    await page.click('#workspace-menu-toggle'); await page.click('#toolkit-button');
    for (const name of ['command_start', 'command_read', 'command_write', 'command_stop', 'command_save_output', 'browser_inspect']) {
      const toggle = page.locator(`[data-tool="${name}"]`); await toggle.waitFor(); await toggle.uncheck(); await page.waitForFunction(async name => !(await window.wixal.state()).enabledTools.includes(name), name);
      await toggle.check(); await page.waitForFunction(async name => (await window.wixal.state()).enabledTools.includes(name), name);
    }
    assert.deepEqual(errors, []);
    console.log('COMMAND_TOOLS_UI_OK: output visible in chat; six tools can be disabled/enabled and settings persist');
  } finally { await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
