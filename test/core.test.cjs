const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { Store } = require('../app/store.cjs');
const { safePath, executeTool, runCommand } = require('../app/tools.cjs');
const { contextMessages, streamChat } = require('../app/agent.cjs');
async function temp(t) { const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-test-')); t.after(() => fs.rm(root, { recursive:true, force:true })); return root; }
test('projects, conversations and memories survive restart and stay separated', async t => {
  const root = await temp(t); const a = path.join(root, 'a'), b = path.join(root, 'b');
  await fs.mkdir(a); await fs.mkdir(b);
  const store = new Store(path.join(root, 'data'));
  store.addProject(a); const projectId = store.data.activeProject;
  store.remember('Use pnpm'); store.session().messages.push({ role:'user', content:'hello' }); store.save();
  store.addProject(b); assert.equal(store.session().messages.length, 0);
  const reloaded = new Store(path.join(root, 'data')); reloaded.selectProject(projectId);
  assert.equal(reloaded.session().messages[0].content, 'hello');
  assert.equal(reloaded.data.memories[0].projectId, projectId);
});
test('file tools block traversal, external symlinks and credentials', async t => {
  const root = await temp(t), outside = await temp(t);
  await fs.writeFile(path.join(outside, 'secret'), 'secret');
  await fs.symlink(outside, path.join(root, 'escape'));
  await assert.rejects(safePath(root, '../secret'));
  await assert.rejects(safePath(root, '.env'));
  await assert.rejects(safePath(root, '.env.local'));
  await assert.rejects(safePath(root, 'escape/secret'));
  await assert.rejects(safePath(root, 'escape/new', true));
  await fs.writeFile(path.join(root, '.env'), 'SECRET=protected');
  await fs.symlink(path.join(root, '.env'), path.join(root, 'innocent.txt'));
  await assert.rejects(safePath(root, 'innocent.txt'));
});
test('declined writes have no side effects; approved writes persist', async t => {
  const root = await temp(t), args = { path:'hello.txt', content:'wixal' };
  const result = await executeTool('write_file', args, { root, approve:async () => false });
  assert.match(result, /declined/); await assert.rejects(fs.access(path.join(root, 'hello.txt')));
  await executeTool('write_file', args, { root, approve:async () => true });
  assert.equal(await executeTool('read_file', { path:'hello.txt' }, { root }), 'wixal');
  assert.match(await executeTool('search_files', { query:'wixal' }, { root }), /hello.txt:1/);
});
test('edit approval detects external changes instead of overwriting them', async t => {
  const root = await temp(t), file = path.join(root, 'a.txt'); await fs.writeFile(file, 'before');
  await assert.rejects(executeTool('write_file', { path:'a.txt', content:'after' }, { root, approve:async () => { await fs.writeFile(file, 'external'); return true; } }), /changed during review/);
  assert.equal(await fs.readFile(file, 'utf8'), 'external');
});
test('shell approval is required and command exit status is returned', async t => {
  const root = await temp(t);
  await executeTool('run_command', { command:'touch denied' }, { root, approve:async () => false });
  await assert.rejects(fs.access(path.join(root, 'denied')));
  const result = JSON.parse(await runCommand('printf wixal; exit 7', root));
  assert.equal(result.output, 'wixal'); assert.equal(result.exitCode, 7);
});
test('cancellation terminates a running shell process', async t => {
  const root = await temp(t), controller = new AbortController();
  const pending = runCommand('sleep 20', root, controller.signal);
  setTimeout(() => controller.abort(), 100);
  const result = JSON.parse(await pending); assert.equal(result.stopped, true);
});
test('context trimming preserves whole tool exchanges', () => {
  const messages = [{ role:'user', content:'old'.repeat(30) }, { role:'assistant', content:'old answer' },
    { role:'user', content:'new' }, { role:'assistant', content:'', tool_calls:[{ function:{ name:'read_file' } }] }, { role:'tool', tool_name:'read_file', content:'contents' }];
  const result = contextMessages(messages, 200);
  assert.equal(result.messages[0].content, 'new'); assert.equal(result.messages.length, 3); assert.equal(result.omitted, 2);
});
test('Ollama NDJSON stream handles split UTF-8 bytes and tool calls', async () => {
  const payload = [{ message:{ content:'夜' } }, { message:{ content:' hello', tool_calls:[{ function:{ name:'list_files', arguments:{} } }] } }, { done:true }].map(JSON.stringify).join('\n');
  const bytes = new TextEncoder().encode(payload); let text = '';
  const fetcher = async () => new Response(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close(); } }));
  const result = await streamChat({}, undefined, token => text += token, fetcher);
  assert.equal(text, '夜 hello'); assert.equal(result.tool_calls[0].function.name, 'list_files');
});
