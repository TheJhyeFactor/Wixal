const { app, BrowserWindow, ipcMain, dialog, Menu, shell, nativeImage, clipboard } = require('electron');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs/promises');
const { Store } = require('./store.cjs');
const { getModels, runAgent } = require('./agent.cjs');
const { modelDetails } = require('./models.cjs');
const { definitions, executeTool } = require('./tools.cjs');
app.setName('Wixal');
if (process.env.WIXAL_DATA_DIR) app.setPath('userData', process.env.WIXAL_DATA_DIR);
let window, store, running, terminal;
const approvals = new Map();
const images = new Map();
const index = path.join(__dirname, '../ui/index.html');
const emit = data => { if (window && !window.isDestroyed()) window.webContents.send('wixal:event', data); };
function idle() { if (running) throw new Error('Stop the current response before changing projects or conversations.'); }
function stop() {
  running?.abort();
  for (const resolve of approvals.values()) resolve(false);
  approvals.clear();
}
function approve(request) {
  if (running?.signal.aborted) return Promise.resolve(false);
  const id = randomUUID();
  return new Promise(resolve => {
    approvals.set(id, resolve);
    emit({ type: 'approval', id, ...request });
  });
}
function destroyTerminal() { if (terminal) { terminal.kill(); terminal = null; } }
function register(name, handler) {
  ipcMain.handle(`wixal:${name}`, async (event, ...args) => {
    if (event.sender !== window?.webContents || event.senderFrame?.url !== pathToFileURL(index).href) throw new Error('Untrusted request');
    return handler(...args);
  });
}
function setupIPC() {
  register('state', () => store.snapshot());
  register('models', async () => {
    const models = await getModels();
    if (!models.some(m => m.name === store.data.model)) {
      if (!running) { store.data.model = models.find(m => m.capabilities?.includes('tools'))?.name || models[0]?.name || ''; store.save(); }
    }
    return { models, selected: store.data.model };
  });
  register('settings', settings => {
    idle();
    if (!settings || typeof settings !== 'object') throw new Error('Invalid settings.');
    if (typeof settings.model === 'string' && settings.model.length < 200) store.data.model = settings.model;
    if (['agent', 'chat'].includes(settings.mode)) store.data.mode = settings.mode;
    if (Array.isArray(settings.enabledTools)) {
      const names = definitions.map(tool => tool.function.name);
      if (settings.enabledTools.some(name => !names.includes(name))) throw new Error('Unknown tool.');
      store.data.enabledTools = [...new Set(settings.enabledTools)];
    }
    if ([8192, 16384, 32768].includes(settings.contextSize)) store.data.contextSize = settings.contextSize;
    store.save(); return store.snapshot();
  });
  register('project-open', async () => {
    idle();
    const result = await dialog.showOpenDialog(window, { title: 'Open a project in Wixal', properties: ['openDirectory'] });
    if (!result.canceled) { idle(); store.addProject(result.filePaths[0]); destroyTerminal(); images.clear(); }
    return { ...store.snapshot(), opened: !result.canceled };
  });
  register('project-select', id => { idle(); store.selectProject(id); destroyTerminal(); images.clear(); return store.snapshot(); });
  register('project-files', () => executeTool('list_files', {}, { root: store.project()?.root }));
  register('project-read', relative => executeTool('read_file', { path: relative }, { root: store.project()?.root }));
  register('images-open', async () => {
    idle();
    if (images.size >= 3) throw new Error('Attach up to three images per message.');
    const result = await dialog.showOpenDialog(window, { title: 'Attach an image', properties: ['openFile', 'multiSelections'], filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }] });
    if (result.canceled) return [];
    idle();
    if (result.filePaths.length + images.size > 3) throw new Error('Attach up to three images per message.');
    const prepared = [];
    for (const file of result.filePaths) {
      if ((await fs.stat(file)).size > 12 * 1024 * 1024) throw new Error('Images must be smaller than 12 MB.');
      let image = nativeImage.createFromPath(file);
      if (image.isEmpty()) throw new Error(`Couldn't open ${path.basename(file)}. Try a PNG or JPEG.`);
      const size = image.getSize();
      if (size.width > 1600 || size.height > 1600) image = image.resize(size.width > size.height ? { width: 1600 } : { height: 1600 });
      const base64 = image.toPNG().toString('base64');
      if (base64.length > 6 * 1024 * 1024) throw new Error('This image is too large after resizing. Try a smaller image.');
      prepared.push({ id: randomUUID(), name: path.basename(file), base64 });
    }
    for (const image of prepared) images.set(image.id, image);
    return prepared;
  });
  register('image-remove', id => { idle(); images.delete(id); });
  register('session-new', () => { idle(); store.newSession(); images.clear(); return store.snapshot(); });
  register('session-select', id => { idle(); store.selectSession(id); images.clear(); return store.snapshot(); });
  register('session-rename', title => {
    idle();
    if (typeof title !== 'string' || !title.trim() || title.length > 80) throw new Error('Use a conversation name under 80 characters.');
    if (!store.session()) throw new Error('Start a conversation first.');
    store.session().title = title.trim(); store.save(); return store.snapshot();
  });
  register('memory-add', content => { idle(); store.remember(content); return store.snapshot(); });
  register('memory-delete', id => { idle(); store.data.memories = store.data.memories.filter(m => m.id !== id || m.projectId !== store.data.activeProject); store.save(); return store.snapshot(); });
  register('chat', async (prompt, imageIds = []) => {
    idle();
    if (typeof prompt !== 'string' || !prompt.trim() || prompt.length > 16000) throw new Error('Enter a message under 16,000 characters.');
    if (!Array.isArray(imageIds) || imageIds.length > 3 || imageIds.some(id => !images.has(id)) || new Set(imageIds).size !== imageIds.length) throw new Error('These attachments are no longer available. Attach them again.');
    const attached = imageIds.map(id => images.get(id));
    if (!store.data.model) throw new Error('Choose a local model first.');
    const model = store.data.model, projectId = store.data.activeProject, sessionId = store.data.activeSession;
    const details = await modelDetails(model);
    idle();
    if (model !== store.data.model || projectId !== store.data.activeProject || sessionId !== store.data.activeSession) throw new Error('Workspace changed. Send your message again.');
    if (store.data.mode === 'agent' && store.project() && !details.capabilities.includes('tools')) throw new Error('Choose a model with tools or switch to Chat.');
    if (attached.length && !details.capabilities.includes('vision')) throw new Error('Choose a model with image support.');
    running = new AbortController();
    const controller = running;
    (async () => {
      try { await runAgent({ store, prompt: prompt.trim(), images: attached, details, signal: controller.signal, emit, approve }); }
      catch (error) { emit({ type: 'error', message: controller.signal.aborted ? 'Response stopped.' : error.message }); }
      finally { running = null; emit({ type: 'done' }); }
    })();
    imageIds.forEach(id => images.delete(id));
    return true;
  });
  register('stop', () => { stop(); return true; });
  register('approval', ({ id, allowed }) => { approvals.get(id)?.(allowed === true); approvals.delete(id); });
  register('terminal-open', () => {
    if (!store.project()) throw new Error('Open a project folder first.');
    if (terminal) return { root: store.project().root };
    const pty = require('node-pty');
    terminal = pty.spawn('/bin/zsh', ['-l'], { name: 'xterm-256color', cols: 100, rows: 20,
      cwd: store.project().root, env: { ...process.env, TERM: 'xterm-256color', COLORTERM: 'truecolor',
        PATH: `${os.homedir()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${process.env.PATH}` },
    });
    const instance = terminal;
    instance.onData(text => emit({ type: 'terminal', text }));
    instance.onExit(({ exitCode }) => { if (terminal === instance) terminal = null; emit({ type: 'terminal-exit', exitCode }); });
    return { root: store.project().root };
  });
  register('terminal-write', text => { if (typeof text === 'string' && text.length < 65536) terminal?.write(text); });
  register('terminal-resize', ({ cols, rows }) => { if (Number.isInteger(cols) && Number.isInteger(rows)) terminal?.resize(Math.max(10, Math.min(cols, 500)), Math.max(2, Math.min(rows, 200))); });
  register('terminal-close', () => destroyTerminal());
  register('reveal-project', () => { if (store.project()) shell.showItemInFolder(store.project().root); });
  register('copy-text', text => { if (typeof text !== 'string' || text.length > 1000000) throw new Error('Nothing to copy.'); clipboard.writeText(text); });
}
function createWindow() {
  window = new BrowserWindow({ width: 1320, height: 880, minWidth: 920, minHeight: 640,
    title: 'Wixal', backgroundColor: '#151619', titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 20, y: 17 },
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
    show: false,
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  window.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  window.loadFile(index);
  window.once('ready-to-show', () => window.show());
  window.on('closed', () => { stop(); destroyTerminal(); window = null; });
}
app.whenReady().then(() => {
  store = new Store(app.getPath('userData'));
  if (process.env.WIXAL_TEST_PROJECT) store.addProject(process.env.WIXAL_TEST_PROJECT);
  if (process.platform === 'darwin') app.dock.setIcon(nativeImage.createFromPath(path.join(__dirname, '../assets/icon.png')));
  setupIPC();
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Wixal', submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' }, { type: 'separator' }, { role: 'quit' }] },
    { label: 'File', submenu: [{ label: 'Open Project…', accelerator: 'CmdOrCtrl+O', click: () => emit({ type: 'shortcut', action: 'open' }) }, { label: 'New Conversation', accelerator: 'CmdOrCtrl+N', click: () => emit({ type: 'shortcut', action: 'new' }) }, { role: 'close' }] },
    { role: 'editMenu' }, { label: 'View', submenu: [{ label: 'Command Palette', accelerator: 'CmdOrCtrl+K', click: () => emit({ type: 'shortcut', action: 'palette' }) }, { label: 'Toggle Terminal', accelerator: 'CmdOrCtrl+J', click: () => emit({ type: 'shortcut', action: 'terminal' }) }, { label: 'Project Memory', accelerator: 'CmdOrCtrl+Shift+M', click: () => emit({ type: 'shortcut', action: 'memory' }) }, { role: 'togglefullscreen' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }] }, { role: 'windowMenu' },
  ]));
  createWindow();
  app.on('activate', () => { if (!window) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { stop(); destroyTerminal(); });
