const LIMIT = 24000, BYTE_LIMIT = 1024 * 1024;
function requestURL(value) {
  if (typeof value !== 'string' || value.length > 4000) throw new Error('Enter a URL under 4,000 characters.');
  let url; try { url = new URL(value); } catch { throw new Error('Enter a complete HTTP(S) URL, such as https://jhye.dev/.'); }
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error('Use an HTTP(S) URL without embedded credentials.');
  url.hash = '';
  return url.href;
}
function entities(text) {
 return text.replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => { const code = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n); return code <= 0x10ffff && !(code >= 0xd800 && code <= 0xdfff) ? String.fromCodePoint(code) : ''; })
 .replace(/&(amp|lt|gt|quot|apos|nbsp);/gi, (_, n) => ({ amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' ' }[n.toLowerCase()]));
}
function plainText(html) {
  return entities(html.replace(/<(script|style|noscript|svg)\b[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<\/(?:p|div|h[1-6]|li|tr)>|<br\s*\/?\s*>/gi, '\n').replace(/<[^>]+>/g, ''))
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
      const remaining = BYTE_LIMIT - bytes;
      text += decoder.decode(next.value.subarray(0, remaining), { stream: true });
      bytes += next.value.length;
      if (bytes > BYTE_LIMIT) return text + decoder.decode() + '\n[Response truncated at 1 MB]';
    }
    return text + decoder.decode();
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
function attributes(tag) {
 const out = {}; for (const match of tag.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) out[match[1].toLowerCase()] = entities(match[2] ?? match[3] ?? match[4]); return out;
}
function searchResults(html, source, limit = 8) {
 const matches = [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)], results = [], seen = new Set();
 for (let i = 0; i < matches.length; i++) {
  const match = matches[i], attrs = attributes(match[1]);
  if (!attrs.class?.split(/\s+/).includes('result__a')) continue;
  try {
   const linked = new URL(attrs.href, source), url = requestURL(linked.searchParams.get('uddg') || linked.href), title = plainText(match[2]);
   if (seen.has(url) || !title) continue;
   const end = matches.slice(i + 1).find(m => attributes(m[1]).class?.split(/\s+/).includes('result__a'))?.index ?? html.length;
   const section = html.slice(match.index + match[0].length, end);
   const snippet = [...section.matchAll(/<(?:a|div|span)\b([^>]*)>([\s\S]*?)<\/(?:a|div|span)>/gi)].find(m => attributes(m[1]).class?.split(/\s+/).includes('result__snippet'));
   results.push({ title, url, ...(snippet ? { snippet: plainText(snippet[2]).slice(0, 1000) } : {}) }); seen.add(url);
   if (results.length === limit) break;
  } catch {}
 }
 return results;
}
async function executeNetwork(name, args, { approve, signal, fetcher = fetch }) {
  let url, method = 'GET', body;
  const offset = args.offset ?? 0, maxChars = args.max_chars ?? LIMIT;
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(maxChars) || maxChars < 100 || maxChars > LIMIT) throw new Error('Use a nonnegative offset and max_chars between 100 and 24,000.');
  const count = args.limit ?? 8;
  if (name === 'web_search') {
    if (typeof args.query !== 'string' || !args.query.trim() || args.query.length > 500) throw new Error('Search query must contain 1–500 characters.');
    if (!Number.isSafeInteger(count) || count < 1 || count > 10) throw new Error('Search limit must be between 1 and 10.');
    url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(args.query.trim())}`;
  } else if (name === 'http_request') {
    url = requestURL(args.url); method = args.method || 'GET';
    if (!['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) throw new Error('Unsupported HTTP method.');
    if (offset && !['GET','HEAD'].includes(method)) throw new Error('Pagination is supported only for GET; a write request must not be repeated to read more output.');
    if (args.body !== undefined) {
      if (['GET','HEAD'].includes(method) || typeof args.body !== 'string' || args.body.length > 16000) throw new Error('Request body must be text under 16,000 characters, on a non-GET request.');
      body = args.body; try { JSON.parse(body); } catch { throw new Error('Request body must be valid JSON.'); }
    }
  } else throw new Error('Unknown network tool.');
  if (signal?.aborted) throw new Error('Stopped');
  if (!(await approve({ name, url, method, body, query: args.query, offset }))) return 'User declined this network request.';
  if (signal?.aborted) throw new Error('Stopped');
  const response = await fetcher(url, { method, ...(body !== undefined ? { body } : {}), redirect: 'manual',
    headers: { Accept: 'text/html, application/json, text/plain', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000) });
  if (response.status >= 300 && response.status < 400) throw new Error(`Redirect requires a separate reviewed request: ${requestURL(new URL(response.headers.get('location') || url, url).href)}`);
  const type = response.headers.get('content-type') || '';
  if (type && !/text\/|json|xml/i.test(type) && method !== 'HEAD') throw new Error(`Unsupported response type: ${type}`);
  const raw = method === 'HEAD' ? '' : await boundedResponse(response);
  if (name === 'web_search') {
    if ([202,403,429].includes(response.status) || /anomaly\.js|challenge-form|bots use DuckDuckGo|<title[^>]*>[^<]*(?:verify you are human|captcha)/i.test(raw)) throw new Error(`Search service blocked this request (HTTP ${response.status}). No search evidence was returned. Try a known source URL or retry later.`);
    if (!response.ok) throw new Error(`Search service HTTP ${response.status}: ${plainText(raw).slice(0, 500)}`);
    const results = searchResults(raw, url, count);
    if (!results.length && !/no results|no more results/i.test(plainText(raw))) throw new Error('Search returned an unsupported page. No search evidence was extracted. Try a known source URL.');
    return JSON.stringify({ query: args.query, source: url, results, state: results.length ? 'completed' : 'no_results', ...(results.length ? {} : { output: 'No results for this query.' }) });
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${plainText(raw).slice(0, 1000)}`);
  const content = /html/i.test(type) ? plainText(raw) : raw;
  if (offset > content.length) throw new Error(`Offset exceeds the ${content.length} characters currently returned. The page may have changed.`);
  const end = Math.min(offset + maxChars, content.length);
  const headers = {}; for (const name of ['content-type','content-length','last-modified','etag','cache-control']) { const value = response.headers.get(name); if (value) headers[name] = value; }
  return JSON.stringify({ url, status: response.status, contentType: type, headers, content: content.slice(offset, end), offset, next_offset: end, total_chars: content.length, more: end < content.length, truncated: end < content.length || raw.includes('[Response truncated at 1 MB]'), ...(raw.includes('[Response truncated at 1 MB]') ? { response_limit: '1 MB; additional bytes were not retained' } : {}) });
}
module.exports = { executeNetwork, requestURL, plainText, boundedResponse, searchResults };
