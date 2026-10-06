const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
async function poll(page, predicate) {
  for (let i = 0; i < 300; i++) { const state = await page.evaluate(() => window.wixal.state()); if (predicate(state)) return state; await new Promise(r => setTimeout(r, 100)); }
  throw new Error('State check timed out.');
}
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-performance-ui-')), project = path.join(temp, 'Benchmark demo');
  await fs.mkdir(project); await fs.writeFile(path.join(project, 'README.md'), 'REAL_TOOL_READ_VERIFIED');
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: path.join(temp, 'state'), WIXAL_TEST_PROJECT: project }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message)); await page.locator('#prompt').waitFor();
    await app.evaluate(() => {
      const real = globalThis.fetch;
      globalThis.perfFixture = { catalog: [{ name: 'tiny:test', digest: 'tiny', size: 1e9 }, { name: 'huge:test', digest: 'huge', size: 96e9 }], bodies: [], block: false };
      globalThis.fetch = async (target, request) => {
        if (!String(target).startsWith('http://127.0.0.1:11434')) return real(target, request);
        const f = globalThis.perfFixture, json = data => new Response(JSON.stringify(data));
        if (String(target).endsWith('/api/version')) return json({ version: 'fixture' });
        if (String(target).endsWith('/api/tags')) return json({ models: f.catalog });
        if (String(target).endsWith('/api/show')) return json({ capabilities: ['tools'], details: { parameter_size: '1B' }, model_info: { 'fixture.context_length': 16384 } });
        if (String(target).endsWith('/api/ps')) return json({ models: [{ name: 'tiny:test', size: 2e9, size_vram: 1.9e9 }] });
        const body = JSON.parse(request.body); f.bodies.push(body);
        if (String(target).endsWith('/api/delete')) { f.catalog = f.catalog.filter(m => m.name !== body.model); return json({}); }
        if (String(target).endsWith('/api/pull')) return new Response('{"status":"success"}\n');
        if (f.block && body.options?.num_predict === 128) return new Promise((_resolve, reject) => request.signal.addEventListener('abort', () => reject(new Error('Stopped')), { once: true }));
        let message;
        if (body.options?.num_predict === 128) message = { content: '1 one\n2 two' };
        else if (body.messages.at(-1).role === 'tool') message = { content: `Read result: ${body.messages.at(-1).content}` };
        else message = { content: '', tool_calls: [{ function: { name: 'read_file', arguments: { path: 'README.md' } } }] };
        return json({ message, done: true, prompt_eval_count: 40, eval_count: 64, eval_duration: 2e9, total_duration: 3e9, load_duration: .1e9 });
      };
    });
    await page.click('#model-button'); await page.click('#model-refresh'); await page.locator('[data-model="tiny:test"]').click();
    await page.evaluate(() => window.wixal.settings({ mode: 'chat' })); await page.reload(); await poll(page, s => s.model === 'tiny:test');
    await page.fill('#prompt', '@read'); await page.locator('[data-mention="read_file"]').waitFor(); await page.keyboard.press('Enter');
    assert.equal(await page.inputValue('#prompt'), '@read_file '); await page.type('#prompt', 'read README.md'); await page.click('#send');
    await page.waitForFunction(() => document.querySelector('#messages').textContent.includes('Read result: REAL_TOOL_READ_VERIFIED'));
    assert.ok(!(await page.textContent('#messages')).includes('Skipped the explicit tool.'));
    const bodies = await app.evaluate(() => globalThis.perfFixture.bodies); assert.deepEqual(bodies[0].tools.map(t => t.function.name), require('../app/tools.cjs').definitions.map(t => t.function.name));
    await page.click('#response-stats'); assert.match(await page.textContent('#performance-totals'), /80/); assert.match(await page.textContent('#performance-totals'), /128/);
    await page.click('[data-close="performance-dialog"]'); await page.click('#model-button');
    await page.locator('#model-filter-panel > summary').click(); await page.selectOption('#model-size-filter', '4'); assert.equal(await page.locator('.model-row').count(), 1); await page.selectOption('#model-size-filter', '0');
    await page.selectOption('#model-fit-filter', 'estimated'); assert.equal(await page.locator('.model-row').count(), 1); await page.selectOption('#model-fit-filter', 'all');
    await page.click('[data-benchmark="tiny:test"]'); await poll(page, s => s.benchmarks.length === 1 && !s.benchmarkProgress);
    await page.selectOption('#model-fit-filter', 'tested'); assert.equal(await page.locator('.model-row').count(), 1); assert.match(await page.textContent('.model-actions'), /32 tok\/s/);
    await page.selectOption('#model-fit-filter', 'fast'); assert.equal(await page.locator('.model-row').count(), 1);
    await app.evaluate(() => { globalThis.perfFixture.block = true; }); await page.click('[data-benchmark="tiny:test"]'); await page.locator('#benchmark-progress').waitFor(); await page.click('#benchmark-cancel'); await poll(page, s => !s.benchmarkProgress); await app.evaluate(() => { globalThis.perfFixture.block = false; });
    await page.locator('.model-entry').filter({ has: page.locator('[data-model="tiny:test"]') }).locator('.model-manage summary').click(); await page.click('[data-model-delete="tiny:test"]'); await page.click('[data-close="model-delete-dialog"]'); assert.equal((await app.evaluate(() => globalThis.perfFixture.catalog)).length, 2);
    await page.click('#model-button'); await page.locator('.model-entry').filter({ has: page.locator('[data-model="tiny:test"]') }).locator('.model-manage summary').click(); await page.click('[data-model-delete="tiny:test"]'); await page.click('#confirm-model-delete'); await poll(page, s => s.model === 'huge:test');
    await page.selectOption('#model-fit-filter', 'all'); await page.locator('[data-model="huge:test"]').waitFor(); assert.equal(await page.locator('.model-row').count(), 1); await page.click('[data-close="models-dialog"]');
    await page.click('#workspace-menu-toggle'); await page.click('#toolkit-button'); await page.fill('#tool-search', 'read_file'); assert.equal(await page.locator('[data-tool]').count(), 1); await page.locator('[data-tool="read_file"]').uncheck(); await poll(page, s => !s.enabledTools.includes('read_file')); await page.click('#tools-enable-all'); await poll(page, s => s.enabledTools.length === require('../app/tools.cjs').definitions.length); await page.fill('#tool-search', '');
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true }); await page.screenshot({ path: path.join(root, 'artifacts/wixal-toolkit-v07.png') }); await page.click('#close-toolkit'); await page.click('#response-stats'); await page.screenshot({ path: path.join(root, 'artifacts/wixal-performance-v07.png') });
    await page.reload(); const state = await poll(page, s => s.benchmarks.length === 1); assert.equal(state.usage.length, 2); assert.deepEqual(errors, []);
    console.log('PASS: @tool keyboard selection and real file read in Chat, reported usage, fit/size/benchmark filters, benchmark cancel, delete cancel/confirm, searchable toolkit/all-enabled and persistence');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
