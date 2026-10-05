// Capture actual Wixal interactions in a disposable project, with no model responses.
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
  delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow();
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1320, 960));
    await page.locator('#connection-label').filter({ hasText: 'Ollama connected' }).waitFor();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('#welcome img').evaluateAll(images => Promise.all(images.map(i => i.decode())));
    const shots = path.join(root, 'docs/screenshots'), media = path.join(root, 'docs/media');
    await fs.mkdir(shots, { recursive: true }); await fs.mkdir(media, { recursive: true });
    const tour = [], tourDelays = [];
    async function capture(caption, name) {
      await page.locator('#toast').waitFor({ state: 'hidden' });
      await page.mouse.move(1250, 25);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const screenshot = await page.screenshot(name ? { path: path.join(shots, `${name}.png`) } : {});
      const image = await sharp(screenshot).resize(990, 720).toBuffer();
      const label = Buffer.from(`<svg width="990" height="48"><rect width="990" height="48" fill="#17191f"/><text x="22" y="31" font-family="Helvetica,Arial,sans-serif" font-size="16" fill="#f4f0e9">${caption}</text><text x="968" y="31" text-anchor="end" font-family="Menlo,monospace" font-size="11" fill="#ecabc5">WIXAL</text></svg>`);
      return sharp({ create: { width: 990, height: 768, channels: 3, background: '#17191f' } }).composite([{ input: label, top: 0, left: 0 }, { input: image, top: 48, left: 0 }]).removeAlpha().raw().toBuffer();
    }
    async function saveGif(name, frames, delays) {
      await sharp(Buffer.concat(frames), { raw: { width: 990, height: 768 * frames.length, channels: 3, pageHeight: 768 } }).gif({ delay: delays, loop: 0, colours: 128, dither: .25 }).toFile(path.join(media, name));
    }
    function addTour(frame, delay = 1800) { tour.push(frame); tourDelays.push(delay); }
    const home = await capture('Your project, model, and tools in one workspace.', 'workspace'); addTour(home, 2400);
    const modelFrames = [home], modelDelays = [900];
    await page.click('#model-button'); await page.locator('.model-row').first().waitFor();
    let frame = await capture('Choose a model from your local Ollama library.', 'models'); modelFrames.push(frame); modelDelays.push(1500); addTour(frame);
    const qwen = await page.locator('.model-row').filter({ hasText: 'Qwen' }).first().getAttribute('data-model');
    if (!qwen) throw new Error('Install a Qwen model to record the model-search demo.');
    for (const query of ['q', 'qw', 'qwen']) {
      await page.fill('#model-search', query); frame = await capture('Search your installed models.'); modelFrames.push(frame); modelDelays.push(query === 'qwen' ? 1500 : 250);
    }
    await page.locator('.model-row').filter({ hasText: 'Qwen' }).click();
    await page.locator('#models-dialog').waitFor({ state: 'hidden' });
    frame = await capture('The model is selected. You can get started.'); modelFrames.push(frame); modelDelays.push(1300);
    await saveGif('choose-model.gif', modelFrames, modelDelays);
    const fileFrames = [frame], fileDelays = [900];
    await page.click('#files-button'); await page.locator('[data-file="README.md"]').click();
    await page.locator('#file-content').filter({ hasText: 'A small project' }).waitFor();
    frame = await capture('Read the project before asking for a change.', 'files'); fileFrames.push(frame); fileDelays.push(1700); addTour(frame);
    await page.locator('[data-file="hello.js"]').click(); await page.locator('#file-content').filter({ hasText: 'console.log' }).waitFor();
    frame = await capture('Preview a file and add it to your next message.'); fileFrames.push(frame); fileDelays.push(1700);
    await page.click('#use-file'); await page.locator('#files-dialog').waitFor({ state: 'hidden' });
    frame = await capture('The file is in your prompt. Send it when you are ready.'); fileFrames.push(frame); fileDelays.push(1800);
    await saveGif('project-files.gif', fileFrames, fileDelays); await page.fill('#prompt', '');
    await page.click('#toolkit-button'); frame = await capture('Choose which tools the model can use.', 'toolkit'); addTour(frame); await page.click('#close-toolkit');
    await page.click('#memory-button'); await page.fill('#memory-input', 'Use plain JavaScript in this project.'); await page.locator('#memory-form button').click(); await page.locator('.memory-entry').waitFor();
    frame = await capture('Save a project preference when you want it remembered.', 'memory'); addTour(frame); await page.click('#close-memory');
    const terminalFrames = [home], terminalDelays = [900];
    await page.click('#terminal-button'); await page.locator('#terminal .xterm').waitFor();
    frame = await capture('A real zsh terminal, inside the workspace.'); terminalFrames.push(frame); terminalDelays.push(1200);
    await page.evaluate(() => new Promise((resolve, reject) => {
      let output = '';
      const timer = setTimeout(() => { remove(); reject(new Error('Terminal demo did not finish')); }, 10000);
      const remove = window.wixal.onEvent(event => {
        if (event.type === 'terminal') { output += event.text; if (output.includes('Hello from Wixal')) { clearTimeout(timer); remove(); resolve(); } }
      });
      window.wixal['terminal-write']("export PS1='wixal % '; clear; node hello.js\r").catch(error => { clearTimeout(timer); remove(); reject(error); });
    }));
    frame = await capture('Run your project without leaving the conversation.', 'terminal'); terminalFrames.push(frame); terminalDelays.push(2700); addTour(frame, 2600);
    await page.click('#close-terminal'); frame = await capture('Back to your workspace.'); terminalFrames.push(frame); terminalDelays.push(900);
    await saveGif('terminal.gif', terminalFrames, terminalDelays);
    await saveGif('workspace-tour.gif', tour, tourDelays);
    console.log('Captured six screenshots and four GIFs from the actual Wixal app.');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
