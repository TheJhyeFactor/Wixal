const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
async function main() {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-providers-ui-')), project = path.join(temp, 'Provider demo');
  await fs.mkdir(project); await fs.writeFile(path.join(project, 'README.md'), 'Protocol fixtures, no live cloud account.');
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: path.join(temp, 'data'), WIXAL_TEST_PROJECT: project }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message));
    async function openWorkspace(id) { if (!(await page.locator(id).isVisible())) await page.click('#workspace-menu-toggle'); await page.click(id); }
    await page.locator('#connection-label').filter({ hasText: 'Wixal Local connected' }).waitFor({ timeout: 20000, state: 'attached' });
    await app.evaluate(({ app }, fixturePath) => {
      const fixtures = process.mainModule.require(fixturePath);
      const { providers } = process.mainModule.require(app.getAppPath() + '/app/providers.cjs');
      const original = globalThis.fetch; globalThis.providerRequests = [];
      globalThis.fetch = async (url, options) => {
        const text = String(url);
        const found = Object.entries(providers).find(([, info]) => info.baseURL && text.startsWith(info.baseURL + '/'));
        const id = text.startsWith('http://127.0.0.1:14877/v1/') ? 'custom' : found?.[0];
        if (!id) return original(url, options);
        if (text.includes('/models') || text.endsWith('/language-models')) return new Response(JSON.stringify(fixtures.catalogs[id]));
        const body = JSON.parse(options.body); globalThis.providerRequests.push({ id, body, headers: options.headers });
        const hasResult = body.input?.some(i => i.type === 'function_call_output') || body.messages?.some(m => m.role === 'tool' || Array.isArray(m.content) && m.content.some(c => c.type === 'tool_result'));
        const call = hasResult ? null : { name: 'write_file', args: { path: `${id}-proof.txt`, content: `reviewed-${id}` } };
        const denied = JSON.stringify(body).includes('User declined');
        return id === 'xai' ? fixtures.responses(call, denied ? 'Edit declined.' : 'Reviewed file saved.') : id === 'anthropic' ? fixtures.anthropic(call, denied ? 'Edit declined.' : 'Reviewed file saved.') : fixtures.completion(call, denied ? 'Edit declined.' : 'Reviewed file saved.');
      };
    }, path.join(root, 'test/provider-fixtures.cjs'));
    await openWorkspace('#connections-button');
    for (const provider of ['xai', 'deepseek', 'anthropic', 'gemini', 'groq', 'mistral', 'openrouter']) {
      await page.selectOption('#key-provider-select', provider); await page.fill('#api-key-input', `${provider}-fixture-secret`); await page.locator('#api-key-form button').click();
      await page.locator('#api-key-status').filter({ hasText: 'saved securely' }).waitFor(); assert.equal(await page.inputValue('#api-key-input'), '');
    }
    await page.selectOption('#key-provider-select', 'custom');
    await page.fill('#custom-base-url', 'http://127.0.0.1:14877/v1'); await page.fill('#custom-model', 'local-fixture'); await page.check('#custom-tools'); await page.check('#custom-vision'); await page.locator('#api-key-form button').click();
    await page.locator('[data-cloud]').check();
    const connections = await page.evaluate(() => window.wixal.connections()); assert.doesNotMatch(JSON.stringify(connections), /fixture-secret/);
    assert.doesNotMatch(await fs.readFile(path.join(temp, 'data/credentials.enc'), 'utf8'), /fixture-secret/);
    console.log('PASS: separate provider keys saved with real macOS encryption; custom endpoint configured without a key');
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    await page.selectOption('#key-provider-select', 'anthropic'); await page.locator('#toast').waitFor({ state: 'hidden', timeout: 12000 });
    await page.locator('#connections-dialog').evaluate(dialog => { dialog.scrollTop = 0; }); await page.screenshot({ path: path.join(root, 'artifacts/wixal-providers.png'), animations: 'disabled' });
    await page.click('[data-close="connections-dialog"]');
    for (const provider of ['xai', 'deepseek', 'anthropic', 'gemini', 'groq', 'mistral', 'openrouter', 'custom']) {
      await page.click('#new-chat'); await page.click('#model-button'); await page.selectOption('#provider-select', provider); await page.locator('.model-row').waitFor(); await page.locator('.model-row').click();
      await page.fill('#prompt', `Create a reviewed ${provider} file.`); await page.click('#send');
      await page.locator('#approval-dialog[open]').waitFor(); assert.match(await page.locator('#approval-title').textContent(), new RegExp(`${provider}-proof`));
      await page.click(provider === 'deepseek' ? '#decline' : '#approve'); await page.locator('#activity-label').filter({ hasText: 'Ready' }).waitFor();
      if (provider === 'deepseek') await assert.rejects(fs.access(path.join(project, `${provider}-proof.txt`)));
      else assert.equal(await fs.readFile(path.join(project, `${provider}-proof.txt`), 'utf8'), `reviewed-${provider}`);
      const requests = await app.evaluate(() => globalThis.providerRequests);
      const own = requests.filter(r => r.id === provider); assert.equal(own.length, 2);
      const headers = own[0].headers;
      if (provider === 'anthropic') assert.equal(headers['x-api-key'], `${provider}-fixture-secret`);
      else if (provider === 'custom') assert.equal(headers.Authorization, undefined);
      else assert.equal(headers.Authorization, `Bearer ${provider}-fixture-secret`);
      assert.match(JSON.stringify(own[1].body), provider === 'deepseek' ? /User declined/ : /Saved/);
      console.log(`PASS: ${provider} catalog, isolated credential, native tool continuation and real ${provider === 'deepseek' ? 'declined' : 'approved'} file review`);
    }
    await page.reload(); await page.locator('#connection-label').filter({ hasText: 'Custom endpoint connected' }).waitFor({ state: 'attached' });
    const saved = await page.evaluate(() => window.wixal.state()); assert.equal(saved.providerModels.anthropic, 'claude-fixture'); assert.equal(saved.customProvider.model, 'local-fixture'); assert.equal(saved.sessions.filter(s => s.messages.length).length, 8);
    await openWorkspace('#connections-button'); await page.selectOption('#key-provider-select', 'xai'); await page.click('#remove-api-key'); await page.locator('#api-key-status').filter({ hasText: 'No key saved' }).waitFor();
    const afterRemoval = await page.evaluate(() => window.wixal.connections()); assert.equal(afterRemoval.keysSaved.xai, false); assert.equal(afterRemoval.keysSaved.anthropic, true);
    await page.click('[data-close="connections-dialog"]'); await page.fill('#prompt', 'Confirm the previous reviewed result.'); await page.click('#send'); await page.locator('#activity-label').filter({ hasText: 'Ready' }).waitFor();
    const following = await page.evaluate(() => window.wixal.state()); assert.equal(following.sessions.find(s => s.id === following.activeSession).messages.at(-1).content, 'Reviewed file saved.');
    await openWorkspace('#connections-button'); await page.selectOption('#key-provider-select', 'custom'); await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640));
    await page.locator('#connections-dialog').evaluate(dialog => { dialog.scrollTop = 0; }); await page.locator('#toast').waitFor({ state: 'hidden', timeout: 12000 });
    assert.ok(await page.locator('#connections-dialog').evaluate(dialog => dialog.scrollWidth <= dialog.clientWidth + 1));
    await page.screenshot({ path: path.join(root, 'artifacts/wixal-providers-custom.png'), animations: 'disabled' });
    assert.deepEqual(errors, []); console.log('PASS: reload preserved conversations and provider models; key removal stayed isolated; compact UI had no horizontal overflow or renderer errors');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
