const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { executeNetwork } = require('./network.cjs');
const { searchHistory } = require('./context.cjs');

const { executeCommandSession } = require('./command-sessions.cjs');
const { inspectBrowser } = require('./browser-inspect.cjs');
const MAX_OUTPUT = 24000;
const skipped = new Set(['.git', 'node_modules', '.venv', 'venv', 'release', '.next', 'dist']);
const sensitive = p => p.split(path.sep).some(x => /^\.env(?:\.|$)/.test(x) || ['.ssh', '.aws', '.gnupg', '.npmrc', '.netrc', 'credentials.enc', 'wixal-connection.json'].includes(x) || /\.(pem|key|p12|pfx)$/i.test(x));

async function safePath(root, relative, writing = false) {
  if (typeof relative !== 'string' || path.isAbsolute(relative)) throw new Error('Use a path relative to the selected project.');
  root = await fs.realpath(root);
  const target = path.resolve(root, relative);
  const inside = p => p === root || p.startsWith(root + path.sep);
  if (!inside(target) || sensitive(relative)) throw new Error('Path is outside the project or contains protected credentials.');
  let actual;
  try { actual = await fs.realpath(target); }
  catch (error) {
    if (!writing || error.code !== 'ENOENT') throw error;
    // Require an existing parent, and resolve every symlink before writing.
    actual = path.join(await fs.realpath(path.dirname(target)), path.basename(target));
  }
  if (!inside(actual) || sensitive(path.relative(root, actual))) throw new Error('Symlink points outside the selected project or to protected credentials.');
  return actual;
}

async function walk(root, directory = '.', depth = 0, result = []) {
  if (depth > 6 || result.length >= 1200) return result;
  const entries = await fs.readdir(await safePath(root, directory), { withFileTypes: true });
  for (const entry of entries) {
    if (result.length >= 1200) break;
    const p = path.join(directory, entry.name);
    if (skipped.has(entry.name) || sensitive(p) || entry.isSymbolicLink()) continue;
    if (entry.isDirectory()) await walk(root, p, depth + 1, result);
    else if (entry.isFile()) result.push(p);
  }
  return result;
}

