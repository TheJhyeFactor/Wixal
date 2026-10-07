const http = require('node:http');
const { randomBytes } = require('node:crypto');
const { assessWebsite, markdownReport } = require('./website-assessment.cjs');
async function simulateWebsite({ signal, browserProbe } = {}) {
  const cases = [], started = new Date().toISOString();
  for (const hardened of [false, true]) {
    const mode = hardened ? 'hardened' : 'vulnerable', token = randomBytes(24).toString('hex');
    let valid = true, writes = 0; const attempts = new Map();
    const escape = text => text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    let origin;
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, origin), authenticated = req.headers.cookie === `lab_session=${token}` && valid;
      const json = (status, value) => { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(value)); };
      if (hardened) { res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'"); res.setHeader('X-Content-Type-Options', 'nosniff'); res.setHeader('Referrer-Policy', 'no-referrer'); }
      if (url.pathname === '/api/admin') return json(hardened && !authenticated ? 401 : 200, { labOnly: true });
      if (url.pathname === '/write') { if (!authenticated) return json(401, {}); if (hardened && req.headers.origin !== origin) return json(403, {}); writes++; return json(200, { writes }); }
      if (url.pathname === '/logout') { if (hardened) valid = false; return json(200, {}); }
      if (url.pathname === '/login') { const key = hardened ? req.socket.remoteAddress : req.headers['x-forwarded-for'] || req.socket.remoteAddress; const count = attempts.get(key) || 0; attempts.set(key, count + 1); return json(count >= 8 ? 429 : 401, {}); }
      if (url.pathname === '/.env' || url.pathname === '/.git/HEAD') { if (hardened) return json(404, {}); res.setHeader('Content-Type', 'text/plain'); return res.end(url.pathname === '/.env' ? 'LAB_SECRET=SYNTHETIC_CANARY_ONLY' : 'ref: refs/heads/lab'); }
      if (url.searchParams.has('next') && !hardened) { res.writeHead(302, { Location: url.searchParams.get('next') }); return res.end(); }
      const input = url.searchParams.get('wixal_probe') || ''; res.setHeader('Content-Type', 'text/html'); res.end(`<html><title>Wixal ${mode} lab</title><body>${hardened ? escape(input) : input}</body></html>`);
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
    const request = (route, init) => { if (signal?.aborted) throw new Error('Simulation stopped.'); return fetch(origin + route, { signal, ...init }); };
    const record = (id, defended, evidence) => cases.push({ id, fixture: mode, status: (hardened ? defended : !defended) ? 'expected-result' : 'unexpected-result', defenseHeld: defended, evidence });
    try {
      const report = await assessWebsite({ url: origin, profile: 'probes', max_pages: 1, protected_paths: ['/api/admin'] }, { signal, delayMs: 0 });
      for (const id of ['frame-protection', 'reflection-canary', 'sensitive-file-exposure', 'open-redirect', 'unauthenticated-access']) record(id, !report.findings.some(f => f.id === id), { findingObserved: report.findings.some(f => f.id === id) });
      const csrf = await request('/write', { method: 'POST', headers: { Cookie: `lab_session=${token}`, Origin: 'https://wixal-attacker.invalid' } }); record('cross-origin-write', csrf.status === 403, { status: csrf.status, writes });
      const statuses = []; for (let i = 0; i < 9; i++) statuses.push((await request('/login', { method: 'POST', headers: { 'x-forwarded-for': '198.51.100.9' } })).status);
      const spoof = await request('/login', { method: 'POST', headers: { 'x-forwarded-for': '198.51.100.10' } }); record('forwarded-header-throttle', spoof.status === 429, { statuses, spoofedHeaderStatus: spoof.status });
      await request('/logout', { method: 'POST', headers: { Cookie: `lab_session=${token}` } }); const replay = await request('/api/admin', { headers: { Cookie: `lab_session=${token}` } }); record('logout-replay', replay.status === 401, { status: replay.status });
      if (browserProbe) {
        const payload = '<script>document.body.append("WIXAL_XSS_EXECUTED")</script>';
        const url = new URL(origin); url.searchParams.set('wixal_probe', payload);
        const result = await browserProbe(url.href); record('browser-script-execution', !result.text.includes('WIXAL_XSS_EXECUTED') || result.text.includes('<script>'), { visibleText: result.text.slice(0, 300), scriptExecuted: result.text === 'WIXAL_XSS_EXECUTED' });
      }
    } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  }
  return { schema: 1, target: 'disposable loopback fixtures', profile: 'attack-simulation', started, finished: new Date().toISOString(), cases, findings: [], references: {}, summary: { cases: cases.length, expected: cases.filter(c => c.status === 'expected-result').length, unexpected: cases.filter(c => c.status === 'unexpected-result').length }, limitations: ['These are deliberately vulnerable and hardened local fixtures, not findings about a production website.', 'Synthetic session tokens and canary secrets only. No external target or credentials are used.'] };
}
function simulationMarkdown(report) {
  return `# Wixal website attack simulations\n\n${report.limitations.join('\n\n')}\n\n| Test | Fixture | Defense held | Validation | Evidence |\n| --- | --- | --- | --- | --- |\n${report.cases.map(c => `| ${c.id} | ${c.fixture} | ${c.defenseHeld} | ${c.status} | ${JSON.stringify(c.evidence).replace(/\|/g,'\\|')} |`).join('\n')}\n\n${report.summary.expected}/${report.summary.cases} expected results; ${report.summary.unexpected} unexpected results.\n`;
}
module.exports = { simulateWebsite, simulationMarkdown };
