const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

function preferences(data) {
  const ui = data?.ui || {};
  if (!['sakura', 'midnight', 'forest', 'paper'].includes(ui.theme) || ![13, 15, 17].includes(ui.textSize) ||
      typeof ui.reduceMotion !== 'boolean' || typeof ui.sidebarCollapsed !== 'boolean' ||
      ![4096, 8192, 16384, 32768, 65536, 131072].includes(data.contextSize) || typeof data.autoSummary !== 'boolean' || !['chat', 'agent'].includes(data.mode)) throw new Error('Invalid workspace preset.');
  return { ui: { theme: ui.theme, textSize: ui.textSize, reduceMotion: ui.reduceMotion, sidebarCollapsed: ui.sidebarCollapsed }, contextSize: Math.min(32768, data.contextSize), autoSummary: data.autoSummary, mode: data.mode };
}
class Accounts {
  constructor(credentials, config = {}, request = fetch) {
    this.credentials = credentials;
    this.config = config;
    this.request = request;
    this.presets = [];
    this.globalMemory = "";
    this.pending = false;
    this.ready = false;
    this.message = '';
  }
  snapshot() {
    const user = this.credentials.data.wixalAccount;
    return { configured: !!(this.config.apiKey && this.config.projectId), projectId: this.config.projectId || '', signedIn: !!user && this.ready,
      profile: user && this.ready ? { id: user.localId, email: user.email, name: user.displayName || user.email.split('@')[0], verified: !!user.emailVerified } : null,
      globalMemory: this.ready ? this.globalMemory : '',
      presets: this.ready ? structuredClone(this.presets) : [], message: this.message };
  }
  async json(url, body, options = {}) {
    let response;
    try { response = await this.request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(20000), ...options }); }
    catch { throw new Error('Cannot reach Firebase. Check your connection and try again. Guest mode is available.'); }
    const value = response.status === 204 ? {} : await response.json();
    if (!response.ok) {
      const code = value.error?.message || value.error?.status || '';
      const errors = { EMAIL_EXISTS: 'That email already has an account. Sign in instead.', INVALID_LOGIN_CREDENTIALS: 'Email or password is incorrect.', EMAIL_NOT_FOUND: 'Email or password is incorrect.', INVALID_PASSWORD: 'Email or password is incorrect.', TOO_MANY_ATTEMPTS_TRY_LATER: 'Too many attempts. Please try again later.', OPERATION_NOT_ALLOWED: 'Email sign-in is not enabled in this Firebase project.', USER_DISABLED: 'This account has been disabled.', CONFIGURATION_NOT_FOUND: 'The Firebase account service is not initialized yet. Guest mode is available.', INVALID_ID_TOKEN: 'Your session expired. Sign in again.', TOKEN_EXPIRED: 'Your session expired. Sign in again.', PERMISSION_DENIED: 'Cloud settings access was denied. Verify your email and check Firebase rules.' };
      const error = new Error(errors[code] || (code.startsWith('WEAK_PASSWORD') ? 'Use a stronger password of at least 10 characters.' : 'Firebase could not complete this request. Check the account service configuration.'));
      error.status = response.status; error.code = code; throw error;
    }
    return value;
  }
  auth(method, body) {
    if (!this.snapshot().configured) throw new Error('Wixal accounts have not been connected to Firebase yet. You can continue as a guest.');
    return this.json(`https://identitytoolkit.googleapis.com/v1/accounts:${method}?key=${encodeURIComponent(this.config.apiKey)}`, body);
  }
  persist(user) {
    const previous = this.credentials.data.wixalAccount;
    this.credentials.data.wixalAccount = user;
    try { this.credentials.save(); } catch (error) { this.credentials.data.wixalAccount = previous; throw error; }
  }
  async exclusive(work) {
    if (this.pending) throw new Error('An account request is already running.');
    this.pending = true;
    try { return await work(); } finally { this.pending = false; }
  }
  async authenticate(action, value) {
    return this.exclusive(async () => {
      if (!value || typeof value.email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.email.trim()) || value.email.length > 254) throw new Error('Enter a valid email address.');
      if (typeof value.password !== 'string' || value.password.length > 256 || value.password.length < (action === 'create' ? 10 : 1)) throw new Error('Enter your password. New accounts need at least 10 characters.');
      const displayName = typeof value.name === 'string' ? value.name.trim() : '';
      if (action === 'create' && (!displayName || displayName.length > 60)) throw new Error('Enter a display name of up to 60 characters.');
      const result = await this.auth(action === 'create' ? 'signUp' : 'signInWithPassword', { email: value.email.trim(), password: value.password, returnSecureToken: true });
      this.persist({ localId: result.localId, email: result.email, idToken: result.idToken, refreshToken: result.refreshToken, expiresAt: Date.now() + Number(result.expiresIn) * 1000, projectId: this.config.projectId });
      this.ready = true; this.presets = []; this.globalMemory = ''; this.message = '';
      if (action === 'create') {
        try { await this.auth('update', { idToken: result.idToken, displayName, returnSecureToken: false }); await this.auth('sendOobCode', { requestType: 'VERIFY_EMAIL', idToken: result.idToken }); this.message = 'Account created. Check your email for the verification link.'; }
        catch { this.message = 'Account created. Use Resend verification if the email did not arrive.'; }
      }
      await this.lookup();
      if (this.snapshot().profile.verified) { try { await this.sync(); await this.syncMemory(); } catch (error) { this.message = error.message; } }
    });
  }
  async token(force = false) {
    const user = this.credentials.data.wixalAccount;
    if (!user || user.projectId !== this.config.projectId) throw new Error('Sign in to your Wixal account.');
    if (force || user.expiresAt < Date.now() + 60000) {
      const result = await this.json(`https://securetoken.googleapis.com/v1/token?key=${encodeURIComponent(this.config.apiKey)}`, { grant_type: 'refresh_token', refresh_token: user.refreshToken });
      this.persist({ ...user, idToken: result.id_token, refreshToken: result.refresh_token, expiresAt: Date.now() + Number(result.expires_in) * 1000 });
    }
    return this.credentials.data.wixalAccount.idToken;
  }
  async lookup() {
    const result = await this.auth('lookup', { idToken: await this.token() });
    const user = result.users?.[0];
    if (!user) throw new Error('Your account is no longer available. Sign in again.');
    this.persist({ ...this.credentials.data.wixalAccount, email: user.email, displayName: user.displayName || '', emailVerified: !!user.emailVerified });
    this.ready = true;
  }
  async restore() { return this.exclusive(async () => {
    if (!this.credentials.data.wixalAccount) return;
    try { await this.lookup(); }
    catch (error) { this.message = error.message; return; }
    if (this.snapshot().profile.verified) { try { await this.sync(); await this.syncMemory(); } catch (error) { this.message = error.message; } }
  }); }
  async verify() { return this.exclusive(async () => { await this.lookup(); await this.token(true); if (this.snapshot().profile.verified) { await this.sync(); await this.syncMemory(); this.message = 'Email verified. Cloud presets are available.'; } else this.message = 'Your email is not verified yet. Open the link in your verification email first.'; }); }
  async resend() { await this.auth('sendOobCode', { requestType: 'VERIFY_EMAIL', idToken: await this.token() }); this.message = 'Verification email sent.'; }
  async reset(email) {
    if (typeof email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) throw new Error('Enter your email address first.');
    try { await this.auth('sendOobCode', { requestType: 'PASSWORD_RESET', email }); } catch (error) { if (error.code !== 'EMAIL_NOT_FOUND') throw error; }
    this.message = 'If an account exists for that email, a password reset link has been sent.';
  }
  signOut() { if (this.pending) throw new Error('Wait for the account request to finish.'); this.persist(null); this.ready = false; this.presets = []; this.globalMemory = ''; this.message = 'Signed out. Your local projects and chats are still on this Mac.'; }
  async cloud(method, id, body) {
    if (!this.ready || !this.snapshot().profile?.verified) throw new Error('Verify your email before using cloud presets.');
    const user = this.credentials.data.wixalAccount;
    const url = `https://firestore.googleapis.com/v1/projects/${encodeURIComponent(this.config.projectId)}/databases/(default)/documents/users/${encodeURIComponent(user.localId)}/presets${id ? '/' + encodeURIComponent(id) : '?pageSize=100'}`;
    return this.json(url, body, { method, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await this.token()}` }, ...(body === undefined ? { body: undefined } : {}) });
  }
  async memoryCloud(method, body) {
    if (!this.ready || !this.snapshot().profile?.verified) throw new Error('Verify your email before saving account memory.');
    const user = this.credentials.data.wixalAccount;
    const url = `https://firestore.googleapis.com/v1/projects/${encodeURIComponent(this.config.projectId)}/databases/(default)/documents/users/${encodeURIComponent(user.localId)}/profile/memory`;
    return this.json(url, body, { method, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await this.token()}` }, ...(body === undefined ? { body: undefined } : {}) });
  }
  async syncMemory() {
    try {
      const result = await this.memoryCloud('GET');
      this.globalMemory = require('./memory.cjs').globalProfile(result.fields?.content?.stringValue || '');
    } catch (error) { if (error.status === 404) this.globalMemory = ''; else throw error; }
  }
  async saveMemory(content) {
    const clean = require('./memory.cjs').globalProfile(content);
    await this.memoryCloud('PATCH', { fields: { content: { stringValue: clean } } });
    this.globalMemory = clean; this.message = clean ? 'Global preferences saved to your account.' : 'Global preferences cleared from your account.';
  }
  async sync() {
    const result = await this.cloud('GET');
    this.presets = (result.documents || []).map(doc => {
      const name = doc.fields?.name?.stringValue, payload = doc.fields?.preferences?.stringValue;
      if (typeof name !== 'string' || !name || name.length > 60 || typeof payload !== 'string' || payload.length > 4096) throw new Error('A cloud preset is invalid.');
      return { id: doc.name.split('/').at(-1), name, ...preferences(JSON.parse(payload)) };
    });
    this.message = 'Cloud presets refreshed.';
  }
  async savePreset(name, store) {
    if (typeof name !== 'string' || !name.trim() || name.trim().length > 60) throw new Error('Name your preset using up to 60 characters.');
    const preset = preferences(store.data);
    await this.cloud('PATCH', randomUUID(), { fields: { name: { stringValue: name.trim() }, preferences: { stringValue: JSON.stringify(preset) } } });
    await this.sync(); this.message = 'Workspace preset saved to your account.';
  }
  applyPreset(id, store) {
    if (!this.ready || !this.snapshot().profile?.verified) throw new Error('Sign in and verify your email to use presets.');
    const preset = this.presets.find(p => p.id === id);
    if (!preset) throw new Error('Unknown preset. Refresh your cloud presets.');
    const clean = preferences(preset);
    store.data.ui = { ...store.data.ui, ...clean.ui };
    for (const key of ['contextSize', 'autoSummary', 'mode']) store.data[key] = clean[key];
    store.save(); this.message = `Applied ${preset.name}.`;
  }
  async deletePreset(id) {
    if (!this.presets.some(p => p.id === id)) throw new Error('Unknown preset.');
    await this.cloud('DELETE', id); await this.sync();
  }
}
function loadConfig() {
  const file = path.join(__dirname, '../resources/firebase-config.json');
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
}
module.exports = { Accounts, preferences, loadConfig };
