// Browser plugin not available. Exercise the real Electron renderer through Playwright.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { Store } = require('../app/store.cjs');
const root = path.resolve(__dirname, '..');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-workspace-ui-'));
  const folder = path.join(temp, 'Workspace check'); await fs.mkdir(folder); await fs.writeFile(path.join(folder, 'README.md'), '# Workspace check\nActual project file.');
  const directory = path.join(temp, 'state'), store = new Store(directory); store.addProject(folder);
  const history = store.session(); history.title = 'Saved code and long chat';
  history.messages = [{ role: 'user', content: 'Show an example', created: Date.now() }, { role: 'assistant', content: '```js\nconsole.log("Workspace verified");\n```\n\n' + Array.from({ length: 70 }, (_, i) => `Paragraph ${i}: saved conversation content.`).join('\n\n'), created: Date.now() }];
  const start = store.newSession(); store.data.setup = { completed: true, entryCompleted: true }; store.data.ui.launchAnimation = false; store.data.mode = 'chat'; store.data.autoSummary = false; store.save();
  const env = { ...process.env, WIXAL_RUNTIME_MODE: 'external', WIXAL_DATA_DIR: directory }; delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_TEST_PROJECT;
  let app, previousClipboard;
  try {
    const launch = async () => electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    app = await launch(); let page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.locator('.session-item').first().waitFor(); assert.equal(await page.textContent('.title-version'), require('../package.json').version);
    const installFixture = () => app.evaluate(() => {
      const real = globalThis.fetch;
      globalThis.fetch = async (target, request) => {
        if (!String(target).startsWith('http://127.0.0.1:11434')) return real(target, request);
        const json = data => new Response(JSON.stringify(data));
        if (String(target).endsWith('/api/version')) return json({ version: 'fixture' });
        if (String(target).endsWith('/api/tags')) return json({ models: [{ name: 'workspace:test', size: 1e9 }] });
        if (String(target).endsWith('/api/show')) return json({ capabilities: ['tools'], details: { parameter_size: '1B' }, model_info: { 'fixture.context_length': 16384 } });
        if (String(target).endsWith('/api/ps')) return json({ models: [] });
        if (String(target).endsWith('/api/chat')) {
          return new Response(new ReadableStream({ async start(controller) {
            for (let i = 0; i < 35; i++) { controller.enqueue(new TextEncoder().encode(JSON.stringify({ message: { content: `Streaming chunk ${i}. ` }, done: false }) + '\n')); await new Promise(r => setTimeout(r, 80)); }
            controller.enqueue(new TextEncoder().encode(JSON.stringify({ message: { content: '' }, done: true, eval_count: 35, eval_duration: 3e9 }) + '\n')); controller.close();
          } }));
        }
        return json({});
      };
    });
    await installFixture(); await page.reload(); await page.locator('.session-item').first().waitFor();
    await page.click('#model-button'); await page.click('#model-refresh'); await page.locator('[data-model="workspace:test"]').click();
    await page.fill('#prompt', 'First chat draft'); await page.locator('#draft-status').filter({ hasText: 'Draft saved' }).waitFor();
    await page.locator(`.session-item[data-id="${history.id}"]`).click(); assert.equal(await page.inputValue('#prompt'), '');
    await page.fill('#prompt', 'Second chat draft'); await page.locator(`.session-item[data-id="${start.id}"]`).click(); assert.equal(await page.inputValue('#prompt'), 'First chat draft');
    await page.reload(); await page.waitForFunction(() => document.querySelector('#prompt').value === 'First chat draft');
    await app.close(); app = await launch(); page = await app.firstWindow(); page.on('pageerror', e => errors.push(e.message));
    await page.waitForFunction(() => document.querySelector('#prompt').value === 'First chat draft');
    const rejected = await page.evaluate(async () => {
      const failures = []; for (const [id, text] of [['missing', 'x'], [null, 'x'], [document.querySelector('.session-item.active').dataset.id, 'x'.repeat(16001)]]) { try { await window.wixal['session-draft'](id, text); } catch (e) { failures.push(e.message); } } return failures;
    }); assert.equal(rejected.length, 3);
    await installFixture(); await page.reload(); await page.waitForFunction(() => document.querySelector('#prompt').value === 'First chat draft');
    await page.click('#model-button'); await page.click('#model-refresh'); await page.locator('[data-model="workspace:test"]').click();
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1360, 880));
    await page.click('#header-tools'); await page.locator('#toolkit-drawer').waitFor(); assert.equal(await page.getAttribute('#header-tools', 'aria-expanded'), 'true');
    const drawerFit = await page.evaluate(() => ({ main: document.querySelector('main').getBoundingClientRect().right, drawer: document.querySelector('#toolkit-drawer').getBoundingClientRect().left })); assert.ok(drawerFit.main <= drawerFit.drawer + 1);
    await page.click('#close-toolkit'); await page.click('#header-memory'); await page.locator('#memory-drawer').waitFor(); await page.keyboard.press('Escape'); await page.locator('#memory-drawer').waitFor({ state: 'hidden' });
    await page.click('#header-files'); await page.locator('[data-file="README.md"]').click(); assert.match(await page.textContent('#file-content'), /Actual project file/); await page.click('[data-close="files-dialog"]');
    await page.click('#composer-tools'); await page.locator('#tool-mentions').waitFor(); assert.match(await page.inputValue('#prompt'), /@$/); await page.keyboard.press('Escape');
    await page.click('#mode-button'); await page.keyboard.press('End'); await page.keyboard.press('Enter'); await page.waitForFunction(() => document.querySelector('#mode-label').textContent === 'Agent');
    await page.click('#mode-button'); await page.keyboard.press('Home'); await page.keyboard.press('Enter'); await page.waitForFunction(() => document.querySelector('#mode-label').textContent === 'Chat');
    await page.locator(`.session-item[data-id="${history.id}"]`).click(); assert.equal(await page.inputValue('#prompt'), 'Second chat draft');
    await page.evaluate(() => { document.querySelector('#chat-scroll').scrollTop = 0; }); await page.locator('#jump-latest').waitFor();
    previousClipboard = await app.evaluate(({ clipboard }) => clipboard.readText()); await page.click('[data-copy-code]'); assert.equal(await app.evaluate(({ clipboard }) => clipboard.readText()), 'console.log("Workspace verified");\n');
    await page.click('#jump-latest'); await page.locator('#jump-latest').waitFor({ state: 'hidden' });
    await page.fill('#prompt', 'Continue this conversation'); await page.click('#send'); await page.locator('.pending-content').waitFor();
    await page.evaluate(() => { window.savedMessageNode = document.querySelector('#messages .message'); window.pendingMessageNode = document.querySelector('.pending-content'); document.querySelector('#chat-scroll').scrollTop = 0; });
    await page.waitForFunction(() => document.querySelector('.pending-content')?.textContent.includes('chunk 15'));
    const stable = await page.evaluate(() => ({ saved: window.savedMessageNode === document.querySelector('#messages .message'), pending: window.pendingMessageNode === document.querySelector('.pending-content'), scroll: document.querySelector('#chat-scroll').scrollTop }));
    assert.equal(stable.saved, true); assert.equal(stable.pending, true); assert.ok(stable.scroll < 10);
    await page.waitForFunction(() => !document.querySelector('#prompt').disabled); assert.equal(await page.inputValue('#prompt'), ''); assert.equal(await page.locator('.pending-content').count(), 0);
    const disk = JSON.parse(await fs.readFile(path.join(directory, 'workspace.json'), 'utf8')); assert.equal(disk.sessions.find(s => s.id === history.id).draft, ''); assert.match(disk.sessions.find(s => s.id === history.id).messages.at(-1).content, /chunk 34/);
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640)); await page.click('#mode-button');
    const compact = await page.locator('#mode-menu').boundingBox(); assert.ok(compact.x >= 0 && compact.y >= 0 && compact.x + compact.width <= 920); await page.keyboard.press('Escape');
    await page.click('#models-page-button'); await page.locator('#models-page').waitFor(); await page.locator(`.session-item[data-id="${start.id}"]`).click(); await page.locator('#models-page').waitFor({ state: 'hidden' });
    assert.deepEqual(errors, []);
    console.log('PASS: text drafts survive chat changes, reload and process restart; invalid drafts rejected; header tools/files/memory; mode keyboard selection; code clipboard; long-chat navigation; stable streaming nodes and scroll; sent draft cleared; compact mode menu; return from Models; no renderer errors.');
  } finally { if (app && previousClipboard !== undefined) await app.evaluate(({ clipboard }, text) => clipboard.writeText(text), previousClipboard); if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
