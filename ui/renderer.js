// File access and shell commands go through the main process.
const $ = id => document.getElementById(id);
const api = window.wixal;
const tools = [
  { id: 'command_start', name: 'Start command session', description: 'Run an AI-selected host command for up to an hour. Read its results in this chat.', review: true },
  { id: 'command_read', name: 'Review command output', description: 'Read output chunks, errors and completion status from a command session.' },
  { id: 'command_write', name: 'Send command input', description: 'Send reviewed stdin text to a running command.', review: true },
  { id: 'command_stop', name: 'Stop command session', description: 'Cancel a command and its child processes.' },
  { id: 'command_save_output', name: 'Save command evidence', description: 'Save captured output and status to a project file.', review: true },
  { id: 'browser_inspect', name: 'Inspect rendered website', description: 'Read a JavaScript-rendered page, links, forms and console messages.', review: true },

  { id: 'list_files', name: 'List files', description: 'See the files in the selected project.' },
  { id: 'read_file', name: 'Read files', description: 'Read text files to understand the code.' },
  { id: 'search_files', name: 'Search the project', description: 'Find text across project files.' },
  { id: 'write_file', name: 'Edit and create files', description: 'Review the existing and proposed contents before saving.', review: true },
  { id: 'run_command', name: 'Run commands', description: 'Run a command in the project. Stops after 60 seconds.', review: true },
  { id: 'search_history', name: 'Recall project conversations', description: 'Search saved conversations in this project.' },
  { id: 'save_memory', name: 'Save project memory', description: 'Keep reviewed decisions and preferences for future chats.', review: true },
  { id: 'web_search', name: 'Search the web', description: 'Send a reviewed search query to DuckDuckGo and return source links.', review: true },
  { id: 'http_request', name: 'Web pages and APIs', description: 'Review the URL, HTTP method and JSON body before any network request.', review: true },
];
const availableTools = () => [...tools, ...(state?.externalConnections || []).flatMap(server => server.tools.map(tool => ({ ...tool, description: tool.description, review: true })))];
let menuSessionId, renameSessionId, deleteSessionId, welcomeSessionId;
let modelsPageOpen = false, libraryInfo = null, libraryRequest = 0;
let downloadStateKey = '';
let modelView = 'installed';
const modelViewFilters = {};
let deleteModelName, mentionIndex = 0, mentionCandidates = [];
let connections, modelRequest = 0, keyProvider = 'openai';
const providerLabels = { ollama: 'Wixal Local', openai: 'OpenAI API', chatgpt: 'ChatGPT' };
let state, models = [], connected = false, busy = false, streamText = '', terminal, fitAddon;
let terminalOpen = false, approvalId, toastTimer, streamFrame, attachments = [], files = [], previewPath = '', previewContent = '', fileRequest = 0;
const escapeHTML = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const shortModel = name => (name || '').split('/').at(-1).split(':')[0];
const selectedModel = () => models.find(model => model.name === state?.model);
const project = () => state?.projects.find(item => item.id === state.activeProject);
const session = () => state?.sessions.find(item => item.id === state.activeSession);
function toast(message) {
  $('toast').textContent = String(message).replace(/^Error invoking remote method '[^']+': Error: /, '');
  $('toast').classList.remove('hidden'); clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.add('hidden'), 6500);
}
async function invoke(name, ...args) { try { return await api[name](...args); } catch (error) { toast(error.message); throw error; } }
async function refresh() { state = await api.state(); render(); }
function render() {
  providerLabels.ollama = 'Wixal Local';
  const p = project(), s = session(), model = selectedModel();
  applyAppearance(); renderSettings();
  applySidebarLayout();
  $('title-project').textContent = p?.name || 'workspace';
  $('project-label').textContent = p?.name || 'Personal workspace';
  $('conversation-label').textContent = s?.title || 'New conversation';
  $('conversation-label').disabled = !s || busy;
  $('reveal-project').disabled = !p;
  renderSessions();
  $('mode-label').textContent = state.mode === 'agent' ? 'Agent' : 'Chat';
  $('mode-button').title = state.mode === 'agent' ? 'Agent uses the enabled project tools. Click to switch to chat.' : 'Chat has no project tools. Click to switch to agent.';
  $('model-label').textContent = connected ? selectedModel()?.displayName || shortModel(state.model) || 'Choose a model' : `${providerLabels[state.provider]} · connect`;
  $('model-button').title = state.model || 'Choose a model';
  $('mode-button').disabled = busy; $('model-button').disabled = busy; $('attach-image').disabled = busy;
  $('model-refresh').disabled = busy; $('refresh-models').disabled = busy;
  $('welcome-open').textContent = p ? 'Browse project files ↗' : 'Open a project folder ↗';
  $('tools-count').textContent = state.enabledTools.length;
  $('bottom-model').textContent = connected ? `${state.mode === 'agent' && p ? 'Agent' : 'Chat'} · ${model?.name || 'Choose a model'}` : `${providerLabels[state.provider]} · open the model picker to connect`;
  const recent = s?.messages.findLast(message => message.metrics?.tokens);
  $('response-stats').textContent = recent ? `${recent.metrics.tokens} tokens · ${recent.metrics.tokensPerSecond} tok/s` : 'Usage & performance ↗';
  const cloud = state.provider !== 'ollama', allowed = p ? state.cloudProjects.includes(p.id) : state.cloudPersonal;
  $('cloud-notice').classList.toggle('hidden', !cloud);
  $('cloud-notice-text').textContent = allowed ? `${state.provider === 'chatgpt' ? 'Using ChatGPT plan' : providerLabels[state.provider]} · conversation and enabled project context sent to ${state.provider === 'custom' ? state.customProvider.baseURL : providerLabels[state.provider]}` : `${providerLabels[state.provider]} · enable cloud context before sending`;
  $('composer-usage').classList.toggle('hidden', state.provider !== 'chatgpt');
  $('task-count').textContent = state.tasks.filter(task => task.status === 'queued').length;
  const archived = !!s?.archivedAt;
  $('archived-banner').classList.toggle('hidden', !archived);
  $('prompt').disabled = busy || archived; $('send').disabled = archived; $('attach-image').disabled = busy || archived;
  $('activity-label').textContent = archived ? 'Restore to continue chatting' : busy ? state.provider === 'ollama' ? 'Working locally…' : 'Working…' : 'Ready';
  renderArchives();
  renderMessages(); renderMemories(); renderToolkit(); renderPerformance(); renderModelList(); renderAttachments(); renderTasks();
}
const expandedProjects = new Set();
let sidebarProjectId;
function renderSessions() {
  if (sidebarProjectId !== state.activeProject) { expandedProjects.add(state.activeProject || 'personal'); sidebarProjectId = state.activeProject; }
  const query = $('session-search').value.trim().toLowerCase();
  const current = state.sessions.filter(item => item.projectId === state.activeProject && !item.archivedAt);
  $('session-count').textContent = current.length;
  $('archive-count').textContent = state.sessions.filter(item => item.projectId === state.activeProject && item.archivedAt).length;
  const groups = [...state.projects, { id: null, name: 'Personal chats' }];
  const rows = groups.map(p => {
    const key = p.id || 'personal', selected = state.activeProject === p.id;
    const chats = state.sessions.filter(item => item.projectId === p.id && !item.archivedAt).toReversed();
    const matchesProject = p.name.toLowerCase().includes(query);
    const filtered = chats.filter(item => matchesProject || item.title.toLowerCase().includes(query));
    if (query && !matchesProject && !filtered.length) return '';
    const expanded = !!query || expandedProjects.has(key);
    const count = state.memories.filter(m => m.projectId === p.id).length;
    return `<section class="project-group ${selected ? 'selected' : ''}" data-project-group="${key}">
      <div class="project-group-heading"><button class="project-expand" data-project-expand="${key}" aria-label="${expanded ? 'Collapse' : 'Expand'} ${escapeHTML(p.name)}" aria-expanded="${expanded}" aria-controls="project-children-${key}">›</button><button class="project-item ${selected ? 'active' : ''}" data-project-select="${key}" title="${escapeHTML(p.root || 'Chats without a project folder')}" ${busy ? 'disabled' : ''}><span class="folder" aria-hidden="true">${p.id ? '▱' : '◌'}</span><span>${escapeHTML(p.name)}</span></button><button class="project-new-chat" data-project-new="${key}" aria-label="New chat in ${escapeHTML(p.name)}" title="New chat" ${busy ? 'disabled' : ''}>＋</button></div>
      <div id="project-children-${key}" class="project-children ${expanded ? '' : 'hidden'}"><button class="project-memory" data-project-memory="${key}" ${busy ? 'disabled' : ''}><span aria-hidden="true">◇</span> ${p.id ? 'Project memory' : 'Personal memory'}<span class="memory-total">${count}</span></button>
      ${filtered.length ? filtered.map(item => `<div class="session-row ${session()?.id === item.id ? 'active' : ''}"><button class="session-item ${session()?.id === item.id ? 'active' : ''}" data-id="${item.id}" data-project="${key}" title="${escapeHTML(item.title)}" ${busy ? 'disabled' : ''}><span class="chat-branch" aria-hidden="true">↳</span><span class="chat-title">${escapeHTML(item.title)}</span></button><button class="session-more" data-menu-id="${item.id}" aria-label="Options for ${escapeHTML(item.title)}" aria-haspopup="menu" ${busy ? 'disabled' : ''}>···</button></div>`).join('') : '<div class="project-empty">No chats yet</div>'}</div></section>`;
  }).join('');
  $('sessions').innerHTML = rows || '<div class="empty-project">No matching projects or chats.</div>';
  const projectId = key => key === 'personal' ? null : key;
  $('sessions').querySelectorAll('[data-project-expand]').forEach(button => button.onclick = () => { const key = button.dataset.projectExpand; expandedProjects.has(key) ? expandedProjects.delete(key) : expandedProjects.add(key); renderSessions(); });
  $('sessions').querySelectorAll('[data-project-select]').forEach(button => button.onclick = async () => { const key = button.dataset.projectSelect; expandedProjects.add(key); if (state.activeProject !== projectId(key)) await switchProject(projectId(key)); else renderSessions(); });
  $('sessions').querySelectorAll('[data-project-new]').forEach(button => button.onclick = async () => { if (await ensureProject(projectId(button.dataset.projectNew))) { expandedProjects.add(button.dataset.projectNew); await newSession(); } });
  $('sessions').querySelectorAll('[data-project-memory]').forEach(button => button.onclick = async () => { if (await ensureProject(projectId(button.dataset.projectMemory))) { renderMemories(); if ($('memory-drawer').classList.contains('hidden')) toggleDrawer('memory'); } });
  $('sessions').querySelectorAll('.session-item').forEach(button => button.onclick = async () => { if (await ensureProject(projectId(button.dataset.project))) await selectConversation(button.dataset.id); });
  $('sessions').querySelectorAll('.session-more').forEach(button => button.onclick = async () => {
    const item = state.sessions.find(s => s.id === button.dataset.menuId);
    const rect = button.getBoundingClientRect();
    if (!await ensureProject(item.projectId)) return;
    menuSessionId = item.id;
    const menu = $('session-menu'); menu.showPopover();
    menu.style.left = `${Math.min(rect.right + 8, window.innerWidth - 220)}px`;
    menu.style.top = `${Math.max(8, Math.min(rect.top, window.innerHeight - menu.offsetHeight - 12))}px`;
    menu.querySelector('button').focus();
  });
}
async function ensureProject(id) {
  if (state.activeProject === id) return true;
  await switchProject(id);
  return state.activeProject === id;
}
async function selectConversation(id) {
  try { state = await invoke('session-select', id); clearDraft(); render(); } catch {}
}
function showRename(id) {
  renameSessionId = id;
  $('rename-input').value = state.sessions.find(item => item.id === id).title;
  $('rename-dialog').showModal(); $('rename-input').select();
}
function showDelete(id) {
  deleteSessionId = id;
  $('delete-title').textContent = state.sessions.find(item => item.id === id).title;
  $('delete-dialog').showModal(); $('cancel-delete').focus();
}
async function changeConversation(action, id) {
  try {
    const active = state.activeSession;
    state = await invoke(`session-${action}`, id);
    if (state.activeSession !== active) clearDraft();
    render();
    toast(action === 'archive' ? 'Conversation archived. Find it in Archived chats.' : action === 'restore' ? 'Conversation restored.' : 'Conversation deleted.');
    return true;
  } catch { return false; }
}
function renderArchives() {
  const query = $('archive-search').value.toLowerCase();
  $('archive-project-label').textContent = project()?.name || 'Personal workspace';
  const archived = state.sessions.filter(item => item.projectId === state.activeProject && item.archivedAt && item.title.toLowerCase().includes(query)).toSorted((a, b) => b.archivedAt - a.archivedAt);
  $('archive-list').innerHTML = archived.length ? archived.map(item => `<article class="archive-row"><div><strong>${escapeHTML(item.title)}</strong><small>Archived ${new Date(item.archivedAt).toLocaleDateString()} · ${item.messages.filter(m => m.role === 'user').length} ${item.messages.filter(m => m.role === 'user').length === 1 ? 'message' : 'messages'} from you</small></div><div class="archive-actions"><button data-archive-view="${item.id}" ${busy ? 'disabled' : ''}>Read</button><button data-archive-restore="${item.id}" ${busy ? 'disabled' : ''}>Restore</button><button data-archive-delete="${item.id}" class="danger-text" ${busy ? 'disabled' : ''}>Delete</button></div></article>`).join('') : `<div class="archive-empty">${query ? 'No matching archived chats.' : 'No archived chats in this workspace yet.'}</div>`;
  $('archive-list').querySelectorAll('[data-archive-view]').forEach(button => button.onclick = async () => { await selectConversation(button.dataset.archiveView); $('archives-dialog').close(); });
  $('archive-list').querySelectorAll('[data-archive-restore]').forEach(button => button.onclick = async () => { if (await changeConversation('restore', button.dataset.archiveRestore)) $('archives-dialog').close(); });
  $('archive-list').querySelectorAll('[data-archive-delete]').forEach(button => button.onclick = () => showDelete(button.dataset.archiveDelete));
}
function showArchives() { $('archive-search').value = ''; renderArchives(); $('archives-dialog').showModal(); }
function renderStartLayout() {
  const start = !session()?.messages.length && !streamText && !busy && !session()?.archivedAt;
  document.querySelector('main').classList.toggle('is-new-chat', start && !terminalOpen);
  $('starter-suggestions').classList.toggle('hidden', !start);
  $('start-links').classList.toggle('hidden', !start);
  $('welcome').classList.toggle('hidden', !start);
  if (start && welcomeSessionId !== state.activeSession) {
    welcomeSessionId = state.activeSession;
    const wordmark = document.querySelector('.welcome-wordmark');
    wordmark.classList.remove('arriving'); void wordmark.offsetWidth; wordmark.classList.add('arriving');
  }
}
function sizePrompt() {
  const prompt = $('prompt'); prompt.style.height = 'auto'; prompt.style.height = `${Math.min(180, Math.max(56, prompt.scrollHeight))}px`;
}
function markdown(text) { return DOMPurify.sanitize(marked.parse(text || '', { breaks: true }), { FORBID_TAGS: ['img', 'iframe', 'style', 'input', 'button', 'form'], FORBID_ATTR: ['style'] }); }
function resultStatus(message) {
  if (message.content.startsWith('Error:')) return 'Failed';
  if (message.content.startsWith('User declined')) return 'Declined';
  if (['command_start', 'command_read', 'command_stop'].includes(message.tool_name)) {
    try { const result = JSON.parse(message.content); return result.state === 'running' ? 'Running' : result.state === 'stopped' ? 'Stopped' : result.state === 'failed' ? 'Failed' : result.exitCode === 0 ? 'Done' : `Exit ${result.exitCode ?? '?'}`; } catch {}
  }
  if (message.tool_name === 'run_command') {
    try { const result = JSON.parse(message.content); return result.stopped ? 'Stopped' : result.exitCode === 0 ? 'Done' : `Exit ${result.exitCode ?? '?'}`; } catch {}
  }
  return 'Done';
}
function renderMessages() {
  const messages = session()?.messages || [], container = $('chat-scroll');
  const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150;
  $('welcome').classList.toggle('hidden', !!messages.length || !!streamText);
  $('messages').classList.toggle('hidden', !messages.length && !streamText);
  $('messages').innerHTML = messages.map((message, index) => {
    if (message.role === 'tool') { const status = resultStatus(message); return `<details class="tool-message" ${['command_read', 'browser_inspect'].includes(message.tool_name) ? 'open' : ''}><summary>⌁ ${escapeHTML(availableTools().find(tool => tool.id === message.tool_name)?.name || message.tool_name)}<span class="tool-status ${['Done', 'Running'].includes(status) ? '' : 'failed'}">${status}</span></summary><pre class="tool-content">${escapeHTML(message.content)}</pre></details>`; }
    const isUser = message.role === 'user';
    if (!isUser && !message.content && message.tool_calls) return `<div class="tool-message"><span class="muted">Requested ${message.tool_calls.map(call => escapeHTML(availableTools().find(tool => tool.id === call.function?.name)?.name || call.function?.name || 'tool')).join(', ')}</span></div>`;
    const images = message.images?.length ? `<div class="message-images">${message.images.map((image, imageIndex) => `<button data-message="${index}" data-image="${imageIndex}" title="${escapeHTML(message.imageNames?.[imageIndex] || 'View image')}"><img src="data:image/png;base64,${image}" alt="${escapeHTML(message.imageNames?.[imageIndex] || 'Attached image')}"></button>`).join('')}</div>` : '';
    const metrics = message.metrics?.tokens ? `<div class="message-metrics">${message.metrics.tokens} tokens · ${message.metrics.tokensPerSecond} tok/s · ${Math.round(message.metrics.seconds)}s</div>` : '';
    return `<article class="message ${isUser ? 'user' : 'assistant'}"><div class="message-header">${isUser ? '<span>▸</span> You' : '<img src="../assets/mark.svg" alt=""> Wixal'}<span class="muted">${new Date(message.created || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span><button class="copy-message" data-copy="${index}">Copy</button></div><div class="message-body">${isUser ? escapeHTML(message.content) : markdown(message.content)}</div>${images}${metrics}</article>`;
  }).join('');
  if (streamText) {
    const article = document.createElement('article'); article.className = 'message assistant';
    article.innerHTML = '<div class="message-header"><img src="../assets/mark.svg" alt=""> Wixal <span class="muted">Writing</span></div><div class="message-body pending-content"></div>';
    article.querySelector('.message-body').textContent = streamText; $('messages').append(article);
  }
  renderStartLayout();
  if (!messages.length && !streamText) container.scrollTop = 0;
  else if (nearBottom) container.scrollTop = container.scrollHeight;
}
$('messages').addEventListener('click', async event => {
  if (event.target.closest('a')) { event.preventDefault(); const link = event.target.closest('a'); try { await invoke('copy-text', link.href); toast('Link copied.'); } catch {} }
  const copy = event.target.closest('[data-copy]');
  if (copy) { try { await invoke('copy-text', session().messages[Number(copy.dataset.copy)].content); toast('Copied.'); } catch {} }
  const image = event.target.closest('[data-image]');
  if (image) { const message = session().messages[Number(image.dataset.message)], index = Number(image.dataset.image); $('image-title').textContent = message.imageNames?.[index] || 'Image attachment'; $('image-preview').src = `data:image/png;base64,${message.images[index]}`; $('image-dialog').showModal(); }
});
function renderMemories() {
  const memories = state.memories.filter(memory => memory.projectId === state.activeProject);
  $('memory-count').textContent = memories.length;
  $('memory-project-title').textContent = project() ? `${project().name} memory` : 'Personal memory';
  $('memory-description').textContent = project() ? 'Save preferences and decisions for this project. Wixal includes these in future project messages.' : 'Save preferences for your personal chats. These stay separate from project memory.';
  $('memories').innerHTML = memories.length ? memories.map(memory => `<div class="memory-entry"><p>${escapeHTML(memory.content)}</p><footer>${new Date(memory.created).toLocaleDateString()}<button data-id="${memory.id}" title="Delete memory" ${busy ? 'disabled' : ''}>Forget</button></footer></div>`).join('') : '<p class="empty-project">Nothing saved yet. Add a preference or project decision below.</p>';
  $('memory-form').querySelector('button').disabled = busy;
  $('auto-summary').checked = state.autoSummary !== false; $('auto-summary').disabled = busy;
  const summary = session()?.summary;
  $('saved-summary').classList.toggle('hidden', !summary);
  $('summary-content').textContent = summary?.content || '';
  $('summary-meta').textContent = summary ? `${summary.count} older messages · ${summary.method === 'excerpts' ? 'Fallback excerpts' : 'Model summary'} · ${new Date(summary.updated).toLocaleString()}. Full history remains saved.` : '';
  $('summary-clear').disabled = busy;
  $('memories').querySelectorAll('button').forEach(button => button.onclick = async () => { try { state = await invoke('memory-delete', button.dataset.id); render(); } catch {} });
}
function toolCategory(id) { return id.startsWith('mcp_') ? 'external' : id.startsWith('command_') || id === 'run_command' ? 'commands' : ['web_search', 'http_request', 'browser_inspect'].includes(id) ? 'web' : ['search_history', 'save_memory'].includes(id) ? 'memory' : 'files'; }
function renderToolkit() {
  const p = project();
  $('toolkit-summary').textContent = state.mode === 'chat' ? 'You’re in Chat mode. Use @tool_name to call a tool from Chat, or switch to Agent for automatic selection. File tools need a project.' : p ? `Tools for ${p.name}. Tools are enabled by default. Type @ in chat to select one explicitly.` : 'Open a project folder to use these tools in Agent mode.';
  const catalog = availableTools(), query = $('tool-search').value.toLowerCase();
  $('tool-list').innerHTML = catalog.filter(tool => ($('tool-category').value === 'all' || toolCategory(tool.id) === $('tool-category').value) && `${tool.name} ${tool.id} ${tool.description}`.toLowerCase().includes(query)).sort((a, b) => ['files', 'commands', 'web', 'memory', 'external'].indexOf(toolCategory(a.id)) - ['files', 'commands', 'web', 'memory', 'external'].indexOf(toolCategory(b.id))).map(tool => `<label class="tool-toggle"><input type="checkbox" data-tool="${escapeHTML(tool.id)}" ${state.enabledTools.includes(tool.id) ? 'checked' : ''} ${busy ? 'disabled' : ''}><span><strong>${escapeHTML(tool.name)}</strong><code>@${escapeHTML(tool.id)}</code><small>${escapeHTML(tool.description)}</small>${tool.review ? '<em>REVIEW EACH TIME</em>' : ''}</span></label>`).join('');
  $('tool-list').querySelectorAll('input').forEach(input => input.onchange = async () => {
    const enabledTools = [...new Set([...state.enabledTools.filter(name => name !== input.dataset.tool), ...(input.checked ? [input.dataset.tool] : [])])];
    enabledTools.push(...state.enabledTools.filter(name => !catalog.some(tool => tool.id === name)));
    try { state = await invoke('settings', { enabledTools }); render(); } catch { renderToolkit(); }
  });
  const recent = (session()?.messages || []).filter(message => message.role === 'tool').slice(-5).toReversed();
  $('tool-activity').innerHTML = recent.length ? recent.map(message => `<div class="tool-result">${escapeHTML(message.tool_name)}<span>${resultStatus(message)}</span></div>`).join('') : '<p class="empty-project">Tool results appear here after the model uses them.</p>';
  $('manage-extensions').disabled = busy; $('tools-enable-all').disabled = busy;
  renderExtensions();
}
function renderExtensions() {
  $('extension-list').innerHTML = (state.mcpServers || []).map(server => {
    const connection = state.externalConnections?.find(c => c.id === server.id);
    return `<div class="extension-entry"><strong>${escapeHTML(server.name)}</strong><small>${escapeHTML([server.command, ...server.args].join(' '))}</small><p>${connection ? `${escapeHTML(connection.status)} · ${connection.tools.length} tools` : 'Disconnected'}</p><div class="form-row"><button data-extension-connect="${server.id}" ${busy || connection?.status === 'connecting' ? 'disabled' : ''}>${connection ? 'Disconnect' : 'Connect'}</button><button data-extension-delete="${server.id}" ${busy ? 'disabled' : ''}>Remove</button></div></div>`;
  }).join('') || '<p class="muted">No external tool servers saved yet.</p>';
  $('extension-list').querySelectorAll('[data-extension-connect]').forEach(button => button.onclick = async () => {
    const id = button.dataset.extensionConnect, connected = state.externalConnections?.some(c => c.id === id);
    button.disabled = true; button.textContent = connected ? 'Disconnecting…' : 'Connecting…';
    try { state = await invoke(connected ? 'mcp-disconnect' : 'mcp-connect', id); render(); if (!connected) toast('Server connected. Enable its tools in the tool kit.'); } catch { await refresh(); }
  });
  $('extension-list').querySelectorAll('[data-extension-delete]').forEach(button => button.onclick = async () => { try { state = await invoke('mcp-delete', button.dataset.extensionDelete); render(); } catch {} });
  $('extension-form').querySelectorAll('input, textarea, button').forEach(input => input.disabled = busy);
}
const modelFilterIds = ['model-type-filter', 'model-fit-filter', 'model-size-filter', 'model-sort'];
function setModelView(view, focus = false) {
  modelViewFilters[modelView] = Object.fromEntries(modelFilterIds.map(id => [id, $(id).value]));
  modelView = view === 'downloads' && state.provider === 'ollama' ? 'downloads' : 'installed';
  for (const id of modelFilterIds) $(id).value = modelViewFilters[modelView]?.[id] || (id === 'model-size-filter' ? '0' : id === 'model-sort' ? 'name' : 'all');
  $('model-search').value = '';
  document.querySelector('.model-browser-content').scrollTop = 0;
  renderModelList();
  if (focus) $(modelView === 'downloads' ? 'model-downloads-tab' : 'model-installed-tab').focus();
}
function renderModelList() {
  const query = $('model-search').value.trim().toLowerCase(), local = state?.provider === 'ollama';
  if (!local && modelView === 'downloads') setModelView('installed');
  const downloads = modelView === 'downloads';
  const type = $('model-type-filter').value, fit = $('model-fit-filter').value;
  const sizeLimit = Number($('model-size-filter').value) * 1e9;
  const filtered = models.filter(model => (!local || !sizeLimit || model.size <= sizeLimit) && `${model.name} ${model.displayName || ''}`.toLowerCase().includes(query) && (type === 'all' || model.capabilities?.includes(type)) && (!local || fit === 'all' || (fit === 'estimated' ? model.fit?.fits : fit === 'tested' ? !!modelBenchmark(model) : (modelBenchmark(model)?.tokensPerSecond || 0) >= 20)));
  filtered.sort((a, b) => $('model-sort').value === 'size' ? a.size - b.size : $('model-sort').value === 'speed' ? (modelBenchmark(b)?.tokensPerSecond || 0) - (modelBenchmark(a)?.tokensPerSecond || 0) : a.name.localeCompare(b.name));
  const benchmarkBusy = !!state.benchmarkProgress;
  $('model-hardware').classList.toggle('hidden', !local);
  $('hardware-name').textContent = `${state.hardware.cpu} · ${(state.hardware.totalMemory / 1024 ** 3).toFixed(0)} GB RAM`;
  $('hardware-hint').textContent = 'Fit estimates reserve 25% for macOS and use your context setting. Benchmark to measure speed.';
  $('model-fit-filter').disabled = !local; $('model-size-filter').disabled = !local; $('model-sort').disabled = !local;
  for (const option of $('model-fit-filter').options) option.disabled = downloads && ['tested', 'fast'].includes(option.value);
  $('model-sort').querySelector('[value="speed"]').disabled = downloads;
  const activeFilters = Number(type !== 'all') + Number(local && fit !== 'all') + Number(local && sizeLimit > 0) + Number(local && $('model-sort').value !== 'name');
  $('model-filter-count').textContent = activeFilters ? String(activeFilters) : '';
  $('model-filter-panel').open ||= activeFilters > 0;
  $('model-downloads-tab').classList.toggle('hidden', !local);
  $('model-installed-tab').firstChild.textContent = local ? 'Installed ' : 'Available ';
  $('model-installed-count').textContent = String(models.length);
  for (const view of ['installed', 'downloads']) {
    $(`model-${view}-tab`).setAttribute('aria-selected', String(view === modelView));
    $(`model-${view}-tab`).tabIndex = view === modelView ? 0 : -1;
    $(`model-${view}-panel`).classList.toggle('hidden', view !== modelView);
  }
  $('model-search').placeholder = downloads ? 'Search downloads…' : local ? 'Search installed models…' : 'Search available models…';
  renderBenchmarkProgress(); renderCatalog();
  if (connections?.providers) { for (const item of connections.providers) providerLabels[item.id] = item.id === 'ollama' ? 'Wixal Local' : item.label; $('provider-select').innerHTML = connections.providers.map(item => `<option value="${escapeHTML(item.id)}">${escapeHTML(providerLabels[item.id])}${item.id === 'ollama' ? ' · local' : item.id === 'chatgpt' ? ' · connected account' : ''}</option>`).join(''); }
  $('provider-select').value = state?.provider || 'ollama'; $('provider-select').disabled = busy || benchmarkBusy || (state.modelDownloads || []).some(item => ['queued', 'downloading'].includes(item.state));
  $('model-provider-heading').textContent = local ? `${providerLabels.ollama.toUpperCase()} · ON THIS MAC` : `${providerLabels[state?.provider]} · CLOUD`;
  const current = selectedModel();
  $('model-current-name').textContent = current?.displayName || shortModel(state.model) || 'No model selected';
  $('model-current-tag').textContent = state.model || 'Choose from your library';
  $('model-results-info').textContent = `${filtered.length} ${local ? 'installed' : 'available'} model${filtered.length === 1 ? '' : 's'}${filtered.length !== models.length ? ` of ${models.length}` : ''} · select a model to use it`;
  $('model-list').innerHTML = filtered.length ? filtered.map(model => {
    const selected = state.model === model.name, benchmark = modelBenchmark(model);
    return `<div class="model-entry ${selected ? 'is-selected' : ''}"><button class="model-row ${selected ? 'selected' : ''}" data-model="${escapeHTML(model.name)}" aria-pressed="${selected}" ${busy || benchmarkBusy ? 'disabled' : ''}><div class="model-row-info"><div class="model-name-line"><strong>${escapeHTML(model.displayName || shortModel(model.name))}</strong>${selected ? '<span class="model-selected-badge">✓ Current</span>' : '<span class="model-select-hint">Use model →</span>'}</div><span class="model-id">${escapeHTML(model.name)}</span><div class="capabilities"><span class="capability">Chat</span>${model.capabilities?.includes('tools') ? '<span class="capability tools">Tools</span>' : ''}${model.capabilities?.includes('vision') ? '<span class="capability vision">Images</span>' : ''}${model.capabilities?.includes('thinking') ? '<span class="capability">Thinking</span>' : ''}${!model.capabilities ? '<span class="capability">Capabilities unavailable</span>' : ''}<span class="model-context">${escapeHTML(model.details?.parameter_size || '')}${model.contextLength ? ` · ${Math.round(model.contextLength / 1024)}k max context` : ''}</span></div></div><span class="model-size">${local ? `${(model.size / 1e9).toFixed(1)} GB<small>on disk</small>` : '<small>Cloud</small>'}</span></button>${local ? `<div class="model-actions"><span class="${model.fit?.fits || benchmark ? '' : 'model-fit-warning'}">${benchmark ? `${benchmark.tokensPerSecond} tok/s · tested at ${Math.round(benchmark.context / 1024)}k` : model.fit ? model.fit.fits ? `Estimated fit · ${(model.fit.required / 1024 ** 3).toFixed(1)} GiB` : `May exceed RAM · ${(model.fit.required / 1024 ** 3).toFixed(1)} GiB estimate` : 'Memory estimate unavailable'}</span><button data-benchmark="${escapeHTML(model.name)}" ${busy || benchmarkBusy || state.modelDownload ? 'disabled' : ''}>Benchmark</button><details class="model-manage"><summary aria-label="Manage ${escapeHTML(model.name)}">•••</summary><button data-model-delete="${escapeHTML(model.name)}" ${busy || benchmarkBusy || state.modelDownload ? 'disabled' : ''}>Delete model…</button></details></div>` : ''}</div>`;
  }).join('') : `<div class="model-empty"><strong>${query || activeFilters ? 'No matching models' : local ? connected ? 'Your library is empty' : 'Local engine offline' : 'Connect your provider'}</strong><p>${query || activeFilters ? 'Try another search or reset the filters.' : local ? connected ? 'Open Downloads to add your first model, or import from Ollama in Local engine.' : 'Open Local engine to check the connection, then refresh.' : 'Open Manage connections to connect this provider, then refresh.'}</p></div>`;
  $('model-list').querySelectorAll('[data-benchmark]').forEach(button => button.onclick = async () => { try { state = await invoke('benchmark-start', button.dataset.benchmark); render(); } catch {} });
  $('model-list').querySelectorAll('[data-model-delete]').forEach(button => button.onclick = () => { deleteModelName = button.dataset.modelDelete; $('model-delete-description').textContent = `${deleteModelName} · ${state.localRuntime.mode === 'managed' ? 'Wixal Local library' : 'external Ollama library'}`; $('models-dialog').close(); $('model-delete-dialog').showModal(); });
  $('context-size').value = String(state?.contextSize || 16384); $('context-size').disabled = busy || benchmarkBusy;
  $('model-pull-form').classList.toggle('hidden', !local);
  renderDownload(); renderRuntime(); renderModelAdvice();
  $('model-library-info').textContent = local ? connected ? 'Capabilities reported by the local engine · memory fit is an estimate' : 'Start the local engine, then refresh.' : 'Tool and image support varies by model';
  $('ollama-help').classList.toggle('hidden', !local || (connected && models.length > 0));
  $('model-list').querySelectorAll('[data-model]').forEach(button => button.onclick = () => useModel(button.dataset.model));
}
async function useModel(name) {
  const model = models.find(item => item.name === name);
  if (!model) { await loadModels(); return useModelAfterRefresh(name); }
  const mode = model.capabilities?.includes('tools') ? state.mode : 'chat';
  try {
    const before = state.mode; state = await invoke('settings', { model: model.name, mode }); render();
    if (!modelsPageOpen) $('models-dialog').close();
    $('model-selection-status').textContent = `Using ${model.displayName || shortModel(model.name)}`;
    if (before !== mode) toast('Switched to Chat. This model has no confirmed tool support.');
  } catch {}
}
function useModelAfterRefresh(name) { if (models.some(item => item.name === name)) return useModel(name); toast('Refresh the library before selecting this model.'); }
function renderCatalog() {
  const local = state.provider === 'ollama', type = $('model-type-filter').value, fit = $('model-fit-filter').value;
  $('model-discover').classList.toggle('hidden', !local);
  const query = $('model-search').value.trim().toLowerCase(), sizeLimit = Number($('model-size-filter').value) * 1e9;
  const items = (state.modelCatalog || []).filter(m => m.name.toLowerCase().includes(query) && (!sizeLimit || m.size <= sizeLimit) && (type === 'all' || m.capabilities.includes(type)) && (fit === 'all' || fit === 'estimated' && m.fit.fits));
  items.sort((a, b) => $('model-sort').value === 'size' ? a.size - b.size : a.name.localeCompare(b.name));
  $('model-catalog-list').innerHTML = items.map(m => {
    const installed = models.some(model => model.name === m.name), job = state.modelDownloads?.findLast(item => item.name === m.name && item.mode === state.localRuntime.mode && ['queued', 'downloading', 'paused'].includes(item.state));
    return `<div class="catalog-card"><button type="button" class="catalog-row" data-download-tag="${escapeHTML(m.name)}"><div><strong>${escapeHTML(m.name)}</strong><small>${m.capabilities.map(c => c === 'vision' ? 'Images' : c[0].toUpperCase() + c.slice(1)).join(' · ') || 'Chat'} · ${m.fit.fits ? 'Estimated fit' : 'May exceed RAM'}</small></div><span class="catalog-size">${(m.size / 1e9).toFixed(1)} GB<small>download</small></span><span class="catalog-choose">Choose tag →</span></button><button type="button" class="catalog-download ${installed ? 'text-button' : 'secondary'}" ${installed ? `data-catalog-use="${escapeHTML(m.name)}"` : `data-catalog-download="${escapeHTML(m.name)}"`} ${busy || state.benchmarkProgress || (!installed && job) ? 'disabled' : ''}>${installed ? 'Use model' : job ? job.state === 'paused' ? 'Paused · see queue' : job.state === 'queued' ? 'Queued' : 'Downloading' : 'Download'}</button></div>`;
  }).join('') || '<p class="empty-project">No downloads match. Try another search or reset the filters.</p>';
  $('model-catalog-list').querySelectorAll('[data-download-tag]').forEach(button => button.onclick = () => { $('model-pull-name').value = button.dataset.downloadTag; $('model-pull-name').focus(); });
  $('model-catalog-list').querySelectorAll('[data-catalog-download]').forEach(button => button.onclick = () => queueModel(button.dataset.catalogDownload));
  $('model-catalog-list').querySelectorAll('[data-catalog-use]').forEach(button => button.onclick = () => useModel(button.dataset.catalogUse));
}
async function queueModel(name) {
  try { state = await invoke('model-pull', name); $('model-pull-name').value = ''; renderModelList(); } catch {}
}
function renderModelAdvice() {
  const local = state.provider === 'ollama', model = selectedModel();
  $('model-performance-advice').classList.toggle('hidden', !local || !model);
  const cacheBytes = state.localRuntime.mode === 'managed' ? 1 : 2;
  const required = context => (model?.size || 0) * 1.15 + Math.min(context, model?.contextLength || context) * (model?.kvBytesPerToken ? model.kvBytesPerToken * cacheBytes : 128 * 1024) + 1024 ** 3;
  const recommended = [16384, 8192].find(context => required(context) <= state.hardware.memoryBudget && (!model?.contextLength || context <= model.contextLength));
  $('model-context-advice').textContent = recommended ? `Suggested: ${recommended / 1024}k context for this model. More context needs more memory; benchmark at the setting you plan to use.` : 'This model may exceed the memory budget even at 8k context. Try a smaller model or check a benchmark before relying on it.';
  $('model-context-recommend').disabled = busy || !!state.benchmarkProgress || !recommended || state.contextSize === recommended;
  $('model-context-recommend').dataset.context = recommended || '';
  $('model-runtime-tuning').textContent = state.localRuntime.mode === 'managed' ? 'Wixal manages one loaded model and one request at a time, with Flash Attention and an 8-bit context cache.' : 'External engine performance settings are managed by its installation.';
  $('model-library-metrics').classList.toggle('hidden', !local || !modelsPageOpen);
  const currentInfo = libraryInfo?.mode === state.localRuntime.mode ? libraryInfo : null;
  $('model-disk-info').textContent = currentInfo?.diskFree != null ? `${formatBytes(currentInfo.diskFree)} available on the model drive` : 'Model-drive space unavailable';
  const loaded = currentInfo?.loaded;
  $('model-loaded-info').textContent = loaded ? loaded.length ? `${loaded.length} loaded · ${formatBytes(loaded.reduce((total, item) => total + (item.size || 0), 0))} model memory` : 'No models loaded in memory' : 'Loaded memory unavailable';
  $('model-unload').disabled = busy || !!state.benchmarkProgress || !loaded?.length;
}
function formatBytes(bytes) { return bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GiB` : `${(bytes / 1024 ** 2).toFixed(1)} MiB`; }
async function loadLibraryInfo() {
  if (!modelsPageOpen || state.provider !== 'ollama') return;
  const request = ++libraryRequest;
  try { const info = await api['model-library'](); if (request === libraryRequest) { libraryInfo = info; renderModelAdvice(); } } catch {}
}
function modelBenchmark(model) { return state.benchmarks?.findLast(b => b.name === model.name && b.digest === model.digest && b.hardwareId === state.hardware.id && b.mode === state.localRuntime.mode && b.status === 'completed'); }
function renderBenchmarkProgress() {
  const progress = state.benchmarkProgress;
  $('benchmark-progress').classList.toggle('hidden', !progress);
  $('benchmark-status').textContent = progress ? `${progress.name} · ${progress.phase}${progress.sample ? ` · run ${progress.sample}/2` : ''}` : '';
}
function renderPerformance() {
  if (!state.hardware) return;
  const records = state.usage || [], chat = records.filter(r => r.sessionId === session()?.id), sum = (rows, key) => rows.reduce((n, r) => n + (r[key] || 0), 0), latest = records.at(-1);
  $('performance-hardware').textContent = `${state.hardware.cpu} · ${state.hardware.arch} · ${state.hardware.cores} cores · ${(state.hardware.totalMemory / 1024 ** 3).toFixed(0)} GB RAM`;
  const cards = [['Reported chat input', chat.length && !chat.some(r => r.inputTokens != null) ? 'Unavailable' : sum(chat, 'inputTokens').toLocaleString()], ['Reported chat output', sum(chat, 'tokens').toLocaleString()], ['Reported saved output', sum(records, 'tokens').toLocaleString()], ['Last generation', latest ? `${latest.tokensPerSecond} tok/s` : 'No runs yet'], ['First output', latest?.timeToFirstToken != null ? `${latest.timeToFirstToken.toFixed(2)}s` : 'Unavailable'], ['Saved requests', records.length]];
  $('performance-totals').innerHTML = cards.map(([label, value]) => `<div><small>${escapeHTML(label)}</small><strong>${escapeHTML(value)}</strong></div>`).join('') + '<p>Counts use engine/provider reports. Missing usage is unavailable. Includes tool steps, summaries and retries; saved totals cover the last 2,000 requests. Benchmarks are listed separately.</p>';
  $('performance-benchmarks').innerHTML = (state.benchmarks || []).filter(b => b.hardwareId === state.hardware.id).toReversed().map(b => `<div class="benchmark-result"><strong>${escapeHTML(b.name)}</strong><span>${b.tokensPerSecond} tok/s · ${Math.round(b.context / 1024)}k context</span><small>${b.timeToFirstToken != null ? `First output ${b.timeToFirstToken.toFixed(2)}s · ` : ''}${b.loadedBytes ? `${(b.loadedBytes / 1024 ** 3).toFixed(1)} GiB loaded · ` : ''}${new Date(b.created).toLocaleString()}</small></div>`).join('') || '<p class="muted">Benchmark an installed local model from the model manager.</p>';
}
function renderMentions() {
  const text = $('prompt').value, cursor = $('prompt').selectionStart, match = text.slice(0, cursor).match(/(?:^|\s)@([a-zA-Z0-9_]*)$/);
  mentionCandidates = match ? availableTools().filter(t => state.enabledTools.includes(t.id) && `${t.id} ${t.name}`.toLowerCase().includes(match[1].toLowerCase())).sort((a, b) => Number(!a.id.startsWith(match[1])) - Number(!b.id.startsWith(match[1])) || a.id.localeCompare(b.id)).slice(0, 10) : [];
  mentionIndex = Math.min(mentionIndex, Math.max(0, mentionCandidates.length - 1));
  $('tool-mentions').classList.toggle('hidden', !mentionCandidates.length);
  $('tool-mentions').innerHTML = mentionCandidates.map((t, index) => `<button type="button" role="option" aria-selected="${index === mentionIndex}" data-mention="${escapeHTML(t.id)}"><strong>@${escapeHTML(t.id)}</strong><small>${escapeHTML(t.name)}</small></button>`).join('');
  $('tool-mentions').querySelectorAll('button').forEach(b => b.onclick = () => insertMention(b.dataset.mention));
  const selected = availableTools().filter(t => new RegExp(`(?:^|\\s)@${t.id}(?=\\s|$|[.,!?])`).test(text));
  $('selected-mentions').classList.toggle('hidden', !selected.length);
  $('selected-mentions').textContent = selected.length ? `Explicit tools: ${selected.map(t => '@' + t.id).join(', ')}` : '';
}
function insertMention(id) {
  const input = $('prompt'), cursor = input.selectionStart, before = input.value.slice(0, cursor), replaced = before.replace(/@([a-zA-Z0-9_]*)$/, '@' + id + ' ');
  input.value = replaced + input.value.slice(cursor); input.focus(); input.setSelectionRange(replaced.length, replaced.length); sizePrompt(); renderMentions();
}
function renderRuntime() {
  const runtime = state?.localRuntime; if (!runtime) return;
  const local = state.provider === 'ollama', managed = runtime.mode === 'managed';
  $('runtime-panel').classList.toggle('hidden', !local);
  $('runtime-mode').value = runtime.mode;
  $('ollama-help').querySelector('p').textContent = managed ? 'Open Downloads to add a model, or import from Ollama in Local engine.' : 'Open Ollama, then add a model from Downloads and refresh the list.';
  const locked = busy || !!state.benchmarkProgress || !!state.modelDownload || runtime.importing || ['starting', 'stopping'].includes(runtime.status);
  $('runtime-mode').disabled = locked;
  $('runtime-status').textContent = runtime.importing ? 'Importing…' : managed ? `${runtime.status} · ${runtime.version}` : 'External server';
  $('runtime-description').textContent = managed ? 'Your model library lives with Wixal. No separate Ollama app is required.' : 'Uses your Ollama server on this Mac at port 11434 and its existing model library.';
  if (managed && runtime.error) $('runtime-panel').open = true;
  $('runtime-error').textContent = runtime.error; $('runtime-error').classList.toggle('hidden', !runtime.error || !managed);
  $('runtime-start').disabled = locked || runtime.status === 'ready'; $('runtime-stop').disabled = locked || runtime.status !== 'ready';
  for (const id of ['runtime-start', 'runtime-stop', 'runtime-reveal', 'runtime-import-section']) $(id).classList.toggle('hidden', !managed);
  $('runtime-scan').disabled = locked; $('runtime-import').disabled = locked || !$('runtime-import-model').value;
}
function renderDownload(progress = state?.modelDownload) {
  const jobs = state?.modelDownloads || [], active = jobs.find(item => item.state === 'downloading'), pending = jobs.filter(item => ['queued', 'downloading'].includes(item.state));
  $('model-pull-button').disabled = busy || !!state.benchmarkProgress || !!state?.localRuntime?.importing;
  $('model-pull-name').disabled = $('model-pull-button').disabled;
  $('model-pull-button').textContent = active ? 'Queue download' : 'Download';
  $('model-download-indicator').textContent = pending.length ? ` · ${pending.length}` : '';
  $('download-queue-badge').textContent = String(pending.length); $('download-queue-badge').classList.toggle('hidden', !pending.length);
  $('model-pull-cancel').classList.toggle('hidden', !active);
  $('model-pull-status').textContent = active ? `${active.name} · ${active.status}` : '';
  $('model-download-summary').textContent = jobs.length ? `${pending.length} pending · downloads run one at a time. Paused transfers can resume.` : 'No downloads yet. Choose a model below or enter its tag.';
  const key = jobs.map(item => `${item.id}:${item.state}`).join('|');
  if (key !== downloadStateKey) {
    downloadStateKey = key;
    $('model-download-jobs').innerHTML = jobs.toReversed().map(item => `<article class="download-job" data-state="${item.state}" data-download-id="${item.id}"><div class="download-job-heading"><strong>${escapeHTML(item.name)}</strong><span data-job-state>${escapeHTML(item.state)}</span></div><p data-job-status></p><progress data-job-progress max="100" aria-label="Reported download progress for ${escapeHTML(item.name)}"></progress><small data-job-bytes></small><p data-job-error class="runtime-error"></p><div class="download-job-actions">${['downloading', 'queued'].includes(item.state) ? `<button data-download-action="pause">Pause</button><button data-download-action="cancel">Cancel</button>` : ['paused', 'failed', 'cancelled'].includes(item.state) ? `<button data-download-action="${item.state === 'paused' ? 'resume' : 'retry'}">${item.state === 'paused' ? 'Resume' : 'Retry'}</button><button data-download-action="remove">Remove</button>` : `<button data-download-use="${escapeHTML(item.name)}">Use model →</button><button data-download-action="remove">Dismiss</button>`}</div></article>`).join('');
    $('model-download-jobs').querySelectorAll('[data-download-action]').forEach(button => button.onclick = async () => { try { state = await invoke('model-download-action', button.closest('[data-download-id]').dataset.downloadId, button.dataset.downloadAction); renderModelList(); } catch {} });
    $('model-download-jobs').querySelectorAll('[data-download-use]').forEach(button => button.onclick = () => useModel(button.dataset.downloadUse));
  }
  for (const item of jobs) {
    const row = $('model-download-jobs').querySelector(`[data-download-id="${item.id}"]`); if (!row) continue;
    row.querySelector('[data-job-status]').textContent = item.status;
    row.querySelector('[data-job-error]').textContent = item.error || '';
    const bar = row.querySelector('progress'); bar.hidden = !['downloading', 'paused'].includes(item.state);
    if (item.total) bar.value = Math.min(100, item.completed / item.total * 100); else bar.removeAttribute('value');
    row.querySelector('[data-job-bytes]').textContent = item.total ? `${formatBytes(item.completed)} / ${formatBytes(item.total)} reported${item.rate > 0 ? ` · ${formatBytes(item.rate)}/s` : ''}${item.eta ? ` · about ${item.eta < 60 ? `${item.eta}s` : `${Math.ceil(item.eta / 60)}m`} remaining in reported layers` : ''}` : '';
    row.querySelectorAll('button').forEach(button => button.disabled = !!state.benchmarkProgress || (!!busy && ['resume', 'retry'].includes(button.dataset.downloadAction)));
  }
}
async function loadModels(force = false) {
  const request = ++modelRequest, provider = state.provider;
  $('connection-label').textContent = `Checking ${providerLabels[provider]}…`;
  $('connection-detail').textContent = provider === 'ollama' ? 'On this Mac · 127.0.0.1' : 'Cloud · context shared when enabled';
  try {
    const response = await api.models(force === true); if (request !== modelRequest) return;
    models = response.models; connected = true;
    $('connection-label').textContent = models.length ? `${providerLabels[provider]} connected` : `${providerLabels[provider]} · no models`;
    $('connection-dot').classList.remove('offline'); state = await api.state();
  } catch (error) {
    if (request !== modelRequest) return;
    connected = false; models = []; $('connection-label').textContent = provider === 'ollama' ? `${providerLabels.ollama} offline` : `${providerLabels[provider]} not connected`;
    $('connection-dot').classList.add('offline'); state = await api.state(); if (provider !== 'ollama') toast(error.message);
  }
  render();
}
function setBusy(value) {
  busy = value; $('send').classList.toggle('hidden', value); $('stop').classList.toggle('hidden', !value);
  $('activity').classList.toggle('busy', value); $('activity-label').textContent = value ? state.provider === 'ollama' ? 'Working locally…' : 'Working…' : 'Ready';
  $('prompt').disabled = value; render();
}
async function showConnections() {
  try { connections = await invoke('connections'); if (!['ollama', 'chatgpt'].includes(state.provider)) keyProvider = state.provider; const custom = connections.customProvider; $('custom-base-url').value = custom.baseURL; $('custom-model').value = custom.model; $('custom-tools').checked = custom.tools; $('custom-vision').checked = custom.vision; renderConnections(); if (!$('connections-dialog').open) $('connections-dialog').showModal(); } catch {}
}
function renderConnections() {
  if (!connections || !state) return;
  const provider = connections.providers.find(item => item.id === keyProvider), custom = keyProvider === 'custom';
  $('key-provider-select').innerHTML = connections.providers.filter(item => item.apiKey).map(item => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.label)}</option>`).join('');
  $('key-provider-select').value = keyProvider; $('key-provider-select').disabled = busy;
  $('key-provider-heading').textContent = provider.label;
  $('api-key-status').textContent = connections.error || (connections.keysSaved[keyProvider] ? 'Key saved securely' : custom ? 'Key optional' : 'No key saved');
  $('remove-api-key').disabled = busy || !connections.keysSaved[keyProvider];
  $('api-key-input').placeholder = custom ? 'Optional key for this endpoint' : `Paste your ${provider.label.replace(/ API$/, '')} API key`;
  $('api-key-input').required = !custom; $('api-key-input').disabled = busy;
  $('api-key-form').querySelector('button').textContent = custom ? 'Save connection' : 'Save key';
  $('provider-keys-link').classList.toggle('hidden', !provider.keysURL);
  $('key-provider-description').textContent = custom ? 'Connect a server that supports Chat Completions. Enter its base URL and exact model ID.' : `Requests use your ${provider.label} API account. API access and billing are managed by that provider.`;
  $('custom-provider-fields').classList.toggle('hidden', !custom);
  for (const id of ['custom-base-url', 'custom-model', 'custom-tools', 'custom-vision']) $(id).disabled = busy;
  $('provider-connection-status').innerHTML = connections.providers.filter(item => item.apiKey && connections.keysSaved[item.id]).map(item => `<span>${escapeHTML(item.label)} · key saved</span>`).join('');
  $('chatgpt-sign-in').disabled = busy || connections.pending;
  $('chatgpt-cancel').classList.toggle('hidden', !connections.pending);
  $('chatgpt-auth-status').textContent = connections.pending ? 'Finish sign-in in your browser…' : '';
  $('chatgpt-accounts').innerHTML = connections.accounts.map(account => `<div class="account-row"><div><strong>${escapeHTML(account.label)}</strong><small>${account.signedIn ? account.id === connections.activeAccount ? 'Active' : 'Saved account' : 'Signed out'} · ${account.planEnabled ? 'Plan usage authorized' : 'Plan usage not authorized'}</small></div><div>${account.signedIn && account.id !== connections.activeAccount ? `<button data-account-select="${escapeHTML(account.id)}" class="secondary" ${busy ? 'disabled' : ''}>Use</button>` : ''}<button data-account-connect="${escapeHTML(account.id)}" class="secondary" ${busy || connections.pending ? 'disabled' : ''}>Reconnect</button>${account.signedIn ? `<button data-account-out="${escapeHTML(account.id)}" class="text-button" ${busy ? 'disabled' : ''}>Sign out</button>` : ''}</div></div>`).join('');
  $('chatgpt-accounts').querySelectorAll('[data-account-select]').forEach(button => button.onclick = async () => { try { connections = await invoke('chatgpt-select', button.dataset.accountSelect); renderConnections(); if (state.provider === 'chatgpt') await loadModels(); } catch {} });
  $('chatgpt-accounts').querySelectorAll('[data-account-connect]').forEach(button => button.onclick = () => signIn(button.dataset.accountConnect));
  $('chatgpt-accounts').querySelectorAll('[data-account-out]').forEach(button => button.onclick = async () => { try { connections = await invoke('chatgpt-sign-out', button.dataset.accountOut); toast(connections.message); renderConnections(); if (state.provider === 'chatgpt') await loadModels(); } catch {} });
  $('sharing-projects').innerHTML = state.projects.length ? `<table class="sharing-table"><thead><tr><th>Project</th><th>Cloud models</th><th>Companion</th></tr></thead><tbody>${state.projects.map(p => `<tr><td>${escapeHTML(p.name)}</td><td><input type="checkbox" data-cloud="${p.id}" aria-label="Allow cloud context for ${escapeHTML(p.name)}" ${connections.cloudProjects.includes(p.id) ? 'checked' : ''} ${busy ? 'disabled' : ''}></td><td><input type="checkbox" data-share="${p.id}" aria-label="Share ${escapeHTML(p.name)} with companion" ${connections.companion.sharedProjects.includes(p.id) ? 'checked' : ''} ${busy ? 'disabled' : ''}></td></tr>`).join('')}</tbody></table>` : '<p class="muted">Open a project to choose what to share.</p>';
  $('cloud-personal').checked = connections.cloudPersonal;
  $('companion-memory').checked = connections.companion.shareMemory;
  $('companion-enabled').checked = connections.companion.running;
  for (const id of ['cloud-personal', 'companion-memory', 'companion-enabled']) $(id).disabled = busy;
  $('sharing-projects').querySelectorAll('input').forEach(input => input.onchange = saveSharing);
  $('companion-status').textContent = connections.companion.running ? 'Local bridge running' : 'Paused';
  $('companion-setup').classList.toggle('hidden', !connections.companion.running);
  $('companion-command').textContent = connections.companion.command || '';
  $('api-key-form').querySelector('button').disabled = busy;
}
async function saveSharing() {
  const settings = { cloudProjects: [...$('sharing-projects').querySelectorAll('[data-cloud]:checked')].map(input => input.dataset.cloud),
    sharedProjects: [...$('sharing-projects').querySelectorAll('[data-share]:checked')].map(input => input.dataset.share),
    cloudPersonal: $('cloud-personal').checked, shareMemory: $('companion-memory').checked, enabled: $('companion-enabled').checked };
  try { connections = await invoke('sharing', settings); state = await api.state(); render(); renderConnections(); } catch { renderConnections(); }
}
async function signIn(id) { try { await invoke('chatgpt-sign-in', id); connections = await api.connections(); renderConnections(); } catch {} }
function showTasks() { renderTasks(); if (!$('tasks-dialog').open) $('tasks-dialog').showModal(); }
function renderTasks() {
  if (!state) return;
  $('task-list').innerHTML = state.tasks.length ? state.tasks.toReversed().map(task => `<article class="task-card"><div class="section-top"><strong>${escapeHTML(task.title)}</strong><span class="task-state">${escapeHTML(task.status.replace('_', ' '))}</span></div><p class="muted">${escapeHTML(state.projects.find(p => p.id === task.projectId)?.name || 'Project')} · from ${escapeHTML(task.source)}</p><details><summary>Read task brief</summary><pre>${escapeHTML(task.prompt)}</pre></details>${task.error ? `<p class="task-error">${escapeHTML(task.error)}</p>` : ''}${task.result ? `<details><summary>Completed response</summary><div>${markdown(task.result)}</div></details>` : ''}<div class="connection-actions">${['queued', 'failed', 'interrupted', 'cancelled'].includes(task.status) ? `<button data-task-start="${task.id}" class="primary" ${busy ? 'disabled' : ''}>${task.status === 'queued' ? 'Start in Wixal' : 'Retry in new conversation'}</button>` : ''}${task.status === 'queued' ? `<button data-task-cancel="${task.id}" class="secondary" ${busy ? 'disabled' : ''}>Dismiss</button>` : ''}${task.sessionId ? `<button data-task-open="${task.id}" class="text-button" ${busy ? 'disabled' : ''}>Open conversation ↗</button>` : ''}</div></article>`).join('') : '<div class="empty-project">No tasks yet. Connect the Wixal companion and ask ChatGPT to send a task.</div>';
  $('task-list').querySelectorAll('[data-task-start]').forEach(button => button.onclick = async () => {
    if (!connected || !selectedModel()) { $('tasks-dialog').close(); toast('Choose a connected model before starting a task.'); showModels(); return; }
    try { state = await invoke('task-start', button.dataset.taskStart); clearDraft(); resetTerminal(); render(); $('tasks-dialog').close(); } catch {}
  });
  $('task-list').querySelectorAll('[data-task-cancel]').forEach(button => button.onclick = async () => { try { state = await invoke('task-cancel', button.dataset.taskCancel); render(); } catch {} });
  $('task-list').querySelectorAll('[data-task-open]').forEach(button => button.onclick = async () => {
    const task = state.tasks.find(t => t.id === button.dataset.taskOpen);
    try { await switchProject(task.projectId); state = await invoke('session-select', task.sessionId); render(); $('tasks-dialog').close(); } catch {}
  });
}
$('connections-button').onclick = showConnections; $('cloud-settings').onclick = showConnections; $('tasks-button').onclick = showTasks;
$('key-provider-select').onchange = event => {
  keyProvider = event.target.value; $('api-key-input').value = '';
  const custom = connections.customProvider;
  $('custom-base-url').value = custom.baseURL; $('custom-model').value = custom.model;
  $('custom-tools').checked = custom.tools; $('custom-vision').checked = custom.vision;
  renderConnections();
};
$('provider-keys-link').onclick = () => invoke('connection-link', `provider:${keyProvider}`).catch(() => {});
$('api-key-form').onsubmit = async event => {
  event.preventDefault(); const provider = keyProvider, key = $('api-key-input').value; $('api-key-input').value = '';
  try {
    connections = provider === 'custom' ? await invoke('custom-provider-save', { key, baseURL: $('custom-base-url').value, model: $('custom-model').value, tools: $('custom-tools').checked, vision: $('custom-vision').checked }) : await invoke('provider-key-save', { provider, key });
    state = await api.state(); renderConnections(); render(); toast(`Connection saved. Choose ${providerLabels[provider]} in the model picker.`);
    if (state.provider === provider) await loadModels();
  } catch {}
};
$('remove-api-key').onclick = async () => { try { const provider = keyProvider; connections = await invoke('provider-key-remove', provider); renderConnections(); if (state.provider === provider) await loadModels(); } catch {} };
$('chatgpt-sign-in').onclick = () => signIn();
$('plan-notice-dismiss').onclick = async () => { try { await invoke('chatgpt-plan-notice'); $('plan-notice-dialog').close(); await showConnections(); } catch {} };
$('plan-notice-dialog').addEventListener('cancel', event => { event.preventDefault(); $('plan-notice-dismiss').click(); });
$('chatgpt-cancel').onclick = async () => { try { connections = await invoke('chatgpt-cancel'); renderConnections(); } catch {} };
$('connections-dialog').addEventListener('close', () => { $('api-key-input').value = ''; });
for (const id of ['cloud-personal', 'companion-memory', 'companion-enabled']) $(id).onchange = saveSharing;
$('copy-companion-command').onclick = () => invoke('copy-text', connections.companion.command).then(() => toast('MCP command copied.')).catch(() => {});
document.querySelectorAll('[data-link]').forEach(button => button.onclick = () => invoke('connection-link', button.dataset.link).catch(() => {}));
$('provider-select').onchange = async event => {
  try { state = await invoke('settings', { provider: event.target.value }); models = []; connected = false; render(); await loadModels(); await loadLibraryInfo(); } catch { renderModelList(); }
};
function clearDraft() { streamText = ''; attachments = []; $('prompt').value = ''; sizePrompt(); renderMentions(); $('context-note').textContent = ''; renderAttachments(); }
let folderBrowser, folderBrowseRequest = 0, folderLoading = false;
function folderError(error) {
  const message = String(error.message).replace(/^Error invoking remote method '[^']+': Error: /, '');
  $('folder-status').textContent = /EACCES|EPERM/.test(message) ? 'Wixal cannot access this folder. Choose another location or allow access in macOS settings.' : /ENOENT/.test(message) ? 'That folder could not be found. Check the path and try again.' : message;
}
function renderFolderList() {
  const query = $('folder-filter').value.toLowerCase();
  const folders = (folderBrowser?.folders || []).filter(folder => folder.name.toLowerCase().includes(query));
  $('folder-list').innerHTML = folders.length ? folders.map(folder => `<button class="folder-row" data-folder-path="${escapeHTML(folder.path)}"><span aria-hidden="true">▱</span><span>${escapeHTML(folder.name)}</span><span aria-hidden="true">›</span></button>`).join('') : `<p class="empty-project">${query ? 'No matching folders.' : 'No subfolders here. You can use this folder or create one.'}</p>`;
  $('folder-list').querySelectorAll('button').forEach(button => button.onclick = () => browseProjectFolder(button.dataset.folderPath));
}
async function browseProjectFolder(path) {
  const request = ++folderBrowseRequest; folderLoading = true; folderBrowser = null;
  $('folder-list').innerHTML = '<p class="empty-project">Loading folders…</p>';
  $('folder-open').disabled = true; $('folder-create').disabled = true; $('folder-new-toggle').disabled = true;
  $('folder-status').textContent = 'Loading folders…';
  try {
    const result = await api['project-browse'](path, $('folder-hidden').checked);
    if (request !== folderBrowseRequest) return;
    folderBrowser = result; $('folder-path').value = result.path; $('folder-filter').value = '';
    $('folder-up').disabled = result.parent === result.path;
    $('folder-locations').innerHTML = [...result.locations, ...state.projects.map(p => ({ name: p.name, path: p.root }))].map(location => `<button data-location="${escapeHTML(location.path)}" title="${escapeHTML(location.path)}">${escapeHTML(location.name)}</button>`).join('');
    $('folder-locations').querySelectorAll('button').forEach(button => button.onclick = () => browseProjectFolder(button.dataset.location));
    renderFolderList(); $('folder-status').textContent = result.truncated ? 'Showing the first 1,000 folders. Paste a path to go directly to another folder.' : 'Use this folder to keep its chats and memory together.';
  } catch (error) { if (request === folderBrowseRequest) folderError(error); }
  finally { if (request === folderBrowseRequest) { folderLoading = false; $('folder-open').disabled = !folderBrowser; $('folder-create').disabled = !folderBrowser; $('folder-new-toggle').disabled = !folderBrowser; } }
}
async function openProject() {
  if (busy) { toast('Finish or stop the current response before opening a project.'); return; }
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
  folderBrowser = null; $('folder-new-form').classList.add('hidden'); $('folder-new-name').value = ''; $('folder-hidden').checked = false;
  $('folder-list').innerHTML = ''; $('project-dialog').showModal();
  await browseProjectFolder(project()?.root); $('folder-path').focus();
}
$('folder-path-form').onsubmit = event => { event.preventDefault(); browseProjectFolder($('folder-path').value); };
$('folder-filter').oninput = renderFolderList;
$('folder-up').onclick = () => { if (folderBrowser) browseProjectFolder(folderBrowser.parent); };
$('folder-hidden').onchange = () => browseProjectFolder(folderBrowser?.path);
$('folder-new-toggle').onclick = () => { $('folder-new-form').classList.remove('hidden'); $('folder-new-name').focus(); };
$('folder-new-cancel').onclick = () => $('folder-new-form').classList.add('hidden');
$('folder-new-form').onsubmit = async event => {
  event.preventDefault(); if (folderLoading || !folderBrowser) return;
  folderLoading = true; $('folder-create').disabled = true; $('folder-open').disabled = true;
  try { const folder = await api['project-create-folder'](folderBrowser.path, $('folder-new-name').value); $('folder-new-form').classList.add('hidden'); $('folder-new-name').value = ''; await browseProjectFolder(folder); }
  catch (error) { folderError(error); }
  finally { folderLoading = false; $('folder-create').disabled = !folderBrowser; $('folder-open').disabled = !folderBrowser; }
};
$('folder-open').onclick = async () => {
  if (folderLoading || !folderBrowser) return;
  $('folder-open').disabled = true;
  try { state = await api['project-open'](folderBrowser.path); clearDraft(); resetTerminal(); render(); $('project-dialog').close(); $('prompt').focus(); }
  catch (error) { folderError(error); }
  finally { $('folder-open').disabled = false; }
};
async function switchProject(id) { closeModelPage(); try { state = await invoke('project-select', id); clearDraft(); resetTerminal(); render(); } catch {} }
async function newSession() { closeModelPage(); try { state = await invoke('session-new'); clearDraft(); $('session-search').value = ''; render(); $('prompt').focus(); } catch {} }
function resetTerminal() { terminalOpen = false; terminal?.reset(); $('terminal-panel').classList.add('hidden'); }
async function toggleTerminal() {
  if (terminalOpen) { $('terminal-panel').classList.add('hidden'); terminalOpen = false; renderStartLayout(); return; }
  if (!project()) { toast('Open a project folder to start its terminal.'); return; }
  $('terminal-panel').classList.remove('hidden'); terminalOpen = true; renderStartLayout();
  if (!terminal) {
    terminal = new Terminal({ fontFamily: 'Menlo, monospace', fontSize: 11, cursorBlink: true, scrollback: 3000,
      theme: { background: '#111215', foreground: '#ddd4df', cursor: '#e9a5bd', selectionBackground: '#513c51', black: '#1b1920', red: '#df96a5', green: '#a4c5ac', yellow: '#dbc394', blue: '#a4b0df', magenta: '#ce9cde', cyan: '#93c9cb', white: '#e7dceb', brightBlack: '#877d8b' },
    });
    fitAddon = new FitAddon.FitAddon(); terminal.loadAddon(fitAddon); terminal.open($('terminal')); applyAppearance();
    terminal.onData(text => api['terminal-write'](text));
    new ResizeObserver(() => { if (terminalOpen) { fitAddon.fit(); api['terminal-resize']({ cols: terminal.cols, rows: terminal.rows }); } }).observe($('terminal'));
  }
  try { const result = await invoke('terminal-open'); $('terminal-root').textContent = result.root; requestAnimationFrame(() => { fitAddon.fit(); api['terminal-resize']({ cols: terminal.cols, rows: terminal.rows }); terminal.focus(); }); }
  catch { resetTerminal(); }
}
function toggleDrawer(name) {
  const drawer = $(`${name}-drawer`), open = drawer.classList.contains('hidden');
  ['memory', 'toolkit'].forEach(other => { $(`${other}-drawer`).classList.add('hidden'); $(`${other}-button`).setAttribute('aria-expanded', 'false'); });
  if (open) { drawer.classList.remove('hidden'); $(`${name}-button`).setAttribute('aria-expanded', 'true'); if (name === 'memory') $('memory-input').focus(); else $('close-toolkit').focus(); }
  else $(`${name}-button`).focus();
}
function showModels() { if (modelsPageOpen) closeModelPage(); setModelView('installed'); if (!$('models-dialog').open) $('models-dialog').showModal(); $('model-search').focus(); }
function showModelPage(view = 'installed') {
  $('models-dialog').close();
  document.querySelectorAll('.drawer:not(.hidden)').forEach(drawer => drawer.classList.add('hidden'));
  $('models-page-manager').append(document.querySelector('#models-dialog .model-manager'));
  modelsPageOpen = true; $('models-page').classList.remove('hidden'); $('models-page-button').setAttribute('aria-current', 'page');
  setModelView(view); $('model-search').focus(); loadLibraryInfo();
}
function closeModelPage() {
  if (!modelsPageOpen) return;
  $('models-dialog').append(document.querySelector('#models-page .model-manager'));
  modelsPageOpen = false; $('models-page').classList.add('hidden'); $('models-page-button').removeAttribute('aria-current'); $('model-library-metrics').classList.add('hidden'); $('prompt').focus();
}
$('models-page-button').onclick = () => { if (!modelsPageOpen) showModelPage(); };
$('models-page-back').onclick = closeModelPage;
$('model-open-page').onclick = () => showModelPage(modelView);
$('model-context-recommend').onclick = async () => { try { state = await invoke('settings', { contextSize: Number($('model-context-recommend').dataset.context) }); await loadModels(); render(); } catch {} };
$('model-unload').onclick = async () => { try { for (const item of libraryInfo?.loaded || []) await invoke('model-unload', item.name || item.model); await loadLibraryInfo(); } catch {} };
async function showFiles() {
  if (!project()) { toast('Open a project folder to browse its files.'); return; }
  $('files-dialog').showModal(); files = []; previewPath = ''; previewContent = ''; $('file-search').value = '';
  $('file-name').textContent = 'Choose a file'; $('file-content').textContent = 'Preview a file, then add its contents to your next message.'; $('use-file').disabled = true;
  $('file-list').innerHTML = '<p class="empty-project">Reading the project…</p>';
  try { files = (await invoke('project-files')).split('\n').filter(Boolean).sort(); renderFiles(); $('file-search').focus(); } catch { $('file-list').innerHTML = '<p class="empty-project">Couldn’t list these files. Close this panel and try again.</p>'; }
}
function renderFiles() {
  const query = $('file-search').value.toLowerCase(), filtered = files.filter(file => file.toLowerCase().includes(query));
  $('file-list').innerHTML = filtered.length ? filtered.map(file => `<button data-file="${escapeHTML(file)}" class="${previewPath === file ? 'selected' : ''}">${escapeHTML(file)}</button>`).join('') : '<p class="empty-project">No matching files.</p>';
  $('file-list').querySelectorAll('button').forEach(button => button.onclick = async () => {
    const request = ++fileRequest; previewPath = button.dataset.file; previewContent = ''; $('file-name').textContent = previewPath; $('file-content').textContent = 'Reading…'; $('use-file').disabled = true; renderFiles();
    try { const content = await invoke('project-read', previewPath); if (request !== fileRequest) return; previewContent = content; $('file-content').textContent = content; $('use-file').disabled = busy; }
    catch { if (request === fileRequest) $('file-content').textContent = 'This file cannot be previewed. Choose a text file under 1 MB.'; }
  });
}
$('use-file').onclick = () => {
  if (busy || !previewPath) return;
  const text = `\n\nFile context: ${previewPath}\n\`\`\`\n${previewContent.slice(0, 8000)}${previewContent.length > 8000 ? '\n[Excerpt truncated]' : ''}\n\`\`\``;
  if ($('prompt').value.length + text.length > 16000) { toast('There’s not enough room in this message. Shorten the prompt first.'); return; }
  $('prompt').value += text; sizePrompt(); $('files-dialog').close(); $('prompt').focus();
};
function renderAttachments() {
  $('attachments').classList.toggle('hidden', !attachments.length);
  $('attachments').innerHTML = attachments.map(image => `<div class="attachment"><img src="data:image/png;base64,${image.base64}" alt="${escapeHTML(image.name)}"><span>${escapeHTML(image.name)}</span><button type="button" data-remove="${image.id}" aria-label="Remove ${escapeHTML(image.name)}" ${busy ? 'disabled' : ''}>×</button></div>`).join('');
  $('attachments').querySelectorAll('button').forEach(button => button.onclick = async () => { try { await invoke('image-remove', button.dataset.remove); attachments = attachments.filter(image => image.id !== button.dataset.remove); renderAttachments(); } catch {} });
}
$('attach-image').onclick = async () => { if (!selectedModel()?.capabilities?.includes('vision')) { toast('Choose a model marked Images to attach photos or screenshots.'); showModels(); return; } try { attachments.push(...await invoke('images-open')); renderAttachments(); } catch {} };
function applySidebarLayout() {
  const collapsed = !!state?.ui?.sidebarCollapsed;
  const reopening = $('sidebar').classList.contains('collapsed') && !collapsed;
  if (reopening) { const wordmark = $('sidebar-wordmark'); wordmark.classList.remove('arriving'); void wordmark.offsetWidth; wordmark.classList.add('arriving'); }
  $('sidebar').classList.toggle('collapsed', collapsed);
  $('sidebar-toggle').setAttribute('aria-expanded', String(!collapsed));
  $('sidebar-toggle').setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
  $('sidebar-toggle').title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  $('show-sidebar').classList.add('hidden');
  requestAnimationFrame(positionWorkspaceMenu);
}
async function toggleSidebar(collapsed = !state.ui.sidebarCollapsed) {
  if (!!state.ui.sidebarCollapsed === !!collapsed) return;
  try { state = await invoke('layout', !!collapsed); applySidebarLayout(); }
  catch { applySidebarLayout(); }
}
function positionWorkspaceMenu() {
  const menu = $('workspace-menu'); if (!menu.matches(':popover-open')) return;
  const button = $('workspace-menu-toggle').getBoundingClientRect(), rect = menu.getBoundingClientRect();
  menu.style.left = `${Math.max(12, Math.min(button.left, innerWidth - rect.width - 12))}px`;
  menu.style.top = `${Math.max(12, button.top - rect.height - 8)}px`;
}
function toggleWorkspaceMenu() {
  const menu = $('workspace-menu');
  if (menu.matches(':popover-open')) { menu.hidePopover(); return; }
  menu.showPopover(); positionWorkspaceMenu();
}
window.addEventListener('resize', positionWorkspaceMenu);
$('sidebar').addEventListener('transitionend', positionWorkspaceMenu);
const themes = [
  { id: 'sakura', name: 'Sakura', note: 'Charcoal & pink', bg: '#17181b', panel: '#25232a', accent: '#e9a5bd' },
  { id: 'midnight', name: 'Midnight', note: 'Cool blue', bg: '#151823', panel: '#222937', accent: '#a5b9e9' },
  { id: 'forest', name: 'Forest', note: 'Quiet green', bg: '#151e19', panel: '#22372c', accent: '#a5e9c1' },
  { id: 'paper', name: 'Paper', note: 'Warm & light', bg: '#f1eee9', panel: '#ded9ce', accent: '#73583e' },
];
function applyAppearance() {
  document.documentElement.dataset.theme = state.ui.theme || 'sakura';
  document.documentElement.dataset.reduceMotion = String(!!state.ui.reduceMotion);
  document.documentElement.style.setProperty('--conversation-size', `${state.ui.textSize || 13}px`);
  if (terminal) {
    const css = getComputedStyle(document.documentElement);
    terminal.options.theme = { background: css.getPropertyValue('--bg').trim(), foreground: css.getPropertyValue('--text').trim(), cursor: css.getPropertyValue('--pink').trim(), selectionBackground: css.getPropertyValue('--line').trim() };
    terminal.options.fontSize = state.ui.textSize || 13;
    requestAnimationFrame(() => { if (terminalOpen) fitAddon.fit(); });
  }
}
function renderSettings() {
  $('theme-options').innerHTML = themes.map(t => `<button class="theme-card" data-theme-choice="${t.id}" aria-pressed="${(state.ui.theme || 'sakura') === t.id}" ${busy ? 'disabled' : ''}><span class="theme-preview" style="--preview-bg:${t.bg};--preview-panel:${t.panel};--preview-accent:${t.accent}" aria-hidden="true"></span>${t.name}<small>${t.note}</small></button>`).join('');
  $('theme-options').querySelectorAll('button').forEach(button => button.onclick = () => savePreference({ theme: button.dataset.themeChoice }));
  $('settings-text-size').value = state.ui.textSize || 13;
  $('settings-motion').checked = !!state.ui.reduceMotion;
  $('settings-sidebar').checked = !!state.ui.sidebarCollapsed;
  $('settings-summary').checked = state.autoSummary !== false;
  $('settings-context').value = state.contextSize;
  ['settings-text-size', 'settings-motion', 'settings-summary', 'settings-context'].forEach(id => $(id).disabled = busy);
  $('settings-status').textContent = busy ? 'Model preferences can be changed when the current task finishes.' : 'Changes are saved automatically.';
}
async function savePreference(value) {
  try { state = await invoke('settings', value); render(); } catch { renderSettings(); }
}
function showSettings() {
  $('workspace-menu').hidePopover();
  renderSettings(); $('settings-dialog').showModal(); $('settings-dialog').scrollTop = 0;
}
$('settings-button').onclick = showSettings;
$('settings-text-size').onchange = event => savePreference({ textSize: Number(event.target.value) });
$('settings-motion').onchange = event => savePreference({ reduceMotion: event.target.checked });
$('settings-summary').onchange = event => savePreference({ autoSummary: event.target.checked });
$('settings-context').onchange = async event => { await savePreference({ contextSize: Number(event.target.value) }); await loadModels(); };
$('settings-sidebar').onchange = async event => { await toggleSidebar(event.target.checked); renderSettings(); };
$('settings-dialog').querySelectorAll('[data-settings-action]').forEach(button => button.onclick = () => { $('settings-dialog').close(); actions[button.dataset.settingsAction](); });

