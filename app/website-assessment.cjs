const { createHash, randomBytes } = require('node:crypto');
const hash = value => createHash('sha256').update(value).digest('hex');
const references = {
  headers: 'https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html',
  framing: 'https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/11-Client-side_Testing/09-Testing_for_Clickjacking',
  xss: 'https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/01-Testing_for_Reflected_Cross_Site_Scripting',
};
function websitePlan(args) {
  if (!args || typeof args.url !== 'string') throw new Error('Supply the authorised HTTP(S) website URL.');
  const url = new URL(args.url);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Use an HTTP(S) website URL without credentials, query parameters or fragments.');
  const profile = args.profile || 'baseline';
  if (!['baseline', 'probes'].includes(profile)) throw new Error('Choose baseline or probes.');
  const maxPages = args.max_pages ?? 8;
  if (!Number.isInteger(maxPages) || maxPages < 1 || maxPages > 12) throw new Error('Assess 1–12 pages per run.');
  const protectedPaths = args.protected_paths || [];
  if (!Array.isArray(protectedPaths) || protectedPaths.length > 8 || protectedPaths.some(p => typeof p !== 'string' || p.length > 300 || !p.startsWith('/') || p.startsWith('//') || p.includes('\\') || /[?#\r\n]/.test(p) || new URL(p, url).origin !== url.origin)) throw new Error('Protected paths must be up to eight same-origin absolute paths without queries.');
  return { url: url.href, origin: url.origin, profile, maxPages, protectedPaths, requestLimit: 36, timeoutSeconds: 120 };
}
async function boundedBody(response, limit = 512 * 1024) {
  if (!response.body) return { text: '', bytes: 0, truncated: false };
  const reader = response.body.getReader(), chunks = []; let bytes = 0, truncated = false;
  try {
    while (true) { const { value, done } = await reader.read(); if (done) break; const room = limit - bytes; chunks.push(value.subarray(0, room)); bytes += Math.min(room, value.byteLength); if (value.byteLength >= room) { truncated = true; await reader.cancel(); break; } }
  } finally { reader.releaseLock(); }
  return { text: Buffer.concat(chunks).toString('utf8'), bytes, truncated };
}
function cookieEvidence(cookies) {
  return cookies.map(cookie => ({ name: cookie.split('=')[0], httpOnly: /;\s*httponly(?:;|$)/i.test(cookie), secure: /;\s*secure(?:;|$)/i.test(cookie), sameSite: cookie.match(/;\s*samesite=(\w+)/i)?.[1] || null, path: cookie.match(/;\s*path=([^;]+)/i)?.[1] || null }));
}
async function assessWebsite(args, { fetcher = fetch, signal, onCase = () => {}, delayMs = 200 } = {}) {
  const plan = websitePlan(args), started = new Date().toISOString(), cases = [], findings = [], pages = [], requests = [];
  const abort = AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(plan.timeoutSeconds * 1000)]);
  const seen = new Set(), queue = [plan.url];
  const finding = (id, severity, title, url, evidence, remediation, confidence = 'confirmed configuration') => findings.push({ id, severity, title, url, evidence, remediation, confidence });
  async function request(url, headers = {}) {
    if (new URL(url).origin !== plan.origin) throw new Error('Assessment request left the authorised origin.');
    if (requests.length >= plan.requestLimit) throw new Error('Assessment request limit reached.');
    if (abort.aborted) throw new Error('Assessment stopped or timed out.');
    if (requests.length && delayMs) await new Promise(resolve => setTimeout(resolve, delayMs));
    const requestSignal = AbortSignal.any([abort, AbortSignal.timeout(10000)]);
    let response, body;
    try {
      response = await fetcher(url, { method: 'GET', redirect: 'manual', credentials: 'omit', headers: { 'User-Agent': 'Wixal-Website-Assessment/0.7', ...headers }, signal: requestSignal });
      body = await boundedBody(response);
    } catch (error) { requests.push({ url, method: 'GET', error: error.message }); throw error; }
    const evidence = { url, method: 'GET', status: response.status, contentType: response.headers.get('content-type'), bytes: body.bytes, truncated: body.truncated, bodySha256: hash(body.text), headers: Object.fromEntries(['content-security-policy', 'x-frame-options', 'strict-transport-security', 'x-content-type-options', 'referrer-policy', 'permissions-policy', 'cache-control', 'access-control-allow-origin', 'access-control-allow-credentials', 'location'].map(h => [h, response.headers.get(h)])), cookies: cookieEvidence(response.headers.getSetCookie?.() || []) };
    requests.push(evidence); return { ...evidence, body: body.text };
  }
  const check = (id, status, target, evidence) => { const row = { id, status, target, evidence }; cases.push(row); onCase(row); };
  while (queue.length && pages.length < plan.maxPages) {
    const url = queue.shift(); if (seen.has(url)) continue; seen.add(url);
    try {
      const result = await request(url); pages.push(result.url);
      check('http-response', result.status < 400 ? 'observed' : 'needs-review', url, { status: result.status, bytes: result.bytes, truncated: result.truncated });
      if (result.status >= 300 && result.status < 400) {
        const location = result.headers.location && new URL(result.headers.location, url);
        if (location?.origin === plan.origin && !location.search) queue.unshift(location.href);
        else check('redirect-scope', 'not-followed', url, { location: location ? location.origin + location.pathname : null });
        continue;
      }
      if (result.status !== 200 || !result.contentType?.includes('text/html')) continue;
      const h = result.headers, csp = h['content-security-policy'];
      const cspMeta = /<meta\s[^>]*http-equiv\s*=\s*["']?content-security-policy/i.test(result.body);
      const framed = csp && /(?:^|;)\s*frame-ancestors\s+(?:'none'|'self')\s*(?:;|$)/i.test(csp) || /^(deny|sameorigin)$/i.test(h['x-frame-options'] || '');
      check('frame-protection', framed ? 'pass' : 'fail', url, { csp, xFrameOptions: h['x-frame-options'] });
      if (!framed) finding('frame-protection', 'medium', 'Page has no restrictive frame protection', url, 'No restrictive frame-ancestors directive or DENY/SAMEORIGIN response header observed. Browser impact requires a framing test.', "Set Content-Security-Policy: frame-ancestors 'none' on HTML responses.");
      check('content-security-policy', csp || cspMeta ? 'observed' : 'missing', url, { responsePolicy: csp, metaPolicy: cspMeta });
      if (!csp && !cspMeta) finding('content-security-policy', 'low', 'Content Security Policy is absent', url, 'No enforced response-header or meta CSP observed. This alone does not establish XSS.', 'Build a policy for the actual script/style/image sources; start with Report-Only to validate compatibility.');
      for (const [header, expected, remediation] of [['x-content-type-options', 'nosniff', 'Set X-Content-Type-Options: nosniff.'], ['referrer-policy', null, 'Set an explicit Referrer-Policy such as strict-origin-when-cross-origin.']]) {
        const present = expected ? h[header]?.toLowerCase() === expected : !!h[header]; check(header, present ? 'pass' : 'missing', url, h[header]);
        if (!present) finding(header, 'low', `Missing or ineffective ${header}`, url, `Observed value: ${h[header] || '(absent)'}`, remediation);
      }
      check('https-hsts', new URL(url).protocol === 'https:' && /max-age=[1-9]\d*/i.test(h['strict-transport-security'] || '') ? 'pass' : 'needs-review', url, { protocol: new URL(url).protocol, hsts: h['strict-transport-security'] });
      for (const c of result.cookies) if (!c.httpOnly || new URL(url).protocol === 'https:' && !c.secure || !c.sameSite) finding('cookie-attributes', 'needs-triage', 'A response cookie needs attribute review', url, c, 'Determine whether this cookie carries a session. Apply HttpOnly, Secure and appropriate SameSite to authentication cookies.', 'cookie purpose unknown');
      for (const match of result.body.matchAll(/<a\b[^>]*\bhref=["']([^"']+)["']/gi)) {
        try { const link = new URL(match[1].replace(/&amp;/g, '&'), url); const start = new URL(plan.url); if (link.origin === plan.origin && !link.search && !link.hash && (start.pathname === '/' || link.pathname.startsWith(start.pathname)) && !/\.(?:png|jpg|pdf|zip|svg|webp)$/i.test(link.pathname) && !seen.has(link.href) && queue.length < 100) queue.push(link.href); } catch {}
      }
    } catch (error) { if (abort.aborted) throw error; check('request-error', 'error', url, error.message); }
  }
  for (const path of plan.protectedPaths) {
    const url = new URL(path, plan.origin).href;
    try { const r = await request(url); check('unauthenticated-access', [401, 403].includes(r.status) ? 'pass' : 'needs-review', url, { status: r.status, contentType: r.contentType, noStore: /no-store/i.test(r.headers['cache-control'] || '') });
      if (r.status === 200 && r.contentType?.includes('application/json')) finding('unauthenticated-access', 'needs-triage', 'Protected path returned JSON without authentication', url, { status: r.status, bodySha256: r.bodySha256 }, 'Verify whether this response contains protected data or is an intentionally public status response.', 'protected-path semantics require validation');
      const cors = await request(url, { Origin: 'https://wixal-probe.invalid' }); check('credentialed-cors', cors.headers['access-control-allow-origin'] === 'https://wixal-probe.invalid' && cors.headers['access-control-allow-credentials'] === 'true' ? 'fail' : 'pass', url, { origin: cors.headers['access-control-allow-origin'], credentials: cors.headers['access-control-allow-credentials'] });
    } catch (error) { if (abort.aborted) throw error; check('protected-path-error', 'error', url, error.message); }
  }
  if (plan.profile === 'probes') {
    const marker = 'WIXAL_' + randomBytes(8).toString('hex'), payload = `<script>globalThis.__wixalProbe='${marker}'</script>`;
    const url = new URL(plan.url); url.searchParams.set('wixal_probe', payload);
    try { const r = await request(url.href); const raw = r.body.includes(payload); check('reflection-canary', raw ? 'needs-review' : r.truncated ? 'inconclusive' : 'no-reflection-observed', url.href, { marker, rawMarkupReflected: raw, truncated: r.truncated }); if (raw) finding('reflection-canary', 'needs-triage', 'Raw canary markup was reflected', url.href, { marker, bodySha256: r.bodySha256 }, 'Validate the HTML context and execution in an isolated browser before claiming XSS.', 'reflection observed; execution unverified'); } catch (e) { if (abort.aborted) throw e; check('reflection-canary', 'error', url.href, e.message); }
    for (const path of ['/.env', '/.git/HEAD']) {
      try { const r = await request(new URL(path, plan.origin).href); const signature = path === '/.git/HEAD' ? /^ref: refs\/heads\//m.test(r.body) : /^(?:[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*)\s*=/m.test(r.body); const exposed = r.status === 200 && signature && !r.contentType?.includes('text/html'); check('sensitive-file-exposure', exposed ? 'fail' : r.truncated ? 'inconclusive' : 'no-exposure-observed', r.url, { status: r.status, matchedSignature: signature, bodySha256: r.bodySha256, truncated: r.truncated }); if (exposed) finding('sensitive-file-exposure', 'high', 'Sensitive file signature returned over HTTP', r.url, { status: r.status, bodySha256: r.bodySha256, contents: 'REDACTED' }, 'Remove the file from served assets. If secrets were exposed, rotate them and inspect access logs.'); } catch (e) { if (abort.aborted) throw e; check('sensitive-file-exposure', 'error', path, e.message); }
    }
    const redirect = new URL(plan.url); redirect.searchParams.set('next', 'https://wixal-probe.invalid/');
    try { const r = await request(redirect.href); const destination = r.headers.location && new URL(r.headers.location, redirect); const external = r.status >= 300 && r.status < 400 && destination?.origin === 'https://wixal-probe.invalid'; check('open-redirect-canary', external ? 'fail' : 'no-redirect-observed', redirect.href, { status: r.status, destination: destination?.origin || null }); if (external) finding('open-redirect', 'medium', 'Untrusted next parameter controls an external redirect', redirect.href, { status: r.status, destination: destination.origin }, 'Allow only validated relative or explicitly permitted redirect destinations.'); } catch (e) { if (abort.aborted) throw e; check('open-redirect-canary', 'error', redirect.href, e.message); }
  }
  return { schema: 1, target: plan.url, profile: plan.profile, started, finished: new Date().toISOString(), scope: plan, requests, cases, findings, references, limitations: ['Unauthenticated GET checks only; no writes or login attempts.', 'Reflection is not proven code execution. Missing headers are configuration findings.', 'Same-origin crawl; redirects outside the origin are not followed.', 'Bodies are hashed, not saved. Cookie values are omitted.'], summary: { requests: requests.length, pages: pages.length, cases: cases.length, findings: findings.length, errors: cases.filter(c => c.status === 'error').length } };
}
function markdownReport(report) {
  const cell = s => String(s ?? '').replace(/\|/g, '\\|').replace(/[\r\n]/g, ' ');
  return `# Website assessment: ${report.target}\n\nStarted: ${report.started}\n\nFinished: ${report.finished}\n\nProfile: ${report.profile}; ${report.summary.requests} GET requests; ${report.summary.errors} request errors.\n\n## Findings\n\n| Severity | Finding | Target | Confidence |\n| --- | --- | --- | --- |\n${report.findings.map(f => `| ${cell(f.severity)} | ${cell(f.title)} | ${cell(f.url)} | ${cell(f.confidence)} |`).join('\n') || '| — | No findings in these checks | — | Limited coverage |'}\n\n${report.findings.map(f => `### ${f.id}: ${f.title}\n\nEvidence: ${JSON.stringify(f.evidence)}\n\nRemediation: ${f.remediation}\n`).join('\n')}\n## Test cases\n\n| Case | Result | Target | Evidence |\n| --- | --- | --- | --- |\n${report.cases.map(c => `| ${cell(c.id)} | ${cell(c.status)} | ${cell(c.target)} | ${cell(JSON.stringify(c.evidence))} |`).join('\n')}\n\n## Limits\n\n${report.limitations.map(s => '- ' + s).join('\n')}\n\nReferences: ${Object.values(references).join(', ')}\n`;
}
module.exports = { websitePlan, assessWebsite, markdownReport, boundedBody, cookieEvidence };
