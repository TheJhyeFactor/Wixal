const MEMORY_SIZES = [8000, 24000, 48000];
const GLOBAL_LIMIT = 1200;
const MAX_CONTEXT = 32768;
function memorySettings(project) {
  return { mode: project?.memoryMode || 'project', size: MEMORY_SIZES.includes(project?.memorySize) ? project.memorySize : 24000 };
}
function validateMemorySettings(value = {}) {
  if (!['off', 'project', 'global', 'both'].includes(value.mode) || !MEMORY_SIZES.includes(value.size)) throw new Error('Choose a memory scope and an 8,000, 24,000 or 48,000 character budget.');
  return { memoryMode: value.mode, memorySize: value.size };
}
function globalProfile(content) {
  if (typeof content !== 'string' || content.length > GLOBAL_LIMIT) throw new Error('Global memory can contain up to 1,200 characters. Keep only a few preferences.');
  return content.trim();
}
// Estimates only: local model tokenizers vary. Non-Latin text gets a larger allowance.
function estimateTokens(text = '') {
  const ascii = (text.match(/[\x00-\x7f]/g) || []).length;
  return Math.ceil(ascii / 3 + (text.length - ascii));
}
function safeContext(model = {}, requested = 8192, device) {
  let cap = device?.totalMemory && device.totalMemory < 24 * 1024 ** 3 ? 16384 : MAX_CONTEXT;
  if (device && model.size) {
    const bytesPerToken = model.kvBytesPerToken || 128 * 1024;
    const room = (device.memoryBudget || device.totalMemory * .75) - model.size * 1.15 - 1024 ** 3;
    if (room > 0) cap = Math.min(cap, Math.max(2048, Math.floor(room / bytesPerToken)));
    else cap = Math.min(cap, 4096);
  }
  return Math.max(512, Math.min(Number(requested) || 8192, model.contextLength || 8192, cap));
}
function usage(messages, tools, limit, extra = '') {
  const used = estimateTokens(messages.map(m => m.content || '').join('\n') + JSON.stringify(tools || []) + extra)
    + messages.reduce((n, m) => n + 12 + (m.images?.length || 0) * 2048 + estimateTokens(JSON.stringify(m.tool_calls || [])), 0);
  const reserve = Math.min(2048, Math.max(512, Math.floor(limit * .15)));
  return { used, limit, reserve, inputLimit: limit - reserve, percent: Math.min(100, Math.round(used / (limit - reserve) * 100)), estimated: true };
}
module.exports = { MEMORY_SIZES, GLOBAL_LIMIT, MAX_CONTEXT, memorySettings, validateMemorySettings, globalProfile, estimateTokens, safeContext, usage };
