const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { executeTool } = require('../app/tools.cjs');
const { stopAllCommands } = require('../app/command-sessions.cjs');
async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-command-'));
  t.after(async () => { stopAllCommands(); await fs.rm(root, { recursive: true, force: true }); });
  return { root, approve: async () => true };
}
async function finished(id, context) {
  for (let i = 0; i < 100; i++) {
    const result = JSON.parse(await executeTool('command_read', { session_id: id }, context));
    if (result.state !== 'running') return result;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  throw new Error('Command did not finish');
}
test('AI command sessions expose real output, accept stdin and save evidence', async t => {
  const context = await fixture(t);
  const started = JSON.parse(await executeTool('command_start', { command: 'read answer; print "result:$answer"; print problem >&2; exit 7' }, context));
  await executeTool('command_write', { session_id: started.session_id, input: 'hello\n' }, context);
  const result = await finished(started.session_id, context);
  assert.equal(result.exitCode, 7); assert.match(result.output, /result:hello/); assert.match(result.output, /problem/);
  await executeTool('command_save_output', { session_id: started.session_id, path: 'evidence.json' }, context);
  const saved = JSON.parse(await fs.readFile(path.join(context.root, 'evidence.json'), 'utf8'));
  assert.equal(saved.exitCode, 7); assert.equal(saved.output, result.output);
  await assert.rejects(executeTool('command_read', { session_id: started.session_id }, { ...context, root: os.tmpdir() }), /unavailable/);
  await assert.rejects(executeTool('command_save_output', { session_id: started.session_id, path: '../escape.json' }, context), /outside/);
});
test('command tools honor enablement, decline, cancellation and output offsets', async t => {
  const context = await fixture(t);
  await assert.rejects(executeTool('command_start', { command: 'true' }, { ...context, allowedTools: [] }), /switched off/);
  assert.match(await executeTool('command_start', { command: 'touch declined' }, { ...context, approve: async () => false }), /declined/);
  await assert.rejects(fs.access(path.join(context.root, 'declined')));
  const started = JSON.parse(await executeTool('command_start', { command: 'print ready; sleep 20' }, context));
  await new Promise(resolve => setTimeout(resolve, 100));
  const chunk = JSON.parse(await executeTool('command_read', { session_id: started.session_id }, context));
  assert.match(chunk.output, /ready/);
  const next = JSON.parse(await executeTool('command_read', { session_id: started.session_id, offset: chunk.next_offset }, context));
  assert.equal(next.output, '');
  await executeTool('command_stop', { session_id: started.session_id }, context);
  assert.equal((await finished(started.session_id, context)).reason, 'cancelled');
});
