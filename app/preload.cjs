const { contextBridge, ipcRenderer } = require('electron');
const names = ['state', 'copy-text', 'models', 'settings', 'project-open', 'project-select', 'project-files', 'project-read', 'images-open', 'image-remove', 'session-new', 'session-select', 'session-rename', 'memory-add', 'memory-delete', 'chat', 'stop', 'approval', 'terminal-open', 'terminal-write', 'terminal-resize', 'terminal-close', 'reveal-project'];
const api = {};
names.push('layout');
names.push('model-delete', 'benchmark-start', 'benchmark-cancel', 'runtime-mode', 'runtime-start', 'runtime-stop', 'runtime-imports', 'runtime-import', 'runtime-reveal',
  'model-pull', 'model-pull-cancel', 'mcp-save', 'mcp-connect', 'mcp-disconnect', 'mcp-delete', 'summary-clear');
names.push('session-archive', 'session-restore', 'session-delete');
names.push('provider-key-save', 'provider-key-remove', 'custom-provider-save', 'connections', 'api-key-save', 'api-key-remove', 'chatgpt-sign-in', 'chatgpt-cancel', 'chatgpt-select', 'chatgpt-sign-out', 'chatgpt-plan-notice', 'sharing', 'connection-link', 'task-start', 'task-cancel');
for (const name of names) api[name] = (...args) => ipcRenderer.invoke(`wixal:${name}`, ...args);
api.onEvent = callback => {
  const listener = (_event, data) => callback(data);
  ipcRenderer.on('wixal:event', listener);
  return () => ipcRenderer.removeListener('wixal:event', listener);
};
contextBridge.exposeInMainWorld('wixal', api);
