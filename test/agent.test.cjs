const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { Store } = require('../app/store.cjs');
const { runAgent, contextMessages, streamChat } = require('../app/agent.cjs');
const { modelDetails, getModels } = require('../app/models.cjs');
const { executeTool } = require('../app/tools.cjs');
async function setup(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-agent-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const store = new Store(path.join(root, 'state')); store.addProject(root); store.data.model = 'fixture';
  return { root, store, signal: new AbortController().signal, emit: () => {}, approve: async () => true };
}
const response = message => new Response(JSON.stringify({ message, done: true, eval_count: 10, eval_duration: 2e9, total_duration: 3e9 }));
test('an invented call to a disabled tool cannot change a file', async t => {
  const options = await setup(t); options.store.data.enabledTools = ['read_file'];
  const requests = [];
  await runAgent({ ...options, prompt: 'Do something', details: { capabilities: ['tools'], contextLength: 8192 }, fetcher: async (_url, request) => {
    requests.push(JSON.parse(request.body));
    return response(requests.length === 1 ? { content: '', tool_calls: [{ function: { name: 'write_file', arguments: { path: 'denied.txt', content: 'no' } } }] } : { content: 'The tool is off.' });
  } });
  await assert.rejects(fs.access(path.join(options.root, 'denied.txt')));
  assert.deepEqual(requests[0].tools.map(tool => tool.function.name), ['read_file']);
  assert.equal(requests[0].options.num_ctx, 8192);
  assert.match(options.store.session().messages.find(message => message.role === 'tool').content, /switched off/);
  await assert.rejects(executeTool('run_command', { command: 'touch bad' }, { root: options.root, allowedTools: [] }), /switched off/);
});
test('unsupported agent and image requests are rejected before adding a turn', async t => {
  const options = await setup(t);
  await assert.rejects(runAgent({ ...options, prompt: 'Edit it', details: { capabilities: ['completion'] } }), /cannot use project tools/);
  options.store.data.mode = 'chat';
  await assert.rejects(runAgent({ ...options, prompt: 'Describe', images: [{ base64: 'AAAA', name: 'photo.png' }], details: { capabilities: ['completion'] } }), /image support/);
  assert.equal(options.store.session().messages.length, 0);
});
test('vision sends image bytes, saves names and removes images when switching to a text model', async t => {
  const options = await setup(t); options.store.data.mode = 'chat'; let request;
  await runAgent({ ...options, prompt: 'Describe this', images: [{ base64: 'AAAA', name: 'photo.png' }], details: { capabilities: ['vision'] }, fetcher: async (_url, body) => { request = JSON.parse(body.body); return response({ content: 'An image.' }); } });
  assert.deepEqual(request.messages.at(-1).images, ['AAAA']); assert.equal(request.tools, undefined);
  const reloaded = new Store(path.join(options.root, 'state'));
  assert.deepEqual(reloaded.session().messages[0].imageNames, ['photo.png']);
  const textContext = contextMessages(reloaded.session().messages, 44000, false);
  assert.equal(textContext.messages[0].images, undefined);
  assert.equal(reloaded.session().messages[0].images[0], 'AAAA');
  assert.equal(reloaded.session().messages.at(-1).metrics.tokensPerSecond, 5);
});
test('old state gets tool preferences without losing saved conversations', async t => {
  const options = await setup(t); options.store.session().messages.push({ role: 'user', content: 'Keep me' });
  delete options.store.data.enabledTools; delete options.store.data.contextSize; options.store.save();
  const migrated = new Store(path.join(options.root, 'state'));
  assert.equal(migrated.session().messages[0].content, 'Keep me'); assert.equal(migrated.data.enabledTools.length, require('../app/tools.cjs').definitions.length); assert.equal(migrated.data.contextSize, 16384);
});
test('model information comes from show, including missing capabilities', async () => {
  const fetcher = async url => new Response(JSON.stringify(url.endsWith('/tags') ? { models: [{ name: 'working' }, { name: 'gone' }] } : { capabilities: ['tools', 'vision'], details: { parameter_size: '12B' }, model_info: { 'fixture.context_length': 32768 } }));
  assert.equal((await modelDetails('working', fetcher)).contextLength, 32768);
  const models = await getModels(async (url, request) => { if (url.endsWith('/show') && JSON.parse(request.body).model === 'gone') return new Response('', { status: 404 }); return fetcher(url); });
  assert.deepEqual(models[0].capabilities, ['tools', 'vision']); assert.equal(models[1].capabilities, null);
});
test('an incomplete or error stream never looks like a completed response', async () => {
  await assert.rejects(streamChat({}, undefined, () => {}, async () => new Response('{"message":{"content":"partial"}}\n')), /ended.*early/);
  await assert.rejects(streamChat({}, undefined, () => {}, async () => new Response('{"error":"out of memory"}\n')), /out of memory/);
});
test('command output returns to the model, drives a follow-up command and persists in the same chat', async t => {
  const options = await setup(t);
  options.store.data.enabledTools = ['command_start', 'command_read', 'command_save_output', 'write_file'];
  let step = 0, first, second;
  const call = (name, args) => response({ content: '', tool_calls: [{ function: { name, arguments: args } }] });
  await runAgent({ ...options, prompt: 'Inspect, follow up and save evidence', details: { capabilities: ['tools'], contextLength: 32768 }, fetcher: async (_url, request) => {
    const body = JSON.parse(request.body), last = body.messages.at(-1);
    switch (step++) {
      case 0: return call('command_start', { command: 'print initial-observation' });
      case 1: first = JSON.parse(last.content).session_id; return call('command_read', { session_id: first });
      case 2: assert.match(JSON.parse(last.content).output, /initial-observation/); return call('command_start', { command: 'print follow-up-evidence' });
      case 3: second = JSON.parse(last.content).session_id; return call('command_read', { session_id: second });
      case 4: assert.match(JSON.parse(last.content).output, /follow-up-evidence/); return call('command_save_output', { session_id: second, path: 'output.json' });
      case 5: return call('write_file', { path: 'findings.md', content: 'Reviewed initial observation and follow-up evidence.' });
      default: return response({ content: 'Review complete; evidence and findings saved.' });
    }
  } });
  assert.match(await fs.readFile(path.join(options.root, 'output.json'), 'utf8'), /follow-up-evidence/);
  assert.match(await fs.readFile(path.join(options.root, 'findings.md'), 'utf8'), /Reviewed/);
  const reloaded = new Store(path.join(options.root, 'state'));
  assert.equal(reloaded.session().messages.filter(m => m.role === 'tool').length, 6);
  assert.match(reloaded.session().messages.at(-1).content, /Review complete/);
});
