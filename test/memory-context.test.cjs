const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Store } = require('../app/store.cjs');
const { projectMemory, searchHistory } = require('../app/context.cjs');
const { safeContext, globalProfile, usage } = require('../app/memory.cjs');
const { runAgent, ollamaMessages, fitRequest, summarizeHandoff } = require('../app/agent.cjs');
function setup(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wixal-memory-')); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const store = new Store(path.join(root, 'state')); store.addProject(root); store.data.model = 'first'; store.data.enabledTools = [];
  return { root, store, signal: new AbortController().signal, emit() {}, details: { capabilities: ['tools'], contextLength: 32768 } };
}
const answer = content => new Response(JSON.stringify({ message: { content }, done: true }));
test('project recall is automatic, scoped, excludes archived chats and obeys off/global modes', t => {
  const { store, root } = setup(t), projectId = store.data.activeProject;
  store.remember('sapphire note'); store.session().messages.push({ role: 'user', content: 'sapphire approved decision' });
  const original = store.session(); store.newSession();
  assert.match(projectMemory(store, 'sapphire'), /approved decision/);
  original.archivedAt = Date.now(); assert.doesNotMatch(projectMemory(store, 'sapphire'), /approved decision/);
  fs.mkdirSync(path.join(root, 'other')); store.addProject(path.join(root, 'other')); store.remember('sapphire OTHER SECRET');
  store.selectProject(projectId); assert.doesNotMatch(projectMemory(store, 'sapphire'), /OTHER SECRET/);
  for (const mode of ['off', 'global']) { store.setMemorySettings({ mode, size: 8000 }); assert.equal(projectMemory(store, 'sapphire'), ''); assert.deepEqual(searchHistory(store, 'sapphire'), []); assert.throws(() => store.remember('new note'), /off/); }
});
test('saved memory budgets reject overflow and unsafe shrinking; scoped edits survive reload', t => {
  const { store, root } = setup(t); store.setMemorySettings({ mode: 'project', size: 24000 });
  for (let i = 0; i < 3; i++) store.remember('x'.repeat(3000));
  assert.throws(() => store.setMemorySettings({ mode: 'project', size: 8000 }), /Remove/);
  const id = store.data.memories[0].id; store.updateMemory(id, 'actual corrected preference');
  store.setMemorySettings({ mode: 'both', size: 8000 }); assert.throws(() => store.remember('x'.repeat(3000)), /full/);
  assert.equal(new Store(path.join(root, 'state')).data.memories.find(m => m.id === id).content, 'actual corrected preference');
  assert.throws(() => globalProfile('x'.repeat(1201)), /1,200/);
});
test('global preferences follow scope and can be disabled without deleting them', async t => {
  const options = setup(t); options.store.data.globalMemory = 'Call me profile-marker.';
  for (const mode of ['project', 'both', 'global', 'off']) {
    options.store.setMemorySettings({ mode, size: 24000 }); let body;
    await runAgent({ ...options, prompt: 'Hello', fetcher: async (_url, req) => { body = JSON.parse(req.body); return answer('Hello'); } });
    assert.equal(body.messages[0].content.includes('profile-marker'), ['both', 'global'].includes(mode));
  }
  options.store.selectProject(null); options.store.data.globalMemoryEnabled = false;
  await runAgent({ ...options, prompt: 'Hello', fetcher: async (_url, req) => { assert.doesNotMatch(JSON.parse(req.body).messages[0].content, /profile-marker/); return answer('Hello'); } });
});
test('model swaps keep evidence and discard foreign tool schemas and thinking even within Ollama', async t => {
  const options = setup(t); const original = [{ role: 'user', content: 'Read file' }, { role: 'assistant', model: 'first', content: '', thinking: 'private-format', tool_calls: [{ function: { name: 'read_file', arguments: { path: 'a' } } }] }, { role: 'tool', tool_name: 'read_file', content: 'REAL FILE EVIDENCE' }];
  options.store.session().messages = structuredClone(original); options.store.data.model = 'second'; options.store.data.mode = 'chat';
  await runAgent({ ...options, prompt: 'What did it say?', details: { capabilities: ['completion'], contextLength: 8192 }, fetcher: async (_url, req) => {
    const body = JSON.parse(req.body); assert.match(JSON.stringify(body.messages), /REAL FILE EVIDENCE/); assert.doesNotMatch(JSON.stringify(body.messages), /private-format|tool_calls|tool_name/); assert.ok(body.messages.every(m => m.role !== 'tool')); return answer('Evidence retained.');
  } });
  assert.deepEqual(options.store.session().messages.slice(0, 3), original); assert.equal(options.store.session().messages.at(-1).model, 'second');
  assert.equal(ollamaMessages(original, 'first', true)[1].thinking, 'private-format');
});
test('context cap accounts for model and RAM and reserves output; oversized latest turns are rejected', () => {
  assert.equal(safeContext({ contextLength: 131072 }, 131072), 32768);
  assert.equal(safeContext({ contextLength: 8192 }, 32768), 8192);
  assert.equal(safeContext({ contextLength: 131072 }, 32768, { totalMemory: 16 * 1024 ** 3 }), 16384);
  const model = { contextLength: 131072, size: 14 * 1024 ** 3 }; assert.ok(safeContext(model, 32768, { totalMemory: 24 * 1024 ** 3, memoryBudget: 18 * 1024 ** 3 }) < 16384);
  const messages = [{ role: 'system', content: 'Rules' }, { role: 'user', content: 'x'.repeat(30000) }, { role: 'assistant', content: 'older reply' }, { role: 'user', content: 'latest request' }];
  const bounded = fitRequest(messages, [], 4096); assert.equal(bounded.at(-1).content, 'latest request'); assert.ok(usage(bounded, [], 4096).used < usage(bounded, [], 4096).inputLimit);
  assert.throws(() => fitRequest(messages.slice(0, 2), [], 4096), /safe context budget/); assert.equal(messages[1].content.length, 30000);
});
test('handoff uses selected model, bounds summary requests, labels failures and leaves source intact', async t => {
  const options = setup(t); options.store.session().messages.push({ role: 'user', content: 'Goal sapphire; never delete files. '.repeat(500) }, { role: 'assistant', content: 'Tests failed; fix remains.' });
  const before = structuredClone(options.store.session()), calls = [];
  const summary = await summarizeHandoff({ ...options, source: options.store.session(), fetcher: async (_url, req) => { const body = JSON.parse(req.body); calls.push(body); assert.equal(body.model, 'first'); assert.ok(usage(body.messages, [], body.options.num_ctx).used <= usage(body.messages, [], body.options.num_ctx).inputLimit); return answer('Goal sapphire; preserve files; tests failed, fix remains.'); } });
  assert.equal(summary.method, 'model'); assert.match(summary.content, /tests failed/); assert.ok(calls.length > 0); assert.deepEqual(options.store.session(), before);
  const fallback = await summarizeHandoff({ ...options, source: options.store.session(), fetcher: async () => { throw new Error('offline'); } }); assert.equal(fallback.method, 'excerpts');
  const controller = new AbortController(); controller.abort(); await assert.rejects(summarizeHandoff({ ...options, source: options.store.session(), signal: controller.signal }), /Stopped/);
});

