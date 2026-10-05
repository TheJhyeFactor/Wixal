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
  delete env.ELECTRON_RUN_AS_NODE;
  let app;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow();
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1320, 960));
    await page.locator('#connection-label').filter({ hasText: 'Ollama connected' }).waitFor();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('#welcome img').evaluateAll(images => Promise.all(images.map(i => i.decode())));
    const shots = path.join(root, 'docs/screenshots');
    await fs.mkdir(shots, { recursive: true });
    const frames = [], delays = [];
    async function capture(name, caption, delay = 2200) {
      await page.locator('#toast').waitFor({ state: 'hidden' });
      await page.mouse.move(1250, 25);
      const screenshot = await page.screenshot({ path: path.join(shots, `${name}.png`) });
      const image = await sharp(screenshot).resize(990, 720).toBuffer();
      const label = Buffer.from(`<svg width="990" height="52"><rect width="990" height="52" fill="#191a20"/><text x="24" y="32" font-family="Helvetica,Arial,sans-serif" font-size="16" fill="#f1eee9">${caption}</text><text x="966" y="32" text-anchor="end" font-family="Menlo,monospace" font-size="11" fill="#e9a5bd">WIXAL</text></svg>`);
      const raw = await sharp({ create: { width: 990, height: 772, channels: 3, background: '#191a20' } }).composite([{ input: label, top: 0, left: 0 }, { input: image, top: 52, left: 0 }]).removeAlpha().raw().toBuffer();
      frames.push(raw); delays.push(delay);
    }
    await capture('workspace', 'Open a project and make yourself at home.', 3000);
    await page.click('#model-button');
    await page.locator('.model-row').first().waitFor();
    await capture('models', 'Choose a model from your local Ollama library.');
    await page.click('[data-close="models-dialog"]');
    await page.click('#files-button');
    await page.locator('[data-file="README.md"]').click();
    await page.locator('#file-content').filter({ hasText: 'A small project' }).waitFor();
    await capture('files', 'Browse the project and bring a file into the conversation.');
    await page.click('[data-close="files-dialog"]');
    await page.click('#toolkit-button');
    await capture('toolkit', 'Choose which tools the model can use.');
    await page.click('#close-toolkit');
    await page.click('#memory-button');
    await page.fill('#memory-input', 'Use plain JavaScript in this project.');
    await page.locator('#memory-form button').click();
    await page.locator('.memory-entry').waitFor();
    await capture('memory', 'Save a project preference when you want it remembered.');
    await page.click('#close-memory');
    await page.click('#terminal-button');
    await page.locator('#terminal .xterm').waitFor();
    await page.evaluate(() => window.wixal['terminal-write']("clear; printf 'Hello from the Wixal terminal\\n'; pwd\r"));
    await page.waitForFunction(() => document.querySelector('#terminal').textContent.includes('Hello from the Wixal terminal'));
    await capture('terminal', 'Use a real zsh terminal, right beside your conversation.', 3000);
    const media = path.join(root, 'docs/media'); await fs.mkdir(media, { recursive: true });
    await sharp(Buffer.concat(frames), { raw: { width: 990, height: 772 * frames.length, channels: 3, pageHeight: 772 } }).gif({ delay: delays, loop: 1, colours: 128, dither: .4 }).toFile(path.join(media, 'workspace-tour.gif'));
    console.log('Saved six real app screenshots and docs/media/workspace-tour.gif.');
  } finally { if (app) await app.close(); await fs.rm(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
