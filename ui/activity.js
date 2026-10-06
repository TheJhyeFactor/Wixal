// Presentation model only: the original conversation and tool results stay intact.
(function (root) {
  function parse(value) { try { return JSON.parse(value); } catch { return null; } }
  function status(message) {
    const content = String(message.content || '');
    if (content.startsWith('Error:')) return 'Failed';
    if (content.startsWith('User declined')) return 'Declined';
    const result = parse(content);
    if (result?.stopped || result?.state === 'stopped') return 'Stopped';
    if (result?.state === 'failed' || (typeof result?.exitCode === 'number' && result.exitCode !== 0)) return 'Failed';
    if (result?.state === 'running') return 'Running';
    if (result?.state === 'completed' || result?.exitCode === 0) return 'Completed';
    return 'Completed';
  }
  function turns(messages) {
    const output = [];
    let turn, pending = [], sessions = new Map();
    messages.forEach((message, index) => {
      if (!turn || message.role === 'user') {
        turn = { key: index, messages: [], actions: [], updates: [], calls: 0, user: message.role === 'user' ? message : null };
        output.push(turn); pending = []; sessions = new Map();
      }
      turn.messages.push({ message, index });
      if (message.role === 'assistant' && message.tool_calls?.length) {
        if (message.content?.trim()) turn.updates.push({ message, index });
        for (const call of message.tool_calls) {
          const action = { key: index + '-' + turn.actions.length, name: call.function?.name || 'tool', args: typeof call.function?.arguments === 'string' ? parse(call.function.arguments) : call.function?.arguments, results: [], status: 'Pending', created: message.created };
          turn.actions.push(action); pending.push(action); turn.calls++;
        }
      }
      if (message.role !== 'tool') return;
      const match = pending.findIndex(action => action.name === message.tool_name);
      let action;
      if (match >= 0) action = pending.splice(match, 1)[0];
      else {
        action = { key: String(index), name: message.tool_name || 'tool', results: [], status: 'Pending', created: message.created };
        turn.actions.push(action); turn.calls++;
      }
      const result = parse(message.content), sessionId = result?.session_id;
      if (sessionId && /^(command|network)_(start|scan|read|write|stop)$/.test(action.name)) {
        if (sessions.has(sessionId)) {
          const original = action;
          action = sessions.get(sessionId);
          turn.actions.splice(turn.actions.indexOf(original), 1);
        } else sessions.set(sessionId, action);
      }
      action.results.push({ message, index });
      if (!result?.inputSent) action.status = status(message);
      action.command = result?.command || action.command || action.args?.command;
      action.finished = result?.finished || message.created;
      action.result = result;
    });
    return output;
  }
  function title(action, fallback) {
    const path = action.args?.path || action.args?.file;
    if (action.command) return action.command;
    if (action.name === 'read_file' && path) return 'Read ' + path;
    if (action.name === 'write_file' && path) return 'Edited ' + path;
    if (action.name === 'list_files') return 'Listed project files';
    if (action.name === 'search_files') return 'Searched the project';
    return fallback || action.name;
  }
  function evidence(action) {
    if (!action.results.length) return { command: action.command || action.args?.command || '', output: 'Waiting for the tool result.', meta: action.status };
    const last = action.results.at(-1).message;
    const chunks = action.results.map(({ message }) => parse(message.content)).filter(Boolean);
    const hasOutput = chunks.some(result => typeof result.output === 'string');
    // Poll results can be empty or overlap. Display each real output range once.
    const seen = new Set();
    const ranges = chunks.filter(result => result.output);
    if (ranges.length && ranges.every(result => Number.isSafeInteger(result.offset))) ranges.sort((a, b) => a.offset - b.offset);
    let covered = null;
    const output = ranges.map(result => {
      if (!result.output) return false;
      const key = [result.session_id || '', result.offset ?? '', result.output].join(':');
      if (seen.has(key)) return ''; seen.add(key);
      if (!Number.isSafeInteger(result.offset)) return result.output;
      const end = result.offset + result.output.length;
      if (covered !== null && end <= covered) return '';
      const prefix = covered !== null && result.offset > covered ? '\n[Gap in captured output]\n' : '';
      const value = result.output.slice(covered === null ? 0 : Math.max(0, covered - result.offset));
      covered = end; return prefix + value;
    }).join('');
    const result = parse(last.content);
    const failure = /^(Error:|User declined)/.test(last.content || '') ? '\n' + last.content : '';
    return { command: action.command || action.args?.command || '', output: hasOutput ? (output || '(No output)') + failure : last.content, meta: typeof result?.exitCode === 'number' ? 'Exit ' + result.exitCode : action.status };
  }
  const api = { turns, status, title, evidence };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.WixalActivity = api;
})(typeof window === 'undefined' ? globalThis : window);
