// Bound model input without corrupting JSON, source URLs or actionable session refs.
function boundedToolResult(content, limit) {
  if (content.length <= limit) return content;
  let value; try { value = JSON.parse(content); } catch {}
  if (!value || typeof value !== 'object' || Array.isArray(value)) return content.slice(0, Math.max(0, limit - 130)) + '\n[Context excerpt. Full result is saved in chat; use the tool offset or filter to read more.]';
  const result = { context_excerpt: true };
  const keys = ['session_id','snapshot_id','url','state','status','exitCode','reason','offset','next_offset','more','total_chars','total_characters','truncated','readiness','reports','summary','contentType','query','source','earliest_offset','blocked'];
  for (const key of keys) if (value[key] !== undefined && JSON.stringify({ ...result, [key]: value[key] }).length <= limit - 30) result[key] = value[key];
  const texts = ['output','text','content'];
  const arrayKeys = ['results','controls','headings','links','findings','checks','cases','forms','console','scripts'];
  const arrayCeiling = JSON.stringify(result).length + Math.max(0, (limit - JSON.stringify(result).length) * .3);
  // Reserve a bounded part for whole evidence items so browser refs and search sources survive.
  for (const key of arrayKeys) if (Array.isArray(value[key]) && !(key === 'links' && value.controls)) {
    const keyCeiling = key === 'controls' && value.headings?.length ? Math.min(arrayCeiling, JSON.stringify(result).length + (limit - JSON.stringify(result).length) * .2) : arrayCeiling;
    result[key] = [];
    for (const item of value[key]) {
      if (JSON.stringify({ ...result, [key]: [...result[key], item] }).length > keyCeiling) break;
      result[key].push(item);
    }
    if (result[key].length < value[key].length) result[key + '_omitted'] = value[key].length - result[key].length;
    if (!result[key].length) delete result[key];
  }
  for (const key of texts) if (typeof value[key] === 'string') {
    const overhead = JSON.stringify({ ...result, [key]: '' }).length;
    let room = Math.max(0, limit - overhead - 150);
    // JSON escape expansion is measured rather than assumed.
    let text = value[key];
    while (text.length && JSON.stringify({ ...result, [key]: text }).length > limit) {
      text = key === 'output' ? value[key].slice(0, Math.floor(room / 3)) + '\n[Excerpt; full result saved in chat]\n' + value[key].slice(-Math.ceil(room * 2 / 3)) : value[key].slice(0, room);
      room = Math.floor(room * .8);
      if (room < 30) { text = ''; break; }
    }
    if (text) {
      result[key] = text;
      if (key !== 'output' && text.length < value[key].length && Number.isSafeInteger(value.next_offset)) { result.next_offset = (value.offset || 0) + text.length; result.more = true; }
    }
  }
  // Small fields from other tools can still be useful when they fit.
  for (const [key, item] of Object.entries(value)) if (!(key in result) && !arrayKeys.includes(key) && !texts.includes(key) && JSON.stringify({ ...result, [key]: item }).length <= limit) result[key] = item;
  while (JSON.stringify(result).length > limit) {
    const key = Object.keys(result).find(key => key.endsWith('_omitted')) || arrayKeys.find(key => key in result);
    if (!key) break; delete result[key];
  }
  return JSON.stringify(result);
}
function hasEvidence(message) {
 const content = message.content || '';
 if (/^(Error:|User declined)/.test(content) || ['workspace_info','browser_close','command_start','command_write','command_stop','network_scan','network_stop','write_file','edit_file','make_directory','save_memory','command_save_output'].includes(message.tool_name)) return false;
 try { const value = JSON.parse(content); return ['text','content','output'].some(key => typeof value[key] === 'string' && value[key].trim()) || ['results','findings','checks','cases','controls'].some(key => Array.isArray(value[key]) && value[key].length); } catch { return !!content.trim(); }
}
function latestEvidence(messages) { const index = messages.findLastIndex(hasEvidence); return index >= 0 ? index : messages.length - 1; }
module.exports = { boundedToolResult, hasEvidence, latestEvidence };
