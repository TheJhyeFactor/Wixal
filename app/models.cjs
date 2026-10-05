const OLLAMA = 'http://127.0.0.1:11434';
let endpoint = async () => OLLAMA;
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
  return { kvBytesPerToken: layers && embedding && heads && kvHeads ? Math.ceil(2 * layers * (embedding / heads) * kvHeads) : null, capabilities: info.capabilities || [], details: info.details || {}, contextLength: contextEntry?.[1] || null };
}
async function getModels(fetcher = fetch) {
  const response = await fetcher(`${await localEndpoint()}/api/tags`, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Ollama returned ${response.status}`);
  const models = (await response.json()).models || [];
  // Small batches keep a large model library from flooding the local server.
  const enriched = [];
  for (let i = 0; i < models.length; i += 4) enriched.push(...await Promise.all(models.slice(i, i + 4).map(async model => {
    try { return { ...model, ...await modelDetails(model.name, fetcher) }; }
    catch { return { ...model, capabilities: null, contextLength: null }; }
  })));
  return enriched;
}
async function pullModel(name, signal, onProgress, fetcher = fetch) {
  if (typeof name !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._/:+-]{0,199}$/.test(name)) throw new Error('Enter a valid Ollama model name, such as qwen3:8b.');
  const response = await fetcher(`${await localEndpoint()}/api/pull`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: name, stream: true }), signal });
  if (!response.ok) throw new Error((await response.text()).slice(0, 800));
  const decoder = new TextDecoder(); let pending = '', success = false;
  const consume = line => {
    if (!line.trim()) return;
    const chunk = JSON.parse(line);
    if (chunk.error) throw new Error(chunk.error);
    if (chunk.status === 'success') success = true;
    onProgress({ name, status: chunk.status || 'Downloading', completed: chunk.completed || 0, total: chunk.total || 0 });
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
async function deleteModel(name, fetcher = fetch) {
  const response = await fetcher(`${await localEndpoint()}/api/delete`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: name }), signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Could not delete this model (${response.status}).`);
}
module.exports = { deleteModel, OLLAMA, configureLocalRuntime, localEndpoint, getModels, modelDetails, pullModel };
