const LIMIT = 24000;
function requestURL(value) {
  if (typeof value !== 'string' || value.length > 4000) throw new Error('Enter a URL under 4,000 characters.');
  const url = new URL(value);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error('Use an HTTP(S) URL without embedded credentials.');
  url.hash = '';
  return url.href;
}
function plainText(html) {
  return html.replace(/<(script|style|noscript|svg)\b[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<\/(?:p|div|h[1-6]|li|tr)>|<br\s*\/?\s*>/gi, '\n').replace(/<[^>]+>/g, '')
    .replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => { const code = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n); return code <= 0x10ffff ? String.fromCodePoint(code) : ''; })
    .replace(/&(amp|lt|gt|quot|apos|nbsp);/g, (_, n) => ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' }[n]))
    .replace(/[ \t]+/g, ' ').replace(/\n\s*\n/g, '\n').trim();
}
async function boundedResponse(response) {
  if (!response.body) return '';
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let text = '', bytes = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      bytes += next.value.length;
      if (bytes > 1024 * 1024) { text += '\n[Response truncated at 1 MB]'; break; }
      text += decoder.decode(next.value, { stream: true });
    }
    return text + decoder.decode();
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
async function executeNetwork(name, args, { approve, signal, fetcher = fetch }) {
  let url, method = 'GET', body;
  if (name === 'web_search') {
    if (typeof args.query !== 'string' || !args.query.trim() || args.query.length > 500) throw new Error('Search query must contain 1–500 characters.');
    url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(args.query.trim())}`;
  } else {
    url = requestURL(args.url);
    method = args.method || 'GET';
    if (!['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) throw new Error('Unsupported HTTP method.');
    if (args.body !== undefined) {
      if (method === 'GET' || typeof args.body !== 'string' || args.body.length > 16000) throw new Error('Request body must be text under 16,000 characters, on a non-GET request.');
      body = args.body;
      try { JSON.parse(body); } catch { throw new Error('Request body must be valid JSON.'); }
    }
  }
  if (signal?.aborted) throw new Error('Stopped');
  if (!(await approve({ name, url, method, body, query: args.query }))) return 'User declined this network request.';
  if (signal?.aborted) throw new Error('Stopped');
  const response = await fetcher(url, { method, ...(body !== undefined ? { body } : {}), redirect: 'manual',
    headers: { Accept: 'text/html, application/json, text/plain', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000) });
  if (response.status >= 300 && response.status < 400) throw new Error(`Redirect requires a separate reviewed request: ${new URL(response.headers.get('location') || url, url).href}`);
  const type = response.headers.get('content-type') || '';
  if (type && !/text\/|json|xml/.test(type)) throw new Error(`Unsupported response type: ${type}`);
  const raw = await boundedResponse(response);
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${plainText(raw).slice(0, 1000)}`);
  if (name === 'web_search') {
    const results = [];
    const pattern = /<a\b[^>]*class=["'][^"']*result__a[^"']*["'][^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
    for (const match of raw.matchAll(pattern)) {
      try {
        const linked = new URL(match[1].replace(/&amp;/g, '&'), url);
        const href = requestURL(linked.searchParams.get('uddg') || linked.href);
        results.push({ title: plainText(match[2]), url: href });
        if (results.length === 8) break;
      } catch {}
    }
    if (!results.length) throw new Error('Search returned no readable results. The search service may be rate limited. Try http_request on a known source.');
    return JSON.stringify({ query: args.query, source: url, results });
  }
  const content = /html/.test(type) ? plainText(raw) : raw;
  return JSON.stringify({ url, status: response.status, contentType: type, content: content.slice(0, LIMIT), truncated: content.length > LIMIT || raw.includes('[Response truncated at 1 MB]') });
}
module.exports = { executeNetwork, requestURL, plainText, boundedResponse };
