const { readEvents } = require('./sse.cjs');
const API = 'https://api.openai.com/v1';

function apiError(status, data = {}) {
  const code = String(data.error?.code || data.error || '').slice(0, 100);
  if (status === 401) return new Error('OpenAI authentication expired or was rejected. Reconnect in Connections.');
  if (status === 429 || code.includes('usage_limit')) return new Error(`OpenAI usage limit reached${code ? ` (${code})` : ''}. Check your plan or API billing.`);
  return new Error(`OpenAI request failed (${status}${code ? `: ${code}` : ''}). Check account access and the selected model.`);
}
function functionTools(tools) {
  return tools.map(({ function: f }) => ({ type: 'function', ...f,
    // The optional directory becomes nullable for strict Responses schemas.
    parameters: { ...f.parameters, properties: Object.fromEntries(Object.entries(f.parameters.properties).map(([key, value]) =>
      [key, f.parameters.required.includes(key) ? value : { ...value, type: [value.type, 'null'] }])), required: Object.keys(f.parameters.properties) }, strict: true }));
}
function responseInput(messages, provider) {
  const input = []; let pending = [];
  for (const message of messages) {
    if (message.role === 'tool') {
      const call = pending.shift();
      if (call) input.push({ type: 'function_call_output', call_id: call.call_id, output: message.content });
      else input.push({ role: 'user', content: `Evidence from a previous local tool (${message.tool_name}):\n${message.content}` });
      continue;
    }
    if (message.role === 'assistant' && message.responseOutput && message.provider === provider) {
      input.push(...message.responseOutput);
      pending = message.responseOutput.filter(item => item.type === 'function_call');
      continue;
    }
    if (message.content || message.images?.length) {
      const content = [{ type: message.role === 'assistant' ? 'output_text' : 'input_text', text: message.content || '' }];
      if (message.role === 'user') for (const bytes of message.images || []) content.push({ type: 'input_image', image_url: `data:image/png;base64,${bytes}` });
      input.push({ role: message.role, content });
    }
    pending = [];
    // A provider switch retains evidence as text, without foreign call identifiers.
    if (message.tool_calls?.length) input.push({ role: 'assistant', content: `Previously requested tools: ${message.tool_calls.map(c => c.function.name).join(', ')}` });
  }
  return input;
}
async function streamResponses({ model, messages, instructions, tools, provider, token, signal, onToken, fetcher = fetch, baseURL = API, label = 'OpenAI' }) {
  const started = Date.now(), functions = functionTools(tools);
  const body = { model, instructions, input: responseInput(messages, provider), store: false, stream: true,
    include: ['reasoning.encrypted_content'], ...(functions.length ? { tools: provider === 'chatgpt' ? [{ type: 'namespace', name: 'wixal', description: 'Selected local project tools. Edits and commands require review.', tools: functions }] : functions } : {}) };
  const response = await fetcher(`${baseURL}/responses`, { method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  if (!response.ok) throw new Error(apiError(response.status, await response.json().catch(() => ({}))).message.replaceAll('OpenAI', label));
  let output, content = '', usage;
  await readEvents(response, data => {
    if (data === '[DONE]') return;
    const event = JSON.parse(data);
    if (event.type === 'response.output_text.delta') { content += event.delta; onToken(event.delta); }
    if (event.type === 'error' || event.type === 'response.failed') throw new Error(apiError(400, { error: event.response?.error || event.error || { code: event.code } }).message.replaceAll('OpenAI', label));
    if (event.type === 'response.incomplete') throw new Error(`${label} returned an incomplete response. Review the partial text and retry.`);
    if (event.type === 'response.completed') { output = event.response.output; usage = event.response.usage; }
  });
  if (!output) throw new Error(`${label} ended its stream before confirming completion.`);
  const seconds = (Date.now() - started) / 1000, tokens = usage?.output_tokens || 0;
  // Retain encrypted reasoning and complete call records for stateless continuation.
  const responseOutput = output.map(item => { const copy = { ...item }; delete copy.id; return copy; });
  const calls = output.filter(item => item.type === 'function_call').map(item => ({ call_id: item.call_id, namespace: item.namespace, function: { name: item.name, arguments: item.arguments } }));
  return { role: 'assistant', provider, content: content || output.filter(i => i.type === 'message').flatMap(i => i.content || []).filter(c => c.type === 'output_text').map(c => c.text).join(''), responseOutput,
    ...(calls.length ? { tool_calls: calls } : {}), metrics: { inputTokens: usage?.input_tokens ?? null, tokens, seconds, tokensPerSecond: seconds ? Math.round(tokens / seconds * 10) / 10 : 0 } };
}
async function cloudModels(provider, token, fetcher = fetch) {
  const response = await fetcher(`${API}/models`, { headers: { Authorization: `Bearer ${token}` }, redirect: 'error', signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw apiError(response.status, await response.json().catch(() => ({})));
  const body = await response.json();
  if (provider === 'chatgpt') return (body.models || []).filter(m => m.visibility === 'list').map(m => ({ name: m.slug, displayName: m.display_name || m.slug, capabilities: ['tools', 'vision'], provider }));
  // Catalog access is not proof of inference entitlement. Model-specific errors remain visible.
  return (body.data || []).filter(m => /^(gpt-(?:[4-9]|oss)|o[1-9])/.test(m.id) && !/(audio|realtime|transcri|tts|image|search|embedding|moderation|instruct)/.test(m.id))
    .map(m => ({ name: m.id, displayName: m.id, capabilities: ['tools', 'vision'], provider })).sort((a, b) => b.name.localeCompare(a.name));
}
module.exports = { API, apiError, functionTools, responseInput, streamResponses, cloudModels };
