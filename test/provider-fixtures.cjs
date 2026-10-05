// Protocol fixtures only. They never contact a provider or imply live account access.
function sse(events, done = false) { return new Response(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('') + (done ? 'data: [DONE]\n\n' : '')); }
function completion(call, text = 'Reviewed result.', finish = call ? 'tool_calls' : 'stop') {
  return sse([{ choices: [{ index: 0, delta: call ? { reasoning_content: 'fixture reasoning', tool_calls: [{ index: 0, id: 'call_fixture', type: 'function', function: { name: call.name, arguments: JSON.stringify(call.args) }, extra_content: { google: { thought_signature: 'opaque-fixture' } } }] } : { content: text } }] }, { choices: [{ index: 0, delta: {}, finish_reason: finish }], usage: { completion_tokens: 8 } }], true);
}
function anthropic(call, text = 'Reviewed result.', finish = call ? 'tool_use' : 'end_turn') {
  return sse([{ type: 'message_start', message: { role: 'assistant', content: [] } }, { type: 'content_block_start', index: 0, content_block: call ? { type: 'tool_use', id: 'tool_fixture', name: call.name, input: {} } : { type: 'text', text: '' } }, { type: 'content_block_delta', index: 0, delta: call ? { type: 'input_json_delta', partial_json: JSON.stringify(call.args) } : { type: 'text_delta', text } }, { type: 'content_block_stop', index: 0 }, { type: 'message_delta', delta: { stop_reason: finish }, usage: { output_tokens: 8 } }, { type: 'message_stop' }]);
}
function responses(call, text = 'Reviewed result.') {
  return sse([{ type: 'response.completed', response: { output: call ? [{ type: 'function_call', call_id: 'call_fixture', name: call.name, arguments: JSON.stringify(call.args) }] : [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text }] }], usage: { output_tokens: 8 } } }]);
}
const catalogs = {
  xai: { models: [{ id: 'grok-fixture', input_modalities: ['text', 'image'], output_modalities: ['text'] }, { id: 'imagine-fixture', output_modalities: ['image'] }] },
  deepseek: { data: [{ id: 'deepseek-fixture' }] },
  anthropic: { data: [{ id: 'claude-fixture', display_name: 'Claude fixture', max_input_tokens: 200000, max_tokens: 4096 }], has_more: false },
  gemini: { data: [{ id: 'gemini-fixture' }, { id: 'gemini-tts-fixture' }] },
  groq: { data: [{ id: 'llama-4-fixture', context_window: 32768 }, { id: 'whisper-fixture' }] },
  mistral: { data: [{ id: 'mistral-fixture', capabilities: { completion_chat: true, function_calling: true, vision: true }, max_context_length: 32768 }, { id: 'mistral-embed', capabilities: { completion_chat: false } }] },
  openrouter: { data: [{ id: 'router/fixture', name: 'Router fixture', architecture: { input_modalities: ['text', 'image'], output_modalities: ['text'] }, supported_parameters: ['tools'], context_length: 32768 }, { id: 'router/image', architecture: { output_modalities: ['image'] } }] },
};
module.exports = { sse, completion, anthropic, responses, catalogs };
