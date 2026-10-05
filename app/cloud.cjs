const { streamResponses, cloudModels: openaiModels } = require('./openai.cjs');
const { providerInfo, customSettings, providerError, headers } = require('./providers.cjs');
const { readEvents, metrics } = require('./sse.cjs');

function completionMessages(messages, provider, endpoint) {
  const result = []; let pending = [];
  for (const message of messages) {
    if (message.role === 'tool') {
      const call = pending.shift();
      result.push(call ? { role: 'tool', tool_call_id: call.id, content: message.content } : { role: 'user', content: `Previous tool evidence (${message.tool_name}):\n${message.content}` });
      continue;
    }
    pending = [];
    if (message.role === 'assistant' && message.provider === provider && message.chatOutput && (provider !== 'custom' || message.endpoint === endpoint)) {
      result.push(message.chatOutput); pending = [...(message.chatOutput.tool_calls || [])]; continue;
    }
    let content = message.content || '';
    if (message.role === 'user' && message.images?.length) content = [{ type: 'text', text: content }, ...message.images.map(data => ({ type: 'image_url', image_url: { url: `data:image/png;base64,${data}` } }))];
    if (content || message.images?.length) result.push({ role: message.role, content });
    if (message.tool_calls?.length) result.push({ role: 'assistant', content: `Previously requested tools: ${message.tool_calls.map(c => c.function.name).join(', ')}` });
  }
  return result;
}
async function streamCompletions({ model, messages, instructions, tools, provider, token, info, signal, onToken, fetcher = fetch }) {
  const started = Date.now();
  const body = { model, messages: [{ role: 'system', content: instructions }, ...completionMessages(messages, provider, info.baseURL)], stream: true, ...(tools.length ? { tools } : {}) };
  // Require OpenRouter to route to a backend that implements the selected tools.
  if (provider === 'openrouter' && tools.length) body.provider = { require_parameters: true };
  const response = await fetcher(`${info.baseURL}/chat/completions`, { method: 'POST', redirect: 'error', headers: headers(info, token), body: JSON.stringify(body), signal });
  if (!response.ok) throw providerError(info.label, response.status);
  let content = '', reasoning = '', finish, usage, ended = false, chunkContent = false; const calls = new Map(), reasoningBlocks = new Map(), contentChunks = [];
  await readEvents(response, data => {
    if (data === '[DONE]') { ended = true; return; }
    const event = JSON.parse(data);
    if (event.error) throw providerError(info.label, Number(event.error.code) || 500);
    if (event.usage) usage = event.usage;
    const choice = event.choices?.find(c => c.index === 0) || event.choices?.[0]; if (!choice) return;
    if (choice.finish_reason) finish = choice.finish_reason;
    const delta = choice.delta || {};
    if (typeof delta.content === 'string') { content += delta.content; onToken(delta.content); if (provider === 'mistral') contentChunks.push({ type: 'text', text: delta.content }); }
    if (Array.isArray(delta.content)) {
      chunkContent = true; contentChunks.push(...delta.content);
      for (const chunk of delta.content) if (chunk.type === 'text' && chunk.text) { content += chunk.text; onToken(chunk.text); }
    }
    if (typeof delta.reasoning_content === 'string') reasoning += delta.reasoning_content;
    for (const detail of delta.reasoning_details || []) {
      const index = detail.index ?? reasoningBlocks.size, previous = reasoningBlocks.get(index);
      const combined = { ...previous, ...detail };
      for (const key of ['text', 'summary', 'data']) if (previous?.[key] && detail[key]) combined[key] = previous[key] + detail[key];
      reasoningBlocks.set(index, combined);
    }
    for (const [position, item] of (delta.tool_calls || []).entries()) {
      const index = item.index ?? position;
      if (!Number.isInteger(index) || index < 0 || index > 100) throw new Error('Provider returned an invalid tool index.');
      const call = calls.get(index) || { id: '', type: 'function', function: { name: '', arguments: '' } };
      if (item.id) call.id = item.id;
      if (item.function?.name) call.function.name += item.function.name;
      if (item.function?.arguments) call.function.arguments += item.function.arguments;
      // Gemini's compatibility API carries opaque thought signatures on tool calls.
      if (item.extra_content) call.extra_content = item.extra_content;
      calls.set(index, call);
    }
    if (JSON.stringify([...calls.values(), ...reasoningBlocks.values(), ...contentChunks]).length + content.length + reasoning.length > 10 * 1024 * 1024) throw new Error('Provider response exceeded the size limit.');
  });
  if (!ended || !finish) throw new Error(`${info.label} ended its stream before confirming completion.`);
  if (!['stop', 'tool_calls'].includes(finish)) throw new Error(`${info.label} stopped with ${finish}. Review the partial text and retry.`);
  const toolCalls = [...calls.entries()].sort((a, b) => a[0] - b[0]).map(([, c]) => c);
  if ((finish === 'tool_calls' && !toolCalls.length) || toolCalls.some(c => !c.id || !c.function.name || !c.function.arguments)) throw new Error(`${info.label} returned incomplete tool calls.`);
  const reasoningDetails = [...reasoningBlocks.values()];
  const chatOutput = { role: 'assistant', content: chunkContent ? contentChunks : content || null, ...(toolCalls.length ? { tool_calls: toolCalls } : {}),
    ...(reasoning ? { reasoning_content: reasoning } : {}), ...(reasoningDetails.length ? { reasoning_details: reasoningDetails } : {}) };
  return { role: 'assistant', provider, ...(provider === 'custom' ? { endpoint: info.baseURL } : {}), content, chatOutput, ...(toolCalls.length ? { tool_calls: toolCalls.map(c => ({ call_id: c.id, function: c.function })) } : {}), metrics: { ...metrics(started, usage?.completion_tokens), inputTokens: usage?.prompt_tokens ?? null } };
}
function anthropicMessages(messages) {
  const result = []; let pending = [];
  const add = (role, content) => { if (!content.length) return; if (result.at(-1)?.role === role) result.at(-1).content.push(...content); else result.push({ role, content }); };
  for (const message of messages) {
    if (message.role === 'tool') {
      const call = pending.shift();
      add('user', call ? [{ type: 'tool_result', tool_use_id: call.id, content: message.content, is_error: /^(Error:|User declined)/.test(message.content) }] : [{ type: 'text', text: `Previous tool evidence (${message.tool_name}):\n${message.content}` }]);
      continue;
    }
    pending = [];
    if (message.role === 'assistant' && message.provider === 'anthropic' && message.anthropicOutput) {
      add('assistant', [...message.anthropicOutput]); pending = message.anthropicOutput.filter(c => c.type === 'tool_use'); continue;
    }
    const content = message.content ? [{ type: 'text', text: message.content }] : [];
    if (message.role === 'user') for (const data of message.images || []) content.push({ type: 'image', source: { type: 'base64', media_type: 'image/png', data } });
    if (message.tool_calls?.length) content.push({ type: 'text', text: `Previously requested tools: ${message.tool_calls.map(c => c.function.name).join(', ')}` });
    add(message.role, content);
  }
  return result;
}
async function streamAnthropic({ model, messages, instructions, tools, provider, token, info, details, signal, onToken, fetcher = fetch }) {
  const started = Date.now();
  const body = { model, system: instructions, messages: anthropicMessages(messages), max_tokens: Math.min(8192, details?.maxOutputTokens || 8192), stream: true,
    ...(tools.length ? { tools: tools.map(({ function: f }) => ({ name: f.name, description: f.description, input_schema: f.parameters })) } : {}) };
  const response = await fetcher(`${info.baseURL}/messages`, { method: 'POST', redirect: 'error', headers: headers(info, token), body: JSON.stringify(body), signal });
  if (!response.ok) throw providerError(info.label, response.status);
  const blocks = new Map(), fragments = new Map(), stopped = new Set(); let content = '', finish, ended = false, tokens = 0, inputTokens = null;
  await readEvents(response, data => {
    const event = JSON.parse(data);
    if (event.type === 'error') throw providerError(info.label, event.error?.type === 'overloaded_error' ? 529 : 500);
    if (event.type === 'content_block_start') { blocks.set(event.index, { ...event.content_block }); fragments.set(event.index, ''); if (event.content_block.type === 'text' && event.content_block.text) { content += event.content_block.text; onToken(event.content_block.text); } }
    if (event.type === 'content_block_delta') {
      const block = blocks.get(event.index); if (!block) throw new Error('Claude returned a delta without a content block.');
      const delta = event.delta;
      if (delta.type === 'text_delta') { block.text = (block.text || '') + delta.text; content += delta.text; onToken(delta.text); }
      if (delta.type === 'input_json_delta') fragments.set(event.index, fragments.get(event.index) + delta.partial_json);
      if (delta.type === 'thinking_delta') block.thinking = (block.thinking || '') + delta.thinking;
      if (delta.type === 'signature_delta') block.signature = (block.signature || '') + delta.signature;
    }
    if (event.type === 'content_block_stop') stopped.add(event.index);
    if (event.type === 'message_start') inputTokens = event.message?.usage?.input_tokens ?? null;
    if (event.type === 'message_delta') { finish = event.delta?.stop_reason; tokens = event.usage?.output_tokens || tokens; }
    if (event.type === 'message_stop') ended = true;
    if (JSON.stringify([...blocks.values()]).length + [...fragments.values()].join('').length > 10 * 1024 * 1024) throw new Error('Claude response exceeded the size limit.');
  });
  if (!ended || !finish || [...blocks.keys()].some(i => !stopped.has(i))) throw new Error('Claude ended its stream before confirming completion.');
  if (!['end_turn', 'tool_use', 'stop_sequence', 'refusal'].includes(finish)) throw new Error(`Claude stopped with ${finish}. Review the partial text and retry.`);
  const output = [...blocks.entries()].sort((a, b) => a[0] - b[0]).map(([index, block]) => {
    if (block.type === 'tool_use' && fragments.get(index)) block.input = JSON.parse(fragments.get(index));
    return block;
  });
  const calls = output.filter(c => c.type === 'tool_use');
  if (calls.length && (finish !== 'tool_use' || calls.some(c => !c.id || !c.name || !c.input))) throw new Error('Claude returned incomplete tool calls.');
  return { role: 'assistant', provider, content, anthropicOutput: output, ...(calls.length ? { tool_calls: calls.map(c => ({ call_id: c.id, function: { name: c.name, arguments: JSON.stringify(c.input) } })) } : {}), metrics: { ...metrics(started, tokens), inputTokens } };
}
async function streamCloud(options) {
  const info = providerInfo(options.provider, options.provider === 'custom' ? customSettings(options.custom) : {});
  if (info.protocol === 'responses') return streamResponses({ ...options, baseURL: info.baseURL, label: info.label });
  if (info.protocol === 'anthropic') return streamAnthropic({ ...options, info });
  return streamCompletions({ ...options, info });
}
async function cloudModels(provider, token, custom = {}, fetcher = fetch) {
  const info = providerInfo(provider, provider === 'custom' ? customSettings(custom) : {});
  if (['openai', 'chatgpt'].includes(provider)) return openaiModels(provider, token, fetcher);
  if (provider === 'custom') return [{ name: info.model, displayName: info.model, provider, capabilities: [...(info.tools ? ['tools'] : []), ...(info.vision ? ['vision'] : [])] }];
  const all = []; let after;
  for (let page = 0; page < 20; page++) {
    const suffix = provider === 'xai' ? '/language-models' : provider === 'anthropic' ? `/models?limit=100${after ? `&after_id=${encodeURIComponent(after)}` : ''}` : '/models';
    const response = await fetcher(`${info.baseURL}${suffix}`, { headers: headers(info, token), redirect: 'error', signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw providerError(info.label, response.status);
    const body = await response.json(); all.push(...(body.models || body.data || []));
    if (!body.has_more || provider !== 'anthropic') break;
    if (!body.last_id || body.last_id === after || page === 19) throw new Error('Claude model catalog pagination did not finish.'); after = body.last_id;
  }
  return all.filter(m => typeof m.id === 'string' && m.id.length < 200 && m.active !== false && !m.archived).filter(m => {
    if (provider === 'mistral') return m.capabilities?.completion_chat === true;
    if (provider === 'openrouter') return m.architecture?.output_modalities?.includes('text');
    if (provider === 'xai') return m.output_modalities?.includes('text');
    return !/(embed|whisper|tts|transcri|audio|image|moderation|guard|veo|live|robotics|research)/i.test(m.id);
  }).map(m => {
    let tools = ['xai', 'deepseek', 'anthropic', 'gemini'].includes(provider), vision = ['anthropic', 'gemini'].includes(provider);
    if (provider === 'xai') vision = m.input_modalities?.includes('image');
    if (provider === 'mistral') { tools = m.capabilities?.function_calling === true; vision = m.capabilities?.vision === true; }
    if (provider === 'openrouter') { tools = m.supported_parameters?.includes('tools'); vision = m.architecture?.input_modalities?.includes('image'); }
    // Groq's catalog has no capability metadata. Be conservative for specialised models.
    if (provider === 'groq') { tools = /^(llama-|meta-llama\/|qwen\/|openai\/gpt-oss|moonshotai\/kimi)/.test(m.id); vision = /llama-4|vision/.test(m.id); }
    return { name: m.id, displayName: m.display_name || m.name || m.id, provider, capabilities: [...(tools ? ['tools'] : []), ...(vision ? ['vision'] : [])], contextLength: m.max_input_tokens || m.max_context_length || m.context_length || m.context_window, maxOutputTokens: m.max_tokens };
  });
}
module.exports = { cloudModels, streamCloud, completionMessages, anthropicMessages };
