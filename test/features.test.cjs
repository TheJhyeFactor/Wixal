const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { Store } = require('../app/store.cjs');
const { runAgent } = require('../app/agent.cjs');
const { compactSession, searchHistory, projectMemory } = require('../app/context.cjs');
const { executeTool } = require('../app/tools.cjs');
const { executeNetwork } = require('../app/network.cjs');
const { Extensions, serverConfig } = require('../app/extensions.cjs');
const { pullModel } = require('../app/models.cjs');
async function setup(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-features-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const store = new Store(path.join(root, 'data')); store.addProject(root); store.data.model = 'fixture';
  return { root, store, signal: new AbortController().signal, emit: () => {}, approve: async () => true };
}
const response = content => new Response(JSON.stringify({ message: typeof content === 'string' ? { content } : content, done: true }));
test('automatic summaries use the selected model, survive restart, and preserve full history', async t => {
  const options = await setup(t); options.store.data.contextSize = 8192;
  options.store.session().messages = [{ role: 'user', content: 'Project codename moon-orchid. '.repeat(400) }, { role: 'assistant', content: 'Decision: use pnpm. '.repeat(300) }];
  const requests = [];
  await runAgent({ ...options, prompt: 'Continue the work', details: { capabilities: ['tools'], contextLength: 8192 }, fetcher: async (_url, request) => {
    const body = JSON.parse(request.body); requests.push(body);
    return response(body.messages[0].content.startsWith('Summarize') ? 'Project codename moon-orchid; use pnpm.' : 'Continuing with pnpm.');
  } });
  const saved = new Store(path.join(options.root, 'data')).session();
  assert.equal(saved.summary.count, 2); assert.equal(saved.summary.method, 'model');
  assert.match(requests.at(-1).messages[1].content, /moon-orchid/);
  assert.equal(saved.messages[0].content, 'Project codename moon-orchid. '.repeat(400));
  assert.equal(saved.messages.length, 4); assert.ok(requests.slice(0, -1).every(r => !r.tools));
});
test('summary cache, incremental updates, failure fallback and cancellation', async () => {
  const session = { messages: [{ role: 'user', content: 'Codename sapphire; use pnpm.' }, { role: 'assistant', content: 'Build failed.' }] };
  let calls = 0, saves = 0;
  const options = { session, omitted: 2, budget: 8000, summarize: async () => { calls++; return 'Codename sapphire; build failed.'; }, signal: new AbortController().signal, save: () => saves++, emit: () => {} };
  await compactSession(options); await compactSession(options); assert.equal(calls, 1); assert.equal(saves, 1);
  session.messages.push({ role: 'user', content: 'Next action: fix tests.' });
  await compactSession({ ...options, omitted: 3, summarize: async (previous, piece) => { assert.match(previous, /sapphire/); assert.match(piece, /fix tests/); throw new Error('offline'); } });
  assert.equal(session.summary.method, 'excerpts'); assert.match(session.summary.content, /sapphire/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(compactSession({ ...options, signal: controller.signal }), /Stopped/);
});
test('history and ranked memory are project scoped, and automatic memory saves require review', async t => {
  const options = await setup(t); const id = options.store.data.activeProject;
  options.store.remember('Unrelated preference. '.repeat(170)); options.store.remember('Use pnpm for sapphire builds.');
  assert.match(projectMemory(options.store, 'sapphire', 100), /pnpm/);
  options.store.session().messages.push({ role: 'user', content: 'sapphire build decision' });
  const second = path.join(options.root, 'second'); await fs.mkdir(second); options.store.addProject(second);
  options.store.session().messages.push({ role: 'user', content: 'sapphire secret other project' });
  options.store.selectProject(id);
  const found = searchHistory(options.store, 'sapphire'); assert.equal(found.length, 1); assert.doesNotMatch(JSON.stringify(found), /secret/);
  const args = { content: 'Keep this decision.' }, context = { ...options, allowedTools: ['save_memory'] };
  await executeTool('save_memory', args, { ...context, approve: async () => false }); assert.equal(options.store.data.memories.length, 2);
  await executeTool('save_memory', args, context); assert.equal(options.store.data.memories.length, 3);
});
test('network requests are opt-in, reviewed, bounded, cancellable and never follow redirects', async t => {
  const options = await setup(t); let fetched = 0;
  const context = { ...options, allowedTools: ['http_request'], fetcher: async (_url, request) => { fetched++; assert.equal(request.redirect, 'manual'); assert.equal(request.headers.Authorization, undefined); return new Response('<script>secret()</script><h1>Useful page</h1>', { headers: { 'content-type': 'text/html' } }); } };
  const args = { url: 'https://example.com' };
  await assert.rejects(executeTool('http_request', args, { ...context, allowedTools: [] }), /switched off/);
  assert.match(await executeTool('http_request', args, { ...context, approve: async () => false }), /declined/); assert.equal(fetched, 0);
  assert.match(await executeTool('http_request', args, context), /Useful page/); assert.equal(fetched, 1);
  await assert.rejects(executeNetwork('http_request', { url: 'https://user:secret@example.com' }, context), /credentials/);
  await assert.rejects(executeNetwork('http_request', { url: 'file:///etc/passwd' }, context), /HTTP/);
  await assert.rejects(executeNetwork('http_request', args, { ...context, fetcher: async () => new Response('', { status: 302, headers: { location: 'https://other.example' } }) }), /separate reviewed request/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(executeNetwork('http_request', args, { ...context, signal: controller.signal }), /Stopped/);
  const output = JSON.parse(await executeNetwork('http_request', args, { ...context, fetcher: async () => new Response('x'.repeat(1100000), { headers: { 'content-type': 'text/plain' } }) }));
  assert.equal(output.truncated, true); assert.ok(output.content.length <= 24000);
});
test('web search yields usable source URLs and reports service failures', async () => {
  const context = { approve: async request => { assert.equal(request.name, 'web_search'); assert.equal(request.query, 'hello world'); return true; }, fetcher: async url => { assert.match(url, /hello%20world/); return new Response('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fsource">Example &amp; result</a>', { headers: { 'content-type': 'text/html' } }); } };
  const result = JSON.parse(await executeNetwork('web_search', { query: 'hello world' }, context));
  assert.deepEqual(result.results[0], { title: 'Example & result', url: 'https://example.com/source' });
  await assert.rejects(executeNetwork('web_search', { query: 'hello world' }, { ...context, fetcher: async () => new Response('bot challenge') }), /no readable results/);
});
test('file offsets expose subsequent chunks without losing original data', async t => {
  const options = await setup(t); await fs.writeFile(path.join(options.root, 'large.txt'), 'a'.repeat(24000) + 'final chunk');
  assert.match(await executeTool('read_file', { path: 'large.txt' }, options), /next offset: 24000/);
  assert.equal(await executeTool('read_file', { path: 'large.txt', offset: 24000 }, options), 'final chunk');
  await assert.rejects(executeTool('read_file', { path: 'large.txt', offset: -1 }, options), /Offset/);
});
test('model downloads parse progress, require completion and propagate failures', async () => {
  const progress = [];
  await pullModel('qwen3:8b', undefined, event => progress.push(event), async (_url, req) => { assert.equal(JSON.parse(req.body).model, 'qwen3:8b'); return new Response('{"status":"pulling","total":100,"completed":50}\n{"status":"success"}\n'); });
  assert.equal(progress[0].completed, 50); assert.equal(progress.at(-1).status, 'success');
  await assert.rejects(pullModel('bad model', undefined, () => {}), /valid/);
  await assert.rejects(pullModel('qwen3:8b', undefined, () => {}, async () => new Response('{"status":"pulling"}')), /ended early/);
  await assert.rejects(pullModel('qwen3:8b', undefined, () => {}, async () => new Response('{"error":"disk full"}')), /disk full/);
});
test('MCP tools connect to a real stdio process, honor approvals and disconnect cleanly', async t => {
  const options = await setup(t), extensions = new Extensions(); t.after(() => extensions.close());
  const server = path.join(options.root, 'server.cjs');
  const sdk = path.resolve(__dirname, '../node_modules/@modelcontextprotocol/sdk/dist/cjs/server/index.js');
  const transport = path.resolve(__dirname, '../node_modules/@modelcontextprotocol/sdk/dist/cjs/server/stdio.js');
  const types = path.resolve(__dirname, '../node_modules/@modelcontextprotocol/sdk/dist/cjs/types.js');
  await fs.writeFile(server, `const {Server}=require(${JSON.stringify(sdk)}); const {StdioServerTransport}=require(${JSON.stringify(transport)}); const {ListToolsRequestSchema,CallToolRequestSchema}=require(${JSON.stringify(types)}); const server=new Server({name:'fixture',version:'1'}, {capabilities:{tools:{}}}); server.setRequestHandler(ListToolsRequestSchema,async()=>({tools:[{name:'echo',description:'Echo a value',inputSchema:{type:'object',properties:{text:{type:'string'}},required:['text']}}]})); server.setRequestHandler(CallToolRequestSchema,async r=>({content:[{type:'text',text:r.params.arguments.text}]})); server.connect(new StdioServerTransport());`);
  assert.throws(() => serverConfig({ name: 'Bad', command: 'node', args: 'not array' }), /JSON array/);
  await extensions.connect({ id: 'fixture', ...serverConfig({ name: 'Echo server', command: process.execPath, args: [server] }) }, options.root);
  const name = extensions.definitions()[0].function.name;
  await assert.rejects(extensions.execute(name, { text: 'test' }, { ...options, allowedTools: [] }), /switched off/);
  assert.match(await extensions.execute(name, { text: 'test' }, { ...options, allowedTools: [name], approve: async () => false }), /declined/);
  assert.equal(await extensions.execute(name, { text: 'real MCP output' }, { ...options, allowedTools: [name] }), 'real MCP output');
  options.store.data.enabledTools = [name]; let requests = 0;
  await runAgent({ ...options, prompt: 'Echo', details: { capabilities: ['tools'] }, extensions, fetcher: async (_url, req) => { requests++; assert.equal(JSON.parse(req.body).tools[0].function.name, name); return response(requests === 1 ? { content: '', tool_calls: [{ function: { name, arguments: { text: 'agent invoked real MCP' } } }] } : 'Done'); } });
  assert.equal(options.store.session().messages.find(m => m.role === 'tool').content, 'agent invoked real MCP');
  await extensions.disconnect('fixture'); assert.equal(extensions.definitions().length, 0);
  await assert.rejects(extensions.execute(name, { text: 'test' }, { ...options, allowedTools: [name] }), /disconnected/);
});
