const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { Store } = require('../app/store.cjs');
const { Companion } = require('../app/companion.cjs');
const { Credentials } = require('../app/credentials.cjs');
const { ChatGPTAuth, verifyIdentity, matches } = require('../app/chatgpt-auth.cjs');
const { streamResponses, responseInput, cloudModels } = require('../app/openai.cjs');
const { runAgent } = require('../app/agent.cjs');
const encryption = { isEncryptionAvailable: () => true, encryptString: s => Buffer.from(s).map(byte => byte ^ 37), decryptString: b => Buffer.from(b).map(byte => byte ^ 37).toString() };
async function setup(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-connect-')); t.after(() => fs.rm(root, { recursive: true, force: true }));
  const store = new Store(path.join(root, 'state')); store.addProject(root);
  return { root, store, credentials: new Credentials(path.join(root, 'state'), encryption) };
}
function events(output, usage = { output_tokens: 12 }) { return new Response(`data: ${JSON.stringify({ type: 'response.output_text.delta', delta: '夜 hello' })}\n\ndata: ${JSON.stringify({ type: 'response.completed', response: { output, usage } })}\n\n`); }
test('credential snapshots never expose keys, tokens or host identifiers; file stays protected', async t => {
  const { root, credentials } = await setup(t); credentials.setKey('sk-private-fixture');
  credentials.data.accounts.push({ client_id: 'oaiapp_test', access_token: 'token-private', refresh_token: 'refresh-private', scopes: ['chatgpt.tokens.use.direct'], email: 'test@example.com' }); credentials.save();
  const snapshot = JSON.stringify(credentials.snapshot()); assert.doesNotMatch(snapshot, /sk-private|token-private|refresh-private|hostId/);
  assert.doesNotMatch(await fs.readFile(credentials.file, 'utf8'), /sk-private/); assert.equal((await fs.stat(credentials.file)).mode & 0o777, 0o600);
  const reloaded = new Credentials(path.join(root, 'state'), encryption); assert.equal(reloaded.data.apiKey, 'sk-private-fixture'); assert.equal(reloaded.data.hostId, credentials.data.hostId);
  const unavailable = new Credentials(root, { isEncryptionAvailable: () => false }); assert.throws(() => unavailable.setKey('sk-reject'), /encryption/);
});
test('Responses handles byte-split SSE, preserves reasoning and tool IDs, rejects failed or interrupted streams', async () => {
  const output = [{ type: 'reasoning', id: 'r1', encrypted_content: 'opaque', summary: [] }, { type: 'function_call', id: 'f1', call_id: 'call_1', name: 'read_file', namespace: 'wixal', arguments: '{"path":"README.md"}' }];
  const base = { model: 'fixture', messages: [{ role: 'user', content: 'Read it', images: ['AAAA'] }], instructions: 'Rules', tools: [], provider: 'chatgpt', token: 'secret', onToken: () => {} };
  let body, streamed = '';
  const message = await streamResponses({ ...base, onToken: token => streamed += token, fetcher: async (_url, request) => {
    body = JSON.parse(request.body); const bytes = new TextEncoder().encode(await events(output).text());
    return new Response(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close(); } }));
  } });
  assert.equal(streamed, '夜 hello'); assert.equal(body.store, false); assert.equal(body.stream, true); assert.equal(body.input[0].content[1].type, 'input_image');
  assert.equal(message.responseOutput[0].encrypted_content, 'opaque'); assert.equal(message.tool_calls[0].call_id, 'call_1');
  const input = responseInput([base.messages[0], message, { role: 'tool', tool_name: 'read_file', content: 'contents' }], 'chatgpt');
  assert.equal(input.at(-1).call_id, 'call_1'); assert.equal(input.at(-1).output, 'contents');
  const switched = responseInput([message, { role: 'tool', tool_name: 'read_file', content: 'local evidence' }], 'openai'); assert.match(switched.at(-1).content, /local evidence/);
  await assert.rejects(streamResponses({ ...base, fetcher: async () => new Response('data: {"type":"response.output_text.delta","delta":"partial"}\n\n') }), /before confirming/);
  await assert.rejects(streamResponses({ ...base, fetcher: async () => new Response('data: {"type":"response.failed","response":{"error":{"code":"subscription_sharing_usage_limit_exceeded"}}}\n\n') }), /usage limit/);
  await assert.rejects(streamResponses({ ...base, fetcher: async () => new Response('data: {"type":"response.incomplete"}\n\n') }), /incomplete/);
});
test('local agent rejects cloud inference even when historical cloud sharing was enabled', async t => {
  for (const provider of ['openai', 'chatgpt']) {
    const { store } = await setup(t); store.data.provider = provider; store.data.model = 'fixture'; store.data.cloudProjects = [store.data.activeProject];
    await assert.rejects(runAgent({ store, prompt: 'Do it', emit: () => {}, fetcher: async () => assert.fail('No provider request is allowed') }), /only with its local engine/);
    assert.equal(store.session().messages.length, 0);
  }
});
test('ChatGPT account model catalogs preserve visibility, slugs and ordering', async () => {
  const models = await cloudModels('chatgpt', 'fixture', async () => new Response(JSON.stringify({ models: [{ slug: 'second', display_name: 'Second', visibility: 'list' }, { slug: 'hidden', visibility: 'hide' }, { slug: 'first', display_name: 'First', visibility: 'list' }] })));
  assert.deepEqual(models.map(m => m.name), ['second', 'first']); assert.equal(models[0].displayName, 'Second');
});
test('companion blocks unauthenticated/browser traffic, revokes sharing, protects credentials and queues without execution', async t => {
  const { store, root } = await setup(t), companion = new Companion(store, path.join(root, 'state'));
  await companion.start(); t.after(() => companion.stop());
  assert.deepEqual(await companion.call('list_projects', {}), []);
  const projectId = store.data.activeProject; store.data.companion.sharedProjects = [projectId];
  await fs.writeFile(path.join(root, 'README.md'), 'project text'); await fs.writeFile(path.join(root, '.env'), 'SECRET');
  assert.equal((await companion.call('read_project_file', { projectId, path: 'README.md' })).result, 'project text');
  await assert.rejects(companion.call('read_project_file', { projectId, path: '.env' }));
  await assert.rejects(companion.call('read_project_file', { projectId, path: 'state/wixal-connection.json' }));
  store.remember('Private memory'); assert.equal((await companion.call('get_project_context', { projectId })).memories, undefined);
  const queued = await companion.call('create_task', { projectId, title: 'Task', prompt: 'touch should-not-exist' });
  assert.equal((await companion.call('get_task_status', { taskId: queued.id })).status, 'queued'); await assert.rejects(fs.access(path.join(root, 'should-not-exist')));
  assert.equal((await fetch(`${companion.endpoint}/bridge`, { method: 'POST', body: '{}' })).status, 401);
  const config = JSON.parse(await fs.readFile(companion.file, 'utf8'));
  assert.equal((await fetch(`${companion.endpoint}/bridge`, { method: 'POST', headers: { Authorization: `Bearer ${config.token}`, Origin: 'http://malicious.example' }, body: '{}' })).status, 403);
  store.data.companion.sharedProjects = []; await assert.rejects(companion.call('get_task_status', { taskId: queued.id }), /not shared/);
  const oldToken = config.token; await companion.stop(); await assert.rejects(fs.access(companion.file)); await companion.start(); assert.notEqual(companion.token, oldToken);
});
test('ID-token validation rejects forged signatures, nonce, issuer, audience and expiration', async () => {
  const { generateKeyPair, exportJWK, SignJWT } = await import('jose');
  const keys = await generateKeyPair('RS256'), forged = await generateKeyPair('RS256'); const jwk = await exportJWK(keys.publicKey); jwk.kid = 'fixture';
  const fetcher = async url => new Response(JSON.stringify(String(url).includes('openid-configuration') ? { issuer: 'https://auth.openai.com', jwks_uri: 'https://auth.openai.com/.well-known/jwks.json' } : { keys: [jwk] }));
  const sign = (changes = {}, key = keys.privateKey) => new SignJWT({ sub: 'verified-user', nonce: 'expected', ...changes }).setProtectedHeader({ alg: 'RS256', kid: 'fixture' }).setIssuedAt().setIssuer(changes.iss || 'https://auth.openai.com').setAudience(changes.aud || 'oaiapp_test').setExpirationTime(changes.exp || '5m').sign(key);
  const options = { clientId: 'oaiapp_test', nonce: 'expected' };
  assert.equal((await verifyIdentity(await sign(), options, fetcher)).sub, 'verified-user');
  for (const changes of [{ nonce: 'wrong' }, { iss: 'https://evil.example' }, { aud: 'other' }, { exp: 1 }]) await assert.rejects(verifyIdentity(await sign(changes), options, fetcher));
  await assert.rejects(verifyIdentity(await sign({}, forged.privateKey), options, fetcher)); assert.equal(matches('é', 'a'), false);
});
test('loopback sign-in validates one-time state and PKCE, isolates registrations, serializes refresh and signs out', async t => {
  const { credentials } = await setup(t); let url, exchanges = [], revocations = 0;
  const auth = new ChatGPTAuth({ credentials, openBrowser: async address => { url = new URL(address); }, verify: async (_token, expected) => ({ sub: 'user', email: 'fixture@example.com', nonce: expected.nonce }), fetcher: async (address, request) => {
    if (String(address).includes('openid-configuration')) return new Response(JSON.stringify({ revocation_endpoint: 'https://auth.openai.com/revoke' }));
    if (String(address).endsWith('/revoke')) { revocations++; return new Response(''); }
    const body = new URLSearchParams(request.body); exchanges.push(body); return new Response(JSON.stringify({ id_token: 'signed-token', access_token: 'access', refresh_token: 'refresh', token_type: 'Bearer', expires_in: 3600, scope: 'openid resource.invoke chatgpt.tokens.use.direct' }));
  } }); t.after(() => auth.cancel());
  await auth.start(); const callback = new URL(url.searchParams.get('redirect_uri'));
  assert.equal(url.searchParams.get('client_id'), 'dynamic_agent_client'); assert.equal(url.searchParams.get('agent_name_hint'), 'Wixal');
  callback.search = new URLSearchParams({ state: 'wrong', code: 'fixture', client_id: 'oaiapp_fixture' }); assert.equal((await fetch(callback)).status, 400); assert.equal(exchanges.length, 0);
  callback.search = new URLSearchParams({ state: url.searchParams.get('state'), code: 'fixture', client_id: 'oaiapp_fixture' }); assert.equal((await fetch(callback)).status, 200);
  assert.equal(exchanges[0].get('redirect_uri'), url.searchParams.get('redirect_uri')); assert.ok(exchanges[0].get('code_verifier')); assert.equal(exchanges[0].get('client_id'), 'oaiapp_fixture');
  assert.equal(credentials.account().subject, 'user'); credentials.account().expiresAt = 0;
  assert.deepEqual(await Promise.all([auth.accessToken(), auth.accessToken()]), ['access', 'access']); assert.equal(exchanges.length, 2);
  await auth.start('oaiapp_fixture'); assert.equal(url.searchParams.get('client_id'), 'oaiapp_fixture'); assert.equal(url.searchParams.has('agent_name_hint'), false); assert.equal(url.searchParams.get('id_token_hint'), 'signed-token'); auth.cancel();
  assert.equal((await auth.signOut('oaiapp_fixture')).revoked, true); assert.equal(revocations, 1); assert.equal(credentials.data.accounts[0].access_token, undefined); assert.equal(credentials.data.accounts[0].client_id, 'oaiapp_fixture');
});
