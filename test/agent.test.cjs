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
  assert.equal(migrated.session().messages[0].content, 'Keep me'); assert.equal(migrated.data.enabledTools.length, require('../app/tools.cjs').definitions.length); assert.equal(migrated.data.contextSize, 8192);
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
  options.store.data.mode = 'chat';
  let step = 0, first, second;
  const call = (name, args) => response({ content: '', tool_calls: [{ function: { name, arguments: args } }] });
  await runAgent({ ...options, prompt: '@command_start inspect, follow up and save evidence', details: { capabilities: ['tools'], contextLength: 32768 }, fetcher: async (_url, request) => {
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

test('Chat advertises enabled tools without mentions and returns real file evidence', async t => {
  const options = await setup(t); options.store.data.mode = 'chat';
  options.store.data.enabledTools = ['read_file']; await fs.writeFile(path.join(options.root, 'proof.txt'), 'actual-file-evidence');
  let requests = 0;
  await runAgent({ ...options, prompt: 'Read proof.txt', details: { capabilities: ['tools'] }, fetcher: async (_url, request) => {
    const body = JSON.parse(request.body); requests++;
    assert.deepEqual(body.tools.map(t => t.function.name), ['read_file']);
    assert.match(body.messages[0].content, /Available tools in this request:\nread_file\n/);
    assert.doesNotMatch(body.messages[0].content, /No tools are available/);
    if (requests === 1) return response({ content: '', tool_calls: [{ function: { name: 'read_file', arguments: { path: 'proof.txt' } } }] });
    assert.equal(body.messages.at(-1).content, 'actual-file-evidence'); return response({ content: 'Read actual-file-evidence.' });
  } });
  assert.equal(requests, 2);
});
test('personal workspaces expose web and memory tools in Chat and Agent but omit project tools', async t => {
  const options = await setup(t); options.store.selectProject(null);
  for (const mode of ['chat', 'agent']) {
    options.store.data.mode = mode;
    await runAgent({ ...options, prompt: 'What tools can you use?', details: { capabilities: ['tools'] }, fetcher: async (_url, request) => {
      const body = JSON.parse(request.body);
      assert.deepEqual(body.tools.map(t => t.function.name), ['workspace_info', 'security_tools', 'browser_inspect', 'web_search', 'http_request', 'search_history', 'save_memory']);
      return response({ content: 'Web and memory tools are available.' });
    } });
  }
});
test('models without native tool support reject mentions before saving a turn', async t => {
  const options = await setup(t); options.store.data.mode = 'chat';
  await assert.rejects(runAgent({ ...options, prompt: '@list_files list the project', details: { capabilities: ['completion'] } }), /model marked Tools/);
  assert.equal(options.store.session().messages.length, 0);
});
test('empty tool output still reaches Ollama as a result of its call', async t => {
  const options = await setup(t); options.store.data.enabledTools = ['list_files']; const empty = path.join(options.root, 'empty'); await fs.mkdir(empty);
  let requests = 0;
  await runAgent({ ...options, prompt: 'List empty/', details: { capabilities: ['tools'] }, fetcher: async (_url, request) => {
    const body = JSON.parse(request.body);
    if (++requests === 1) return response({ content: '', tool_calls: [{ function: { name: 'list_files', arguments: { directory: 'empty' } } }] });
    assert.equal(body.messages.at(-1).role, 'tool'); assert.equal(body.messages.at(-1).content, '');
    return response({ content: 'The folder is empty.' });
  } });
  assert.equal(requests, 2);
});

test('successive report reads retain a useful newest evidence excerpt', async t => {
  const options = await setup(t); options.store.data.enabledTools = ['read_file']; options.store.data.autoSummary = false;
  await fs.writeFile(path.join(options.root, 'report.md'), 'EVIDENCE '.repeat(1200));
  let step = 0;
  await runAgent({ ...options, prompt: 'Read the report evidence', details: { capabilities: ['tools'], contextLength: 8192 }, fetcher: async (_url, request) => {
    const body = JSON.parse(request.body);
    if (step) {
      const latest = body.messages.at(-1);
      assert.equal(latest.role, 'tool');
      assert.ok(latest.content.length >= 1600, 'Newest report evidence must remain readable as tool history grows');
    }
    if (++step <= 8) return response({ content: '', tool_calls: [{ function: { name: 'read_file', arguments: { path: 'report.md', offset: 0 } } }] });
    return response({ content: 'Assessment complete.' });
  } });
  assert.equal(step, 9);
  assert.equal(options.store.session().messages.filter(m => m.role === 'tool')[0].content.length, 10800, 'Full evidence remains in saved history');
});

test('an empty local generation retries a visible answer without running tools twice', async t => {
  const options = await setup(t); options.store.data.enabledTools = ['workspace_info']; let step = 0;
  await runAgent({ ...options, prompt: 'Inspect workspace', details: { capabilities: ['tools'], contextLength: 8192 }, fetcher: async (_url, request) => {
    const body = JSON.parse(request.body);
    if (++step === 1) return response({ content: '', tool_calls: [{ function: { name: 'workspace_info', arguments: {} } }] });
    assert.equal(body.messages.at(-1).role, 'tool');
    if (step === 2) return response({ content: '' });
    assert.equal(body.tools, undefined); assert.match(body.messages[0].content, /previous generation returned no visible answer/);
    return response({ content: 'The workspace was inspected; no further work was performed.' });
  } });
  assert.equal(step, 3); assert.equal(options.store.session().messages.filter(m => m.role === 'tool').length, 1);
  assert.match(options.store.session().messages.at(-1).content, /workspace was inspected/);
});
test('repeated empty local answers surface an error instead of a completed blank turn', async t => {
  const options = await setup(t); let requests = 0;
  await assert.rejects(runAgent({ ...options, prompt: 'Respond', details: { capabilities: ['tools'] }, fetcher: async () => { requests++; return response({ content: '' }); } }), /no visible answer/);
  assert.equal(requests, 2); assert.equal(options.store.session().messages.filter(m => m.role === 'assistant').length, 0);
});
