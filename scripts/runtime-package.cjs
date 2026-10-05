// Node's cp rewrites relative extra-resource links to source-machine absolute paths.
// Restore the verified payload's original links before signing or distribution.
const fs = require('node:fs/promises');
const path = require('node:path');
const { LocalRuntime } = require('../app/runtime.cjs');
(async () => {
  const payload = path.resolve(__dirname, '../release/Wixal-darwin-arm64/Wixal.app/Contents/Resources/ollama');
  const manifest = JSON.parse(await fs.readFile(path.join(payload, 'manifest.json'), 'utf8'));
  for (const entry of manifest.files.filter(file => file.link !== undefined)) {
    const file = path.resolve(payload, entry.path), target = path.resolve(path.dirname(file), entry.link);
    if (!file.startsWith(payload + path.sep) || !target.startsWith(payload + path.sep) || path.isAbsolute(entry.link)) throw new Error('Unsafe runtime library link in payload manifest.');
    const stat = await fs.lstat(file); if (!stat.isSymbolicLink()) throw new Error('Expected a runtime library link.');
    await fs.unlink(file); await fs.symlink(entry.link, file);
  }
  await new LocalRuntime({ directory: payload, payload }).verify();
  console.log('Verified portable runtime resources: all library links stay inside the app.');
})().catch(error => { console.error(error.message); process.exitCode = 1; });
