const test = require('node:test');
const assert = require('node:assert/strict');
const { ModelDownloads } = require('../app/model-downloads.cjs');
const { getModels, validateModelName, unloadModel } = require('../app/models.cjs');
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture(pull, saved = []) {
  let writes = 0; const events = [], store = { data: { modelDownloads: saved }, save: () => writes++ };
  const downloads = new ModelDownloads({ store, pull, emit: event => events.push(event) });
  return { downloads, store, events, writes: () => writes };
}
test('downloads are serialized, deduplicated, and verify installation before success', async () => {
  const releases = [], calls = [], verified = [];
  const f = fixture((name, signal, progress) => new Promise((resolve, reject) => { calls.push(name); progress({ status: 'pulling', digest: 'a', total: 100, completed: 50 }); releases.push(resolve); signal.addEventListener('abort', () => reject(new Error('aborted'))); }));
  f.downloads.verify = async name => { verified.push(name); };
  const first = f.downloads.enqueue('qwen3:0.6b', 'managed'); f.downloads.enqueue('gemma3:270m', 'managed');
  assert.throws(() => f.downloads.enqueue('qwen3:0.6b', 'managed'), /already/);
  assert.deepEqual(calls, ['qwen3:0.6b']); assert.equal(first.completed, 50);
  releases.shift()(); await tick(); assert.equal(first.state, 'completed'); assert.deepEqual(verified, ['qwen3:0.6b']);
  assert.deepEqual(calls, ['qwen3:0.6b', 'gemma3:270m']); releases.shift()(); await tick(); assert.equal(f.downloads.busy, false);
});
test('pause aborts the active request, advances the queue, and resume retains its engine', async () => {
  const signals = [];
  const f = fixture((_name, signal) => new Promise((_resolve, reject) => { signals.push(signal); signal.addEventListener('abort', () => reject(new Error('aborted'))); }));
  const first = f.downloads.enqueue('qwen3:0.6b', 'managed'), second = f.downloads.enqueue('gemma3:270m', 'managed');
  f.downloads.action(first.id, 'pause', 'managed'); await tick();
  assert.equal(signals[0].aborted, true); assert.equal(first.state, 'paused'); assert.equal(second.state, 'downloading');
  assert.throws(() => f.downloads.action(first.id, 'resume', 'external'), /original/);
  f.downloads.action(second.id, 'cancel', 'managed'); await tick();
  f.downloads.action(first.id, 'resume', 'managed'); await tick(); assert.equal(first.state, 'downloading');
  f.downloads.shutdown(); await tick(); assert.equal(first.state, 'paused');
  const restored = fixture(async () => {}, f.store.data.modelDownloads); assert.equal(restored.downloads.busy, false);
});
test('failures can be retried, false success fails verification, and restart never starts a transfer', async () => {
  let attempts = 0; const f = fixture(async () => { if (++attempts === 1) throw new Error('disk full'); });
  const job = f.downloads.enqueue('gemma3:270m', 'external'); await tick(); assert.equal(job.state, 'failed'); assert.match(job.error, /disk full/);
  f.downloads.verify = async () => { throw new Error('not installed'); }; f.downloads.action(job.id, 'retry', 'external'); await tick(); assert.equal(job.state, 'failed'); assert.match(job.error, /not installed/);
  f.downloads.verify = async () => {}; f.downloads.action(job.id, 'retry', 'external'); await tick(); assert.equal(job.state, 'completed');
  const interrupted = fixture(async () => { throw new Error('must not run'); }, [{ ...job, state: 'downloading' }]); assert.equal(interrupted.downloads.items[0].state, 'paused');
});
test('download progress is throttled and unchanged jobs do not write storage for every chunk', async () => {
  const f = fixture(async (_name, _signal, progress) => { for (let i = 0; i < 1000; i++) progress({ status: 'pulling', digest: 'layer', total: 1000, completed: i }); });
  f.downloads.enqueue('gemma3:270m', 'managed'); await tick();
  assert.ok(f.events.length < 10, f.events.length); assert.ok(f.writes() < 10, f.writes()); assert.equal(f.downloads.items[0].state, 'completed');
});
test('model metadata is reused for unchanged digests and refreshed for replacements or explicit refresh', async () => {
  let reads = 0, digest = 'one';
  const fetcher = async url => url.endsWith('/api/tags') ? new Response(JSON.stringify({ models: [{ name: 'cached:test', digest, size: 1e9 }] })) : (reads++, new Response('{"capabilities":["tools"]}'));
  await getModels(fetcher); await getModels(fetcher); assert.equal(reads, 1);
  digest = 'two'; await getModels(fetcher); assert.equal(reads, 2);
  await getModels(fetcher, { refresh: true }); assert.equal(reads, 3);
  let active = 0, peak = 0;
  const many = async url => url.endsWith('/api/tags') ? new Response(JSON.stringify({ models: Array.from({ length: 20 }, (_, i) => ({ name: `model:${i}`, digest: String(i) })) })) : (active++, peak = Math.max(peak, active), await tick(), active--, new Response('{}'));
  await getModels(many); assert.equal(peak, 4);
});
test('local model tags reject cloud-only variants and unload requests explicitly release memory', async () => {
  assert.throws(() => validateModelName('gpt-oss:120b-cloud'), /Cloud-only/); assert.throws(() => validateModelName('bad name'), /valid/);
  validateModelName('org/model:iq4_xs');
  await unloadModel('gemma3:270m', async (_url, request) => { assert.deepEqual(JSON.parse(request.body), { model: 'gemma3:270m', keep_alive: 0, stream: false }); return new Response('{}'); });
});

test('cancelling during installation verification cannot become a completed download', async () => {
  const f = fixture(async () => {}); let finish;
  f.downloads.verify = () => new Promise(resolve => { finish = resolve; });
  const job = f.downloads.enqueue('gemma3:270m', 'managed'); await tick();
  f.downloads.action(job.id, 'cancel', 'managed'); finish(); await tick();
  assert.equal(job.state, 'cancelled'); assert.equal(f.downloads.busy, false);
});
