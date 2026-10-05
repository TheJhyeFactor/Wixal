const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
const root = path.resolve(__dirname, '..');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-model-picker-'));
  const store = new Store(temp); store.addProject(root); store.save();
  const env = { ...process.env, WIXAL_DATA_DIR: temp, WIXAL_RUNTIME_MODE: 'external' }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.locator('#prompt').waitFor();
    await app.evaluate(() => {
      const real = globalThis.fetch;
      globalThis.pickerModels = [
        { name: 'gemma3:12b', size: 8.1e9, digest: 'gemma' },
        { name: 'gpt-oss:20b', size: 13.8e9, digest: 'gpt' },
        { name: 'orcarouter/Qwen3.8-27B-Uncensored:iq4_xs', size: 16.2e9, digest: 'qwen' },
      ];
      globalThis.fetch = async (target, request) => {
        if (!String(target).startsWith('http://127.0.0.1:11434')) return real(target, request);
        const json = value => new Response(JSON.stringify(value));
        if (String(target).endsWith('/api/version')) return json({ version: 'fixture' });
        if (String(target).endsWith('/api/tags')) return json({ models: globalThis.pickerModels });
        if (String(target).endsWith('/api/show')) {
          const name = JSON.parse(request.body).model;
          return json({ capabilities: name.startsWith('gemma') ? ['vision'] : name.startsWith('gpt') ? ['tools', 'thinking'] : ['tools', 'vision'], details: { parameter_size: name.startsWith('gemma') ? '12.2B' : name.startsWith('gpt') ? '20.9B' : '27.3B' }, model_info: { 'fixture.context_length': 131072 } });
        }
        throw new Error(`Unexpected fixture request: ${target}`);
      };
    });
    await page.click('#model-button'); await page.click('#model-refresh');
    await page.locator('[data-model="gemma3:12b"]').waitFor();
    await page.locator('[data-model="orcarouter/Qwen3.8-27B-Uncensored:iq4_xs"]').click();
    await page.click('#model-button');
    assert.equal(await page.locator('#model-installed-tab').getAttribute('aria-selected'), 'true');
    assert.equal(await page.locator('#provider-select option:checked').textContent(), 'Wixal Local · local');
    assert.equal(await page.textContent('#model-provider-heading'), 'WIXAL LOCAL · ON THIS MAC');
    assert.match(await page.textContent('#connection-label'), /^Wixal Local/);
    assert.equal(await page.evaluate(async () => (await window.wixal.connections()).providers.find(p => p.id === 'ollama').label), 'Wixal Local');
    assert.equal(await page.locator('#model-downloads-panel').isVisible(), false);
    assert.equal(await page.locator('#runtime-panel').getAttribute('open'), null);
    assert.equal(await page.locator('.model-row[aria-pressed="true"]').count(), 1);
    assert.equal(await page.locator('[data-model-delete]').first().isVisible(), false);
    assert.match(await page.textContent('#model-current-tag'), /orcarouter/);
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1400, 950));
    await page.waitForFunction(() => document.querySelector('#models-dialog').getBoundingClientRect().width > 0); await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/models-0.7.1-installed.png') });
    await page.fill('#model-search', 'gemma'); assert.equal(await page.locator('.model-row').count(), 1);
    await page.fill('#model-search', 'missing'); assert.match(await page.textContent('#model-list'), /No matching models/);
    await page.fill('#model-search', '');
    await page.locator('#model-filter-panel > summary').click();
    await page.selectOption('#model-type-filter', 'tools'); assert.equal(await page.locator('.model-row').count(), 2);
    await page.selectOption('#model-fit-filter', 'tested'); assert.equal(await page.locator('.model-row').count(), 0);
    await page.click('#model-downloads-tab'); assert.equal(await page.locator('#model-fit-filter').inputValue(), 'all');
    assert.equal(await page.locator('#model-fit-filter option[value="tested"]').evaluate(el => el.disabled), true);
    await page.fill('#model-search', 'qwen3:'); assert.ok(await page.locator('[data-download-tag]').count() > 0);
    await page.selectOption('#model-sort', 'size');
    const sizes = await page.locator('.catalog-size').allTextContents();
    assert.deepEqual(sizes.map(parseFloat), sizes.map(parseFloat).toSorted((a, b) => a - b));
    await page.locator('[data-download-tag="qwen3:8b"]').click();
    assert.equal(await page.inputValue('#model-pull-name'), 'qwen3:8b');
    assert.equal(await page.locator('#model-pull-name').evaluate(el => el === document.activeElement), true);
    await page.click('#model-installed-tab'); assert.equal(await page.locator('#model-fit-filter').inputValue(), 'tested');
    await page.click('#model-filters-reset'); assert.equal(await page.locator('.model-row').count(), 3);
    await page.locator('#model-installed-tab').focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#model-downloads-tab').getAttribute('aria-selected'), 'true');
    await page.fill('#model-search', ''); await page.click('#model-filters-reset');
    await page.locator('#model-filter-panel > summary').click();
    await page.waitForFunction(() => document.querySelector('#models-dialog').getBoundingClientRect().width > 0); await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/models-0.7.1-downloads.png') });
    for (const [width, height] of [[920, 640], [600, 800]]) {
      await app.evaluate(({ BrowserWindow }, size) => { const win = BrowserWindow.getAllWindows()[0]; win.setMinimumSize(400, 400); win.setSize(...size); }, [width, height]);
      assert.ok(await page.locator('#models-dialog').evaluate(el => el.scrollWidth <= el.clientWidth));
      await page.waitForFunction(() => document.querySelector('#models-dialog').getBoundingClientRect().width > 0); await page.screenshot({ animations: 'disabled', path: path.join(root, `artifacts/models-0.7.1-${width}.png`) });
      await page.click('#model-installed-tab');
      assert.ok(await page.locator('#models-dialog').evaluate(el => el.scrollWidth <= el.clientWidth));
      await page.click('#model-downloads-tab');
    }
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1400, 950));
    await page.selectOption('#context-size', '32768');
    await page.waitForFunction(async () => (await window.wixal.state()).contextSize === 32768);
    await page.selectOption('#provider-select', 'openai');
    await page.waitForFunction(() => document.querySelector('#model-installed-tab').getAttribute('aria-selected') === 'true');
    assert.equal(await page.locator('#model-downloads-tab').isVisible(), false);
    assert.equal(await page.locator('#runtime-panel').isVisible(), false);
    assert.equal(await page.locator('#model-hardware').isVisible(), false);
    assert.equal(await page.locator('#model-fit-filter').isDisabled(), true);
    await page.click('#model-connections'); await page.locator('#connections-dialog[open]').waitFor();
    await page.keyboard.press('Escape'); await page.click('#model-button'); await page.selectOption('#provider-select', 'ollama');
    await page.locator('.model-row').first().waitFor();
    await page.locator('#runtime-panel > summary').click(); assert.equal(await page.locator('#runtime-mode').inputValue(), 'external');
    await page.locator('#runtime-panel > summary').click();
    await page.click('[data-close="models-dialog"]');
    await page.evaluate(() => window.wixal.settings({ theme: 'paper' })); await page.reload(); await page.click('#model-button');
    assert.equal(await page.inputValue('#context-size'), '32768');
    await page.waitForFunction(() => document.querySelector('#models-dialog').getBoundingClientRect().width > 0); await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/models-0.7.1-paper.png') });
    await app.evaluate(() => { globalThis.pickerModels = []; }); await page.click('#model-refresh');
    await page.locator('.model-empty').waitFor(); await page.click('#model-empty-downloads');
    assert.equal(await page.locator('#model-downloads-panel').isVisible(), true);
    assert.deepEqual(errors, []);
    console.log('PASS: installed/download navigation, selection, search, tab-specific filters, catalog sort/tag choice, keyboard navigation, hidden delete, provider setup, context persistence, empty library, two themes and compact layouts');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
