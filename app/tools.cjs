const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');

const MAX_OUTPUT = 24000;
const skipped = new Set(['.git', 'node_modules', '.venv', 'venv', 'release', '.next', 'dist']);
const sensitive = p => p.split(path.sep).some(x => /^\.env(?:\.|$)/.test(x) || ['.ssh', '.aws', '.gnupg', '.npmrc', '.netrc', 'credentials.enc', 'wixal-connection.json'].includes(x) || /\.(pem|key|p12|pfx)$/i.test(x));

async function safePath(root, relative, writing = false) {
  if (typeof relative !== 'string' || path.isAbsolute(relative)) throw new Error('Use a path relative to the selected project.');
  root = await fs.realpath(root);
  const target = path.resolve(root, relative);
  const inside = p => p === root || p.startsWith(root + path.sep);
  if (!inside(target) || sensitive(relative)) throw new Error('Path is outside the project or contains protected credentials.');
  let actual;
  try { actual = await fs.realpath(target); }
  catch (error) {
    if (!writing || error.code !== 'ENOENT') throw error;
    // Require an existing parent, and resolve every symlink before writing.
    actual = path.join(await fs.realpath(path.dirname(target)), path.basename(target));
  }
  if (!inside(actual) || sensitive(path.relative(root, actual))) throw new Error('Symlink points outside the selected project or to protected credentials.');
  return actual;
}

async function walk(root, directory = '.', depth = 0, result = []) {
  if (depth > 6 || result.length >= 1200) return result;
  const entries = await fs.readdir(await safePath(root, directory), { withFileTypes: true });
  for (const entry of entries) {
    if (result.length >= 1200) break;
    const p = path.join(directory, entry.name);
    if (skipped.has(entry.name) || sensitive(p) || entry.isSymbolicLink()) continue;
    if (entry.isDirectory()) await walk(root, p, depth + 1, result);
    else if (entry.isFile()) result.push(p);
  }
  return result;
}

const definition = (name, description, properties, required) => ({ type: 'function', function: {
  name, description, parameters: { type: 'object', properties, required, additionalProperties: false },
}});
const str = description => ({ type: 'string', description });
const definitions = [
  definition('list_files', 'List files in the selected project. Skips dependency folders and credential files.', { directory: str('Relative directory, default .') }, []),
  definition('read_file', 'Read a UTF-8 file inside the project, up to 24,000 characters.', { path: str('Relative file path') }, ['path']),
  definition('search_files', 'Find literal text in project files. Case insensitive.', { query: str('Text to find') }, ['query']),
  definition('write_file', 'Create or replace a UTF-8 file after the user reviews the proposed content. Parent folder must exist.', { path: str('Relative file path'), content: str('Complete new file contents') }, ['path', 'content']),
  definition('run_command', 'Run a non-interactive shell command after user approval. Starts in project directory; host shell is not sandboxed. 60 second timeout.', { command: str('Shell command') }, ['command']),
];

function runCommand(command, root, signal, onOutput = () => {}) {
  if (typeof command !== 'string' || !command.trim() || command.length > 8000) throw new Error('Invalid command');
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new Error('Stopped'));
    const child = spawn('/bin/zsh', ['-l', '-c', command], { cwd: root, env: process.env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '', stopped = false;
    const stop = () => { stopped = true; try { process.kill(-child.pid, 'SIGKILL'); } catch {} };
    const timer = setTimeout(stop, 60000);
    signal?.addEventListener('abort', stop, { once: true });
    for (const stream of [child.stdout, child.stderr]) stream.on('data', data => {
      const text = data.toString();
      output = (output + text).slice(-MAX_OUTPUT);
      onOutput(text.slice(-MAX_OUTPUT));
    });
    const cleanup = () => { clearTimeout(timer); signal?.removeEventListener('abort', stop); };
    child.on('error', error => { cleanup(); reject(error); });
    child.on('close', code => { cleanup(); resolve(JSON.stringify({ exitCode: code, stopped, output })); });
  });
}

async function executeTool(name, args, { root, approve, signal, onOutput, allowedTools }) {
  if (allowedTools && !allowedTools.includes(name)) throw new Error(`${name} is switched off in the tool kit.`);
  if (!root) throw new Error('Open a project folder to use tools.');
  if (signal?.aborted) throw new Error('Stopped');
  if (!args || typeof args !== 'object') throw new Error('Invalid tool arguments');
  if (name === 'list_files') return (await walk(root, args.directory || '.')).join('\n').slice(0, MAX_OUTPUT);
  if (name === 'read_file') {
    const file = await safePath(root, args.path);
    const stat = await fs.stat(file);
    if (!stat.isFile() || stat.size > 1024 * 1024) throw new Error('File must be text and smaller than 1 MB.');
    const content = await fs.readFile(file, 'utf8');
    if (content.includes('\0')) throw new Error('Binary file is not supported.');
    return content.slice(0, MAX_OUTPUT) + (content.length > MAX_OUTPUT ? '\n[Truncated]' : '');
  }
  if (name === 'search_files') {
    if (typeof args.query !== 'string' || !args.query.trim()) throw new Error('Search query cannot be empty.');
    let output = '';
    for (const file of await walk(root)) {
      if (signal?.aborted) throw new Error('Stopped');
      try {
        const real = await safePath(root, file);
        if ((await fs.stat(real)).size > 256000) continue;
        const content = await fs.readFile(real, 'utf8');
        if (content.includes('\0')) continue;
        for (const [i, line] of content.split('\n').entries()) {
          if (line.toLowerCase().includes(args.query.toLowerCase())) output += `${file}:${i + 1}: ${line.slice(0, 400)}\n`;
          if (output.length >= MAX_OUTPUT) return output.slice(0, MAX_OUTPUT);
        }
      } catch {}
    }
    return output || 'No matches.';
  }
  if (name === 'write_file') {
    if (typeof args.content !== 'string' || args.content.length > 100000) throw new Error('Content must be text under 100,000 characters.');
    const file = await safePath(root, args.path, true);
    let before = null;
    try { before = await fs.readFile(file, 'utf8'); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (!(await approve({ name, path: args.path, before, after: args.content }))) return 'User declined this file edit.';
    if (signal?.aborted) throw new Error('Stopped');
    const checked = await safePath(root, args.path, true);
    let current = null;
    try { current = await fs.readFile(checked, 'utf8'); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (current !== before || checked !== file) throw new Error('File changed during review. Read it again before editing.');
    await fs.writeFile(file, args.content, { mode: 0o600 });
    return `Saved ${args.path} (${Buffer.byteLength(args.content)} bytes).`;
  }
  if (name === 'run_command') {
    if (typeof args.command !== 'string' || args.command.length > 8000) throw new Error('Invalid command');
    if (!(await approve({ name, command: args.command, root }))) return 'User declined this command.';
    return runCommand(args.command, root, signal, onOutput);
  }
  throw new Error(`Unknown tool: ${name}`);
}
module.exports = { definitions, safePath, executeTool, runCommand };
