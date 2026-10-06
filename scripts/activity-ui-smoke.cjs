// Real Electron UI and tool execution; only model responses use a deterministic local fixture.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
const root = path.resolve(__dirname, '..');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const call = (name, args) => ({ content: '', tool_calls: [{ function: { name, arguments: args } }] });
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-activity-'));
  const project = path.join(temp, 'Timeline demo'); await fs.mkdir(project);
  await fs.writeFile(path.join(project, 'README.md'), '# Timeline demo\nReal project file.');
  const directory = path.join(temp, 'data'), store = new Store(directory); store.addProject(project);
  store.data.setup = { completed: true, entryCompleted: true }; store.data.ui.theme = 'paper';
  store.data.model = 'activity-fixture'; store.data.mode = 'agent'; store.data.autoSummary = false;
  store.data.enabledTools = ['list_files', 'read_file', 'command_start', 'command_read', 'run_command'];
  const historical = [
    { role: 'user', content: 'Read the main docs and files, then explain where I should start.', runStatus: 'completed', created: Date.now() - 40000 },
    { role: 'assistant', content: 'I will check the structure and main documentation.', tool_calls: [{ function: { name: 'list_files', arguments: {} } }] },
    { role: 'tool', tool_name: 'list_files', content: 'README.md\napp/\nui/' },
    { role: 'assistant', content: '', tool_calls: [{ function: { name: 'read_file', arguments: { path: 'README.md' } } }] },
    { role: 'tool', tool_name: 'read_file', content: '# Timeline demo\nReal project file.' },
    { role: 'assistant', content: 'Start with the conversation renderer. The agent coordinates tools and the model; the UI presents their results.', metrics: { tokens: 25, tokensPerSecond: 10, seconds: 2.5 } },
    { role: 'user', content: 'Review the command output.', runStatus: 'completed' },
    { role: 'assistant', content: '', tool_calls: [{ function: { name: 'command_start', arguments: { command: 'printf SAVED_COMMAND_PROOF' } } }] },
    { role: 'tool', tool_name: 'command_start', content: JSON.stringify({ session_id: 'saved', command: 'printf SAVED_COMMAND_PROOF', state: 'running' }) },
    { role: 'assistant', content: '', tool_calls: [{ function: { name: 'command_read', arguments: { session_id: 'saved' } } }] },
    { role: 'tool', tool_name: 'command_read', content: JSON.stringify({ session_id: 'saved', state: 'completed', exitCode: 0, output: 'SAVED_COMMAND_PROOF', offset: 0 }) },
    { role: 'assistant', content: '', tool_calls: [{ function: { name: 'command_read', arguments: { session_id: 'saved', offset: 19 } } }] },
    { role: 'tool', tool_name: 'command_read', content: JSON.stringify({ session_id: 'saved', state: 'completed', exitCode: 0, output: '', offset: 19 }) },
    { role: 'assistant', content: 'The command completed successfully and returned SAVED_COMMAND_PROOF.' },
  ];
  store.session().messages = historical; store.save();
  let fixtureMode = 'tools';
  const server = http.createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/api/tags') return res.end(JSON.stringify({ models: [{ name: 'activity-fixture', size: 1000 }] }));
    if (req.url === '/api/show') return res.end(JSON.stringify({ capabilities: ['tools'], model_info: { 'fixture.context_length': 8192 }, details: { parameter_size: 'fixture' } }));
    if (req.url !== '/api/chat') return res.end('{}');
    if (fixtureMode === 'stop') { await pause(5000); if (!res.destroyed) res.end(JSON.stringify({ message: { content: 'This delayed response should be cancelled.' }, done: true })); return; }
    if (fixtureMode === 'error') return res.end(JSON.stringify({ error: 'Fixture model failure' }));
    const data = JSON.parse(raw), last = data.messages.at(-1);
    let message;
    if (last.role === 'user') message = fixtureMode === 'stream' ? call('run_command', { command: 'printf LIVE_DOCK_STREAM; sleep 2; printf _DONE' }) : call('command_start', { command: 'printf WIXAL_TIMELINE_REAL_OUTPUT' });
    else if (last.role === 'tool' && last.tool_name === 'command_start') {
      if (last.content.startsWith('User declined')) message = { content: 'The command was declined.' };
      else message = call('command_read', { session_id: JSON.parse(last.content).session_id });
    } else if (last.role === 'tool' && last.tool_name === 'command_read') {
      const result = JSON.parse(last.content);
      message = result.state === 'running' ? call('command_read', { session_id: result.session_id, offset: result.next_offset }) : { content: 'The command returned WIXAL_TIMELINE_REAL_OUTPUT and exited successfully.' };
    } else message = { content: 'Finished.' };
    await pause(700);
    res.end(JSON.stringify({ message, done: true, eval_count: 15, eval_duration: 1e9, total_duration: 1e9 }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${server.address().port}`;
  const env = { ...process.env, WIXAL_DATA_DIR: directory, WIXAL_RUNTIME_MODE: 'external' }; delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_TEST_PROJECT;
  let app;
  const shots = process.env.WIXAL_ACTIVITY_SHOTS || '/Users/jhye/.codex/visualizations/2026/10/06/01a11010-0f13-7e71-9b6d-75807606739c';
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    await app.evaluate(({ app }, endpoint) => process.mainModule.require(app.getAppPath() + '/app/models.cjs').configureLocalRuntime({ endpoint: async () => endpoint }), endpoint);
    const page = await app.firstWindow(), errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.reload(); await page.locator('.turn-activity').first().waitFor();
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1360, 880));
    assert.equal(await page.locator('.turn-activity').count(), 2);
    assert.equal(await page.locator('.turn-activity[open]').count(), 0);
    assert.equal(await page.locator('.tool-message').count(), 0);
    assert.doesNotMatch(await page.locator('#messages').innerText(), /Requested |session_id/);
    assert.match(await page.locator('.turn-activity').last().innerText(), /1 step · 3 tool calls/);
    await page.locator('.turn-activity').last().locator('summary').first().click();
    await page.locator('.turn-activity').last().locator('[data-inspect-action]').click();
    assert.match(await page.locator('#activity-dock').innerText(), /SAVED_COMMAND_PROOF/);
    assert.equal(await page.locator('#dock-body .tool-content').first().innerText(), 'SAVED_COMMAND_PROOF');
    await page.click('.dock-raw > summary'); assert.match(await page.locator('.dock-raw').innerText(), /session_id/);
    await page.locator('.turn-activity').first().locator('summary').first().click();
    await page.locator('.turn-activity').first().locator('[data-inspect-action]').last().click();
    assert.match(await page.locator('#activity-dock').innerText(), /Real project file/);
    assert.match(await page.locator('#dock-status').innerText(), /Earlier request/);
    await page.locator('.turn-activity').first().locator('summary').first().click();
    await page.locator('.turn-activity').last().locator('summary').first().click();
    await page.locator('#activity-dock > summary').click();
    await fs.mkdir(shots, { recursive: true }); await page.screenshot({ animations: 'disabled', path: path.join(shots, 'wixal-timeline-folded.png') });
    const persisted = await page.evaluate(() => window.wixal.state());
    assert.equal(persisted.sessions.find(s => s.id === persisted.activeSession).messages.length, historical.length);
    await page.reload(); await page.locator('.turn-activity').first().waitFor(); assert.equal(await page.locator('.turn-activity[open]').count(), 0);
    await page.waitForFunction(() => document.querySelector('#model-label').textContent.includes('activity-fixture'));
    await page.fill('#prompt', 'Run the proof command'); await page.click('#send');
    await page.locator('#approval-dialog[open]').waitFor();
    assert.equal(await page.locator('#approval-content').innerText(), 'printf WIXAL_TIMELINE_REAL_OUTPUT');
    assert.match(await page.locator('#dock-status').innerText(), /Waiting for your review/);
    assert.ok(await page.locator('.turn-activity').last().evaluate(el => el.open));
    await page.screenshot({ animations: 'disabled', path: path.join(shots, 'wixal-timeline-review.png') });
    await page.click('#approve');
    await page.locator('#send:not(.hidden)').waitFor({ timeout: 20000 });
    await page.waitForFunction(async () => { const s = await window.wixal.state(); return s.sessions.find(x => x.id === s.activeSession).messages.findLast(x => x.role === 'user')?.runStatus === 'completed'; });
    assert.equal(await page.locator('.turn-activity').last().evaluate(el => el.open), false);
    assert.match(await page.locator('#messages').innerText(), /WIXAL_TIMELINE_REAL_OUTPUT/);
    await page.locator('.turn-activity').last().locator('summary').first().click();
    await page.locator('.turn-activity').last().locator('[data-inspect-action]').click();
    assert.match(await page.locator('#activity-dock').innerText(), /WIXAL_TIMELINE_REAL_OUTPUT/);
    assert.match(await page.locator('#activity-dock').innerText(), /Exit 0/);
    await page.screenshot({ animations: 'disabled', path: path.join(shots, 'wixal-timeline-output.png') });
    // Real stdout appears in the dock before the command finishes.
    fixtureMode = 'stream'; await page.fill('#prompt', 'Stream the proof command'); await page.click('#send');
    await page.locator('#approval-dialog[open]').waitFor(); await page.click('#approve');
    await page.waitForFunction(() => document.querySelector('#dock-body').textContent.includes('LIVE_DOCK_STREAM'));
    assert.equal(await page.locator('#activity-dock').evaluate(el => el.classList.contains('is-running')), true);
    assert.match(await page.locator('#dock-status').innerText(), /Using Run commands/);
    await page.locator('#activity-dock > summary').click();
    assert.match(await page.locator('.dock-selection').innerText(), /Running/);
    await page.screenshot({ animations: 'disabled', path: path.join(shots, 'wixal-timeline-running.png') });
    await page.locator('#send:not(.hidden)').waitFor();
    assert.match(await page.locator('#dock-body').innerText(), /LIVE_DOCK_STREAM_DONE/);
    fixtureMode = 'tools';
    // A declined command must remain visibly declined, including after reload.
    await page.fill('#prompt', 'Decline this command'); await page.click('#send');
    await page.locator('#approval-dialog[open]').waitFor(); await page.click('#decline');
    await page.locator('#send:not(.hidden)').waitFor();
    assert.match(await page.locator('.turn-activity').last().innerText(), /Finished with issues/);
    await page.locator('.turn-activity').last().locator('summary').first().click();
    assert.match(await page.locator('.turn-activity').last().innerText(), /Declined/);
    fixtureMode = 'stop'; await page.fill('#prompt', 'Stop this request'); await page.click('#send'); await page.locator('#stop:not(.hidden)').waitFor(); await pause(250); await page.click('#stop');
    await page.locator('#send:not(.hidden)').waitFor(); await page.waitForFunction(() => document.querySelector('#dock-status').textContent === 'Stopped');
    await page.reload(); await page.waitForFunction(() => document.querySelector('#dock-status').textContent === 'Stopped');
    fixtureMode = 'error'; await page.waitForFunction(() => document.querySelector('#model-label').textContent.includes('activity-fixture')); await page.fill('#prompt', 'Fail this request'); await page.click('#send');
    await page.waitForFunction(() => document.querySelector('#dock-status').textContent === 'Failed');
    assert.equal(await page.locator('#send').isVisible(), true);
    // Compact layout and both motion preferences.
    await page.evaluate(async () => { await window.wixal.settings({ theme: 'sakura', reduceMotion: true }); }); await page.reload();
    await page.locator('.turn-activity').last().waitFor(); await page.emulateMedia({ reducedMotion: 'reduce' });
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640));
    await page.locator('.turn-activity').last().locator('summary').first().click(); await page.locator('.turn-activity').last().locator('[data-inspect-action]').click();
    assert.equal(await page.locator('.dock-dot').evaluate(el => getComputedStyle(el).animationName), 'none');
    const layout = await page.evaluate(() => ({ overflow: document.body.scrollWidth > innerWidth, bottom: document.querySelector('#composer').getBoundingClientRect().bottom, height: innerHeight, dock: document.querySelector('#dock-body').getBoundingClientRect().height }));
    assert.equal(layout.overflow, false); assert.ok(layout.bottom < layout.height); assert.ok(layout.dock < layout.height * .4);
    await page.screenshot({ animations: 'disabled', path: path.join(shots, 'wixal-timeline-compact.png') });
    assert.deepEqual(errors, []);
    console.log('ACTIVITY_UI_OK: folded histories; merged command polling; exact output/raw events; saved history; real reviewed command; decline/stop/error; 1360×880 and 920×640; light/dark themes; reduced motion; no renderer errors.');
  } finally { if (app) await app.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
