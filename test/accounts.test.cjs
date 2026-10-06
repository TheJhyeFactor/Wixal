const test = require('node:test');
const assert = require('node:assert/strict');
const { Accounts, preferences } = require('../app/accounts.cjs');
const config = { projectId: 'wixal-test', apiKey: 'public-test' };
const setup = { ui: { theme: 'sakura', textSize: 13, reduceMotion: false, sidebarCollapsed: false }, contextSize: 8192, autoSummary: true, mode: 'agent', enabledTools: ['run_command'], personalApprovalMode: 'review' };
function fixture() {
  let verified = false; const calls = [], docs = new Map();
  const credentials = { data: {}, save() {} };
  const accounts = new Accounts(credentials, config, async (url, options) => {
    const body = options.body ? JSON.parse(options.body) : null; calls.push({ url, options, body });
    let result = {};
    if (url.includes('signInWithPassword') || url.includes('signUp')) result = { localId: 'user-one', email: 'test@example.com', idToken: 'private-id-token', refreshToken: 'private-refresh-token', expiresIn: '3600' };
    if (url.includes('lookup')) result = { users: [{ localId: 'user-one', email: 'test@example.com', displayName: 'Test', emailVerified: verified }] };
    if (url.includes('securetoken')) result = { id_token: 'refreshed-private-token', refresh_token: 'new-refresh', expires_in: '3600' };
    if (url.includes('firestore')) {
      const id = url.split('/').at(-1);
      if (options.method === 'PATCH') docs.set(id, { name: 'users/user-one/presets/' + id, ...body });
      if (options.method === 'GET') result = { documents: [...docs.values()] };
      if (options.method === 'DELETE') docs.delete(id);
    }
    return { ok: true, status: 200, json: async () => result };
  });
  return { accounts, calls, credentials, verify: () => { verified = true; } };
}
test('Firebase accounts keep tokens private and deny cloud features until email verification', async () => {
  const f = fixture();
  await f.accounts.authenticate('create', { email: 'test@example.com', password: 'test-password-123', name: 'Test' });
  assert.equal(f.accounts.snapshot().profile.verified, false);
  assert.ok(f.calls.some(c => c.body?.requestType === 'VERIFY_EMAIL'));
  assert.doesNotMatch(JSON.stringify(f.accounts.snapshot()), /private-|refreshToken|idToken|password/);
  await assert.rejects(f.accounts.savePreset('Focus', { data: setup }), /Verify your email/);
  f.verify(); await f.accounts.verify();
  await f.accounts.savePreset('Focus', { data: setup });
  assert.equal(f.accounts.snapshot().presets.length, 1);
  const upload = f.calls.find(c => c.options.method === 'PATCH' && c.url.includes('firestore'));
  assert.doesNotMatch(JSON.stringify(upload.body), /enabledTools|approval|messages|root/);
  const store = { data: structuredClone(setup), save() {} }; store.data.ui.theme = 'paper';
  f.accounts.applyPreset(f.accounts.presets[0].id, store);
  assert.equal(store.data.ui.theme, 'sakura'); assert.deepEqual(store.data.enabledTools, ['run_command']); assert.equal(store.data.personalApprovalMode, 'review');
  await f.accounts.deletePreset(f.accounts.presets[0].id); assert.equal(f.accounts.presets.length, 0);
  f.accounts.signOut(); assert.equal(f.credentials.data.wixalAccount, null);
  await assert.rejects(f.accounts.sync(), /Verify/);
});
test('restored Firebase sessions require server lookup and renew expired tokens', async () => {
  const f = fixture(); await f.accounts.authenticate('sign-in', { email: 'test@example.com', password: 'password' });
  f.credentials.data.wixalAccount.expiresAt = 0;
  const restored = new Accounts(f.credentials, config, f.accounts.request);
  assert.equal(restored.snapshot().signedIn, false); await restored.restore(); assert.equal(restored.snapshot().signedIn, true);
  assert.ok(f.calls.some(c => c.url.includes('securetoken')));
  const offline = new Accounts(f.credentials, config, async () => { throw new Error('offline'); });
  await offline.restore(); assert.equal(offline.snapshot().signedIn, false); assert.match(offline.snapshot().message, /Cannot reach/);
});
test('invalid accounts and cloud payloads cannot mutate local settings', async () => {
  const f = fixture();
  await assert.rejects(f.accounts.authenticate('create', { email: 'bad', password: 'password' }), /email/);
  assert.equal(f.calls.length, 0);
  assert.throws(() => preferences({ ...setup, ui: { ...setup.ui, theme: '<script>' } }), /Invalid/);
  f.credentials.save = () => { throw new Error('Keychain unavailable'); };
  await assert.rejects(f.accounts.authenticate('sign-in', { email: 'test@example.com', password: 'password' }), /Keychain/);
  assert.equal(f.credentials.data.wixalAccount, undefined);
});

test('account presets accept small contexts and clamp legacy large windows to the app ceiling', () => {
  assert.equal(preferences({ ...setup, contextSize: 4096 }).contextSize, 4096);
  assert.equal(preferences({ ...setup, contextSize: 131072 }).contextSize, 32768);
});
