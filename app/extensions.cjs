const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const { createHash } = require('node:crypto');
const toolPrefix = id => `mcp_${createHash('sha256').update(id).digest('hex').slice(0, 12)}_`;
function serverConfig(value) {
  if (!value || typeof value.name !== 'string' || !value.name.trim() || value.name.length > 60 || typeof value.command !== 'string' || !value.command.trim() || value.command.length > 1000) throw new Error('Enter a server name and executable.');
  if (!Array.isArray(value.args) || value.args.length > 40 || value.args.some(arg => typeof arg !== 'string' || arg.length > 2000)) throw new Error('Arguments must be a JSON array of strings (up to 40).');
  return { name: value.name.trim(), command: value.command.trim(), args: [...value.args] };
}
class Extensions {
  constructor(onChange = () => {}) { this.connections = new Map(); this.onChange = onChange; }
  async connect(config, root) {
    if (this.connections.has(config.id)) throw new Error('This server is already connected.');
    const client = new Client({ name: 'wixal', version: require('../package.json').version }, { capabilities: {} });
    const transport = new StdioClientTransport({ command: config.command, args: config.args, cwd: root, stderr: 'pipe', maxBufferSize: 2 * 1024 * 1024 });
    // Consume stderr without exposing server diagnostics (which can contain secrets).
    transport.stderr?.on('data', () => {});
    const entry = { client, transport, config, tools: [], status: 'connecting' };
    this.connections.set(config.id, entry);
    client.onclose = () => { if (this.connections.get(config.id) === entry) { this.connections.delete(config.id); this.onChange(); } };
    try {
      await client.connect(transport, { timeout: 15000 });
      let cursor;
      const seen = new Set();
      const seenCursors = new Set();
      do {
        const page = await client.listTools(cursor ? { cursor } : {}, { timeout: 15000 });
        for (const tool of page.tools) {
          if (entry.tools.length >= 80) throw new Error('A server can expose at most 80 tools.');
          if (seen.has(tool.name)) throw new Error('Server returned duplicate tool names.');
          seen.add(tool.name);
          const name = `${toolPrefix(config.id)}${createHash('sha256').update(tool.name).digest('hex').slice(0, 16)}`;
          entry.tools.push({ original: tool.name, type: 'function', function: { name, description: `${config.name}: ${tool.description || tool.name}`.slice(0, 2000), parameters: tool.inputSchema } });
        }
        if (page.nextCursor && seenCursors.has(page.nextCursor)) throw new Error('Server repeated a tool catalog page.');
        cursor = page.nextCursor; if (cursor) seenCursors.add(cursor);
      } while (cursor);
      entry.status = 'connected'; this.onChange();
      return this.snapshot();
    } catch (error) { await this.disconnect(config.id); throw error; }
  }
  definitions() { return [...this.connections.values()].filter(e => e.status === 'connected').flatMap(e => e.tools.map(({ original, ...tool }) => tool)); }
  snapshot() { return [...this.connections.values()].map(e => ({ id: e.config.id, status: e.status, tools: e.tools.map(t => ({ id: t.function.name, name: t.original, description: t.function.description })) })); }
  async execute(name, args, { approve, signal, allowedTools }) {
    if (!allowedTools?.includes(name)) throw new Error('External tool is switched off in the tool kit.');
    const entry = [...this.connections.values()].find(e => e.status === 'connected' && e.tools.some(t => t.function.name === name));
    if (!entry) throw new Error('External tool is disconnected. Reconnect its server in the tool kit.');
    const tool = entry.tools.find(t => t.function.name === name);
    if (signal?.aborted) throw new Error('Stopped');
    if (!args || typeof args !== 'object' || Array.isArray(args) || JSON.stringify(args).length > 100000) throw new Error('Invalid external tool arguments.');
    require('./tool-validation.cjs').validate(args, tool.function.parameters);
    if (!(await approve({ name: 'external_tool', server: entry.config.name, tool: tool.original, arguments: args }))) return 'User declined this external tool call.';
    if (signal?.aborted) throw new Error('Stopped');
    const result = await entry.client.callTool({ name: tool.original, arguments: args }, undefined, { signal, timeout: 60000 });
    const text = (result.content || []).map(block => block.type === 'text' ? block.text : `[${block.type} result omitted; configure the tool to save artifacts in the project]`).join('\n');
    return `${result.isError ? 'Error: ' : ''}${text.slice(0, 24000)}${text.length > 24000 ? '\n[Truncated]' : ''}`;
  }
  async disconnect(id) { const entry = this.connections.get(id); this.connections.delete(id); if (entry) await entry.client.close().catch(() => {}); this.onChange(); }
  async close() { await Promise.all([...this.connections.keys()].map(id => this.disconnect(id))); }
}
module.exports = { Extensions, serverConfig, toolPrefix };
