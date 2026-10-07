const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { Store } = require('../app/store.cjs');
const { modelDetails } = require('../app/models.cjs');
const { thinkingOptions, selectionContext } = require('../app/model-options.cjs');
const { runAgent, boundedToolResult } = require('../app/agent.cjs');
const { definitions, executeTool } = require('../app/tools.cjs');
test('long command evidence keeps parseable status and session metadata during context compaction', () => {
  const result = { session_id: 'scan-proof', state: 'completed', exitCode: 0, next_offset: 18000, more: false, output: 'XML HEADER\n' + 'evidence '.repeat(2000) + '\nPORT 443 OPEN' };
  const bounded = JSON.parse(boundedToolResult(JSON.stringify(result), 900));
  assert.equal(bounded.session_id, result.session_id); assert.equal(bounded.state, 'completed'); assert.equal(bounded.exitCode, 0);
  assert.equal(bounded.next_offset, result.next_offset); assert.equal(bounded.more, false); assert.equal(bounded.context_excerpt, true);
  assert.match(bounded.output, /XML HEADER/); assert.match(bounded.output, /PORT 443 OPEN/);
  assert.ok(bounded.output.length < result.output.length); assert.equal(result.output.includes('Output excerpt'), false);
});
test('engine metadata controls GPT-OSS reasoning levels and boolean thinking models', async () => {
  const info = await modelDetails('fixture', async () => new Response(JSON.stringify({ capabilities: ['tools', 'thinking'], thinking: { values: ['low', 'medium', 'high'], default: 'medium' }, details: { family: 'gptoss' } })));
  assert.deepEqual(thinkingOptions(info), { think: 'low' });
  assert.deepEqual(thinkingOptions({ capabilities: ['thinking'], thinking: { values: [true, false] } }), { think: false });
  assert.deepEqual(thinkingOptions({ capabilities: ['thinking'], details: { family: 'gptoss' } }), { think: 'low' });
  assert.deepEqual(thinkingOptions({ capabilities: ['completion'] }), {});
  assert.equal(selectionContext({ contextLength: 131072 }, 131072), 16384);
  assert.equal(selectionContext({ contextLength: 8192 }, 16384), 8192);
});
test('old cloud/external settings migrate to local execution without losing history or credentials preferences', async t => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-local-migration-')); t.after(() => fs.rm(temp, { recursive: true, force: true }));
  const store = new Store(temp); store.newSession(); store.session().messages.push({ role: 'user', content: 'Keep this conversation' });
  store.data.provider = 'openai'; store.data.model = 'cloud-model'; store.data.providerModels.ollama = 'local-model'; store.data.localRuntimeMode = 'external'; store.data.contextSize = 131072; delete store.data.localEngineVersion; store.save();
  const migrated = new Store(temp);
  assert.equal(migrated.data.provider, 'ollama'); assert.equal(migrated.data.model, 'local-model'); assert.equal(migrated.data.localRuntimeMode, 'managed'); assert.equal(migrated.data.contextSize, 8192);
  assert.equal(migrated.session().messages[0].content, 'Keep this conversation');
  migrated.data.contextSize = 32768; migrated.save(); assert.equal(new Store(temp).data.contextSize, 32768);
});
test('workspace context is embedded without a user mention and workspace_info returns actual enabled access', async t => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-embedded-tools-')); t.after(() => fs.rm(temp, { recursive: true, force: true }));
  const store = new Store(temp); store.addProject(temp); store.data.model = 'fixture'; store.data.enabledTools = ['workspace_info', 'read_file'];
  const info = { capabilities: ['tools', 'thinking'], thinking: { values: ['low', 'high'] } };
  let count = 0;
  await runAgent({ store, prompt: 'What can you do here?', details: info, signal: new AbortController().signal, emit: () => {}, fetcher: async (_url, req) => {
    const body = JSON.parse(req.body); count++;
    assert.equal(body.think, 'low'); assert.match(body.messages[0].content, /App-provided workspace context/); assert.match(body.messages[0].content, /no setup|do not need the user to configure an MCP/i);
    if (count === 1) return new Response(JSON.stringify({ message: { thinking: 'Inspect available access.', content: '', tool_calls: [{ function: { name: 'workspace_info', arguments: {} } }] }, done: true }));
    const actual = JSON.parse(body.messages.at(-1).content); assert.equal(actual.workspace.root, await fs.realpath(temp)); assert.deepEqual(actual.tools.map(t => t.name), ['workspace_info', 'read_file']); assert.equal(body.messages.at(-2).thinking, 'Inspect available access.');
    return new Response(JSON.stringify({ message: { content: 'Project files and workspace information are available.' }, done: true }));
  } });
  assert.equal(count, 2);
  await assert.rejects(executeTool('workspace_info', {}, { store, toolCatalog: definitions, modelInfo: info, allowedTools: [] }), /switched off/);
});
