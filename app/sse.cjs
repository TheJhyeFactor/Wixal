// Decode arbitrary UTF-8 and CRLF chunk boundaries; callers decide what proves completion.
async function readEvents(response, consume) {
  if (!response.body) throw new Error('The provider returned no response stream.');
  const decoder = new TextDecoder(); let buffer = '';
  const block = value => {
    const data = value.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
    if (data) consume(data);
  };
  for await (const bytes of response.body) {
    buffer += decoder.decode(bytes, { stream: true });
    buffer = buffer.replace(/\r\n/g, '\n');
    let end;
    while ((end = buffer.indexOf('\n\n')) !== -1) { block(buffer.slice(0, end)); buffer = buffer.slice(end + 2); }
    if (buffer.length > 10 * 1024 * 1024) throw new Error('Provider stream event exceeded the size limit.');
  }
  buffer += decoder.decode(); if (buffer.trim()) block(buffer);
}
function metrics(started, tokens = 0) {
  const seconds = (Date.now() - started) / 1000;
  return { tokens, seconds, tokensPerSecond: seconds ? Math.round(tokens / seconds * 10) / 10 : 0 };
}
module.exports = { readEvents, metrics };
