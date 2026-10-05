const http = require('node:http');
const { randomBytes, createHash, timingSafeEqual } = require('node:crypto');
const AUTH = 'https://auth.openai.com';
const RESOURCE = 'https://api.openai.com/v1';
const SCOPE = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct';
const random = () => randomBytes(32).toString('base64url');
function matches(a, b) { if (typeof a !== 'string' || typeof b !== 'string') return false; const left = Buffer.from(a), right = Buffer.from(b); return left.length === right.length && timingSafeEqual(left, right); }
async function verifyIdentity(idToken, { clientId, nonce }, fetcher = fetch) {
  const { createRemoteJWKSet, jwtVerify, customFetch } = await import('jose');
  const response = await fetcher(`${AUTH}/.well-known/openid-configuration`, { signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('Could not load OpenAI sign-in configuration.');
  const configuration = await response.json();
  if (configuration.issuer !== AUTH || !configuration.jwks_uri || new URL(configuration.jwks_uri).origin !== AUTH) throw new Error('Unexpected OpenAI identity configuration.');
  const { payload } = await jwtVerify(idToken, createRemoteJWKSet(new URL(configuration.jwks_uri), { [customFetch]: fetcher }), {
    issuer: AUTH, audience: clientId, requiredClaims: ['sub', 'exp', 'iat', 'nonce'], clockTolerance: 5, algorithms: ['RS256', 'ES256'],
  });
  if (!matches(payload.nonce, nonce) || typeof payload.sub !== 'string' || !payload.sub) throw new Error('ChatGPT identity verification failed.');
  return payload;
}
class ChatGPTAuth {
  constructor({ credentials, openBrowser, onChange = () => {}, fetcher = fetch, verify = verifyIdentity }) {
    Object.assign(this, { credentials, openBrowser, onChange, fetcher, verify }); this.refreshes = new Map();
  }
  async tokenRequest(body) {
    const response = await this.fetcher(`${AUTH}/api/accounts/oauth/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(body), signal: AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`ChatGPT token exchange was rejected (${response.status}). Sign in again.`);
    const tokens = await response.json();
    if (tokens.token_type?.toLowerCase() !== 'bearer' || !tokens.access_token || !Number.isFinite(tokens.expires_in) || tokens.expires_in <= 0) throw new Error('ChatGPT returned an invalid token response.');
    return tokens;
  }
  async start(accountId) {
    if (this.pending) throw new Error('A ChatGPT sign-in is already open. Finish it or cancel first.');
    const previous = accountId ? this.credentials.data.accounts.find(a => a.client_id === accountId) : null;
    if (accountId && !previous) throw new Error('Unknown ChatGPT registration.');
    this.credentials.save(); // Persist the stable host identifier before registration.
    const attempt = { state: random(), nonce: random(), verifier: random(), previous, expires: Date.now() + 5 * 60000, consumed: false };
    const server = http.createServer(async (request, response) => {
      const url = new URL(request.url, attempt.redirect);
      response.setHeader('Content-Type', 'text/plain; charset=utf-8'); response.setHeader('Cache-Control', 'no-store');
      if (request.method !== 'GET' || url.pathname !== '/auth/callback') { response.writeHead(404); response.end('Not found'); return; }
      if (request.headers.host !== new URL(attempt.redirect).host || attempt.consumed || Date.now() > attempt.expires || !matches(url.searchParams.get('state'), attempt.state)) {
        response.writeHead(400); response.end('Invalid or expired sign-in request. Return to Wixal.'); return;
      }
      attempt.consumed = true;
      try {
        if (url.searchParams.has('error')) throw new Error('ChatGPT sign-in was declined. Your existing connection was kept.');
        const supplied = url.searchParams.get('client_id'), clientId = previous?.client_id || supplied;
        if (!clientId || clientId === 'dynamic_agent_client' || !/^oaiapp_[A-Za-z0-9_-]+$/.test(clientId) || (previous && supplied && supplied !== previous.client_id)) throw new Error('ChatGPT registration did not return the expected client ID.');
        const code = url.searchParams.get('code'); if (!code || code.length > 8192) throw new Error('ChatGPT did not return an authorization code.');
        const tokens = await this.tokenRequest({ grant_type: 'authorization_code', client_id: clientId, code, code_verifier: attempt.verifier, redirect_uri: attempt.redirect, resource: RESOURCE });
        const identity = await this.verify(tokens.id_token, { clientId, nonce: attempt.nonce }, this.fetcher);
        if (this.pending !== attempt) throw new Error('Sign-in was cancelled.');
        if (previous && identity.sub !== previous.subject) throw new Error('This is a different ChatGPT account. Use Add account instead.');
        const scopes = (tokens.scope || '').split(' ').filter(Boolean);
        const existing = this.credentials.data.accounts.find(a => a.client_id === clientId);
        const record = { ...tokens, client_id: clientId, subject: identity.sub, email: identity.email, name: identity.name, issuer: AUTH,
          scopes, expiresAt: Date.now() + tokens.expires_in * 1000, planNoticeSeen: existing?.planNoticeSeen || false };
        const accounts = this.credentials.data.accounts;
        const index = accounts.findIndex(a => a.client_id === clientId);
        if (index >= 0 && accounts[index].subject !== identity.sub) throw new Error('Registration identity changed unexpectedly.');
        if (index >= 0) accounts[index] = record; else accounts.push(record);
        this.credentials.data.activeAccount = clientId; this.credentials.save();
        response.end(scopes.includes('chatgpt.tokens.use.direct') ? 'Connected to Wixal. You can close this tab and choose a ChatGPT model.' : 'Signed in to Wixal. ChatGPT plan usage was not granted; reconnect to authorize AI requests.');
        this.onChange({ type: 'connections', message: 'ChatGPT sign-in completed.', firstPlanUse: scopes.includes('chatgpt.tokens.use.direct') && !record.planNoticeSeen });
      } catch (error) { response.writeHead(400); response.end('Sign-in did not complete. Return to Wixal for details.'); this.onChange({ type: 'connections', message: error.message }); }
      finally { this.cancel(); }
    });
    attempt.server = server; this.pending = attempt;
    try {
      await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
      attempt.redirect = `http://127.0.0.1:${server.address().port}/auth/callback`;
      const parameters = { client_id: previous?.client_id || 'dynamic_agent_client', ext_agent_host_id: this.credentials.data.hostId,
        response_type: 'code', redirect_uri: attempt.redirect, scope: SCOPE, resource: RESOURCE, state: attempt.state, nonce: attempt.nonce,
        code_challenge_method: 'S256', code_challenge: createHash('sha256').update(attempt.verifier).digest('base64url') };
      if (!previous) parameters.agent_name_hint = 'Wixal';
      else { if (previous.id_token) parameters.id_token_hint = previous.id_token; if (previous.email) parameters.login_hint = previous.email; }
      attempt.timer = setTimeout(() => { this.cancel(); this.onChange({ type: 'connections', message: 'ChatGPT sign-in timed out. Try again.' }); }, 5 * 60000);
      await this.openBrowser(`${AUTH}/api/accounts/authorize?${new URLSearchParams(parameters)}`);
      return { pending: true };
    } catch (error) { this.cancel(); throw error; }
  }
  cancel() { const pending = this.pending; this.pending = null; if (pending) { clearTimeout(pending.timer); pending.server.close(); } }
  async accessToken(account = this.credentials.account()) {
    if (!account?.access_token) throw new Error('Continue with ChatGPT in Connections first.');
    if (!account.scopes.includes('chatgpt.tokens.use.direct') || !account.scopes.includes('resource.invoke')) throw new Error('ChatGPT plan usage has not been authorized. Reconnect this account.');
    if (account.expiresAt > Date.now() + 60000) return account.access_token;
    if (!account.refresh_token) throw new Error('ChatGPT sign-in expired. Reconnect this account.');
    if (!this.refreshes.has(account.client_id)) {
      const refresh = (async () => {
        const tokens = await this.tokenRequest({ grant_type: 'refresh_token', client_id: account.client_id, refresh_token: account.refresh_token, resource: RESOURCE });
        if (!account.access_token) throw new Error('This account was signed out.');
        delete tokens.id_token; // Keep the identity token validated during the original sign-in.
        Object.assign(account, tokens, { scopes: tokens.scope ? tokens.scope.split(' ') : account.scopes, expiresAt: Date.now() + tokens.expires_in * 1000 });
        this.credentials.save();
        if (!account.scopes.includes('chatgpt.tokens.use.direct') || !account.scopes.includes('resource.invoke')) throw new Error('ChatGPT plan permission was revoked. Reconnect this account.');
        return account.access_token;
      })().finally(() => this.refreshes.delete(account.client_id));
      this.refreshes.set(account.client_id, refresh);
    }
    return this.refreshes.get(account.client_id);
  }
  select(id) {
    const account = this.credentials.data.accounts.find(a => a.client_id === id);
    if (!account?.access_token) throw new Error('Reconnect this ChatGPT account first.');
    this.credentials.data.activeAccount = id; this.credentials.save();
  }
  async signOut(id) {
    this.cancel(); const account = this.credentials.data.accounts.find(a => a.client_id === id);
    if (!account) throw new Error('Unknown account.');
    await this.refreshes.get(id)?.catch(() => {});
    let revoked = !account.refresh_token;
    if (account.refresh_token) {
      try {
        const configuration = await (await this.fetcher(`${AUTH}/.well-known/openid-configuration`, { signal: AbortSignal.timeout(10000) })).json();
        if (new URL(configuration.revocation_endpoint).origin !== AUTH) throw new Error('Unexpected revocation endpoint.');
        const response = await this.fetcher(configuration.revocation_endpoint, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({ token: account.refresh_token, token_type_hint: 'refresh_token', client_id: id }), signal: AbortSignal.timeout(10000) }); revoked = response.status === 200;
      } catch {}
    }
    for (const key of ['access_token', 'refresh_token', 'id_token', 'expiresAt']) delete account[key];
    if (this.credentials.data.activeAccount === id) this.credentials.data.activeAccount = null;
    this.credentials.save(); return { revoked, message: revoked ? 'Signed out of ChatGPT.' : 'Signed out locally. Remote revocation was not confirmed. Disconnect Wixal in ChatGPT Settings.' };
  }
}
module.exports = { ChatGPTAuth, verifyIdentity, matches };
