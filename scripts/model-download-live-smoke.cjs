// Real registry download into a disposable Wixal Local library; no existing models are changed.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
async function waitState(page, predicate, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => window.wixal.state());
    if (predicate(state)) return state;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error('Live model workflow timed out.');
}
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-download-live-'));
  const env = { ...process.env, WIXAL_DATA_DIR: temp }; delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_RUNTIME_MODE; delete env.WIXAL_TEST_PROJECT;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message)); await page.locator('#prompt').waitFor();
    await waitState(page, state => state.localRuntime.status === 'ready');
    await page.click('#models-page-button'); await page.click('#model-downloads-tab');
    const started = Date.now(); await page.locator('[data-catalog-download="gemma3:270m"]').click();
    const job = page.locator('.download-job').filter({ hasText: 'gemma3:270m' });
    await waitState(page, state => state.modelDownloads.some(job => ['completed', 'failed'].includes(job.state)), 300000);
    const state = await page.evaluate(() => window.wixal.state()), result = state.modelDownloads.findLast(job => job.name === 'gemma3:270m');
    console.log('Download states:', JSON.stringify(state.modelDownloads.map(({name,state,error,status}) => ({name,state,error,status}))));
    assert.equal(result.state, 'completed', result.error); assert.ok(result.completed > 200e6);
    await job.locator('[data-download-use]').click(); await waitState(page, state => state.model === 'gemma3:270m');
    await page.click('#model-installed-tab'); await page.locator('[data-model="gemma3:270m"]').waitFor();
    await page.selectOption('#context-size', '8192'); await page.click('[data-benchmark="gemma3:270m"]');
    await waitState(page, state => state.benchmarks.length > 0 && !state.benchmarkProgress, 180000);
    await page.click('#model-refresh'); await page.locator('#model-unload:not([disabled])').waitFor();
    const benchmark = await page.evaluate(async () => (await window.wixal.state()).benchmarks.at(-1));
    assert.ok(benchmark.tokensPerSecond > 0); assert.ok(benchmark.loadedBytes > 0);
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true }); await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1400, 950));
    await page.locator('.model-setup').evaluate(el => el.scrollTop = 0);
    await page.screenshot({ path: path.join(root, 'artifacts/models-page-live-installed.png'), animations: 'disabled' });
    await page.click('#model-downloads-tab'); await page.screenshot({ path: path.join(root, 'artifacts/models-page-live-downloads.png'), animations: 'disabled' });
    await page.click('#model-unload'); await page.locator('#model-loaded-info').filter({ hasText: 'No models loaded' }).waitFor();
    await page.click('#models-page-back'); await page.reload(); await page.click('#models-page-button'); await page.click('#model-downloads-tab'); await job.locator('[data-download-use]').waitFor();
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ test: 'PASS: real registry download, verified installation, selection, measured benchmark, memory release and persistence through Wixal UI', name: result.name, reportedBytes: result.completed, elapsedSeconds: Math.round((Date.now() - started) / 1000), benchmarkTokensPerSecond: benchmark.tokensPerSecond, loadedBytes: benchmark.loadedBytes, context: benchmark.context }));
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
