const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises'), os = require('node:os'), path = require('node:path'), http = require('node:http');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-security-ui-'));
  const project = path.join(temp, 'Assessment'); await fs.mkdir(project);
  const server = http.createServer((_req, res) => { res.setHeader('Content-Type', 'text/html'); res.end('<html><title>Wixal security UI proof</title><body>Loopback assessment fixture</body></html>'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); const port = server.address().port;
 const seed = new (require('../app/store.cjs').Store)(path.join(temp, 'state')); seed.data.setup = { completed: true, entryCompleted: true }; seed.data.ui.launchAnimation = false; seed.save();
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: path.join(temp, 'state'), WIXAL_TEST_PROJECT: project }; delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message)); await page.locator('#prompt').waitFor();
    await app.evaluate((_app, port) => {
      const real = globalThis.fetch; globalThis.scanFixture = { requests: [], port };
      globalThis.fetch = async (target, options) => {
        if (!String(target).startsWith('http://127.0.0.1:11434')) return real(target, options);
        const json = data => new Response(JSON.stringify(data));
        if (String(target).endsWith('/api/version')) return json({ version: 'fixture' });
        if (String(target).endsWith('/api/tags')) return json({ models: [{ name: 'scan:test', digest: 'scan', size: 1e9 }] });
        if (String(target).endsWith('/api/show')) return json({ capabilities: ['tools', 'thinking'], thinking: { values: ['low', 'high'] }, model_info: { 'fixture.context_length': 32768 } });
        if (String(target).endsWith('/api/ps')) return json({ models: [] });
        const body = JSON.parse(options.body); globalThis.scanFixture.requests.push(body);
        const last = body.messages.at(-1); let message;
        if (last.role !== 'tool') message = { content: '', tool_calls: [{ function: { name: 'network_scan', arguments: { target: `http://127.0.0.1:${port}`, profile: 'web', timeout_seconds: 60 } } }] };
        else {
          const result = JSON.parse(last.content);
          if (last.tool_name === 'network_scan' || result.state === 'running') message = { content: '', tool_calls: [{ function: { name: 'network_read', arguments: { session_id: result.session_id, wait_ms: 1000 } } }] };
          else message = { content: `Assessment completed with exit code ${result.exitCode}. Actual scanner output contains Wixal security UI proof.` };
        }
        return json({ message, done: true });
      };
    }, port);
    await page.click('#model-button'); await page.click('#model-refresh');
    await page.locator('[data-model="scan:test"]').click();
    await page.waitForFunction(async () => (await window.wixal.state()).model === 'scan:test');
    await page.selectOption('#approval-mode', 'all'); await page.waitForFunction(async () => (await window.wixal.state()).approvalMode === 'all');
    await page.click('#header-tools'); await page.fill('#scan-target', `http://127.0.0.1:${port}`); await page.selectOption('#scan-profile', 'web'); await page.click('#scan-run');
    await page.waitForFunction(() => !document.querySelector('#send').classList.contains('hidden'), null, { timeout: 90000 });
    assert.equal(await page.locator('#approval-dialog').isVisible(), false);
    await page.locator('#activity-dock').evaluate(el => { el.open = true; });
    const evidenceState = await page.evaluate(() => window.wixal.state());
    const evidenceSession = evidenceState.sessions.find(c => c.id === evidenceState.activeSession);
    assert.ok(await page.locator('.scan-result-table').count() > 0, JSON.stringify({ messages: evidenceSession.messages.map(m => ({ role: m.role, name: m.tool_name, content: m.content?.slice(0, 700) })), toast: await page.textContent('#toast') }));
    assert.match(await page.locator('.scan-result-table').last().textContent(), /open/);
    const state = await page.evaluate(() => window.wixal.state()), messages = state.sessions.find(c => c.id === state.activeSession).messages;
    assert.ok(messages.some(m => m.tool_name === 'network_read' && m.content.includes('Wixal security UI proof')), JSON.stringify(messages.filter(m => m.role === 'tool')));
    assert.ok(state.actionApprovals.some(a => a.tool === 'network_scan'));
    assert.equal(await page.locator('#approval-mode').inputValue(), 'all');
    await page.reload(); await page.locator('#prompt').waitFor(); assert.equal(await page.locator('#approval-mode').inputValue(), 'all');
    await page.selectOption('#approval-mode', 'review'); await page.waitForFunction(async () => (await window.wixal.state()).approvalMode === 'review');
    await page.click('#header-tools'); await page.fill('#scan-target', '127.0.0.1'); await page.selectOption('#scan-profile', 'web'); await page.click('#scan-run');
    await page.locator('#approval-dialog[open]').waitFor();
    await page.selectOption('#approval-mode', 'all', { force: true });
    await page.waitForFunction(() => !document.querySelector('#approval-dialog').open);
    await page.waitForFunction(() => !document.querySelector('#send').classList.contains('hidden'), null, { timeout: 90000 });
    const requests = await app.evaluate(() => globalThis.scanFixture.requests); assert.equal(requests[0].think, 'low');
    assert.match(requests[0].messages[0].content, /App-provided workspace context/);
    assert.match(requests[0].messages[0].content, /"approvalMode":"all"/);
    assert.deepEqual(errors, []);
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true }); await page.click('#header-tools'); await page.locator('#scan-target').waitFor(); await page.screenshot({ animations: 'disabled', path: path.join(root, 'artifacts/security-workspace-0.7.5.png') });
    console.log('SECURITY_UI_OK: scan form drives real loopback Nmap; Approved all has no dialogs; Review prompts and can switch to all while waiting; mode persists; live workspace tools and reasoning levels are embedded.');
  } finally { if (app) await app.close(); await new Promise(resolve => server.close(resolve)); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(e => { console.error(e); process.exitCode = 1; });
