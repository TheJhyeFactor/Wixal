const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { Store } = require('../app/store.cjs');
const { runAgent } = require('../app/agent.cjs');
const { hardware, estimate, benchmark } = require('../app/performance.cjs');
const { definitions } = require('../app/tools.cjs');
const { requestedTools } = require('../app/mentions.cjs');
test('memory sizing reserves host RAM, includes context and never presents an estimate as a measured run', () => {
  const device = hardware(); assert.ok(device.memoryBudget < device.totalMemory);
  const sample = { size: 2e9, contextLength: 8192, kvBytesPerToken: 16384 };
  assert.equal(estimate(sample, { memoryBudget: 8e9 }, 16384).context, 8192);
  assert.equal(estimate(sample, { memoryBudget: 8e9 }, 16384).fits, true);
  assert.equal(estimate(sample, { memoryBudget: 1e9 }, 16384).fits, false);
  assert.equal(estimate(sample, device, 8192).estimated, true);
});
test('benchmarks score actual reported tokens in two bounded runs and retain memory/digest/context', async () => {
  const bodies = [], progress = [];
  const result = await benchmark({ name: 'fixture', digest: 'one', contextLength: 8192 }, 16384, new AbortController().signal, p => progress.push(p), async (url, options) => {
    if (url.endsWith('/api/version')) return new Response('{"version":"fixture"}');
    if (url.endsWith('/api/ps')) return new Response(JSON.stringify({ models: [{ name: 'fixture', size: 100, size_vram: 90 }] }));
    bodies.push(JSON.parse(options.body));
    return new Response(JSON.stringify({ message: { content: '1 one' }, done: true, prompt_eval_count: 25, eval_count: 128, eval_duration: 4e9, total_duration: 5e9 }));
  });
  assert.equal(bodies.length, 2); assert.equal(bodies[0].options.num_predict, 128); assert.equal(bodies[0].options.num_ctx, 8192);
  assert.equal(result.tokensPerSecond, 32); assert.equal(result.totalTokens, 256); assert.equal(result.loadedBytes, 100); assert.equal(result.digest, 'one'); assert.ok(progress.length >= 4);
  await assert.rejects(benchmark({ name: 'fixture' }, 8192, new AbortController().signal, () => {}, async () => new Response('{"message":{"content":"none"},"done":true}')), /no generated tokens/);
});
test('explicit tool selection constrains tools, retries skipped calls, records usage and respects declined actions', async t => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-mentions-')); t.after(() => fs.rm(temp, { recursive: true, force: true }));
  const store = new Store(temp); store.addProject(temp); store.data.model = 'fixture'; store.data.mode = 'chat';
  assert.equal(store.data.enabledTools.length, definitions.length);
  assert.deepEqual(requestedTools('@write_file create a file', definitions, store.data.enabledTools, store.project()), ['write_file']);
  assert.throws(() => requestedTools('@read_file read it', definitions, [], store.project()), /switched off/);
  assert.throws(() => requestedTools('@read_file read it', definitions, store.data.enabledTools), /Open a project/);
  let calls = 0, reviews = 0; const requests = [];
  await runAgent({ store, prompt: '@write_file create declined.txt', details: { capabilities: ['tools'] }, signal: new AbortController().signal,
    emit: () => {}, approve: async () => { reviews++; return false; }, fetcher: async (_url, request) => {
      requests.push(JSON.parse(request.body)); calls++;
      const message = calls === 1 ? { content: 'I did it without a tool.' } : calls === 2 ? { content: '', tool_calls: [{ function: { name: 'write_file', arguments: { path: 'declined.txt', content: 'no' } } }] } : { content: 'The edit was declined.' };
      return new Response(JSON.stringify({ message, done: true, eval_count: 10, prompt_eval_count: 20, eval_duration: 1e9 }));
    } });
  assert.equal(calls, 3); assert.equal(reviews, 1); assert.deepEqual(requests[0].tools.map(t => t.function.name), ['write_file']);
  assert.equal(store.data.usage.length, 3); assert.equal(store.data.usage.reduce((n, r) => n + r.inputTokens, 0), 60);
  assert.ok(!store.session().messages.some(m => m.content?.includes('without a tool'))); await assert.rejects(fs.access(path.join(temp, 'declined.txt')));
  await assert.rejects(runAgent({ store, prompt: '@list_files inspect', details: { capabilities: ['tools'] }, signal: new AbortController().signal, emit: () => {}, approve: async () => true, fetcher: async () => new Response('{"message":{"content":"No"},"done":true}') }), /did not call/);
});
