const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

class Store {
  constructor(directory) {
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    this.file = path.join(directory, 'workspace.json');
    this.data = fs.existsSync(this.file) ? JSON.parse(fs.readFileSync(this.file, 'utf8')) : {
      version: 1, projects: [], sessions: [], memories: [], activeProject: null,
      activeSession: null, model: '', mode: 'agent',
    };
    // Fill in new preferences without replacing existing projects or conversations.
    this.data.enabledTools ??= ['list_files', 'read_file', 'search_files', 'write_file', 'run_command'];
    this.data.contextSize ??= 16384;
  }
  save() {
    fs.writeFileSync(this.file + '.tmp', JSON.stringify(this.data, null, 2), { mode: 0o600 });
    fs.renameSync(this.file + '.tmp', this.file);
  }
  project() { return this.data.projects.find(p => p.id === this.data.activeProject); }
  session() { return this.data.sessions.find(s => s.id === this.data.activeSession); }
  addProject(root) {
    root = fs.realpathSync(root);
    if (!fs.statSync(root).isDirectory()) throw new Error('Choose a project folder.');
    let project = this.data.projects.find(p => p.root === root);
    if (!project) {
      project = { id: randomUUID(), name: path.basename(root), root, created: Date.now() };
      this.data.projects.push(project);
    }
    this.selectProject(project.id);
    return project;
  }
  selectProject(id) {
    if (!this.data.projects.some(p => p.id === id)) throw new Error('Unknown project');
    this.data.activeProject = id;
    this.data.activeSession = this.data.sessions.findLast(s => s.projectId === id)?.id || null;
    if (!this.data.activeSession) this.newSession();
    this.save();
  }
  newSession() {
    const session = { id: randomUUID(), projectId: this.data.activeProject, title: 'New conversation', created: Date.now(), messages: [] };
    this.data.sessions.push(session);
    this.data.activeSession = session.id;
    this.save();
    return session;
  }
  selectSession(id) {
    const session = this.data.sessions.find(s => s.id === id && s.projectId === this.data.activeProject);
    if (!session) throw new Error('Unknown conversation');
    this.data.activeSession = id;
    this.save();
  }
  remember(content) {
    if (typeof content !== 'string' || !content.trim() || content.length > 4000) throw new Error('Memory must contain 1–4,000 characters.');
    this.data.memories.push({ id: randomUUID(), projectId: this.data.activeProject, content: content.trim(), created: Date.now() });
    this.save();
  }
  snapshot() { return structuredClone(this.data); }
}
module.exports = { Store };