const definition = (name, description, properties, required) => ({ type: 'function', function: {
  name, description, parameters: { type: 'object', properties, required, additionalProperties: false },
}});
const str = description => ({ type: 'string', description });
const definitions = [
  definition('website_simulate', 'Run reproducible attack simulations against disposable vulnerable and hardened loopback fixtures: reflected scripts, framing headers, sensitive-file canaries, redirects, access checks, cross-origin writes, forwarding-header throttling and logout replay. Saves evidence reports. These fixtures validate tests and do not prove a production website is vulnerable.', { report_prefix: str('Project-relative report filename prefix, default website-simulation') }, []),
  definition('website_assess', 'Assess an authorised website with bounded same-origin GET checks. baseline checks headers, HTTPS and supplied protected paths; probes adds benign reflection, sensitive-file signatures and open-redirect canaries. Saves JSON and Markdown reports in the project. Does not sign in or write to the website. Findings are evidence, not proof of exploitation.', { url: str('Authorised HTTP(S) URL without credentials or query'), profile: { type: 'string', enum: ['baseline', 'probes'] }, max_pages: { type: 'integer', minimum: 1, maximum: 12 }, protected_paths: { type: 'array', maxItems: 8, items: { type: 'string' }, description: 'Known protected same-origin API paths to check without credentials' }, report_prefix: str('Project-relative report filename prefix, default website-assessment') }, ['url']),
  definition('workspace_info', 'Discover the current Wixal workspace, selected local model, enabled tools and review rules. Built-in tools are already connected; no setup is needed.', {}, []),
  definition('security_tools', 'Discover available network scan profiles and whether Nmap is installed. Tools are already connected to Wixal.', {}, []),
  definition('network_scan', 'Start a bounded Nmap scan against an authorised IP, website host or private /24–/32 network. Choose discovery, ports, services, web, tls, ssh, enumeration or checks. Returns session_id; use network_read until complete and command_save_output for evidence.', { target: str('Authorised IP, hostname, HTTP(S) URL or private IPv4 CIDR'), profile: { type: 'string', enum: ['discovery', 'ports', 'services', 'web', 'tls', 'ssh', 'enumeration', 'checks'] }, ports: str('Optional TCP ports or ranges, e.g. 22,80,443'), timeout_seconds: { type: 'integer', minimum: 10, maximum: 600 } }, ['target']),
  definition('network_read', 'Read stdout/stderr, port/service/script evidence and completion status from a network_scan session. Poll until finished; continue using next_offset when more is true.', { session_id: str('Scan session ID'), offset: { type: 'integer', minimum: 0 }, wait_ms: { type: 'integer', minimum: 0, maximum: 10000 } }, ['session_id']),
  definition('network_stop', 'Stop a running network scan and its child processes.', { session_id: str('Scan session ID') }, ['session_id']),
  definition('command_start', 'Start an AI-selected shell command on the Mac after review. Supports website, server and network tools installed on the host. Returns a session ID; read output before deciding next steps. Piped stdin, not a PTY.', { command: str('Shell command'), timeout_seconds: { type: 'integer', minimum: 1, maximum: 3600 } }, ['command']),
  definition('command_read', 'Read real stdout/stderr and status from a command session. Output returns to this chat. Poll running jobs and use next_offset for subsequent chunks.', { session_id: str('Command session ID'), offset: { type: 'integer', minimum: 0 }, wait_ms: { type: 'integer', minimum: 0, maximum: 10000, description: 'Wait before reading a running job, default 1000 milliseconds' } }, ['session_id']),
  definition('command_write', 'Send reviewed text to a running command stdin. Include newline when needed. Never send passwords or credentials.', { session_id: str('Command session ID'), input: str('Text to send'), close_stdin: { type: 'boolean' } }, ['session_id', 'input']),
  definition('command_stop', 'Cancel a running command process group.', { session_id: str('Command session ID') }, ['session_id']),
  definition('command_save_output', 'Save retained command output and execution metadata to a reviewed project file. Parent folder must exist. Reports if older output was discarded.', { session_id: str('Command session ID'), path: str('Relative output file path') }, ['session_id', 'path']),
  definition('browser_inspect', 'Load a website in an isolated JavaScript-enabled browser and return rendered text, links, form field names, script URLs and console messages to this chat for review. Does not submit forms. Redirects need separate review.', { url: str('HTTP(S) website URL') }, ['url']),

  definition('list_files', 'List files in the selected project. Skips dependency folders and credential files.', { directory: str('Relative directory, default .') }, []),
  definition('read_file', 'Read a UTF-8 file inside the project. Use offset to read subsequent chunks of a large file.', { path: str('Relative file path'), offset: { type: 'integer', minimum: 0, description: 'Character offset, default 0' } }, ['path']),
  definition('search_files', 'Find literal text in project files. Case insensitive.', { query: str('Text to find') }, ['query']),
  definition('write_file', 'Create or replace a UTF-8 file after the user reviews the proposed content. Parent folder must exist.', { path: str('Relative file path'), content: str('Complete new file contents') }, ['path', 'content']),
  definition('run_command', 'Run a non-interactive shell command after user approval. Starts in project directory; host shell is not sandboxed. 60 second timeout.', { command: str('Shell command') }, ['command']),
  definition('web_search', 'Search the web using DuckDuckGo after review. Returns titles and source URLs; use http_request to read a source.', { query: str('Search terms, maximum 500 characters') }, ['query']),
  definition('http_request', 'Fetch a web page or call a JSON HTTP API after review. Redirects require a new request. No stored credentials are attached.', { url: str('Complete HTTP(S) URL'), method: { type: 'string', enum: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] }, body: str('Optional JSON request body, maximum 16,000 characters') }, ['url']),
  definition('search_history', 'Search saved conversations in this project for relevant excerpts with conversation titles.', { query: str('Words to recall, maximum 500 characters') }, ['query']),
  definition('save_memory', 'Save a project decision or preference for future conversations after user review.', { content: str('Memory text, maximum 4,000 characters') }, ['content']),
];

function runCommand(command, root, signal, onOutput = () => {}) {
  if (typeof command !== 'string' || !command.trim() || command.length > 8000) throw new Error('Invalid command');
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new Error('Stopped'));
    const child = spawn('/bin/zsh', ['-l', '-c', command], { cwd: root, env: process.env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '', stopped = false;
    const stop = () => { stopped = true; try { process.kill(-child.pid, 'SIGKILL'); } catch {} };
    const timer = setTimeout(stop, 60000);
    signal?.addEventListener('abort', stop, { once: true });
    for (const stream of [child.stdout, child.stderr]) stream.on('data', data => {
      const text = data.toString();
      output = (output + text).slice(-MAX_OUTPUT);
      onOutput(text.slice(-MAX_OUTPUT));
    });
    const cleanup = () => { clearTimeout(timer); signal?.removeEventListener('abort', stop); };
    child.on('error', error => { cleanup(); reject(error); });
    child.on('close', code => { cleanup(); resolve(JSON.stringify({ exitCode: code, stopped, output })); });
  });
}

