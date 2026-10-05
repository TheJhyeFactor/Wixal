const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');
const { LocalRuntime } = require('../app/runtime.cjs');
const pin = require('../resources/runtime.json');
async function fixture(t) {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-runtime-test-'));
  const payload = path.join(temp, 'payload'); await fs.mkdir(payload);
  const code = `#!${process.execPath}\nconst http=require('node:http'); const fs=require('node:fs'); fs.writeFileSync(process.env.OLLAMA_MODELS+'/environment.json',JSON.stringify(process.env)); http.createServer((req,res)=>res.end(JSON.stringify({version:${JSON.stringify(pin.version)}}))).listen(Number(new URL(process.env.OLLAMA_HOST).port),'127.0.0.1');`;
  await fs.writeFile(path.join(payload, 'ollama'), code, { mode: 0o755 });
  await fs.writeFile(path.join(payload, 'manifest.json'), JSON.stringify({ ...pin, files: [{ path: 'ollama', sha256: createHash('sha256').update(code).digest('hex') }] }));
  const runtime = new LocalRuntime({ directory: path.join(temp, 'data'), payload });
  t.after(async () => { await runtime.close(); await fs.rm(temp, { recursive: true, force: true }); });
  return { temp, payload, runtime };
}
test('managed startup is coalesced, loopback only, strips secrets, restarts and cleans up its process', async t => {
  const { runtime } = await fixture(t);
  const secretBefore = process.env.OPENAI_API_KEY; process.env.OPENAI_API_KEY = 'test-secret';
  t.after(() => { if (secretBefore === undefined) delete process.env.OPENAI_API_KEY; else process.env.OPENAI_API_KEY = secretBefore; });
  const urls = await Promise.all([runtime.endpoint(), runtime.endpoint(), runtime.endpoint()]);
  assert.equal(new Set(urls).size, 1); assert.match(urls[0], /^http:\/\/127\.0\.0\.1:/); assert.notEqual(urls[0], 'http://127.0.0.1:11434');
  const env = JSON.parse(await fs.readFile(path.join(runtime.models, 'environment.json')));
  assert.equal(env.OPENAI_API_KEY, undefined); assert.equal(env.OLLAMA_NO_CLOUD, 'true'); assert.equal(env.OLLAMA_MODELS, runtime.models);
  const pid = runtime.snapshot().pid; await runtime.stop(); assert.throws(() => process.kill(pid, 0), /ESRCH/);
  await runtime.endpoint(); assert.notEqual(runtime.snapshot().pid, pid);
  await runtime.setMode('external'); assert.equal(await runtime.endpoint(), 'http://127.0.0.1:11434'); assert.equal(runtime.child, null);
  await assert.rejects(runtime.setMode('bad'), /Choose/);
});
test('failed payload integrity blocks execution and shutdown cancels pending startup', async t => {
  const { runtime, payload } = await fixture(t);
  await fs.appendFile(path.join(payload, 'ollama'), '\n// changed');
  await assert.rejects(runtime.endpoint(), /verification/); assert.equal(runtime.child, null);
  const another = await fixture(t); const starting = another.runtime.endpoint(); await another.runtime.close();
  await assert.rejects(starting, /cancelled/); assert.equal(another.runtime.child, null);
});
test('a crashed server terminates its owned worker and the next request recovers', async t => {
  const { runtime, payload } = await fixture(t);
  const executable = path.join(payload, 'ollama');
  const extra = "\nconst worker=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore'});fs.writeFileSync(process.env.OLLAMA_MODELS+'/worker.pid',String(worker.pid));";
  const code = (await fs.readFile(executable, 'utf8')) + extra;
  await fs.writeFile(executable, code);
  await fs.writeFile(path.join(payload, 'manifest.json'), JSON.stringify({ ...pin, files: [{ path: 'ollama', sha256: createHash('sha256').update(code).digest('hex') }] }));
  await runtime.endpoint();
  const worker = Number(await fs.readFile(path.join(runtime.models, 'worker.pid'), 'utf8'));
  process.kill(runtime.child.pid, 'SIGKILL');
  for (let i = 0; i < 50 && runtime.status !== 'error'; i++) await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(runtime.status, 'error');
  for (let i = 0; i < 50; i++) { try { process.kill(worker, 0); } catch { break; } await new Promise(resolve => setTimeout(resolve, 20)); }
  assert.throws(() => process.kill(worker, 0), /ESRCH/);
  await runtime.endpoint(); assert.equal(runtime.status, 'ready');
});
test('model import validates blobs, creates independent files and publishes only complete manifests', async t => {
  const { runtime, temp } = await fixture(t); const source = path.join(temp, 'source');
  const bytes = Buffer.from('local-model-fixture'), digest = createHash('sha256').update(bytes).digest('hex');
  const manifest = { config: { digest: `sha256:${digest}`, size: bytes.length }, layers: [] };
  const model = path.join(source, 'manifests/registry.ollama.ai/library/fixture/latest');
  await fs.mkdir(path.dirname(model), { recursive: true }); await fs.mkdir(path.join(source, 'blobs'));
  const blob = path.join(source, 'blobs', `sha256-${digest}`); await fs.writeFile(blob, bytes); await fs.writeFile(model, JSON.stringify(manifest));
  assert.equal((await runtime.availableImports(source))[0].name, 'fixture:latest');
  await runtime.importModel('fixture:latest', source);
  const copied = path.join(runtime.models, 'blobs', `sha256-${digest}`);
  assert.notEqual((await fs.stat(blob)).ino, (await fs.stat(copied)).ino);
  await fs.writeFile(blob, 'corrupt-data-fixture'); assert.deepEqual(await fs.readFile(copied), bytes);
  await fs.rm(runtime.models, { recursive: true });
  await assert.rejects(runtime.importModel('fixture:latest', source), /incomplete|checksum/);
  await assert.rejects(fs.access(path.join(runtime.models, 'manifests/registry.ollama.ai/library/fixture/latest')));
  await fs.rm(blob); await fs.symlink(model, blob);
  await assert.rejects(runtime.importModel('fixture:latest', source), /unsafe/);
  assert.equal(runtime.importing, false);
});
