// Fetch one pinned upstream payload, verify it, preserve notices, then stage it outside ASAR.
const fs = require('node:fs/promises');
const path = require('node:path');
const { createReadStream } = require('node:fs');
const { createHash } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const pin = require('../resources/runtime.json');
function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit' });
  if (result.status !== 0) throw new Error(`${command} failed (${result.status ?? result.error}).`);
}
async function hash(file) { const h = createHash('sha256'); for await (const b of createReadStream(file)) h.update(b); return h.digest('hex'); }
async function inventory(directory, prefix = '') {
  const files = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const relative = path.join(prefix, entry.name), file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await inventory(file, relative));
    else if (entry.isSymbolicLink()) files.push({ path: relative, link: await fs.readlink(file) });
    else files.push({ path: relative, sha256: await hash(file) });
  }
  return files;
}
async function seal(directory, origin) {
  const license = await fetch(`https://raw.githubusercontent.com/ollama/ollama/${pin.sourceCommit}/LICENSE`);
  if (!license.ok) throw new Error('Could not fetch the pinned upstream license.');
  await fs.writeFile(path.join(directory, 'OLLAMA_LICENSE'), await license.text());
  for (const notice of ['JSON_LICENSE.MIT', 'METAL_CPP_LICENSE.txt']) await fs.copyFile(path.join(root, 'resources/notices', notice), path.join(directory, notice));
  const files = await inventory(directory);
  await fs.writeFile(path.join(directory, 'manifest.json'), JSON.stringify({ ...pin, origin, files }, null, 2) + '\n');
}
async function main() {
  if (process.platform !== 'darwin' || process.arch !== 'arm64') throw new Error('Stage the runtime on an Apple Silicon Mac.');
  const cache = path.join(root, 'runtime/cache'), archive = path.join(cache, 'ollama-darwin.tgz');
  await fs.mkdir(cache, { recursive: true });
  try { await fs.access(archive); } catch { run('curl', ['-fL', '--retry', '2', pin.archiveURL, '-o', archive]); }
  if (await hash(archive) !== pin.archiveSHA256) throw new Error('Runtime archive checksum mismatch. Remove runtime/cache/ollama-darwin.tgz and retry.');
  const stage = path.join(root, 'runtime/ollama');
  await fs.rm(stage, { recursive: true, force: true }); await fs.mkdir(stage, { recursive: true });
  run('tar', ['-xzf', archive, '-C', stage]);
  await seal(stage, 'verified-upstream-release');
  console.log(`Staged Ollama ${pin.version} with its license notices and payload hashes.`);
}
module.exports = { seal, run, inventory };
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