async function executeTool(name, args, { root, approve, signal, onOutput, allowedTools, store, fetcher, toolCatalog = definitions, modelInfo, outputLimit = 100000 }) {
  if (allowedTools && !allowedTools.includes(name)) throw new Error(`${name} is switched off in the tool kit.`);
  if (name === 'website_simulate') {
    if (!root) throw new Error('Open a project folder for simulation reports.');
    const prefix = args.report_prefix ?? 'website-simulation';
    if (typeof prefix !== 'string' || !prefix || prefix.length > 300) throw new Error('Supply a project-relative report prefix.');
    await safePath(root, prefix + '.json', true); await safePath(root, prefix + '.md', true);
    if (!await approve({ name, command: `Website attack simulation\nTarget: disposable loopback fixtures only\nReports: ${prefix}.json and ${prefix}.md`, root })) return 'User declined this simulation.';
    const { simulateWebsite, simulationMarkdown } = require('./website-simulation.cjs');
    const report = await simulateWebsite({ signal, browserProbe: async url => JSON.parse(await inspectBrowser({ url }, { signal, approve: async () => true })) });
    const context = { root, approve, signal, store, outputLimit: 8000000 };
    const json = await executeTool('write_file', { path: prefix + '.json', content: JSON.stringify(report, null, 2) + '\n' }, context);
    const markdown = await executeTool('write_file', { path: prefix + '.md', content: simulationMarkdown(report) }, context);
    return JSON.stringify({ target: report.target, summary: report.summary, cases: report.cases.map(({ id, fixture, status, defenseHeld }) => ({ id, fixture, status, defenseHeld })), limitations: report.limitations, reports: { json: json.startsWith('User declined') ? json : prefix + '.json', markdown: markdown.startsWith('User declined') ? markdown : prefix + '.md' }, output: simulationMarkdown(report) });
  }
  if (name === 'website_assess') {
    if (!root) throw new Error('Open a project folder for website assessment reports.');
    const { websitePlan, assessWebsite, markdownReport } = require('./website-assessment.cjs');
    const plan = websitePlan(args), prefix = args.report_prefix ?? 'website-assessment';
    if (typeof prefix !== 'string' || !prefix || prefix.length > 300) throw new Error('Supply a project-relative report prefix.');
    await safePath(root, prefix + '.json', true); await safePath(root, prefix + '.md', true);
    if (!await approve({ name, command: `GET-only website assessment\nTarget: ${plan.url}\nProfile: ${plan.profile}\nMaximum pages: ${plan.maxPages}\nProtected paths: ${plan.protectedPaths.join(', ') || '(none)'}\nReports: ${prefix}.json and ${prefix}.md`, root })) return 'User declined this website assessment.';
    const report = await assessWebsite(args, { fetcher, signal });
    const context = { root, approve, signal, store, outputLimit: 8000000 };
    const jsonSaved = await executeTool('write_file', { path: prefix + '.json', content: JSON.stringify(report, null, 2) + '\n' }, context);
    const mdSaved = await executeTool('write_file', { path: prefix + '.md', content: markdownReport(report) }, context);
    const grouped = Object.values(report.findings.reduce((groups, f) => { groups[f.id] ??= { id: f.id, severity: f.severity, title: f.title, confidence: f.confidence, occurrences: 0, example: { url: f.url, evidence: f.evidence }, remediation: f.remediation }; groups[f.id].occurrences++; return groups; }, {}));
    const checks = Object.values(report.cases.reduce((groups, c) => { const key = c.id + ':' + c.status; groups[key] ??= { id: c.id, status: c.status, count: 0, example: { target: c.target, evidence: c.evidence } }; groups[key].count++; return groups; }, {}));
    return JSON.stringify({ target: report.target, summary: report.summary, findings: grouped, checks, protectedPaths: report.scope.protectedPaths, limitations: report.limitations, reports: { json: jsonSaved.startsWith('User declined') ? jsonSaved : prefix + '.json', markdown: mdSaved.startsWith('User declined') ? mdSaved : prefix + '.md' }, output: `Completed ${report.summary.requests} GET requests. ${report.summary.errors} request errors. ${grouped.map(f => `${f.severity}: ${f.title} (${f.occurrences} paths, ${f.confidence})`).join('\n')}\nThe structured findings and checks above are the evidence summary. Read a saved report only for specific additional details. No authentication or website writes were performed.` });
  }
  if (!root && ['list_files', 'read_file', 'search_files', 'write_file', 'run_command'].includes(name)) throw new Error('Open a project folder to use this tool.');
  if (signal?.aborted) throw new Error('Stopped');
  if (!args || typeof args !== 'object') throw new Error('Invalid tool arguments');
  if (['security_tools', 'network_scan', 'network_read', 'network_stop'].includes(name)) return require('./security-tools.cjs').executeSecurity(name, args, { root, approve, signal, store });
  if (name === 'workspace_info') return JSON.stringify(require('./workspace-context.cjs').workspaceContext(store, toolCatalog, modelInfo));
  if (name === 'browser_inspect') return inspectBrowser(args, { approve, signal });
  if (name === 'command_save_output') {
    const chunks = []; let offset = 0, result;
    do { result = JSON.parse(await executeCommandSession('command_read', { session_id: args.session_id, offset, wait_ms: 0 }, { root, store })); chunks.push(result.output); offset = result.next_offset; } while (result.more);
    const content = JSON.stringify({ command: result.command, started: result.started, finished: result.finished, assessment: result.assessment, session_id: args.session_id, state: result.state, exitCode: result.exitCode, reason: result.reason, earliest_offset: result.earliest_offset, output: chunks.join('') }, null, 2);
    // Reuse the existing review, path containment and concurrent-edit checks.
    return executeTool('write_file', { path: args.path, content }, { root, approve, signal, store, outputLimit: 8000000 });
  }
  if (['command_start', 'command_read', 'command_write', 'command_stop'].includes(name)) return executeCommandSession(name, args, { root, approve, signal, store });
  if (['web_search', 'http_request'].includes(name)) return executeNetwork(name, args, { approve, signal, fetcher });
  if (name === 'search_history') { if (!store) throw new Error('Project history is unavailable.'); return JSON.stringify(searchHistory(store, args.query)); }
  if (name === 'save_memory') {
    if (!store || typeof args.content !== 'string' || !args.content.trim() || args.content.length > 4000) throw new Error('Memory must contain 1–4,000 characters.');
    if (!(await approve({ name, content: args.content }))) return 'User declined this memory.';
    if (signal?.aborted) throw new Error('Stopped');
    store.remember(args.content); return 'Saved project memory.';
  }
  if (name === 'list_files') return (await walk(root, args.directory || '.')).join('\n').slice(0, MAX_OUTPUT);
  if (name === 'read_file') {
    const file = await safePath(root, args.path);
    const stat = await fs.stat(file);
    if (!stat.isFile() || stat.size > 1024 * 1024) throw new Error('File must be text and smaller than 1 MB.');
    const content = await fs.readFile(file, 'utf8');
    if (content.includes('\0')) throw new Error('Binary file is not supported.');
    const offset = args.offset ?? 0;
    if (!Number.isSafeInteger(offset) || offset < 0 || offset > content.length) throw new Error('Offset must be a valid character position within the file.');
    const end = offset + MAX_OUTPUT;
    return content.slice(offset, end) + (content.length > end ? `\n[Truncated; next offset: ${end}; total characters: ${content.length}]` : '');
  }
  if (name === 'search_files') {
    if (typeof args.query !== 'string' || !args.query.trim()) throw new Error('Search query cannot be empty.');
    let output = '';
    for (const file of await walk(root)) {
      if (signal?.aborted) throw new Error('Stopped');
      try {
        const real = await safePath(root, file);
        if ((await fs.stat(real)).size > 256000) continue;
        const content = await fs.readFile(real, 'utf8');
        if (content.includes('\0')) continue;
        for (const [i, line] of content.split('\n').entries()) {
          if (line.toLowerCase().includes(args.query.toLowerCase())) output += `${file}:${i + 1}: ${line.slice(0, 400)}\n`;
          if (output.length >= MAX_OUTPUT) return output.slice(0, MAX_OUTPUT);
        }
      } catch {}
    }
    return output || 'No matches.';
  }
  if (name === 'write_file') {
    if (typeof args.content !== 'string' || args.content.length > outputLimit) throw new Error('Content must be text under 100,000 characters.');
    const file = await safePath(root, args.path, true);
    let before = null;
    try { before = await fs.readFile(file, 'utf8'); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (!(await approve({ name, path: args.path, before, after: args.content }))) return 'User declined this file edit.';
    if (signal?.aborted) throw new Error('Stopped');
    const checked = await safePath(root, args.path, true);
    let current = null;
    try { current = await fs.readFile(checked, 'utf8'); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (current !== before || checked !== file) throw new Error('File changed during review. Read it again before editing.');
    await fs.writeFile(file, args.content, { mode: 0o600 });
    return `Saved ${args.path} (${Buffer.byteLength(args.content)} bytes).`;
  }
  if (name === 'run_command') {
    if (typeof args.command !== 'string' || args.command.length > 8000) throw new Error('Invalid command');
    if (!(await approve({ name, command: args.command, root }))) return 'User declined this command.';
    return runCommand(args.command, root, signal, onOutput);
  }
  throw new Error(`Unknown tool: ${name}`);
}
module.exports = { definitions, safePath, executeTool, runCommand };
