const { contextBridge, ipcRenderer } = require('electron');
const names = ['state', 'copy-text', 'models', 'settings', 'project-open', 'project-select', 'project-files', 'project-read', 'images-open', 'image-remove', 'session-new', 'session-select', 'session-rename', 'memory-add', 'memory-delete', 'chat', 'stop', 'approval', 'terminal-open', 'terminal-write', 'terminal-resize', 'terminal-close', 'reveal-project'];
const api = {};
for (const name of names) api[name] = (...args) => ipcRenderer.invoke(`wixal:${name}`, ...args);
api.onEvent = callback => {
  const listener = (_event, data) => callback(data);
  ipcRenderer.on('wixal:event', listener);
  return () => ipcRenderer.removeListener('wixal:event', listener);
};
contextBridge.exposeInMainWorld('wixal', api);
