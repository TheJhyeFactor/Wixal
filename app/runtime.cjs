const fs = require('node:fs/promises');
const { createReadStream, constants } = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const { spawn } = require('node:child_process');
const { createHash, randomUUID } = require('node:crypto');
const pin = require('../resources/runtime.json');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function hash(file) { const h = createHash('sha256'); for await (const b of createReadStream(file)) h.update(b); return h.digest('hex'); }
async function freePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = server.address().port; await new Promise(resolve => server.close(resolve)); return port;
}
class LocalRuntime {
  constructor({ directory, payload, mode = 'managed', onChange = () => {} }) {
    this.directory = directory; this.models = path.join(directory, 'models'); this.payload = payload;
    this.mode = mode; this.onChange = onChange; this.status = 'stopped'; this.error = ''; this.child = null;
    this.starting = null; this.stopping = null; this.checked = false; this.importing = false; this.closed = false;
  }
  snapshot() { return { mode: this.mode, status: this.mode === 'external' ? 'external' : this.status, version: pin.version, modelPath: this.models, error: this.error, importing: this.importing, pid: this.child?.pid || null }; }
  update(status, error = '') { this.status = status; this.error = error; this.onChange(this.snapshot()); }
  async verify() {
    if (this.checked) return;
    let manifest;
    try { manifest = JSON.parse(await fs.readFile(path.join(this.payload, 'manifest.json'), 'utf8')); }
    catch { throw new Error('The bundled runtime is missing. Developers: run npm run runtime:stage.'); }
    if (manifest.version !== pin.version || manifest.sourceCommit !== pin.sourceCommit || !Array.isArray(manifest.files) || !manifest.files.length) throw new Error('The bundled runtime does not match this Wixal version. Rebuild or reinstall the app.');
    for (const entry of manifest.files) {
      const file = path.resolve(this.payload, entry.path);
      if (!file.startsWith(path.resolve(this.payload) + path.sep)) throw new Error('Invalid runtime file path.');
      if (entry.link !== undefined) {
        if (await fs.readlink(file) !== entry.link || !path.resolve(path.dirname(file), entry.link).startsWith(path.resolve(this.payload) + path.sep)) throw new Error('Invalid runtime library link.');
      } else if (await hash(file) !== entry.sha256) throw new Error(`Bundled runtime file failed verification: ${entry.path}. Reinstall Wixal.`);
    }
    this.checked = true;
  }
  async endpoint() {
    if (this.closed) throw new Error('Local runtime is closing.');
    if (this.mode === 'external') return 'http://127.0.0.1:11434';
    if (this.stopping) await this.stopping;
    if (this.status === 'ready' && this.child) return this.url;
    if (!this.starting) this.starting = this.start().finally(() => { this.starting = null; });
    await this.starting; return this.url;
  }
  async start() {
    this.update('starting');
    try {
      await this.verify();
      await fs.mkdir(this.models, { recursive: true, mode: 0o700 });
      if (this.closed || this.status === 'stopping' || this.mode !== 'managed') throw new Error('Local runtime start cancelled.');
      this.url = `http://127.0.0.1:${await freePort()}`;
      if (this.closed || this.status === 'stopping') throw new Error('Local runtime start cancelled.');
      // No provider secrets or user OLLAMA_* overrides are inherited. HOME retains the real user's home.
      const env = { PATH: '/usr/bin:/bin:/usr/sbin:/sbin', HOME: os.homedir(), TMPDIR: os.tmpdir(),
        OLLAMA_HOST: this.url, OLLAMA_MODELS: this.models, OLLAMA_NO_CLOUD: 'true', OLLAMA_NOPRUNE: 'true',
        OLLAMA_MAX_LOADED_MODELS: '1', OLLAMA_NUM_PARALLEL: '1', OLLAMA_KEEP_ALIVE: '2m',
        OLLAMA_FLASH_ATTENTION: 'true', OLLAMA_KV_CACHE_TYPE: 'q8_0' };
      const child = spawn(path.join(this.payload, 'ollama'), ['serve'], { cwd: this.payload, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
      this.child = child; let failed = '', tail = '';
      const capture = chunk => { tail = (tail + chunk.toString()).slice(-4000); };
      child.stdout.on('data', capture); child.stderr.on('data', capture);
      child.on('error', error => { failed = error.message; });
      child.on('exit', (code, signal) => {
        failed ||= `Runner exited (${signal || code}).`;
        // A crashed server may leave its worker alive. Only this app-owned group is terminated.
        if (this.status !== 'stopping' && Number.isInteger(child.pid)) { try { process.kill(-child.pid, 'SIGKILL'); } catch {} }
        if (this.child === child) { this.child = null; if (this.status !== 'stopping') this.update('error', failed); }
      });
      const deadline = Date.now() + 20000;
      while (Date.now() < deadline) {
        if (failed || this.closed || this.status === 'stopping') throw new Error(failed || 'Local runtime start cancelled.');
        try {
          const response = await fetch(`${this.url}/api/version`, { signal: AbortSignal.timeout(800) });
          if (response.ok && (await response.json()).version === pin.version && this.child === child) { this.update('ready'); return; }
        } catch {}
        await pause(150);
      }
      throw new Error(`Local runtime did not become ready. ${tail.slice(-800)}`);
    } catch (error) { await this.killChild(); this.update('error', error.message); throw error; }
  }
  async killChild() {
    const child = this.child; if (!child || !Number.isInteger(child.pid)) { this.child = null; return; }
    const kill = signal => { try { process.kill(-child.pid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; } };
    const exited = new Promise(resolve => child.once('exit', resolve));
    kill('SIGTERM'); await Promise.race([exited, pause(2500)]);
    // Kill the owned process group even if the server exited before its inference worker.
    kill('SIGKILL'); if (this.child === child) this.child = null;
  }
  async stop() {
    if (this.stopping) return this.stopping;
    this.update('stopping');
    this.stopping = (async () => { await this.killChild(); if (this.starting) await this.starting.catch(() => {}); await this.killChild(); this.update('stopped'); })().finally(() => { this.stopping = null; });
    return this.stopping;
  }
  async setMode(mode) {
    if (!['managed', 'external'].includes(mode)) throw new Error('Choose Wixal Local or an external Ollama server.');
    if (this.importing) throw new Error('Wait for model import to finish.');
    await this.stop(); this.mode = mode; this.update('stopped');
  }
  async close() { this.closed = true; await this.stop(); }
  async availableImports(source = path.join(os.homedir(), '.ollama/models')) {
    const base = path.join(source, 'manifests'); const results = [];
    const walk = async (directory, parts = []) => {
      let entries; try { entries = await fs.readdir(directory, { withFileTypes: true }); } catch (error) { if (error.code === 'ENOENT') return; throw error; }
      for (const entry of entries) {
        if (entry.isSymbolicLink()) continue;
        if (entry.isDirectory() && parts.length < 3) await walk(path.join(directory, entry.name), [...parts, entry.name]);
        else if (entry.isFile() && parts.length === 3 && parts[0] === 'registry.ollama.ai') {
          const components = [...parts, entry.name];
          if (components.some(c => !/^[a-zA-Z0-9._+-]+$/.test(c) || c === '.' || c === '..')) continue;
          try {
            const file = path.join(base, ...components); if ((await fs.stat(file)).size > 1000000) continue;
            const manifest = JSON.parse(await fs.readFile(file, 'utf8'));
            const descriptors = [manifest.config, ...(manifest.layers || [])];
            if (!descriptors.length || descriptors.length > 100 || descriptors.some(d => !/^sha256:[a-f0-9]{64}$/.test(d?.digest) || !Number.isSafeInteger(d.size) || d.size < 0)) continue;
            const name = `${parts[1] === 'library' ? '' : parts[1] + '/'}${parts[2]}:${entry.name}`;
            if (/(?:^|[:.-])cloud(?:$|[:.-])/i.test(name)) continue;
            results.push({ name, bytes: descriptors.reduce((n, d) => n + d.size, 0), components, descriptors, manifest });
          } catch {}
        }
      }
    };
    await walk(base); return results;
  }
  async importModel(name, source = path.join(os.homedir(), '.ollama/models')) {
    if (this.mode !== 'managed' || this.importing) throw new Error('Switch to Wixal Local and wait for any current import.');
    this.importing = true; this.onChange(this.snapshot());
    try {
      const model = (await this.availableImports(source)).find(m => m.name === name);
      if (!model) throw new Error('This installed model is unavailable or uses an unsupported manifest.');
      const blobs = path.join(this.models, 'blobs'); await fs.mkdir(blobs, { recursive: true, mode: 0o700 });
      for (const descriptor of model.descriptors) {
        const filename = descriptor.digest.replace(':', '-'), from = path.join(source, 'blobs', filename), to = path.join(blobs, filename);
        const stat = await fs.lstat(from);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.size !== descriptor.size) throw new Error('An installed model file is incomplete or unsafe to import.');
        try { const existing = await fs.lstat(to); if (existing.isSymbolicLink()) throw new Error('The destination model file is a symbolic link.'); if (existing.isFile() && await hash(to) === descriptor.digest.slice(7)) continue; } catch (error) { if (error.code !== 'ENOENT') throw error; }
        const temporary = `${to}.${randomUUID()}.tmp`;
        try {
          // APFS makes an independent copy-on-write clone; other volumes use a normal copy, never a hard link.
          await fs.copyFile(from, temporary, constants.COPYFILE_FICLONE);
          if (await hash(temporary) !== descriptor.digest.slice(7)) throw new Error('Installed model checksum mismatch. Import cancelled.');
          await fs.chmod(temporary, 0o600); await fs.rename(temporary, to);
        } finally { await fs.rm(temporary, { force: true }); }
      }
      const target = path.join(this.models, 'manifests', ...model.components);
      await fs.mkdir(path.dirname(target), { recursive: true, mode: 0o700 });
      await fs.writeFile(target + '.tmp', JSON.stringify(model.manifest), { mode: 0o600 }); await fs.rename(target + '.tmp', target);
      return { name: model.name, bytes: model.bytes };
    } finally { this.importing = false; this.onChange(this.snapshot()); }
  }
}
module.exports = { LocalRuntime };
