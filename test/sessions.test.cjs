const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Store } = require('../app/store.cjs');
const { runAgent } = require('../app/agent.cjs');
function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wixal-sessions-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const store = new Store(path.join(directory, 'data'));
  for (const name of ['a', 'b']) fs.mkdirSync(path.join(directory, name));
  const a = store.addProject(path.join(directory, 'a')), first = store.session();
  const b = store.addProject(path.join(directory, 'b')), other = store.session();
  store.selectProject(a.id);
  return { store, directory, a, b, first, other };
}
test('archives retain full history across restart, stay scoped and restore to the active list', t => {
  const { store, directory, a, b, first, other } = fixture(t);
  first.messages.push({ role: 'user', content: 'Keep my history', images: ['image-bytes'] });
  store.archiveSession(first.id);
  assert.notEqual(store.data.activeSession, first.id);
  const next = store.session().id;
  const reloaded = new Store(path.join(directory, 'data'));
  assert.deepEqual(reloaded.scopedSession(first.id).messages, first.messages);
  assert.ok(reloaded.scopedSession(first.id).archivedAt);
  reloaded.selectProject(b.id);
  for (const action of ['archiveSession', 'restoreSession', 'deleteSession', 'selectSession']) assert.throws(() => reloaded[action](first.id), /Unknown conversation/);
  assert.equal(reloaded.data.activeSession, other.id);
  reloaded.selectProject(a.id); assert.equal(reloaded.data.activeSession, next);
  reloaded.restoreSession(first.id); assert.equal(reloaded.data.activeSession, first.id);
  assert.equal(reloaded.session().archivedAt, undefined);
  assert.deepEqual(new Store(path.join(directory, 'data')).session().messages, first.messages);
});
test('deleting a conversation removes linked task copies while preserving unrelated data and a usable active chat', t => {
  const { store, directory, first, other } = fixture(t);
  store.remember('Keep this preference');
  store.data.tasks.push({ id: 'linked', sessionId: first.id, result: 'private response' }, { id: 'other', sessionId: other.id, result: 'keep this' });
  fs.writeFileSync(path.join(directory, 'a/proof.txt'), 'Keep this file');
  store.deleteSession(first.id);
  assert.ok(store.session()); assert.equal(store.session().projectId, first.projectId);
  assert.ok(!store.data.sessions.some(s => s.id === first.id));
  assert.deepEqual(store.data.tasks.map(t => t.id), ['other']);
  assert.equal(store.data.memories[0].content, 'Keep this preference');
  assert.equal(fs.readFileSync(path.join(directory, 'a/proof.txt'), 'utf8'), 'Keep this file');
  const reloaded = new Store(path.join(directory, 'data'));
  assert.ok(!JSON.stringify(reloaded.data).includes('private response'));
  assert.throws(() => store.deleteSession(first.id), /Unknown conversation/);
});
test('archived chats are readable but cannot send or append model turns before restoration', async t => {
  const { store, first } = fixture(t);
  store.archiveSession(first.id); store.selectSession(first.id);
  const saved = JSON.stringify(store.data);
  await assert.rejects(runAgent({ store, prompt: 'Do something', getDetails: () => { throw new Error('Model must not be contacted'); } }), /Restore this conversation/);
  assert.equal(JSON.stringify(store.data), saved);
});