test('an oversized request is rejected before a user message is persisted', async t => {
  const options = setup(t); options.store.data.contextSize = 4096;
  await assert.rejects(runAgent({ ...options, prompt: 'x'.repeat(16000), fetcher: async () => { throw new Error('Should not fetch'); } }), /safe context budget/);
  assert.equal(options.store.session().messages.length, 0);
});

test('long current-turn tool polling stays bounded while preserving recent native exchanges and saved evidence', () => {
  const messages = [{ role: 'system', content: 'rules '.repeat(600) }, { role: 'user', content: 'Read scan until complete.' }];
  for (let i = 0; i < 12; i++) messages.push({ role: 'assistant', content: '', tool_calls: [{ function: { name: 'network_read', arguments: { session_id: 'actual-scan' } } }] }, { role: 'tool', tool_name: 'network_read', content: JSON.stringify({ state: 'running', output: 'evidence '.repeat(300) }) });
  const before = structuredClone(messages), result = fitRequest(messages, [], 4096);
  assert.match(result[1].content, /Read scan until complete/);
  assert.ok(result.some(m => m.content?.startsWith('Previous tool evidence from earlier steps')));
  assert.equal(result.at(-1).role, 'tool'); assert.equal(result.at(-2).tool_calls[0].function.name, 'network_read');
  assert.ok(usage(result, [], 4096).used <= usage(result, [], 4096).inputLimit); assert.deepEqual(messages, before);
});
