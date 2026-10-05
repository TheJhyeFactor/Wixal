const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
async function directory(value) {
  if (typeof value !== 'string' || !value.trim() || value.length > 4096 || value.includes('\0')) throw new Error('Enter a folder path.');
  value = value.trim();
  if (value === '~' || value.startsWith('~/')) value = path.join(os.homedir(), value.slice(2));
  if (!path.isAbsolute(value)) throw new Error('Use an absolute folder path.');
  const root = await fs.realpath(value);
  if (!(await fs.stat(root)).isDirectory()) throw new Error('Choose a folder, rather than a file.');
  return root;
}
async function browseFolder(value = os.homedir(), showHidden = false) {
  const root = await directory(value);
  const entries = await fs.readdir(root, { withFileTypes: true });
  const names = entries.filter(entry => entry.isDirectory() && (showHidden || !entry.name.startsWith('.'))).map(entry => entry.name).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const locations = [{ name: 'Home', path: os.homedir() }, ...['Desktop', 'Documents', 'Downloads'].map(name => ({ name, path: path.join(os.homedir(), name) })), { name: 'Volumes', path: '/Volumes' }];
  return { path: root, parent: path.dirname(root), folders: names.slice(0, 1000).map(name => ({ name, path: path.join(root, name) })), truncated: names.length > 1000, locations };
}
async function createFolder(parent, name) {
  if (typeof name !== 'string' || !name.trim() || name.length > 200 || /[\/\\\x00-\x1f:]/.test(name) || ['.', '..'].includes(name.trim()) || name.startsWith('.')) throw new Error('Use a folder name without slashes, a leading dot or special characters.');
  const root = await directory(parent), target = path.join(root, name.trim());
  try { await fs.mkdir(target); } catch (error) { if (error.code === 'EEXIST') throw new Error('A folder or file with that name already exists. Choose another name.'); throw error; }
  return target;
}
module.exports = { directory, browseFolder, createFolder };
