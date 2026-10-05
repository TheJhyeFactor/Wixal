const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { randomBytes, randomUUID } = require('node:crypto');
const { matches } = require('./chatgpt-auth.cjs');
const { executeTool } = require('./tools.cjs');
const { toolSpecs } = require('./companion-tools.cjs');
class Companion {
  constructor(store, directory, onChange = () => {}) {
    this.store = store; this.file = path.join(directory, 'wixal-connection.json'); this.onChange = onChange;
    for (const task of store.data.tasks) if (['running', 'waiting_review'].includes(task.status)) { task.status = 'interrupted'; task.updated = Date.now(); }
  }
  snapshot() { return { running: !!this.server, endpoint: this.endpoint || null, connectionFile: this.server ? this.file : null }; }
  sharedProject(id) {
    if (!this.server || !this.store.data.companion.sharedProjects.includes(id)) throw new Error('This project is not shared with ChatGPT. Enable sharing in Wixal.');
    const project = this.store.data.projects.find(p => p.id === id); if (!project) throw new Error('Unknown project.'); return project;
  }
  async call(name, args) {
    const spec = toolSpecs.find(t => t.name === name); if (!spec) throw new Error('Unknown companion tool.');
    const { z } = require('zod'); args = z.object(spec.schema).strict().parse(args);
    if (!this.server) throw new Error('Wixal companion is paused.');
    if (name === 'list_projects') return this.store.data.projects.filter(p => this.store.data.companion.sharedProjects.includes(p.id)).map(p => ({ id: p.id, name: p.name }));
    if (name === 'get_task_status') {
      const task = this.store.data.tasks.find(t => t.id === args.taskId); if (!task) throw new Error('Unknown task.'); this.sharedProject(task.projectId);
      return { id: task.id, title: task.title, status: task.status, result: task.result || null, outcomes: task.outcomes || [], error: task.error || null, updated: task.updated };
    }
    const project = this.sharedProject(args.projectId);
    if (name === 'create_task') {
      if (!args.prompt.trim() || !args.title.trim()) throw new Error('Task title and prompt cannot be blank.');
      if (this.store.data.tasks.filter(t => t.status === 'queued').length >= 100) throw new Error('Task inbox is full. Review existing tasks first.');
      const task = { id: randomUUID(), projectId: project.id, title: args.title.trim(), prompt: args.prompt.trim(), source: 'ChatGPT', status: 'queued', created: Date.now(), updated: Date.now() };
      this.store.data.tasks.push(task); this.store.save(); this.onChange(); return { id: task.id, status: task.status, message: 'Queued. The user must start this task in Wixal.' };
    }
    const mapping = { get_project_context: ['list_files', {}], read_project_file: ['read_file', { path: args.path }], search_project: ['search_files', { query: args.query }] };
    const [tool, arguments_] = mapping[name];
    const result = await executeTool(tool, arguments_, { root: project.root, allowedTools: this.store.data.enabledTools });
    this.sharedProject(project.id);
    if (name === 'get_project_context') return { id: project.id, name: project.name, files: result,
      ...(this.store.data.companion.shareMemory ? { memories: this.store.data.memories.filter(m => m.projectId === project.id).map(m => m.content) } : {}) };
    return { projectId: project.id, result };
  }
  async start() {
    if (this.server) return this.snapshot();
    if (this.starting) return this.starting;
    this.starting = this.startBridge();
    try { return await this.starting; } finally { this.starting = null; }
  }
  async startBridge() {
    this.token = randomBytes(32).toString('base64url');
    let requests = 0, resetAt = Date.now() + 60000;
    const server = http.createServer(async (request, response) => {
      response.setHeader('Content-Type', 'application/json'); response.setHeader('Cache-Control', 'no-store');
      const reject = (status, message) => { response.writeHead(status); response.end(JSON.stringify({ error: message })); };
      if (!this.server || !this.endpoint || request.headers.host !== new URL(this.endpoint).host || request.headers.origin || request.headers['sec-fetch-site']) return reject(403, 'Local paired clients only.');
      if (!matches(request.headers.authorization, `Bearer ${this.token}`)) return reject(401, 'Pairing required.');
      if (request.method !== 'POST' || request.url !== '/bridge') return reject(404, 'Not found.');
      if (Date.now() > resetAt) { requests = 0; resetAt = Date.now() + 60000; }
      if (++requests > 120) return reject(429, 'Slow down companion requests.');
      try {
        let body = '';
        for await (const chunk of request) { body += chunk; if (body.length > 24000) return reject(413, 'Request too large.'); }
        const data = JSON.parse(body), result = await this.call(data.name, data.args);
        response.end(JSON.stringify({ result }));
      } catch (error) { reject(400, error.message); }
    });
    server.requestTimeout = 15000; server.headersTimeout = 10000;
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
    this.server = server; this.endpoint = `http://127.0.0.1:${server.address().port}`;
    try {
      fs.writeFileSync(this.file + '.tmp', JSON.stringify({ endpoint: this.endpoint, token: this.token }), { mode: 0o600 }); fs.chmodSync(this.file + '.tmp', 0o600); fs.renameSync(this.file + '.tmp', this.file);
    } catch (error) { server.close(); this.server = null; this.token = null; this.endpoint = null; throw error; }
    return this.snapshot();
  }
  async stop() {
    await this.starting?.catch(() => {});
    const server = this.server; this.server = null; this.token = null; this.endpoint = null;
    try { fs.unlinkSync(this.file); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (server) { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  }
}
module.exports = { Companion };
