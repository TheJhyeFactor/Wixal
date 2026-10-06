// Exercise actual installed models through the Electron UI in an isolated workspace.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-chat-tools-live-'));
  const project = path.join(temp, 'project'); await fs.mkdir(project);
  await fs.writeFile(path.join(project, 'proof.txt'), 'WIXAL_REAL_FILE_7924');
  const server = http.createServer((_req, res) => { res.setHeader('Content-Type', 'text/html'); res.end('<title>Wixal tool proof</title><body><script>document.body.append("WIXAL_RENDERED_PAGE_7924")</script></body>'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/proof`;
  const seed = new (require('../app/store.cjs').Store)(path.join(temp, 'state'));
  seed.data.setup = { completed: true, entryCompleted: true };
  seed.data.ui.launchAnimation = false; seed.data.ui.launchSound = false; seed.save();
  const env = { ...process.env, WIXAL_DATA_DIR: path.join(temp, 'state'), WIXAL_TEST_PROJECT: project }; delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_RUNTIME_MODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.locator('#prompt').waitFor();
    await page.evaluate(() => { window.toolRunEvents = []; window.wixal.onEvent(e => { if (['error', 'done', 'run-started', 'approval'].includes(e.type)) window.toolRunEvents.push(e); }); });
    const catalog = await page.evaluate(() => window.wixal.models());
    const models = process.env.WIXAL_TOOL_MODELS ? process.env.WIXAL_TOOL_MODELS.split(',') : catalog.models.filter(m => m.capabilities?.includes('tools') || m.name === 'gpt-oss:20b').map(m => m.name);
    assert.ok(models.length, 'Install a tool-capable model before running this live check.');
    async function run(prompt, review) {
      await page.evaluate(() => { window.toolRunEvents = []; });
      await page.fill('#prompt', prompt); await page.click('#send');
      const deadline = Date.now() + 180000; let approvals = 0;
      while (Date.now() < deadline) {
        const events = await page.evaluate(() => window.toolRunEvents);
        const error = events.find(e => e.type === 'error'); if (error) throw new Error(error.message);
        if (await page.locator('#approval-dialog').isVisible()) {
          const content = await page.textContent('#approval-content');
          if (!review || !review(content)) { await page.click('#decline'); throw new Error(`Unexpected tool review: ${content}`); }
          approvals++; await page.click('#approve');
        }
        if (events.some(e => e.type === 'done')) {
          const state = await page.evaluate(() => window.wixal.state());
          return { messages: state.sessions.find(s => s.id === state.activeSession).messages, approvals };
        }
        await new Promise(resolve => setTimeout(resolve, 150));
      }
      await page.evaluate(() => window.wixal.stop()); throw new Error('Live model timed out.');
    }
    for (const model of models) {
      await page.evaluate(name => window.wixal['model-select'](name), model);
      const selected = await page.evaluate(() => window.wixal.models());
      assert.ok(selected.models.find(m => m.name === model)?.capabilities?.includes('tools'), `${model} lacks native tools`);
      await page.evaluate(model => window.wixal.settings({ model, mode: 'chat', contextSize: 8192, autoSummary: false }), model);
      await page.reload(); await page.locator('#prompt').waitFor();
      await page.evaluate(() => { window.toolRunEvents = []; window.wixal.onEvent(e => { if (['error', 'done', 'run-started', 'approval'].includes(e.type)) window.toolRunEvents.push(e); }); });
      await page.evaluate(() => window.wixal['session-new']()); await page.reload();
      await page.evaluate(() => { window.toolRunEvents = []; window.wixal.onEvent(e => { if (['error', 'done', 'run-started', 'approval'].includes(e.type)) window.toolRunEvents.push(e); }); });
      let result;
      if (process.env.WIXAL_TEST_SCAN_ONLY !== '1') {
      result = await run('Read proof.txt and tell me its exact contents.', content => content.trim() === 'cat proof.txt');
      assert.ok(result.messages.some(m => m.role === 'tool' && (m.tool_name === 'read_file' && m.content === 'WIXAL_REAL_FILE_7924' || m.tool_name === 'run_command' && JSON.parse(m.content).output === 'WIXAL_REAL_FILE_7924' && JSON.parse(m.content).exitCode === 0)));
      assert.match(result.messages.at(-1).content, /WIXAL_REAL_FILE_7924/, JSON.stringify(result.messages));
      console.log(`PASS ${model}: ordinary Chat reads a real file without @`);
      result = await run('@browser_inspect use this');
      assert.ok(result.messages.at(-1).role === 'assistant' && /url|website|address|link/i.test(result.messages.at(-1).content));
      assert.equal(result.approvals, 0);
      console.log(`PASS ${model}: missing URL produces a visible clarification`);
      result = await run(`@browser_inspect inspect ${url} and report the rendered proof text. Use default limits and no wait_for expectation.`, content => content.trim() === url);
      assert.ok(result.messages.some(m => m.tool_name === 'browser_inspect' && m.content.includes('WIXAL_RENDERED_PAGE_7924')), JSON.stringify(result.messages.slice(-4)));
      assert.match(result.messages.at(-1).content, /WIXAL_RENDERED_PAGE_7924/); assert.equal(result.approvals, 1);
      console.log(`PASS ${model}: reviewed browser call returns real JavaScript-rendered output`);
      result = await run('@command_start run exactly printf WIXAL_COMMAND_7924 then use command_read until it completes. Report its output and exit status.', content => content.trim() === 'printf WIXAL_COMMAND_7924');
      assert.ok(result.messages.some(m => m.tool_name === 'command_read' && JSON.parse(m.content).output === 'WIXAL_COMMAND_7924' && JSON.parse(m.content).exitCode === 0));
      assert.match(result.messages.at(-1).content, /WIXAL_COMMAND_7924/); assert.equal(result.approvals, 1);
      console.log(`PASS ${model}: @command_start retains command_read and sees real stdout/exit status`);
      await page.evaluate(() => window.wixal['session-new']()); await page.reload();
      await page.evaluate(() => { window.toolRunEvents = []; window.wixal.onEvent(e => { if (['error', 'done', 'run-started', 'approval'].includes(e.type)) window.toolRunEvents.push(e); }); });
      result = await run('@browser_open Open https://jhye.dev/ with browser_open. Find the Work link in its returned fresh refs, click it using browser_action, read the actual selected work text, close the session with browser_close and name two projects supported by the returned page.', content => /^https:\/\/jhye\.dev\/(?:work\/)?$/.test(content.trim()) || /^https:\/\/jhye\.dev\/work\/\n\nclick: All work\b/.test(content));
      const opened = result.messages.filter(m => ['browser_open','browser_action','browser_read'].includes(m.tool_name)).map(m => { try { return JSON.parse(m.content); } catch { return null; } }).filter(Boolean);
      assert.ok(opened.some(p => p.url === 'https://jhye.dev/'));
      const work = opened.find(p => p.url === 'https://jhye.dev/work/'); assert.ok(work && work.status === 200 && work.text.length > 100);
      assert.ok(result.messages.some(m => m.tool_name === 'browser_close' && JSON.parse(m.content).state === 'closed'));
      const workText = opened.filter(p => p.url === 'https://jhye.dev/work/').map(p => p.text).join('\n');
      const projectNames = ['garak scan planner', 'Apertide', 'Sentinel Local', 'The Finest Group', 'Hunter Valley Prestige Wine Tours'];
      assert.ok(projectNames.filter(name => workText.toLowerCase().includes(name.toLowerCase()) && result.messages.at(-1).content.toLowerCase().includes(name.toLowerCase())).length >= 2, 'The answer must name at least two actual projects from the returned page. '+JSON.stringify(result.messages.slice(-5)));
      if (!process.env.WIXAL_APP_PATH) {
        const activities = page.locator('.turn-activity'); await activities.last().locator('summary').first().click();
        const action = activities.last().locator('[data-inspect-action]').nth(Math.min(1, (await activities.last().locator('[data-inspect-action]').count()) - 1)); if (await action.count()) await action.click();
        await page.waitForTimeout(250);
        const preview = await page.evaluate(() => window.wixal['context-preview']('')); assert.ok(preview.used <= preview.inputLimit, 'The idle context meter must reflect bounded inference evidence, not raw saved results.');
        await page.screenshot({ path: '/tmp/wixal-jhye-tools.png', animations: 'disabled' });
      }
      console.log(`PASS ${model}: actual jhye.dev homepage, fresh-ref link interaction, Work evidence and browser cleanup reach a visible answer`);
      result = await run('@web_search Search for jhye.dev. Report two exact titles and URLs from the returned results. Do not browse other sources.', content => content.includes('jhye.dev'));
      const search = result.messages.find(m => m.tool_name === 'web_search');assert.ok(search);const evidence = JSON.parse(search.content);assert.ok(evidence.results.some(r => r.url.startsWith('https://jhye.dev/')));assert.match(result.messages.at(-1).content,/https:\/\/jhye\.dev/);
      console.log(`PASS ${model}: live search results about jhye.dev reach the visible model answer`);

      }
      if (process.env.WIXAL_TEST_SCAN_ONLY === '1') {
        await page.evaluate(() => window.wixal['approval-mode']('all')); await page.reload();
        await page.evaluate(() => { window.toolRunEvents = []; window.wixal.onEvent(e => { if (['error', 'done', 'run-started', 'approval'].includes(e.type)) window.toolRunEvents.push(e); }); });
        result = await run(`@network_scan Run the authorised loopback TCP ports assessment of 127.0.0.1 with profile ports, TCP ports ${server.address().port}, timeout_seconds 60. Use network_read until completion, then command_save_output to save scan-proof.json. Report the actual port state and exit code.`);
        assert.equal(result.approvals, 0);
        assert.ok(result.messages.some(m => m.tool_name === 'network_read' && JSON.parse(m.content).state === 'completed' && JSON.parse(m.content).exitCode === 0));
        assert.ok(result.messages.some(m => m.tool_name === 'command_save_output'));
        const report = JSON.parse(await fs.readFile(path.join(project, 'scan-proof.json'), 'utf8'));
        assert.equal(report.assessment.target, '127.0.0.1'); assert.equal(report.assessment.profile, 'ports');
        assert.match(report.output, /state="open"/); assert.equal(report.exitCode, 0);
        console.log(`PASS ${model}: Approved all runs real Nmap, reads completion and saves actual scan evidence without a dialog`);
      }
    }
    assert.deepEqual(errors, []);
    console.log(`CHAT_TOOLS_LIVE_OK: ${models.length} real models; ${process.env.WIXAL_TEST_SCAN_ONLY === '1' ? 'real loopback scan and evidence report in Approved all' : 'file read, clarification, rendered fixture, command continuation, live jhye.dev navigation and search in Chat'}`);
  } finally { if (app) await app.close(); await new Promise(resolve => server.close(resolve)); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(e => { console.error(e); process.exitCode = 1; });
