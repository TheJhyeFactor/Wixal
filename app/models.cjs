const OLLAMA = 'http://127.0.0.1:11434';
async function modelDetails(name, fetcher = fetch) {
  const response = await fetcher(`${OLLAMA}/api/show`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: name }), signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`Couldn't read this model (${response.status}). Refresh the model list.`);
  const info = await response.json();
  const contextEntry = Object.entries(info.model_info || {}).find(([key]) => key.endsWith('.context_length'));
  return { capabilities: info.capabilities || [], details: info.details || {}, contextLength: contextEntry?.[1] || null };
}
async function getModels(fetcher = fetch) {
  const response = await fetcher(`${OLLAMA}/api/tags`, { signal: AbortSignal.timeout(5000) });
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
module.exports = { OLLAMA, getModels, modelDetails };
