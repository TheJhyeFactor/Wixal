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
    const allTools = require('./tools.cjs').definitions.map(t => t.function.name);
    this.data.enabledTools ??= allTools;
    this.data.contextSize ??= 8192;
    if (this.data.provider && this.data.provider !== 'ollama') this.data.model = this.data.providerModels?.ollama || '';
    this.data.provider = 'ollama';
    this.data.providerModels ??= { ollama: this.data.model, openai: '', chatgpt: '' };
    this.data.customProvider ??= { baseURL: '', model: '', tools: false, vision: false };
    this.data.cloudProjects ??= [];
    this.data.cloudPersonal ??= false;
    this.data.companion ??= { enabled: false, sharedProjects: [], shareMemory: false };
    this.data.tasks ??= [];
    this.data.setup ??= { completed: this.data.projects.length > 0 || this.data.sessions.some(s => s.messages.length > 0), migrated: true };
    this.data.ui ??= { sidebarCollapsed: false };
    this.data.ui.theme ??= 'sakura';
    this.data.ui.textSize ??= 13;
    this.data.ui.reduceMotion ??= false;
    this.data.ui.launchAnimation ??= true;
    this.data.ui.launchSound ??= true;
    this.data.ui.appIcon ??= 'theme';
    this.data.autoSummary ??= true;
    this.data.globalMemory ??= '';
    this.data.globalMemoryEnabled ??= true;
    for (const project of this.data.projects) { project.memoryMode ??= 'project'; project.memorySize ??= 24000; }
    this.data.contextSize = Math.min(this.data.contextSize, 32768);
    this.data.mcpServers ??= [];
    this.data.localRuntimeMode = 'managed';
    if (this.data.localEngineVersion !== 1) {
      this.data.contextSize = Math.min(this.data.contextSize, 8192);
      this.data.localEngineVersion = 1;
    }
    if (!this.data.enabledTools.includes('workspace_info') && this.data.workspaceContextVersion !== 1) this.data.enabledTools.push('workspace_info');
    this.data.workspaceContextVersion = 1;
    if (this.data.websiteToolsVersion !== 1) this.data.enabledTools = [...new Set([...this.data.enabledTools, 'website_assess', 'website_simulate'])];
    this.data.websiteToolsVersion = 1;
    if (this.data.cyberToolsVersion !== 1) {
      this.data.enabledTools = [...new Set([...this.data.enabledTools, 'security_tools', 'network_scan', 'network_read', 'network_stop'])];
      this.data.cyberToolsVersion = 1;
    }
    this.data.benchmarks ??= [];
    this.data.usage ??= this.data.sessions.flatMap(s => s.messages.filter(m => m.metrics).map(m => ({ ...m.metrics, model: m.model || 'Historical model (not recorded)', provider: m.provider || 'ollama', sessionId: s.id, created: m.created || s.created, migrated: true }))).sort((a, b) => a.created - b.created).slice(-2000);
    if (this.data.toolsDefaultsVersion !== 2) {
      this.data.enabledTools = [...new Set([...this.data.enabledTools, ...allTools])];
      this.data.toolsDefaultsVersion = 2;
    }
  }
  save() {
    fs.writeFileSync(this.file + '.tmp', JSON.stringify(this.data, null, 2), { mode: 0o600 });
    fs.renameSync(this.file + '.tmp', this.file);
  }
  project() { return this.data.projects.find(p => p.id === this.data.activeProject); }
  session() { return this.data.sessions.find(s => s.id === this.data.activeSession); }
  addProject(root, options) {
    root = fs.realpathSync(root);
    if (!fs.statSync(root).isDirectory()) throw new Error('Choose a project folder.');
    let project = this.data.projects.find(p => p.root === root);
    if (!project) {
      project = { id: randomUUID(), name: path.basename(root), root, created: Date.now(), ...require('./memory.cjs').validateMemorySettings(options || { mode: 'project', size: 24000 }) };
      this.data.projects.push(project);
    }
    this.selectProject(project.id);
    return project;
  }
  selectProject(id) {
    if (id !== null && !this.data.projects.some(p => p.id === id)) throw new Error('Unknown project');
    this.data.activeProject = id;
    this.data.activeSession = this.data.sessions.findLast(s => s.projectId === id && !s.archivedAt)?.id || null;
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
    this.scopedSession(id);
    this.data.activeSession = id;
    this.save();
  }
  scopedSession(id) {
    const session = this.data.sessions.find(s => s.id === id && s.projectId === this.data.activeProject);
    if (!session) throw new Error('Unknown conversation');
    return session;
  }
  nextSession() {
    this.data.activeSession = this.data.sessions.findLast(s => s.projectId === this.data.activeProject && !s.archivedAt)?.id || null;
    if (!this.data.activeSession) this.newSession();
  }
  archiveSession(id) {
    const session = this.scopedSession(id);
    session.archivedAt ||= Date.now();
    if (this.data.activeSession === id) this.nextSession();
    this.save();
  }
  restoreSession(id) {
    const session = this.scopedSession(id);
    delete session.archivedAt;
    this.data.activeSession = id;
    this.save();
  }
  deleteSession(id) {
    this.scopedSession(id);
    this.data.sessions = this.data.sessions.filter(s => s.id !== id);
    // Task results copy conversation output, so remove those copies as well.
    this.data.tasks = this.data.tasks.filter(task => task.sessionId !== id);
    if (this.data.activeSession === id) this.nextSession();
    this.save();
  }
  remember(content) {
    if (typeof content !== 'string' || !content.trim() || content.length > 4000) throw new Error('Memory must contain 1–4,000 characters.');
    const config = require('./memory.cjs').memorySettings(this.project());
    if (['off', 'global'].includes(config.mode)) throw new Error('Project memory is off for this workspace. Enable it in Memory settings first.');
    const used = this.data.memories.filter(m => m.projectId === this.data.activeProject).reduce((n, m) => n + m.content.length, 0);
    if (used + content.trim().length > config.size) throw new Error(`Project memory is full (${config.size.toLocaleString()} characters). Remove a note or choose a larger budget.`);
    this.data.memories.push({ id: randomUUID(), projectId: this.data.activeProject, content: content.trim(), created: Date.now() });
    this.save();
  }
  updateMemory(id, content) {
    const memory = this.data.memories.find(m => m.id === id && m.projectId === this.data.activeProject);
    if (!memory) throw new Error('Unknown project memory.');
    if (typeof content !== 'string' || !content.trim() || content.length > 4000) throw new Error('Memory must contain 1–4,000 characters.');
    const config = require('./memory.cjs').memorySettings(this.project());
    const used = this.data.memories.filter(m => m.projectId === this.data.activeProject && m.id !== id).reduce((n, m) => n + m.content.length, 0);
    if (used + content.trim().length > config.size) throw new Error('Project memory is full. Remove a note or choose a larger budget.');
    memory.content = content.trim(); memory.updated = Date.now(); this.save();
  }
  setMemorySettings(value) {
    if (!this.project()) throw new Error('Open a project to change project memory.');
    const settings = require('./memory.cjs').validateMemorySettings(value);
    const used = this.data.memories.filter(m => m.projectId === this.data.activeProject).reduce((n, m) => n + m.content.length, 0);
    if (used > settings.memorySize) throw new Error(`This project has ${used.toLocaleString()} saved characters. Remove some notes before lowering its limit.`);
    Object.assign(this.project(), settings); this.save();
  }
  approvalMode() { return (this.project()?.approvalMode || (!this.project() && this.data.personalApprovalMode)) === 'all' ? 'all' : 'review'; }
  setApprovalMode(mode) {
    if (!['review', 'all'].includes(mode)) throw new Error('Choose Review each action or Approved all.');
    if (this.project()) this.project().approvalMode = mode;
    else this.data.personalApprovalMode = mode;
    this.save();
  }
  snapshot() { return { ...structuredClone(this.data), approvalMode: this.approvalMode() }; }
}
module.exports = { Store };
