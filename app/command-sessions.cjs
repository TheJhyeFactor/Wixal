const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const jobs = new Map();
const MAX = 1024 * 1024;
function owner(context) { return context.store?.session()?.id || context.root; }
function get(id, context) {
  const job = jobs.get(id);
  if (!job || job.owner !== owner(context) || job.root !== context.root) throw new Error('Command session is unavailable in this conversation and project.');
  return job;
}
function stop(job, reason = 'cancelled') {
  if (job.state !== 'running') return;
  job.reason = reason;
  try { process.kill(-job.child.pid, 'SIGKILL'); } catch {}
}
async function executeCommandSession(name, args, context) {
  const { root, approve, signal } = context;
  if (name === 'command_start') {
    if (!root) throw new Error('Open a project folder for the command working directory.');
    if (typeof args.command !== 'string' || !args.command.trim() || args.command.length > 8000) throw new Error('Invalid command.');
    const seconds = args.timeout_seconds ?? 600;
    if (!Number.isInteger(seconds) || seconds < 1 || seconds > 3600) throw new Error('Timeout must be 1–3600 seconds.');
    if ([...jobs.values()].filter(j => j.state === 'running').length >= 8) throw new Error('Stop a command before starting another (8 running maximum).');
    if (!await approve({ name: context.approvalName || name, command: args.command, root, timeout_seconds: seconds })) return 'User declined this command.';
    if (signal?.aborted) throw new Error('Stopped');
    for (const [id, job] of jobs) if (jobs.size >= 32 && job.state !== 'running') jobs.delete(id);
    const child = spawn(context.executable || '/bin/zsh', context.executable ? context.argv : ['-l', '-c', args.command], { cwd: root, detached: true, stdio: ['pipe', 'pipe', 'pipe'] });
    const job = { command: args.command, started: Date.now(), timeout_seconds: seconds, ...(context.assessment ? { assessment: context.assessment } : {}), id: randomUUID(), owner: owner(context), root, child, state: 'running', output: '', base: 0, exitCode: null, reason: null };
    jobs.set(job.id, job);
    const append = text => { job.output += text; if (job.output.length > MAX) { const removed = job.output.length - MAX; job.base += removed; job.output = job.output.slice(removed); } };
    for (const stream of [child.stdout, child.stderr]) { stream.setEncoding('utf8'); stream.on('data', append); }
    child.stdin.on('error', error => append(`\n[stdin error: ${error.message}]`));
    const abort = () => stop(job);
    const timer = setTimeout(() => stop(job, 'timeout'), seconds * 1000);
    signal?.addEventListener('abort', abort, { once: true });
    const cleanup = () => { clearTimeout(timer); signal?.removeEventListener('abort', abort); };
    child.on('error', error => { append(error.message); job.state = 'failed'; cleanup(); });
    child.on('close', (code, exitSignal) => { job.state = job.reason ? 'stopped' : job.state === 'failed' ? 'failed' : 'completed'; job.finished = Date.now(); job.exitCode = code; job.exitSignal = exitSignal; cleanup(); });
    return JSON.stringify({ session_id: job.id, state: job.state, timeout_seconds: seconds, message: 'Use command_read to inspect output and exit status. This is a piped process, not a PTY.' });
  }
  const job = get(args.session_id, context);
  if (name === 'command_read') {
    const wait = args.wait_ms ?? 1000;
    if (!Number.isInteger(wait) || wait < 0 || wait > 10000) throw new Error('wait_ms must be 0–10000.');
    if (job.state === 'running' && wait) await new Promise(resolve => setTimeout(resolve, wait));
    const offset = args.offset ?? job.base;
    if (!Number.isSafeInteger(offset) || offset < 0 || offset > job.base + job.output.length) throw new Error('Invalid output offset.');
    const start = Math.max(offset, job.base), output = job.output.slice(start - job.base, start - job.base + 24000);
    return JSON.stringify({ session_id: job.id, command: job.command, started: job.started, finished: job.finished, timeout_seconds: job.timeout_seconds, assessment: job.assessment, state: job.state, exitCode: job.exitCode, signal: job.exitSignal, reason: job.reason, output, offset: start, next_offset: start + output.length, earliest_offset: job.base, discarded: offset < job.base, more: start + output.length < job.base + job.output.length });
  }
  if (name === 'command_stop') { stop(job); return JSON.stringify({ session_id: job.id, state: job.state, cancellationRequested: job.state === 'running' }); }
  if (name === 'command_write') {
    if (job.state !== 'running') throw new Error('Command has finished.');
    if (typeof args.input !== 'string' || args.input.length > 8000) throw new Error('Input must be text under 8,000 characters.');
    if (!await approve({ name, command: args.input, root, session_id: job.id })) return 'User declined command input.';
    if (signal?.aborted) throw new Error('Stopped');
    if (job.state !== 'running' || job.child.stdin.destroyed) throw new Error('Command has finished.');
    job.child.stdin.write(args.input);
    if (args.close_stdin === true) job.child.stdin.end();
    return JSON.stringify({ session_id: job.id, inputSent: true });
  }
  throw new Error('Unknown command tool.');
}
function stopAllCommands() { for (const job of jobs.values()) stop(job, 'app_shutdown'); }
module.exports = { executeCommandSession, stopAllCommands };