function palette() { if ($('palette').open) $('palette').close(); else $('palette').showModal(); }
const actions = { settings: showSettings, sidebar: toggleSidebar, archives: showArchives, open: openProject, new: newSession, terminal: toggleTerminal, connections: showConnections, tasks: showTasks, memory: () => toggleDrawer('memory'), toolkit: () => toggleDrawer('toolkit'), files: showFiles, palette, models: showModels };
$('sidebar-toggle').onclick = () => toggleSidebar(); $('show-sidebar').onclick = () => toggleSidebar(false);
$('workspace-menu-toggle').onclick = toggleWorkspaceMenu;
$('workspace-menu').addEventListener('toggle', event => $('workspace-menu-toggle').setAttribute('aria-expanded', String(event.newState === 'open')));
$('workspace-menu').addEventListener('click', event => { if (event.target.closest('button')) $('workspace-menu').hidePopover(); });
$('new-chat').onclick = newSession; $('open-project').onclick = openProject; $('refresh-models').onclick = () => loadModels(true); $('model-refresh').onclick = async () => { await loadModels(true); await loadLibraryInfo(); };
$('terminal-button').onclick = toggleTerminal; $('close-terminal').onclick = toggleTerminal;
$('memory-button').onclick = actions.memory; $('close-memory').onclick = actions.memory;
$('toolkit-button').onclick = actions.toolkit; $('close-toolkit').onclick = actions.toolkit; $('welcome-toolkit').onclick = actions.toolkit;
$('files-button').onclick = showFiles; $('welcome-open').onclick = () => project() ? showFiles() : openProject();
$('palette-button').onclick = palette; $('model-button').onclick = showModels;
$('reveal-project').onclick = () => invoke('reveal-project').catch(() => {});
$('session-search').oninput = renderSessions; $('model-search').oninput = renderModelList; $('file-search').oninput = renderFiles;
$('auto-summary').onchange = async event => { try { state = await invoke('settings', { autoSummary: event.target.checked }); render(); } catch { render(); } };
$('summary-clear').onclick = async () => { try { state = await invoke('summary-clear'); render(); } catch {} };
$('manage-extensions').onclick = () => { renderExtensions(); $('extensions-dialog').showModal(); };
$('extension-form').onsubmit = async event => {
  event.preventDefault();
  try { const args = JSON.parse($('extension-args').value); state = await invoke('mcp-save', { name: $('extension-name').value, command: $('extension-command').value, args }); $('extension-form').reset(); $('extension-args').value = '[]'; render(); } catch (error) { toast(error.message); }
};
$('runtime-mode').onchange = async event => {
  try { ++modelRequest; state = await invoke('runtime-mode', event.target.value); models = []; connected = false; connections = await api.connections(); libraryInfo = null; render(); await loadModels(); await loadLibraryInfo(); } catch { renderRuntime(); }
};
$('runtime-start').onclick = async () => { try { state = await invoke('runtime-start'); await loadModels(); } catch { await refresh(); } };
$('runtime-stop').onclick = async () => { try { ++modelRequest; state = await invoke('runtime-stop'); models = []; connected = false; $('connection-label').textContent = 'Wixal Local stopped'; $('connection-dot').classList.add('offline'); render(); } catch {} };
$('runtime-reveal').onclick = () => invoke('runtime-reveal').catch(() => {});
$('runtime-scan').onclick = async () => {
  try {
    const imports = await invoke('runtime-imports');
    $('runtime-import-model').innerHTML = imports.map(model => `<option value="${escapeHTML(model.name)}">${escapeHTML(model.name)} · ${(model.bytes / 1e9).toFixed(1)} GB</option>`).join('');
    $('runtime-import-form').classList.toggle('hidden', !imports.length);
    $('runtime-import-status').textContent = imports.length ? 'Choose a model to copy into Wixal.' : 'No supported models found in ~/.ollama/models.'; renderRuntime();
  } catch {}
};
$('runtime-import').onclick = async () => {
  $('runtime-import-status').textContent = 'Copying and verifying model files…';
  try { state = await invoke('runtime-import', $('runtime-import-model').value); $('runtime-import-status').textContent = `Imported ${state.imported.name}.`; await loadModels(); }
  catch (error) { $('runtime-import-status').textContent = error.message; await refresh(); }
};
$('tool-search').oninput = renderToolkit; $('tool-category').onchange = renderToolkit;
$('tools-enable-all').onclick = async () => { try { state = await invoke('settings', { enabledTools: availableTools().map(t => t.id) }); render(); } catch {} };
for (const id of modelFilterIds) $(id).onchange = renderModelList;
$('model-filters-reset').onclick = () => { for (const id of modelFilterIds) $(id).value = id === 'model-size-filter' ? '0' : id === 'model-sort' ? 'name' : 'all'; renderModelList(); };
for (const view of ['installed', 'downloads']) {
  $(`model-${view}-tab`).onclick = () => setModelView(view);
  $(`model-${view}-tab`).onkeydown = event => {
    if (state.provider !== 'ollama' || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); setModelView(event.key === 'Home' ? 'installed' : event.key === 'End' ? 'downloads' : modelView === 'installed' ? 'downloads' : 'installed', true);
  };
}
$('model-empty-downloads').onclick = () => setModelView('downloads', true);
$('model-connections').onclick = () => { $('models-dialog').close(); showConnections(); };
$('response-stats').onclick = () => { renderPerformance(); $('performance-dialog').showModal(); };
$('performance-models').onclick = () => { $('performance-dialog').close(); showModels(); };
$('benchmark-cancel').onclick = () => api['benchmark-cancel']();
$('confirm-model-delete').onclick = async () => { try { state = await invoke('model-delete', deleteModelName); $('model-delete-dialog').close(); await loadModels(); if (!modelsPageOpen) showModels(); toast(`Deleted ${deleteModelName}.`); } catch {} };
$('model-pull-form').onsubmit = event => { event.preventDefault(); queueModel($('model-pull-name').value.trim()); };
$('model-pull-cancel').onclick = async () => { await api['model-pull-cancel'](); };
$('context-size').onchange = async event => { try { state = await invoke('settings', { contextSize: Number(event.target.value) }); await loadModels(); render(); } catch { render(); } };
$('conversation-label').onclick = () => { if (session()) showRename(session().id); };
$('rename-form').onsubmit = async event => { event.preventDefault(); try { state = await invoke('session-rename', $('rename-input').value, renameSessionId); $('rename-dialog').close(); render(); } catch {} };
$('archives-button').onclick = showArchives; $('archive-search').oninput = renderArchives;
$('restore-current').onclick = () => changeConversation('restore', session().id);
$('confirm-delete').onclick = async () => { if (await changeConversation('delete', deleteSessionId)) $('delete-dialog').close(); };
$('session-menu').querySelectorAll('[data-session-action]').forEach(button => button.onclick = () => {
  const id = menuSessionId, action = button.dataset.sessionAction; $('session-menu').hidePopover();
  if (action === 'rename') showRename(id); else if (action === 'delete') showDelete(id); else changeConversation('archive', id);
});
$('session-menu').onkeydown = event => {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault(); const buttons = [...$('session-menu').querySelectorAll('button')], current = buttons.indexOf(document.activeElement);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
  buttons[next].focus();
};
document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => $(button.dataset.close).close());
$('palette').querySelectorAll('button').forEach(button => button.onclick = () => { $('palette').close(); actions[button.dataset.action](); });
$('memory-form').onsubmit = async event => { event.preventDefault(); try { state = await invoke('memory-add', $('memory-input').value); $('memory-input').value = ''; render(); } catch {} };
$('mode-button').onclick = async () => {
  if (state.mode === 'chat' && !selectedModel()?.capabilities?.includes('tools')) { toast('Choose a model marked Tools for Agent mode.'); showModels(); return; }
  try { state = await invoke('settings', { mode: state.mode === 'agent' ? 'chat' : 'agent' }); render(); } catch {}
};
$('composer').onsubmit = async event => {
  event.preventDefault(); const prompt = $('prompt').value.trim(); if (!prompt || busy || session()?.archivedAt) return;
  if (!connected || !selectedModel()) { toast(`Connect ${providerLabels[state.provider]} and choose a model first.`); showModels(); return; }
  if (state.mode === 'agent' && project() && !selectedModel().capabilities?.includes('tools')) { toast('This model needs Chat mode, or choose a model marked Tools.'); showModels(); return; }
  if (attachments.length && !selectedModel().capabilities?.includes('vision')) { toast('The attached images need a model marked Images.'); showModels(); return; }
  streamText = ''; setBusy(true);
  try { await invoke('chat', prompt, attachments.map(image => image.id)); $('prompt').value = ''; renderMentions(); attachments = []; sizePrompt(); renderAttachments(); $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight; }
  catch { setBusy(false); }
};
$('prompt').oninput = () => { sizePrompt(); mentionIndex = 0; renderMentions(); };
$('prompt').addEventListener('keydown', event => { if (!mentionCandidates.length) return; if (['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); mentionIndex = (mentionIndex + (event.key === 'ArrowDown' ? 1 : mentionCandidates.length - 1)) % mentionCandidates.length; renderMentions(); } else if (['Enter', 'Tab'].includes(event.key)) { event.preventDefault(); event.stopImmediatePropagation(); insertMention(mentionCandidates[mentionIndex].id); } else if (event.key === 'Escape') { $('tool-mentions').classList.add('hidden'); mentionCandidates = []; } }, true);
$('prompt').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('composer').requestSubmit(); } };
$('stop').onclick = () => api.stop();
document.querySelectorAll('[data-prompt]').forEach(button => button.onclick = () => { $('prompt').value = button.dataset.prompt; sizePrompt(); $('prompt').focus(); if (button.dataset.project && !project()) toast('Open a project folder to explore its files.'); });
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key === ',') { event.preventDefault(); if (!$('settings-dialog').open) showSettings(); }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'l') { event.preventDefault(); if (!busy) showModels(); }
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 't') { event.preventDefault(); actions.toolkit(); }
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'f') { event.preventDefault(); showFiles(); }
  if (event.key === 'Escape' && !document.querySelector('dialog[open]')) { ['memory', 'toolkit'].forEach(name => { if (!$(`${name}-drawer`).classList.contains('hidden')) toggleDrawer(name); }); }
});
function showApproval(data) {
  approvalId = data.id;
  const custom = {
    browser_inspect: { title: 'Inspect this website?', description: 'Loads scripts and page resources in a fresh browser session. Returns rendered content to this conversation.', content: data.url },
    command_start: { title: 'Start command session?', description: `Runs on your Mac in ${data.root}. Timeout: ${data.timeout_seconds} seconds. This host shell can access files outside the project.`, content: data.command },
    command_write: { title: 'Send command input?', description: `Sends stdin to session ${data.session_id}.`, content: data.command },
    web_search: { title: 'Search the web?', description: 'This query will be sent to DuckDuckGo.', content: `${data.query || ''}\n\n${data.url || ''}` },
    http_request: { title: 'Review network request', description: 'This request sends the shown URL and body from your Mac. Stored provider credentials are not attached.', content: `${data.method || ''} ${data.url || ''}\n\n${data.body || '(no request body)'}` },
    save_memory: { title: 'Save project memory?', description: 'This memory will be included in future project conversations.', content: data.content },
    external_tool: { title: `Use ${data.tool}?`, description: `Runs through ${data.server}. This server may access your files or the network.`, content: JSON.stringify(data.arguments, null, 2) },
  }[data.name];
  if (custom) {
    $('approval-title').textContent = custom.title; $('approval-description').textContent = custom.description;
    $('approval-content').innerHTML = `<pre>${escapeHTML(custom.content)}</pre>`;
  } else {
  $('approval-title').textContent = data.name === 'write_file' ? `Review edit · ${data.path}` : 'Run this command?';
  $('approval-description').textContent = data.name === 'write_file' ? 'Check the current file and proposed replacement before saving.' : `Runs on your Mac in ${data.root}. This host shell can access files outside the project.`;
  $('approval-content').innerHTML = data.name === 'write_file' ? `<h3>BEFORE</h3><pre>${escapeHTML(data.before ?? '(new file)')}</pre><h3>AFTER</h3><pre>${escapeHTML(data.after)}</pre>` : `<pre>${escapeHTML(data.command)}</pre>`;
  }
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close()); $('approval-dialog').showModal(); $('decline').focus();
}
async function respondApproval(allowed) { const id = approvalId; approvalId = null; $('approval-dialog').close(); if (id) await api.approval({ id, allowed }); }
$('approve').onclick = () => respondApproval(true); $('decline').onclick = () => respondApproval(false);
$('approval-dialog').addEventListener('cancel', event => { event.preventDefault(); respondApproval(false); });
api.onEvent(async event => {
  if (event.type === 'runtime' && state) { state.localRuntime = event.value; renderRuntime(); renderDownload(); if (event.value.status === 'error' && state.provider === 'ollama') { connected = false; $('connection-label').textContent = 'Wixal Local offline'; $('connection-dot').classList.add('offline'); } }
  if (event.type === 'run-started') { streamText = ''; setBusy(true); }
  if (event.type === 'benchmark') { state.benchmarkProgress = event.value; renderBenchmarkProgress(); }
  if (event.type === 'benchmark-done') { toast(`Benchmark saved for ${event.name}.`); await refresh(); }
  if (event.type === 'benchmark-idle') { state.benchmarkProgress = null; await refresh(); }
  if (event.type === 'usage') { state = await api.state(); renderPerformance(); }
  if (event.type === 'tasks') await refresh();
  if (event.type === 'connections') { connections = await api.connections(); renderConnections(); if (event.message) toast(event.message); if (event.firstPlanUse) { document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close()); $('plan-notice-dialog').showModal(); } if (state.provider !== 'ollama') await loadModels(); }
  if (event.type === 'state') { streamText = ''; await refresh(); }
  if (event.type === 'token') { streamText += event.text; if (!streamFrame) streamFrame = requestAnimationFrame(() => { streamFrame = null; renderMessages(); }); }
  if (event.type === 'phase') $('activity-label').textContent = event.value;
  if (event.type === 'extensions-changed') await refresh();
  if (event.type === 'model-downloads' && state) {
    const key = event.items.map(item => `${item.id}:${item.state}`).join('|'), changed = key !== downloadStateKey;
    state.modelDownloads = event.items; state.modelDownload = event.items.find(item => item.id === event.active) || null;
    if (changed) renderModelList(); else renderDownload();
  }
  if (event.type === 'model-download-done') { toast(`Downloaded ${event.name}. Choose it in the model picker.`); if (state.provider === 'ollama') { await loadModels(); await loadLibraryInfo(); } }

  if (event.type === 'context') $('context-note').textContent = event.omitted > 0 ? event.summarized ? `${event.summarized} older messages summarized` : `${event.omitted} older messages outside context` : '';
  if (event.type === 'error') { toast(event.message); if (state.provider === 'chatgpt' && /usage limit/i.test(event.message)) { document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close()); $('usage-limit-dialog').showModal(); } }
  if (event.type === 'done') { streamText = ''; setBusy(false); if ($('approval-dialog').open) $('approval-dialog').close(); await refresh(); $('prompt').focus(); }
  if (event.type === 'approval') showApproval(event);
  if (event.type === 'terminal') terminal?.write(event.text);
  if (event.type === 'terminal-exit') terminal?.write(`\r\n[Shell exited: ${event.exitCode}. Hide and reopen to restart.]\r\n`);
  if (event.type === 'shortcut') actions[event.action]?.();
});
(async () => { connections = await api.connections(); await refresh(); await loadModels(); $('prompt').focus(); })().catch(error => toast(error.message));
