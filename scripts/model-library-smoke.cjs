const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-model-library-'));
  const env = { ...process.env, WIXAL_DATA_DIR: temp, WIXAL_RUNTIME_MODE: 'external' }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message)); await page.locator('#prompt').waitFor();
    await app.evaluate(() => {
      const real = globalThis.fetch;
      globalThis.libraryFixture = { models: [], pulls: {}, loaded: [{ name: 'qwen3:0.6b', size: 1e9 }], showCalls: 0 };
      globalThis.fetch = async (target, request) => {
        if (!String(target).startsWith('http://127.0.0.1:11434')) return real(target, request);
        const f = globalThis.libraryFixture, json = value => new Response(JSON.stringify(value));
        if (String(target).endsWith('/api/version')) return json({ version: 'fixture' });
        if (String(target).endsWith('/api/tags')) return json({ models: f.models });
        if (String(target).endsWith('/api/ps')) return json({ models: f.loaded });
        if (String(target).endsWith('/api/show')) { f.showCalls++; return json({ capabilities: ['tools'], details: { parameter_size: '0.6B' }, model_info: { 'fixture.context_length': 131072 } }); }
        const body = JSON.parse(request.body);
        if (String(target).endsWith('/api/generate')) { f.loaded = []; return json({ done: true }); }
        if (String(target).endsWith('/api/pull')) {
          const attempt = f.pulls[body.model] = (f.pulls[body.model] || 0) + 1;
          if (body.model === 'missing:fixture' && attempt === 1) return new Response('model not found', { status: 404 });
          if (body.model === 'qwen3:0.6b' && attempt === 1 || body.model === 'cancel:fixture') return new Response(new ReadableStream({ start(controller) {
            controller.enqueue(new TextEncoder().encode('{"status":"pulling layer","digest":"sha256:fixture","total":100000000,"completed":25000000}\n'));
            request.signal.addEventListener('abort', () => controller.error(new Error('Aborted')));
          } }));
          f.models.push({ name: body.model, digest: body.model, size: 500e6 });
          return new Response('{"status":"pulling layer","digest":"sha256:fixture","total":100000000,"completed":100000000}\n{"status":"success"}\n');
        }
        throw new Error(`Unexpected request ${target}`);
      };
    });
    await page.click('#models-page-button'); await page.locator('#models-page:not(.hidden)').waitFor(); await page.click('#model-refresh');
    await page.click('#model-downloads-tab');
    await page.locator('[data-catalog-download="qwen3:0.6b"]').click();
    const qwen = page.locator('.download-job').filter({ hasText: 'qwen3:0.6b' }); await qwen.locator('[data-job-state]').filter({ hasText: 'downloading' }).waitFor();
    assert.equal(await page.locator('#provider-select').isDisabled(), true);
    await page.locator('[data-catalog-download="gemma3:270m"]').click();
    const gemma = page.locator('.download-job').filter({ hasText: 'gemma3:270m' }); await gemma.locator('[data-job-state]').filter({ hasText: 'queued' }).waitFor();
    assert.equal((await app.evaluate(() => globalThis.libraryFixture.pulls))['gemma3:270m'], undefined);
    await qwen.locator('[data-download-action="pause"]').click();
    await gemma.locator('[data-job-state]').filter({ hasText: 'completed' }).waitFor();
    await qwen.locator('[data-job-state]').filter({ hasText: 'paused' }).waitFor();
    await qwen.locator('[data-download-action="resume"]').click(); await qwen.locator('[data-job-state]').filter({ hasText: 'completed' }).waitFor();
    await qwen.locator('[data-download-use]').click();
    assert.equal(await page.locator('#models-page').isVisible(), true);
    await page.waitForFunction(async () => (await window.wixal.state()).model === 'qwen3:0.6b');
    await page.fill('#model-pull-name', 'missing:fixture'); await page.click('#model-pull-button');
    const failed = page.locator('.download-job').filter({ hasText: 'missing:fixture' }); await failed.locator('[data-job-state]').filter({ hasText: 'failed' }).waitFor();
    assert.match(await failed.textContent('[data-job-error]'), /not found/); await failed.locator('[data-download-action="retry"]').click(); await failed.locator('[data-job-state]').filter({ hasText: 'completed' }).waitFor();
    await page.fill('#model-pull-name', 'cancel:fixture'); await page.click('#model-pull-button');
    const cancelled = page.locator('.download-job').filter({ hasText: 'cancel:fixture' }); await cancelled.locator('[data-download-action="pause"]').click();
    await page.reload(); await page.click('#models-page-button'); await page.click('#model-downloads-tab'); await cancelled.locator('[data-job-state]').filter({ hasText: 'paused' }).waitFor();
    await cancelled.locator('[data-download-action="remove"]').click();
    await page.click('#model-installed-tab');
    await page.selectOption('#context-size', '65536'); await page.locator('#model-context-recommend').click(); await page.waitForFunction(async () => (await window.wixal.state()).contextSize === 16384);
    await page.click('#model-refresh'); await page.locator('#model-unload:not([disabled])').waitFor(); await page.click('#model-unload'); await page.locator('#model-loaded-info').filter({ hasText: 'No models loaded' }).waitFor();
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1400, 950));
    await page.screenshot({ path: path.join(root, 'artifacts/models-page-installed.png'), animations: 'disabled' });
    await page.click('#model-downloads-tab'); await page.screenshot({ path: path.join(root, 'artifacts/models-page-downloads.png'), animations: 'disabled' });
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640));
    assert.ok(await page.locator('#models-page').evaluate(el => el.scrollWidth <= el.clientWidth));
    await page.screenshot({ path: path.join(root, 'artifacts/models-page-compact.png'), animations: 'disabled' });
    await page.click('#models-page-back'); await page.locator('#models-page.hidden').waitFor({ state: 'hidden' }); await page.click('#model-button'); await page.locator('#models-dialog[open]').waitFor();
    assert.equal(await page.locator('#models-dialog .model-manager').count(), 1);
    await page.click('#model-open-page'); await page.locator('#models-page:not(.hidden)').waitFor(); assert.deepEqual(errors, []);
    console.log('PASS: dedicated page/selector navigation, direct catalog downloads, serial queue, pause/resume/retry, verification and selection, persistence, context suggestion, memory release and compact layout');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
