const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { Credentials } = require('../app/credentials.cjs');
const { providers, customSettings } = require('../app/providers.cjs');
const { cloudModels, streamCloud, completionMessages, anthropicMessages } = require('../app/cloud.cjs');
const { contextMessages, runAgent } = require('../app/agent.cjs');
const { Store } = require('../app/store.cjs');
const fixtures = require('./provider-fixtures.cjs');
const encryption = { isEncryptionAvailable: () => true, encryptString: s => Buffer.from(s).map(byte => byte ^ 31), decryptString: b => Buffer.from(b).map(byte => byte ^ 31).toString() };
async function directory(t) { const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-providers-')); t.after(() => fs.rm(dir, { recursive: true, force: true })); return dir; }
const base = { model: 'fixture', messages: [{ role: 'user', content: 'Read it' }], instructions: 'Rules', tools: [], token: 'fixture-secret', onToken: () => {}, signal: new AbortController().signal };
test('provider keys migrate, remain isolated and survive reload without appearing in snapshots', async t => {
  const dir = await directory(t);
  await fs.writeFile(path.join(dir, 'credentials.enc'), encryption.encryptString(JSON.stringify({ apiKey: 'sk-legacy', accounts: [], hostId: 'urn:uuid:legacy' })));
  const credentials = new Credentials(dir, encryption); assert.equal(credentials.key('openai'), 'sk-legacy');
  for (const provider of ['xai', 'deepseek', 'anthropic', 'gemini', 'groq', 'mistral', 'openrouter', 'custom']) credentials.setKey(`${provider}-private-secret`, provider);
  const reloaded = new Credentials(dir, encryption); assert.equal(reloaded.key('anthropic'), 'anthropic-private-secret'); assert.equal(reloaded.key('openai'), 'sk-legacy');
  reloaded.setKey('', 'xai'); assert.equal(reloaded.key('xai'), ''); assert.equal(reloaded.key('deepseek'), 'deepseek-private-secret');
  assert.doesNotMatch(JSON.stringify(reloaded.snapshot()), /private-secret|sk-legacy|hostId/);
  assert.throws(() => reloaded.setKey('key\nheader', 'gemini'), /valid/); assert.throws(() => reloaded.setKey('a', 'chatgpt'), /does not use/);
  reloaded.encryption = { isEncryptionAvailable: () => false }; assert.throws(() => reloaded.setKey('replacement', 'deepseek'), /encryption/); assert.equal(reloaded.key('deepseek'), 'deepseek-private-secret');
});
test('custom endpoints accept only explicit safe URLs and capabilities', () => {
  for (const baseURL of ['http://example.com/v1', 'https://user:password@example.com/v1', 'https://example.com/v1?key=secret', 'file:///tmp/model', 'https://example.com/#token']) assert.throws(() => customSettings({ baseURL, model: 'fixture' }));
  assert.deepEqual(customSettings({ baseURL: 'http://127.0.0.1:1234/v1/', model: 'local-model', tools: true, vision: 'true' }), { baseURL: 'http://127.0.0.1:1234/v1', model: 'local-model', tools: true, vision: false });
});
test('each provider uses its own model endpoint, authentication and capability metadata', async () => {
  for (const [provider, catalog] of Object.entries(fixtures.catalogs)) {
    const models = await cloudModels(provider, 'private-key', {}, async (url, options) => {
      assert.ok(url.startsWith(providers[provider].baseURL)); assert.equal(options.redirect, 'error');
      if (provider === 'anthropic') { assert.equal(options.headers['x-api-key'], 'private-key'); assert.equal(options.headers.Authorization, undefined); }
      else assert.equal(options.headers.Authorization, 'Bearer private-key');
      return new Response(JSON.stringify(catalog));
    });
    assert.equal(models.length, 1, provider); assert.ok(models[0].capabilities.includes('tools'), provider);
    assert.equal(models[0].capabilities.includes('vision'), provider !== 'deepseek', provider);
  }
  let pages = 0;
  const catalog = await cloudModels('anthropic', 'key', {}, async url => { pages++; if (pages === 2) assert.match(url, /after_id=claude-first/); return new Response(JSON.stringify({ data: [{ id: pages === 1 ? 'claude-first' : 'claude-second' }], has_more: pages === 1, last_id: 'claude-first' })); });
  assert.equal(catalog.length, 2);
});
test('DeepSeek reasoning, Gemini signatures and complete tool results persist across context trimming', async () => {
  for (const provider of ['deepseek', 'gemini', 'groq', 'mistral', 'openrouter']) {
    const message = await streamCloud({ ...base, provider, fetcher: async (url, options) => { assert.equal(url, providers[provider].baseURL + '/chat/completions'); assert.equal(options.headers.Authorization, 'Bearer fixture-secret'); return fixtures.completion({ name: 'read_file', args: { path: 'README.md' } }); } });
    const history = contextMessages([...base.messages, message, { role: 'tool', tool_name: 'read_file', content: 'file evidence' }], 10).messages;
    const request = completionMessages(history, provider);
    assert.equal(request[1].reasoning_content, 'fixture reasoning'); assert.equal(request[1].tool_calls[0].extra_content.google.thought_signature, 'opaque-fixture'); assert.equal(request[2].tool_call_id, 'call_fixture');
    const switched = completionMessages(history, 'another-provider'); assert.doesNotMatch(JSON.stringify(switched), /opaque-fixture|fixture reasoning|call_fixture/); assert.match(JSON.stringify(switched), /file evidence/);
  }
});
test('Claude native blocks, parallel tool results, thinking signatures and image inputs are retained', async () => {
  const message = await streamCloud({ ...base, provider: 'anthropic', messages: [{ role: 'user', content: 'Read image', images: ['AAAA'] }], fetcher: async (url, options) => {
    assert.equal(url, 'https://api.anthropic.com/v1/messages'); const body = JSON.parse(options.body); assert.equal(body.messages[0].content[1].source.media_type, 'image/png'); assert.equal(body.system, 'Rules'); return fixtures.anthropic({ name: 'read_file', args: { path: 'README.md' } });
  } });
  message.anthropicOutput.unshift({ type: 'thinking', thinking: 'opaque state', signature: 'signed' });
  message.anthropicOutput.push({ type: 'tool_use', id: 'tool_second', name: 'list_files', input: {} });
  const history = contextMessages([...base.messages, message, { role: 'tool', tool_name: 'read_file', content: 'Error: denied' }, { role: 'tool', tool_name: 'list_files', content: 'files' }], 10).messages;
  const input = anthropicMessages(history); assert.equal(input[1].content[0].signature, 'signed'); assert.equal(input[2].content.length, 2); assert.equal(input[2].content[0].is_error, true); assert.equal(input[2].content[1].tool_use_id, 'tool_second');
});
test('partial, token-limited and error streams never execute a provider tool call', async () => {
  for (const provider of ['deepseek', 'anthropic']) {
    const complete = await (provider === 'anthropic' ? fixtures.anthropic({ name: 'write_file', args: {} }) : fixtures.completion({ name: 'write_file', args: {} })).text();
    await assert.rejects(streamCloud({ ...base, provider, fetcher: async () => new Response(complete.replace(/data: \[DONE\]\n\n|data: \{"type":"message_stop"\}\n\n/, '')) }), /before confirming/);
    await assert.rejects(streamCloud({ ...base, provider, fetcher: async () => provider === 'anthropic' ? fixtures.anthropic({ name: 'write_file', args: {} }, '', 'max_tokens') : fixtures.completion({ name: 'write_file', args: {} }, '', 'length') }), /stopped with/);
    await assert.rejects(streamCloud({ ...base, provider, fetcher: async () => new Response('', { status: 401 }) }), /authentication/);
  }
});
test('all new providers enforce real edit review and return denial through their native tool protocol', async t => {
  for (const provider of ['xai', 'deepseek', 'anthropic', 'gemini', 'groq', 'mistral', 'openrouter', 'custom']) {
    const dir = await directory(t), store = new Store(path.join(dir, 'data')); store.addProject(dir); store.data.provider = provider; store.data.model = 'fixture'; store.data.cloudProjects = [store.data.activeProject];
    store.data.customProvider = { baseURL: 'http://127.0.0.1:1234/v1', model: 'fixture', tools: true, vision: false };
    let count = 0, approvals = 0;
    await runAgent({ store, prompt: 'Write a file', details: { capabilities: ['tools'] }, signal: new AbortController().signal, emit: () => {}, approve: async () => { approvals++; return false; }, cloudToken: async () => 'fixture-key', fetcher: async (url, options) => {
      const body = JSON.parse(options.body); count++;
      if (count === 2) assert.match(JSON.stringify(body), /User declined this file edit/);
      const call = count === 1 ? { name: 'write_file', args: { path: 'denied.txt', content: 'must not save' } } : null;
      return provider === 'xai' ? fixtures.responses(call) : provider === 'anthropic' ? fixtures.anthropic(call) : fixtures.completion(call);
    } });
    assert.equal(approvals, 1, provider); assert.equal(count, 2, provider); await assert.rejects(fs.access(path.join(dir, 'denied.txt')));
  }
});
test('a custom endpoint change strips old endpoint signatures but retains textual evidence', async () => {
  const custom = { baseURL: 'http://127.0.0.1:1234/v1', model: 'fixture', tools: true, vision: false };
  const message = await streamCloud({ ...base, provider: 'custom', custom, fetcher: async () => fixtures.completion({ name: 'read_file', args: {} }) });
  const input = completionMessages([message, { role: 'tool', content: 'evidence', tool_name: 'read_file' }], 'custom', 'https://other.example/v1');
  assert.doesNotMatch(JSON.stringify(input), /opaque-fixture|call_fixture/); assert.match(JSON.stringify(input), /evidence/);
});
test('split UTF-8/CRLF, streamed arguments and OpenRouter reasoning fragments preserve complete records', async () => {
  const events = [
    { choices: [{ index: 0, delta: { content: '夜', reasoning_details: [{ index: 0, type: 'reasoning.text', text: 'first ' }], tool_calls: [{ index: 0, id: 'call_split', function: { name: 'read_file', arguments: '{"path":' } }] } }] },
    { choices: [{ index: 0, delta: { reasoning_details: [{ index: 0, type: 'reasoning.text', text: 'second' }], tool_calls: [{ index: 0, function: { arguments: '"README.md"}' } }] } }] },
    { choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }] },
  ];
  const bytes = new TextEncoder().encode((await fixtures.sse(events, true).text()).replaceAll('\n', '\r\n'));
  let streamed = '';
  const message = await streamCloud({ ...base, provider: 'openrouter', onToken: text => streamed += text, fetcher: async () => new Response(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close(); } })) });
  assert.equal(streamed, '夜'); assert.equal(message.chatOutput.reasoning_details.length, 1); assert.equal(message.chatOutput.reasoning_details[0].text, 'first second'); assert.deepEqual(JSON.parse(message.tool_calls[0].function.arguments), { path: 'README.md' });
});
test('Mistral thinking chunks survive continuation while only answer text is displayed', async () => {
  let text = '';
  const message = await streamCloud({ ...base, provider: 'mistral', onToken: part => text += part, fetcher: async () => fixtures.sse([
    { choices: [{ index: 0, delta: { content: [{ type: 'thinking', thinking: [{ type: 'text', text: 'private reasoning' }] }, { type: 'text', text: 'The answer ' }] } }] },
    { choices: [{ index: 0, delta: { content: 'is 42.' }, finish_reason: 'stop' }] },
  ], true) });
  assert.equal(text, 'The answer is 42.'); assert.equal(message.content, text); assert.equal(message.chatOutput.content[0].type, 'thinking'); assert.equal(completionMessages([message], 'mistral')[0].content[0].thinking[0].text, 'private reasoning');
});
test('switching back to Ollama retains cloud evidence without foreign metadata or malformed calls', async t => {
  const dir = await directory(t), store = new Store(path.join(dir, 'data')); store.addProject(dir); store.data.model = 'local-fixture';
  store.session().messages.push({ role: 'user', content: 'Prior question' }, { role: 'assistant', provider: 'deepseek', content: '', chatOutput: { reasoning_content: 'private-state' }, tool_calls: [{ call_id: 'foreign-call', function: { name: 'write_file', arguments: '{malformed' } }] }, { role: 'tool', tool_name: 'write_file', content: 'Error: malformed argument' });
  await runAgent({ store, prompt: 'Explain the result', details: { capabilities: ['tools'] }, signal: new AbortController().signal, emit: () => {}, fetcher: async (url, options) => {
    assert.match(url, /127.0.0.1:11434/); const body = JSON.parse(options.body); assert.match(JSON.stringify(body.messages), /Error: malformed argument/); assert.doesNotMatch(JSON.stringify(body.messages), /private-state|foreign-call|malformed"|chatOutput/);
    return new Response(JSON.stringify({ message: { role: 'assistant', content: 'The previous action failed.' }, done: true }) + '\n');
  } });
});
