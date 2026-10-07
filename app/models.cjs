const OLLAMA = 'http://127.0.0.1:11434';
let endpoint = async () => OLLAMA;
const metadata = new WeakMap();
function validateModelName(name) {
  if (typeof name !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._/:+-]{0,199}$/.test(name)) throw new Error('Enter a valid model tag, such as qwen3:8b.');
  if (/(?:^|[:.-])cloud(?:$|[:.-])/i.test(name)) throw new Error('Choose a downloadable local model. Cloud-only tags do not install on this Mac.');
}
function clearModelMetadata() { metadata.delete(fetch); }
function configureLocalRuntime(runtime) { endpoint = () => runtime.endpoint(); }
async function localEndpoint() { return endpoint(); }
async function modelDetails(name, fetcher = fetch) {
  const response = await fetcher(`${await localEndpoint()}/api/show`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: name }), signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`Couldn't read this model (${response.status}). Refresh the model list.`);
  const info = await response.json();
  const contextEntry = Object.entries(info.model_info || {}).find(([key]) => key.endsWith('.context_length'));
  const values = info.model_info || {};
  const number = suffix => Number(Object.entries(values).find(([key]) => key.endsWith(suffix))?.[1]) || 0;
  const layers = number('.block_count'), embedding = number('.embedding_length'), heads = number('.attention.head_count'), kvHeads = number('.attention.head_count_kv');
  return { kvBytesPerToken: layers && embedding && heads && kvHeads ? Math.ceil(2 * layers * (embedding / heads) * kvHeads) : null, capabilities: info.capabilities || [], thinking: info.thinking || null, details: info.details || {}, contextLength: contextEntry?.[1] || null };
}
async function getModels(fetcher = fetch, { refresh = false } = {}) {
  const response = await fetcher(`${await localEndpoint()}/api/tags`, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Wixal Local returned ${response.status}`);
  const models = (await response.json()).models || [];
  const server = await localEndpoint();
  let cache = metadata.get(fetcher); if (!cache || refresh) { cache = new Map(); metadata.set(fetcher, cache); }
  const valid = new Set(models.map(model => `${server}:${model.name}:${model.digest || model.modified_at || model.size}`));
  for (const key of cache.keys()) if (!valid.has(key)) cache.delete(key);
  // Small batches keep a large model library from flooding the local server.
  const enriched = [];
  for (let i = 0; i < models.length; i += 4) enriched.push(...await Promise.all(models.slice(i, i + 4).map(async model => {
    try {
      const key = `${server}:${model.name}:${model.digest || model.modified_at || model.size}`;
      let entry = cache.get(key);
      if (!entry || Date.now() - entry.created > 300000) {
        entry = { created: Date.now(), value: modelDetails(model.name, fetcher) }; cache.set(key, entry);
        entry.value.catch(() => { if (cache.get(key) === entry) cache.delete(key); });
      }
      if (cache.size > 256) cache.delete(cache.keys().next().value);
      return { ...model, ...await entry.value };
    }
    catch { return { ...model, capabilities: null, contextLength: null }; }
  })));
  return enriched;
}
async function pullModel(name, signal, onProgress, fetcher = fetch) {
  validateModelName(name);
  const response = await fetcher(`${await localEndpoint()}/api/pull`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: name, stream: true }), signal });
  if (!response.ok) throw new Error((await response.text()).slice(0, 800));
  const decoder = new TextDecoder(); let pending = '', success = false;
  const consume = line => {
    if (!line.trim()) return;
    const chunk = JSON.parse(line);
    if (chunk.error) throw new Error(chunk.error);
    if (chunk.status === 'success') success = true;
    onProgress({ name, digest: chunk.digest || '', status: chunk.status || 'Downloading', completed: chunk.completed || 0, total: chunk.total || 0 });
  };
  for await (const bytes of response.body) {
    pending += decoder.decode(bytes, { stream: true });
    let newline;
    while ((newline = pending.indexOf('\n')) >= 0) { consume(pending.slice(0, newline)); pending = pending.slice(newline + 1); }
    if (pending.length > 100000) throw new Error('Invalid model download stream.');
  }
  consume(pending + decoder.decode());
  if (!success) throw new Error('Model download ended early. Retry to resume.');
}
async function loadedModels(fetcher = fetch) {
  const response = await fetcher(`${await localEndpoint()}/api/ps`, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error('Could not read loaded model memory.');
  return (await response.json()).models || [];
}
async function unloadModel(name, fetcher = fetch) {
  validateModelName(name);
  const response = await fetcher(`${await localEndpoint()}/api/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: name, keep_alive: 0, stream: false }), signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('Could not free this model’s memory.');
}
async function deleteModel(name, fetcher = fetch) {
  const response = await fetcher(`${await localEndpoint()}/api/delete`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: name }), signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Could not delete this model (${response.status}).`);
}
module.exports = { loadedModels, unloadModel, validateModelName, clearModelMetadata, deleteModel, OLLAMA, configureLocalRuntime, localEndpoint, getModels, modelDetails, pullModel };
