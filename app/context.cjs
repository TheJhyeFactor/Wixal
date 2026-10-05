const { createHash } = require('node:crypto');
const digest = messages => createHash('sha256').update(JSON.stringify(messages)).digest('hex');
function chunks(text, size = 1800) {
  const result = [];
  for (let offset = 0; offset < text.length; offset += size - 200) result.push({ offset, text: text.slice(offset, offset + size) });
  return result;
}
function relevant(items, query, budget = 8000) {
  const words = [...new Set((query.toLowerCase().match(/[\p{L}\p{N}_-]{3,}/gu) || []))];
  const ranked = items.map((item, index) => ({ ...item, index, score: words.reduce((sum, word) => sum + (item.text.toLowerCase().includes(word) ? 1 : 0), 0) }))
    .sort((a, b) => b.score - a.score || b.index - a.index);
  const selected = []; let remaining = budget;
  for (const item of ranked) {
    if (remaining <= 0) break;
    const text = item.text.slice(0, remaining); selected.push({ ...item, text }); remaining -= text.length + 100;
  }
  return selected;
}
function projectMemory(store, prompt, budget = 8000) {
  return relevant(store.data.memories.filter(m => m.projectId === store.data.activeProject).flatMap(m => chunks(m.content).map(c => ({ ...c, id: m.id }))), prompt, budget)
    .map(item => item.text).join('\n');
}
function searchHistory(store, query) {
  if (typeof query !== 'string' || !query.trim() || query.length > 500) throw new Error('History query must contain 1–500 characters.');
  const items = store.data.sessions.filter(s => s.projectId === store.data.activeProject && !s.archivedAt)
    .flatMap(s => s.messages.filter(m => ['user', 'assistant'].includes(m.role) && m.content).flatMap(m => chunks(m.content).map(c => ({ ...c, sessionId: s.id, title: s.title, role: m.role, created: m.created }))));
  return relevant(items, query, 18000).filter(item => item.score > 0).slice(0, 10).map(({ index, score, ...item }) => item);
}
async function compactSession({ session, omitted, budget, summarize, signal, save, emit }) {
  if (!omitted) return;
  const prefix = session.messages.slice(0, omitted), hash = digest(prefix);
  if (session.summary?.hash === hash) return;
  if (signal?.aborted) throw new Error('Stopped');
  emit({ type: 'phase', value: 'Summarizing older conversation' });
  const prior = session.summary;
  const covered = prior && prior.count <= omitted && digest(prefix.slice(0, prior.count)) === prior.hash ? prior.count : 0;
  let summary = covered ? prior.content : '';
  const limit = Math.max(600, Math.min(4000, Math.floor(budget * .16)));
  // Bound each summary request, even when a single turn contains large tool output.
  const inputSize = Math.max(1000, Math.min(14000, budget - limit - 1800));
  const text = prefix.slice(covered).map(m => `${m.role}${m.tool_name ? ` (${m.tool_name})` : ''}: ${m.content || ''}${m.tool_calls?.length ? `\nRequested tools: ${m.tool_calls.map(c => c.function?.name).join(', ')}` : ''}${m.images?.length ? '\n[Attached images omitted]' : ''}`).join('\n\n');
  let method = covered ? prior.method : 'model';
  for (let offset = 0; offset < text.length; offset += inputSize) {
    if (signal?.aborted) throw new Error('Stopped');
    const piece = text.slice(offset, offset + inputSize);
    try {
      const result = await summarize(summary, piece, limit);
      if (!result.trim()) throw new Error('Empty summary');
      summary = result.slice(0, limit);
    } catch (error) {
      if (signal?.aborted) throw error;
      // A failed summary must not prevent the actual chat; retain labelled excerpts.
      summary = relevant(chunks([summary, piece].filter(Boolean).join('\n')), session.messages.findLast(m => m.role === 'user')?.content || '', limit).map(c => c.text).join('\n').slice(0, limit);
      method = 'excerpts';
    }
  }
  session.summary = { content: summary, count: omitted, hash, method, updated: Date.now() };
  save();
}
module.exports = { compactSession, projectMemory, searchHistory, relevant, chunks };
