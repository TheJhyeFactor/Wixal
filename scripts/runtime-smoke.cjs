// Real bundled engine + existing model bytes, through the app's UI and IPC.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
async function waitState(page, predicate) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) { const state = await page.evaluate(() => window.wixal.state()); if (predicate(state)) return state; await new Promise(resolve => setTimeout(resolve, 100)); }
  throw new Error('Runtime state did not reach the expected condition.');
}
const alive = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-local-ui-'));
  const env = { ...process.env, WIXAL_DATA_DIR: path.join(temp, 'data') };
  delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_RUNTIME_MODE; delete env.WIXAL_TEST_PROJECT;
  let app, lastPid;
  const launch = async () => {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(); await waitState(page, state => state.localRuntime.status === 'ready'); return page;
  };
  try {
    let page = await launch(); const errors = []; page.on('pageerror', error => errors.push(error.message));
    let runtime = await page.evaluate(async () => (await window.wixal.state()).localRuntime); lastPid = runtime.pid;
    assert.equal(runtime.mode, 'managed'); assert.ok(alive(lastPid));
    await page.click('#model-button'); await page.locator('#runtime-panel > summary').click(); await page.locator('#runtime-import-section summary').click(); await page.click('#runtime-scan');
    const model = process.env.WIXAL_RUNTIME_TEST_MODEL || 'gemma3:12b';
    await page.selectOption('#runtime-import-model', model); await page.click('#runtime-import');
    await page.waitForFunction(() => document.querySelector('#runtime-import-status').textContent.startsWith('Imported '), null, { timeout: 180000 });
    await page.locator('.model-row').filter({ hasText: model }).click();
    await page.fill('#prompt', 'Reply with exactly WIXAL_LOCAL_OK.'); await page.click('#send');
    await page.waitForFunction(() => !document.querySelector('#send').classList.contains('hidden'), null, { timeout: 180000 });
    assert.match(await page.evaluate(async () => (await window.wixal.state()).sessions.at(-1).messages.findLast(m => m.role === 'assistant')?.content || ''), /WIXAL_LOCAL_OK/);
    await page.click('#model-button');
    await page.selectOption('#context-size', '8192'); await page.locator('[data-benchmark]').first().waitFor();
    await page.click('[data-benchmark]');
    const benchDeadline = Date.now() + 180000;
    while (Date.now() < benchDeadline) { const value = await page.evaluate(() => window.wixal.state()); if (value.benchmarks.length && !value.benchmarkProgress) break; await new Promise(r => setTimeout(r, 200)); }
    const result = await page.evaluate(async () => (await window.wixal.state()).benchmarks.at(-1));
    assert.ok(result.tokensPerSecond > 0); assert.equal(result.samples.length, 2); console.log('Real benchmark:', JSON.stringify(result));
    await page.locator('#model-filter-panel > summary').click(); await page.selectOption('#model-fit-filter', 'tested'); assert.equal((await page.evaluate(() => window.wixal.models())).models.filter(m => !m.importable).length, 1); await page.selectOption('#model-fit-filter', 'all');
    await page.click('#runtime-stop');
    await waitState(page, state => state.localRuntime.status === 'stopped'); assert.equal(alive(lastPid), false);
    await page.click('#runtime-start'); await waitState(page, state => state.localRuntime.status === 'ready');
    runtime = await page.evaluate(async () => (await window.wixal.state()).localRuntime); lastPid = runtime.pid;
    assert.notEqual(lastPid, null); await page.locator('.model-row').first().waitFor(); assert.equal((await page.evaluate(() => window.wixal.models())).models.filter(m => !m.importable).length, 1);
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true }); await page.locator('#runtime-import-section').evaluate(el => { el.open = false; }); await page.locator('#models-dialog').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.join(root, 'artifacts/wixal-local-runtime.png') });
    await assert.rejects(page.evaluate(() => window.wixal['runtime-mode']('external')), /included local engine/);
    assert.equal((await page.evaluate(() => window.wixal.state())).localRuntime.mode, 'managed');
    lastPid = await page.evaluate(async () => (await window.wixal.state()).localRuntime.pid);
    await app.close(); app = null; assert.equal(alive(lastPid), false);
    page = await launch(); lastPid = await page.evaluate(async () => (await window.wixal.state()).localRuntime.pid);
    assert.match(await page.evaluate(async () => (await window.wixal.state()).sessions.at(-1).messages.findLast(m => m.role === 'assistant')?.content || ''), /WIXAL_LOCAL_OK/); await page.click('#model-button'); await page.locator('.model-row').first().waitFor(); assert.equal((await page.evaluate(() => window.wixal.models())).models.filter(m => !m.importable).length, 1);
    await page.locator('.model-manage summary').click(); await page.click('[data-model-delete]'); await page.locator('#model-delete-dialog[open]').waitFor(); await page.click('#confirm-model-delete');
    await page.waitForFunction(() => document.querySelector('#model-list').textContent.includes('Your library is empty'));
    await fs.access(path.join(os.homedir(), '.ollama/models/manifests/registry.ollama.ai/library/gemma3/12b'));
    assert.deepEqual(errors, []); await app.close(); app = null; assert.equal(alive(lastPid), false);
    console.log('PASS: bundled engine, import, real inference, stop/start, external rejection, persistent library/chat, benchmark/filter, scoped deletion and quit cleanup');
  } finally { if (app) await app.close(); if (lastPid) assert.equal(alive(lastPid), false); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
