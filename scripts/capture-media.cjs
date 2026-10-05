// Record real UI interactions with disposable state; no staged model responses.
const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-media-'));
  const project = path.join(temp, 'Wixal demo');
  await fs.mkdir(project);
  await fs.writeFile(path.join(project, 'README.md'), '# Wixal demo\n\nA small project used to record the Wixal interface.\n\nExplore files, choose a local model, and use the terminal.\n');
  await fs.writeFile(path.join(project, 'hello.js'), "console.log('Hello from Wixal');\n");
  const env = { ...process.env, WIXAL_DATA_DIR: path.join(temp, 'state'), WIXAL_TEST_PROJECT: project };
  delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_RUNTIME_MODE;
  const { LocalRuntime } = require('../app/runtime.cjs');
  const runtime = new LocalRuntime({ directory: path.join(temp, 'state/local-runtime'), payload: path.join(root, 'runtime/ollama') });
  await runtime.importModel('gemma3:12b');
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow();
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1680, 1080));
    await page.locator('.title-version').filter({ hasText: require('../package.json').version }).waitFor();
    await page.locator('#project-label').filter({ hasText: 'Wixal demo' }).waitFor();
    await page.locator('#connection-label').filter({ hasText: 'Wixal Local connected' }).waitFor({ state: 'attached' });
    if (await page.locator('#sidebar').evaluate(element => element.classList.contains('collapsed'))) {
      await page.locator('#sidebar-toggle').click();
      await page.waitForFunction(() => !document.querySelector('#sidebar').classList.contains('collapsed'));
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('#welcome img').evaluateAll(images => Promise.all(images.map(i => i.decode())));
    const shots = path.join(root, 'docs/screenshots');
    await fs.mkdir(shots, { recursive: true });
    const frames = [], delays = [];
    async function capture(name, caption, delay = 2200) {
      await page.locator('#toast').waitFor({ state: 'hidden' });
      await page.mouse.move(1250, 25);
      const screenshot = await page.screenshot({ path: path.join(shots, `${name}.png`) });
      const image = await sharp(screenshot).resize(990, 720, { fit: 'contain', background: '#191a20' }).toBuffer();
      const label = Buffer.from(`<svg width="990" height="52"><rect width="990" height="52" fill="#191a20"/><text x="24" y="32" font-family="Helvetica,Arial,sans-serif" font-size="16" fill="#f1eee9">${caption}</text><text x="966" y="32" text-anchor="end" font-family="Menlo,monospace" font-size="11" fill="#e9a5bd">WIXAL</text></svg>`);
      const raw = await sharp({ create: { width: 990, height: 772, channels: 3, background: '#191a20' } }).composite([{ input: label, top: 0, left: 0 }, { input: image, top: 52, left: 0 }]).removeAlpha().raw().toBuffer();
      frames.push(raw); delays.push(delay);
    }
    async function openWorkspaceSection(id) {
      await page.locator('#workspace-menu-toggle').click();
      await page.locator(id).click();
    }
    await capture('workspace', 'Open a project and make yourself at home.', 3000);
    await page.click('#model-button');
    await page.locator('.model-row').first().waitFor();
    await page.locator('#models-dialog').evaluate(el => { el.scrollTop = 0; });
    await capture('models', 'Wixal Local: the engine and model library are managed by the app.');
    await page.click('[data-benchmark]');
    const deadline = Date.now() + 180000;
    while (Date.now() < deadline) { const current = await page.evaluate(() => window.wixal.state()); if (current.benchmarks.length && !current.benchmarkProgress) break; await new Promise(r => setTimeout(r, 200)); }
    await page.click('[data-close="models-dialog"]');
    await page.click('#models-page-button');
    await capture('models-page', 'Models: your library, context settings and measured performance.');
    await page.click('#model-downloads-tab');
    await page.locator('[data-catalog-download="gemma3:270m"]').click();
    const downloadDeadline = Date.now() + 300000;
    let downloaded = false;
    while (Date.now() < downloadDeadline) {
      const current = await page.evaluate(() => window.wixal.state());
      const job = current.modelDownloads.find(j => j.name === 'gemma3:270m');
      if (job?.state === 'failed') throw new Error(job.error);
      if (job?.state === 'completed') { downloaded = true; break; }
      await new Promise(r => setTimeout(r, 200));
    }
    if (!downloaded) throw new Error('Media download timed out');
    await capture('model-downloads', 'Download in Wixal, then choose the installed model.');
    await page.click('#models-page-back');
    await page.evaluate(() => { window.mediaReplyDone = false; window.wixal.onEvent(e => { if (e.type === 'done') window.mediaReplyDone = true; }); });
    await page.fill('#prompt', 'Explain what a local AI model is in one short sentence.'); await page.click('#send'); await page.waitForFunction(() => window.mediaReplyDone, null, { timeout: 180000 });
    await page.click('#response-stats'); await capture('performance', 'Measure real model throughput and memory on your Mac.'); await page.click('[data-close="performance-dialog"]');
    await openWorkspaceSection('#files-button');
    await page.locator('[data-file="README.md"]').click();
    await page.locator('#file-content').filter({ hasText: 'A small project' }).waitFor();
    await capture('files', 'Browse the project and bring a file into the conversation.');
    await page.click('[data-close="files-dialog"]');
    await openWorkspaceSection('#toolkit-button');
    await capture('toolkit', 'Choose which tools the model can use.');
    await page.click('#manage-extensions');
    await capture('extensions', 'Connect trusted MCP servers and review each tool call.');
    await page.click('[data-close="extensions-dialog"]');
    await page.click('#close-toolkit');
    await openWorkspaceSection('#memory-button');
    await page.fill('#memory-input', 'Use plain JavaScript in this project.');
    await page.locator('#memory-form button').click();
    await page.locator('.memory-entry').waitFor();
    await capture('memory', 'Save a project preference when you want it remembered.');
    await page.click('#close-memory');
    await openWorkspaceSection('#terminal-button');
    await page.locator('#terminal .xterm').waitFor();
    await page.evaluate(() => window.wixal['terminal-write']("clear; printf 'Hello from the Wixal terminal\\n'; pwd\r"));
    await page.waitForFunction(() => document.querySelector('#terminal').textContent.includes('Hello from the Wixal terminal'));
    await capture('terminal', 'Use a real zsh terminal, right beside your conversation.', 3000);
    const media = path.join(root, 'docs/media'); await fs.mkdir(media, { recursive: true });
    await sharp(Buffer.concat(frames), { raw: { width: 990, height: 772 * frames.length, channels: 3, pageHeight: 772 } }).gif({ delay: delays, loop: 1, colours: 128, dither: .4 }).toFile(path.join(media, 'workspace-tour.gif'));
    await sharp(Buffer.concat(frames.slice(0, 4)), { raw: { width: 990, height: 772 * 4, channels: 3, pageHeight: 772 } }).gif({ delay: delays.slice(0, 4), loop: 1, colours: 128, dither: .4 }).toFile(path.join(media, 'choose-model.gif'));
    console.log('Saved current app screenshots and model/workspace tours.');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
