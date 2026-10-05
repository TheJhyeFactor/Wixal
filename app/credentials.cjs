const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { providerInfo } = require('./providers.cjs');

// Only the main process can decrypt this file. Never include it in workspace snapshots.
class Credentials {
  constructor(directory, encryption) {
    this.file = path.join(directory, 'credentials.enc');
    this.encryption = encryption;
    this.data = { apiKey: '', accounts: [], activeAccount: null, hostId: `urn:uuid:${randomUUID()}` };
    if (fs.existsSync(this.file)) {
      try {
        if (!encryption.isEncryptionAvailable()) throw new Error('encryption unavailable');
        this.data = JSON.parse(encryption.decryptString(fs.readFileSync(this.file)));
      } catch { this.loadError = 'Saved credentials could not be decrypted. Unlock the macOS login keychain and restart Wixal. Local models are still available.'; }
    }
    this.data.keys ??= {};
    this.data.keys.openai ??= this.data.apiKey || '';
  }
  save() {
    if (this.loadError) throw new Error(this.loadError);
    if (!this.encryption.isEncryptionAvailable()) throw new Error('macOS credential encryption is unavailable. Credentials were not saved.');
    fs.writeFileSync(this.file + '.tmp', this.encryption.encryptString(JSON.stringify(this.data)), { mode: 0o600 });
    fs.chmodSync(this.file + '.tmp', 0o600);
    fs.renameSync(this.file + '.tmp', this.file);
  }
  key(provider) { return this.data.keys[provider] || ''; }
  setKey(key, provider = 'openai') {
    const info = providerInfo(provider);
    if (['ollama', 'chatgpt'].includes(provider)) throw new Error('This provider does not use an API key.');
    if (typeof key !== 'string' || key.length > 1024 || (key && (!/^[\x21-\x7e]+$/.test(key) || (provider === 'openai' && !/^sk-[A-Za-z0-9_-]+$/.test(key))))) throw new Error(`Enter a valid ${info.label} API key.`);
    const previous = this.data.keys[provider], legacy = this.data.apiKey;
    this.data.keys[provider] = key;
    if (provider === 'openai') this.data.apiKey = key;
    try { this.save(); } catch (error) { this.data.keys[provider] = previous; this.data.apiKey = legacy; throw error; }
  }
  account() { return this.data.accounts.find(a => a.client_id === this.data.activeAccount); }
  snapshot() {
    return { apiKeySaved: !!this.key('openai'), keysSaved: Object.fromEntries(Object.entries(this.data.keys).map(([provider, key]) => [provider, !!key])), activeAccount: this.data.activeAccount, error: this.loadError || null,
      accounts: this.data.accounts.map(a => ({ id: a.client_id, label: `${a.email || a.name || 'ChatGPT account'} · ${a.client_id.slice(-6)}`,
        signedIn: !!a.access_token, planEnabled: !!a.access_token && !!a.scopes?.includes('chatgpt.tokens.use.direct') })) };
  }
}
module.exports = { Credentials };
