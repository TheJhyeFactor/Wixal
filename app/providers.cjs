const providers = Object.freeze({
  ollama: { label: 'Ollama', protocol: 'ollama' },
  openai: { label: 'OpenAI API', protocol: 'responses', baseURL: 'https://api.openai.com/v1', keysURL: 'https://platform.openai.com/api-keys' },
  chatgpt: { label: 'ChatGPT', protocol: 'responses', baseURL: 'https://api.openai.com/v1' },
  xai: { label: 'xAI · Grok', protocol: 'responses', baseURL: 'https://api.x.ai/v1', keysURL: 'https://console.x.ai' },
  deepseek: { label: 'DeepSeek', protocol: 'completions', baseURL: 'https://api.deepseek.com/v1', keysURL: 'https://platform.deepseek.com/api_keys' },
  anthropic: { label: 'Anthropic · Claude', protocol: 'anthropic', baseURL: 'https://api.anthropic.com/v1', keysURL: 'https://platform.claude.com/settings/keys' },
  gemini: { label: 'Google · Gemini', protocol: 'completions', baseURL: 'https://generativelanguage.googleapis.com/v1beta/openai', keysURL: 'https://aistudio.google.com/apikey' },
  groq: { label: 'Groq', protocol: 'completions', baseURL: 'https://api.groq.com/openai/v1', keysURL: 'https://console.groq.com/keys' },
  mistral: { label: 'Mistral', protocol: 'completions', baseURL: 'https://api.mistral.ai/v1', keysURL: 'https://console.mistral.ai' },
  openrouter: { label: 'OpenRouter', protocol: 'completions', baseURL: 'https://openrouter.ai/api/v1', keysURL: 'https://openrouter.ai/settings/keys' },
  custom: { label: 'Custom endpoint', protocol: 'completions' },
});
function providerInfo(id, custom = {}) {
  if (!Object.hasOwn(providers, id)) throw new Error('Unknown model provider.');
  return { ...providers[id], ...(id === 'custom' ? custom : {}), id };
}
function customSettings(value) {
  if (!value || typeof value !== 'object') throw new Error('Enter a custom endpoint and model.');
  let url; try { url = new URL(value.baseURL); } catch { throw new Error('Enter a valid API base URL.'); }
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || !['https:', 'http:'].includes(url.protocol) || (url.protocol === 'http:' && !loopback)) throw new Error('Use HTTPS, or HTTP on localhost. Keep credentials out of the URL.');
  if (typeof value.model !== 'string' || !value.model.trim() || value.model.length > 200 || /[\x00-\x1f\x7f]/.test(value.model)) throw new Error('Enter the model ID served by this endpoint.');
  return { baseURL: url.href.replace(/\/+$/, ''), model: value.model.trim(), tools: value.tools === true, vision: value.vision === true };
}
function providerError(label, status) {
  if (status === 401 || status === 403) return new Error(`${label} rejected authentication or access. Check its key in Connections.`);
  if (status === 429) return new Error(`${label} usage or rate limit reached. Check the provider's billing and limits.`);
  return new Error(`${label} request failed (${status}). Check model access and connection settings.`);
}
function headers(info, token) {
  return { 'Content-Type': 'application/json', ...(info.protocol === 'anthropic' ? { 'x-api-key': token, 'anthropic-version': '2023-06-01' } : token ? { Authorization: `Bearer ${token}` } : {}) };
}
module.exports = { providers, providerInfo, customSettings, providerError, headers };
