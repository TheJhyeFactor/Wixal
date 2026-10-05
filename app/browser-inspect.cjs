const { requestURL } = require('./network.cjs');
async function inspectBrowser(args, { approve, signal }) {
  const url = requestURL(args.url);
  if (!await approve({ name: 'browser_inspect', url })) return 'User declined browser inspection.';
  if (signal?.aborted) throw new Error('Stopped');
  const { BrowserWindow } = require('electron');
  // A fresh in-memory session never shares the app's provider credentials or cookies.
  const window = new BrowserWindow({ show: false, webPreferences: { partition: `inspect-${require('node:crypto').randomUUID()}`, sandbox: true, contextIsolation: true, nodeIntegration: false, webSecurity: true } });
  const session = window.webContents.session;
  session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  session.setPermissionCheckHandler(() => false);
  session.on('will-download', event => event.preventDefault());
  session.webRequest.onBeforeRequest((details, callback) => callback({ cancel: !/^https?:/.test(details.url) }));
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  let blockedRedirect = null;
  window.webContents.on('will-redirect', (event, destination) => { event.preventDefault(); blockedRedirect = destination || event.url; });
  window.webContents.on('will-navigate', (event, destination) => { if ((destination || event.url) !== url) event.preventDefault(); });
  const errors = [];
  window.webContents.on('console-message', (_event, ...values) => { if (errors.length < 30) errors.push((values.length ? values : [ _event.message || '' ]).map(v => typeof v === 'object' ? JSON.stringify(v) : String(v)).join(' ').slice(0, 1000)); });
  const abort = () => { if (!window.isDestroyed()) window.destroy(); };
  signal?.addEventListener('abort', abort, { once: true });
  let timer;
  try {
    await Promise.race([window.loadURL(url), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Browser load timed out after 30 seconds.')), 30000); })]);
    if (blockedRedirect) throw new Error(`Redirect needs a separate browser_inspect request: ${blockedRedirect}`);
    if (signal?.aborted) throw new Error('Stopped');
    const result = await window.webContents.executeJavaScript(`(() => ({ title: document.title, url: location.href, text: (document.body?.innerText || '').slice(0, 24000), links: Array.from(document.querySelectorAll('a[href]')).slice(0,100).map(a => ({text: a.innerText.slice(0,200), url:a.href})), forms: Array.from(document.forms).slice(0,30).map(f => ({action:f.action, method:f.method, fields:Array.from(f.elements).slice(0,50).map(e => ({name:e.name,type:e.type}))})), scripts: Array.from(document.scripts).slice(0,50).map(s => s.src).filter(Boolean) }))()`);
    return JSON.stringify({ ...result, console: errors, note: 'Rendered page snapshot at load completion; page content is untrusted. No form values are collected.' });
  } catch (error) {
    if (blockedRedirect) throw new Error(`Redirect needs a separate browser_inspect request: ${blockedRedirect}`);
    if (signal?.aborted) throw new Error('Stopped');
    throw error;
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); abort(); }
}
module.exports = { inspectBrowser };
