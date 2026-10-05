const { app, BrowserWindow, ipcMain, dialog, Menu, shell, nativeImage, clipboard, safeStorage } = require('electron');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');
const { randomUUID } = require('node:crypto');
const { Store } = require('./store.cjs');
const { getModels, runAgent } = require('./agent.cjs');
const { modelDetails, pullModel } = require('./models.cjs');
const { Extensions, serverConfig, toolPrefix } = require('./extensions.cjs');
const { importImage } = require('./images.cjs');
const { definitions, executeTool } = require('./tools.cjs');
const { Credentials } = require('./credentials.cjs');
const { ChatGPTAuth } = require('./chatgpt-auth.cjs');
const { cloudModels } = require('./cloud.cjs');
const { providers, providerInfo, customSettings } = require('./providers.cjs');
let catalogRevision = 0;
function invalidateCatalog() { catalogRevision++; modelCatalog = []; catalogKey = ''; }
const { Companion } = require('./companion.cjs');
app.setName('Wixal');
if (process.env.WIXAL_DATA_DIR) app.setPath('userData', process.env.WIXAL_DATA_DIR);
let window, store, running, terminal, credentials, auth, companion, activeTask, extensions, downloading;
let modelCatalog = [], catalogKey = '';
const approvals = new Map();
const images = new Map();
const index = path.join(__dirname, '../ui/index.html');
const emit = data => { if (window && !window.isDestroyed()) window.webContents.send('wixal:event', data); };
function idle() { if (running) throw new Error('Stop the current response before changing projects or conversations.'); }
function snapshot() { return { ...store.snapshot(), externalConnections: extensions.snapshot(), modelDownload: downloading?.progress || null }; }
function stop() {
  running?.abort();
  for (const resolve of approvals.values()) resolve(false);
  approvals.clear();
}
function approve(request) {
  if (running?.signal.aborted) return Promise.resolve(false);
  const id = randomUUID();
  return new Promise(resolve => {
    if (activeTask) { activeTask.status = 'waiting_review'; store.save(); emit({ type: 'tasks' }); }
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
async function providerToken(provider, account = credentials.account()) {
  if (provider === 'chatgpt') return auth.accessToken(account);
  const key = credentials.key(provider);
  if (!key && provider !== 'custom') throw new Error(`Add a ${providerInfo(provider).label} API key in Connections first.`);
  return key;
}
async function selectedDetails() {
  if (!store.data.model) throw new Error('Choose a model first.');
  if (store.data.provider === 'ollama') return modelDetails(store.data.model);
  const key = `${store.data.provider}:${store.data.provider === 'chatgpt' ? credentials.data.activeAccount || '' : ''}`;
  const model = catalogKey === key && modelCatalog.find(m => m.name === store.data.model);
  if (!model) throw new Error('Refresh the model list for this account and choose a model.');
  return model;
}
function connectionState() {
  const appRoot = app.getAppPath().replace(/app\.asar$/, 'app.asar.unpacked');
  const quote = value => `'${value.replace(/'/g, "'\\''")}'`;
  return { ...credentials.snapshot(), providers: Object.entries(providers).map(([id, info]) => ({ id, label: info.label, apiKey: !['ollama', 'chatgpt'].includes(id), keysURL: info.keysURL })), customProvider: store.data.customProvider, pending: !!auth.pending, companion: { ...store.data.companion, ...companion.snapshot(), helperPath: path.join(appRoot, 'app/companion-stdio.cjs'),
    command: companion.server ? `node ${quote(path.join(appRoot, 'app/companion-stdio.cjs'))} ${quote(companion.file)}` : '' },
    cloudProjects: store.data.cloudProjects, cloudPersonal: store.data.cloudPersonal };
}
function launchRun(prompt, attached, details, task = null) {
  const provider = store.data.provider, account = credentials.account(), apiKey = credentials.key(provider), custom = { ...store.data.customProvider };
  if (provider !== 'ollama' && !(store.project() ? store.data.cloudProjects.includes(store.data.activeProject) : store.data.cloudPersonal)) throw new Error('Enable cloud context for this workspace in Connections first.');
  running = new AbortController(); const controller = running; activeTask = task;
  emit({ type: 'run-started' });
  (async () => {
    try {
      await runAgent({ store, prompt, images: attached, details, signal: controller.signal, emit, approve,
        custom, extensions, cloudToken: () => provider === 'chatgpt' ? auth.accessToken(account) : Promise.resolve(apiKey) });
      if (task) {
        task.status = 'completed';
        const messages = store.session().messages;
        task.result = messages.findLast(m => m.role === 'assistant')?.content || '';

      }
    } catch (error) {
      const message = controller.signal.aborted ? 'Response stopped.' : error.message;
      if (task) { task.status = controller.signal.aborted ? 'cancelled' : 'failed'; task.error = message; }
      emit({ type: 'error', message });
    } finally {
      if (task) {
        task.outcomes = (store.data.sessions.find(s => s.id === task.sessionId)?.messages || []).filter(m => m.role === 'tool').map(m => {
          if (m.tool_name === 'run_command') { try { const result = JSON.parse(m.content); return { tool: m.tool_name, exitCode: result.exitCode, stopped: result.stopped }; } catch {} }
          return { tool: m.tool_name, status: m.content.startsWith('Error:') ? 'failed' : m.content.startsWith('User declined') ? 'declined' : 'done' };
        });
        task.updated = Date.now(); store.save();
      }
      running = null; activeTask = null; emit({ type: 'done' }); emit({ type: 'tasks' });
    }
  })();
}
function setupIPC() {
  register('state', () => snapshot());
  register('model-pull', name => {
    idle();
    if (downloading) throw new Error('A model download is already running.');
    if (store.data.provider !== 'ollama') throw new Error('Switch to Ollama to download local models.');
    const controller = new AbortController();
    downloading = { controller, progress: { name, status: 'Starting download', completed: 0, total: 0 } };
    pullModel(name, controller.signal, progress => { downloading.progress = progress; emit({ type: 'model-download', ...progress }); })
      .then(() => { invalidateCatalog(); emit({ type: 'model-download-done', name }); })
      .catch(error => emit({ type: 'error', message: controller.signal.aborted ? 'Model download cancelled. Retry to resume.' : error.message }))
      .finally(() => { downloading = null; emit({ type: 'model-download-idle' }); });
    return snapshot();
  });
  register('model-pull-cancel', () => { downloading?.controller.abort(); return true; });
  register('mcp-save', value => {
    idle(); const config = serverConfig(value);
    if (store.data.mcpServers.length >= 12) throw new Error('Connect up to 12 MCP servers.');
    store.data.mcpServers.push({ id: randomUUID(), ...config }); store.save(); return snapshot();
  });
  register('mcp-connect', async id => {
    idle(); const config = store.data.mcpServers.find(s => s.id === id);
    if (!config) throw new Error('Unknown MCP server.');
    // Clicking Connect is the explicit consent to launch this configured executable.
    await extensions.connect(config, store.project()?.root || os.homedir()); return snapshot();
  });
  register('mcp-disconnect', async id => { idle(); await extensions.disconnect(id); return snapshot(); });
  register('mcp-delete', async id => {
    idle(); if (!store.data.mcpServers.some(s => s.id === id)) throw new Error('Unknown MCP server.');
    await extensions.disconnect(id);
    store.data.enabledTools = store.data.enabledTools.filter(name => !name.startsWith(toolPrefix(id)));
    store.data.mcpServers = store.data.mcpServers.filter(s => s.id !== id); store.save(); return snapshot();
  });
  register('summary-clear', () => { idle(); const session = store.session(); if (session) delete session.summary; store.save(); return snapshot(); });
  register('models', async () => {
    const provider = store.data.provider;
    const account = credentials.account(), revision = catalogRevision, custom = { ...store.data.customProvider };
    const key = `${provider}:${provider === 'chatgpt' ? account?.client_id || '' : ''}`;
    const models = provider === 'ollama' ? await getModels() : await cloudModels(provider, await providerToken(provider, account), custom);
    if (revision !== catalogRevision || provider !== store.data.provider || (provider === 'chatgpt' && account !== credentials.account())) throw new Error('Provider changed. Refresh the model list.');
    modelCatalog = models; catalogKey = key;
    if (!models.some(m => m.name === store.data.model)) {
      if (!running) { store.data.model = models.find(m => m.capabilities?.includes('tools'))?.name || models[0]?.name || ''; store.data.providerModels[provider] = store.data.model; store.save(); }
    }
    return { models, selected: store.data.model, provider };
  });
  register('layout', collapsed => {
    if (typeof collapsed !== 'boolean') throw new Error('Invalid sidebar preference.');
    store.data.ui.sidebarCollapsed = collapsed;
    store.save(); return snapshot();
  });
  register('settings', settings => {
    idle();
    if (!settings || typeof settings !== 'object') throw new Error('Invalid settings.');
    if (settings.provider !== undefined) {
      if (!Object.hasOwn(providers, settings.provider)) throw new Error('Unknown model provider.');
      store.data.providerModels[store.data.provider] = store.data.model;
      store.data.provider = settings.provider; store.data.model = store.data.providerModels[settings.provider] || '';
      invalidateCatalog();
    }
    if (typeof settings.model === 'string' && settings.model.length < 200) { store.data.model = settings.model; store.data.providerModels[store.data.provider] = settings.model; }
    if (['agent', 'chat'].includes(settings.mode)) store.data.mode = settings.mode;
    if (Array.isArray(settings.enabledTools)) {
      const names = [...definitions, ...extensions.definitions()].map(tool => tool.function.name);
      names.push(...store.data.enabledTools.filter(name => name.startsWith('mcp_')));
      if (settings.enabledTools.some(name => !names.includes(name))) throw new Error('Unknown tool.');
      store.data.enabledTools = [...new Set(settings.enabledTools)];
    }
    if ([8192, 16384, 32768, 65536, 131072].includes(settings.contextSize)) store.data.contextSize = settings.contextSize;
    if (typeof settings.autoSummary === 'boolean') store.data.autoSummary = settings.autoSummary;
    store.save(); return snapshot();
  });
  register('project-open', async () => {
    idle();
    const result = await dialog.showOpenDialog(window, { title: 'Open a project in Wixal', properties: ['openDirectory'] });
    if (!result.canceled) { idle(); store.addProject(result.filePaths[0]); destroyTerminal(); images.clear(); }
    return { ...snapshot(), opened: !result.canceled };
  });
  register('project-select', id => { idle(); store.selectProject(id); destroyTerminal(); images.clear(); return snapshot(); });
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
      prepared.push({ id: randomUUID(), ...await importImage(file) });
    }
    for (const image of prepared) images.set(image.id, image);
    return prepared;
  });
  register('image-remove', id => { idle(); images.delete(id); });
  register('session-new', () => { idle(); store.newSession(); images.clear(); return snapshot(); });
  register('session-select', id => { idle(); store.selectSession(id); images.clear(); return snapshot(); });
  for (const action of ['archive', 'restore', 'delete']) register(`session-${action}`, id => {
    idle(); const active = store.data.activeSession; store[`${action}Session`](id);
    if (store.data.activeSession !== active) images.clear();
    return snapshot();
  });
  register('session-rename', (title, id = store.data.activeSession) => {
    idle();
    if (typeof title !== 'string' || !title.trim() || title.length > 80) throw new Error('Use a conversation name under 80 characters.');
    store.scopedSession(id).title = title.trim(); store.save(); return snapshot();
  });
  register('memory-add', content => { idle(); store.remember(content); return snapshot(); });
  register('memory-delete', id => { idle(); store.data.memories = store.data.memories.filter(m => m.id !== id || m.projectId !== store.data.activeProject); store.save(); return snapshot(); });
  register('chat', async (prompt, imageIds = []) => {
    idle();
    if (store.session()?.archivedAt) throw new Error('Restore this conversation before sending a message.');
    if (typeof prompt !== 'string' || !prompt.trim() || prompt.length > 16000) throw new Error('Enter a message under 16,000 characters.');
    if (!Array.isArray(imageIds) || imageIds.length > 3 || imageIds.some(id => !images.has(id)) || new Set(imageIds).size !== imageIds.length) throw new Error('These attachments are no longer available. Attach them again.');
    const attached = imageIds.map(id => images.get(id));
    if (!store.data.model) throw new Error('Choose a model first.');
    const model = store.data.model, projectId = store.data.activeProject, sessionId = store.data.activeSession;
    const provider = store.data.provider, revision = catalogRevision;
    const details = await selectedDetails();
    idle();
    if (revision !== catalogRevision || provider !== store.data.provider || model !== store.data.model || projectId !== store.data.activeProject || sessionId !== store.data.activeSession) throw new Error('Workspace changed. Send your message again.');
    if (store.data.mode === 'agent' && store.project() && !details.capabilities.includes('tools')) throw new Error('Choose a model with tools or switch to Chat.');
    if (attached.length && !details.capabilities.includes('vision')) throw new Error('Choose a model with image support.');
    launchRun(prompt.trim(), attached, details);
    imageIds.forEach(id => images.delete(id));
    return true;
  });
  register('stop', () => { stop(); return true; });
  register('approval', ({ id, allowed }) => { approvals.get(id)?.(allowed === true); approvals.delete(id); if (activeTask) { activeTask.status = 'running'; store.save(); emit({ type: 'tasks' }); } });
  register('connections', () => connectionState());
  register('api-key-save', key => { idle(); if (typeof key !== 'string') throw new Error('Invalid API key.'); credentials.setKey(key.trim()); if (store.data.provider === 'openai') invalidateCatalog(); return connectionState(); });
  register('api-key-remove', () => { idle(); credentials.setKey(''); if (store.data.provider === 'openai') invalidateCatalog(); return connectionState(); });
  register('provider-key-save', value => { idle(); if (!value || typeof value.provider !== 'string' || typeof value.key !== 'string') throw new Error('Invalid API key.'); credentials.setKey(value.key.trim(), value.provider); if (store.data.provider === value.provider) invalidateCatalog(); return connectionState(); });
  register('provider-key-remove', provider => { idle(); if (typeof provider !== 'string') throw new Error('Invalid provider.'); credentials.setKey('', provider); if (store.data.provider === provider) invalidateCatalog(); return connectionState(); });
  register('custom-provider-save', value => {
    idle(); const settings = customSettings(value);
    if (typeof value.key !== 'string') throw new Error('Invalid API key.');
    // A new endpoint gets a new explicitly supplied key; never reuse the old endpoint's credential.
    credentials.setKey(value.key.trim(), 'custom'); store.data.customProvider = settings;
    store.data.providerModels.custom = settings.model;
    if (store.data.provider === 'custom') store.data.model = settings.model;
    store.save(); if (store.data.provider === 'custom') invalidateCatalog(); return connectionState();
  });
  register('chatgpt-sign-in', id => { idle(); return auth.start(id); });
  register('chatgpt-cancel', () => { auth.cancel(); return connectionState(); });
  register('chatgpt-plan-notice', () => { const account = credentials.account(); if (account) { account.planNoticeSeen = true; credentials.save(); } });
  register('chatgpt-select', id => { idle(); auth.select(id); invalidateCatalog(); return connectionState(); });
  register('chatgpt-sign-out', async id => { idle(); const result = await auth.signOut(id); invalidateCatalog(); return { ...connectionState(), message: result.message }; });
  register('sharing', async settings => {
    idle(); if (!settings || typeof settings !== 'object') throw new Error('Invalid sharing settings.');
    const ids = store.data.projects.map(p => p.id);
    for (const key of ['cloudProjects', 'sharedProjects']) if (settings[key] !== undefined && (!Array.isArray(settings[key]) || settings[key].some(id => !ids.includes(id)))) throw new Error('Unknown shared project.');
    if (settings.cloudProjects) store.data.cloudProjects = [...new Set(settings.cloudProjects)];
    if (typeof settings.cloudPersonal === 'boolean') store.data.cloudPersonal = settings.cloudPersonal;
    if (settings.sharedProjects) store.data.companion.sharedProjects = [...new Set(settings.sharedProjects)];
    if (typeof settings.shareMemory === 'boolean') store.data.companion.shareMemory = settings.shareMemory;
    if (typeof settings.enabled === 'boolean') { if (settings.enabled) await companion.start(); else await companion.stop(); store.data.companion.enabled = settings.enabled; }
    store.save(); return connectionState();
  });
  register('connection-link', name => {
    const urls = { usage: 'https://chatgpt.com/settings/usage', keys: 'https://platform.openai.com/api-keys', tunnel: 'https://platform.openai.com/settings/organization/tunnels', guide: 'https://developers.openai.com/api/docs/guides/secure-mcp-tunnels', plugins: 'https://chatgpt.com/plugins' };
    if (typeof name === 'string' && name.startsWith('provider:')) { const info = providerInfo(name.slice(9)); if (!info.keysURL) throw new Error('This provider has no key page.'); return shell.openExternal(info.keysURL); }
    if (!urls[name]) throw new Error('Unknown connection link.'); return shell.openExternal(urls[name]);
  });
  register('task-start', async id => {
    idle(); const task = store.data.tasks.find(t => t.id === id); if (!task || !['queued', 'failed', 'interrupted', 'cancelled'].includes(task.status)) throw new Error('This task cannot be started.');
    const model = store.data.model, provider = store.data.provider, revision = catalogRevision;
    const details = await selectedDetails(); idle();
    if (revision !== catalogRevision || model !== store.data.model || provider !== store.data.provider) throw new Error('Provider changed. Start the task again.');
    if (!details.capabilities.includes('tools')) throw new Error('Choose a model with tools to start a project task.');
    if (provider !== 'ollama' && !store.data.cloudProjects.includes(task.projectId)) throw new Error('Enable cloud context for this task’s project in Connections first.');
    store.selectProject(task.projectId); destroyTerminal(); images.clear(); store.newSession();
    task.sessionId = store.data.activeSession; task.status = 'running'; task.error = null; task.result = null; task.outcomes = []; task.updated = Date.now();
    store.data.mode = 'agent'; store.save(); launchRun(task.prompt, [], details, task); return snapshot();
  });
  register('task-cancel', id => { idle(); const task = store.data.tasks.find(t => t.id === id); if (!task || task.status !== 'queued') throw new Error('Only queued tasks can be dismissed.'); task.status = 'cancelled'; task.updated = Date.now(); store.save(); return snapshot(); });
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
  extensions = new Extensions(() => emit({ type: 'extensions-changed' }));
  credentials = new Credentials(app.getPath('userData'), safeStorage);
  auth = new ChatGPTAuth({ credentials, openBrowser: url => shell.openExternal(url), onChange: event => { invalidateCatalog(); emit(event); } });
  companion = new Companion(store, app.getPath('userData'), () => emit({ type: 'tasks' }));
  store.save();
  if (store.data.companion.enabled) companion.start().catch(error => { store.data.companion.enabled = false; store.save(); emit({ type: 'error', message: error.message }); });
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
app.on('before-quit', () => { stop(); downloading?.controller.abort(); extensions?.close().catch(() => {}); destroyTerminal(); auth?.cancel(); companion?.stop().catch(() => {}); });
