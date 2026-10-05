// File access and shell commands go through the main process.
const $ = id => document.getElementById(id);
const api = window.wixal;
const tools = [
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
let connections, modelRequest = 0, keyProvider = 'openai';
const providerLabels = { ollama: 'Ollama', openai: 'OpenAI API', chatgpt: 'ChatGPT' };
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
  const p = project(), s = session(), model = selectedModel();
  applySidebarLayout();
  $('title-project').textContent = p?.name || 'workspace';
  $('project-label').textContent = p?.name || 'Personal workspace';
  $('conversation-label').textContent = s?.title || 'New conversation';
  $('conversation-label').disabled = !s || busy;
  $('reveal-project').disabled = !p;
  $('projects').innerHTML = state.projects.length ? state.projects.map(item => `<button class="project-item ${item.id === state.activeProject ? 'active' : ''}" data-id="${item.id}" title="${escapeHTML(item.root)}"><span class="folder">▱</span><span>${escapeHTML(item.name)}</span></button>`).join('') : '<div class="empty-project">No folder open yet.<br><button id="empty-open">Open a project ↗</button></div>';
  $('projects').querySelectorAll('[data-id]').forEach(button => button.onclick = () => switchProject(button.dataset.id));
  if ($('empty-open')) $('empty-open').onclick = openProject;
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
  $('response-stats').textContent = recent ? `${recent.metrics.tokens} tokens · ${recent.metrics.tokensPerSecond} tok/s` : 'Stored on this Mac';
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
  renderMessages(); renderMemories(); renderToolkit(); renderModelList(); renderAttachments(); renderTasks();
}
function renderSessions() {
  const query = $('session-search').value.toLowerCase();
  const sessions = state.sessions.filter(item => item.projectId === state.activeProject && !item.archivedAt).toReversed();
  $('session-count').textContent = sessions.length;
  $('archive-count').textContent = state.sessions.filter(item => item.projectId === state.activeProject && item.archivedAt).length;
  const filtered = sessions.filter(item => item.title.toLowerCase().includes(query));
  $('sessions').innerHTML = filtered.length ? filtered.map(item => `<div class="session-row ${session()?.id === item.id ? 'active' : ''}"><button class="session-item ${session()?.id === item.id ? 'active' : ''}" data-id="${item.id}" title="${escapeHTML(item.title)}" ${busy ? 'disabled' : ''}>${escapeHTML(item.title)}</button><button class="session-more" data-menu-id="${item.id}" aria-label="Options for ${escapeHTML(item.title)}" aria-haspopup="menu" ${busy ? 'disabled' : ''}>···</button></div>`).join('') : `<div class="empty-project">${query ? 'No matching conversations.' : 'Your conversations will appear here.'}</div>`;
  $('sessions').querySelectorAll('.session-item').forEach(button => button.onclick = () => selectConversation(button.dataset.id));
  $('sessions').querySelectorAll('.session-more').forEach(button => button.onclick = () => {
    menuSessionId = button.dataset.menuId;
    const menu = $('session-menu'); menu.showPopover();
    const rect = button.getBoundingClientRect();
    menu.style.left = `${Math.min(rect.right + 8, window.innerWidth - 220)}px`;
    menu.style.top = `${Math.max(8, Math.min(rect.top, window.innerHeight - menu.offsetHeight - 12))}px`;
    menu.querySelector('button').focus();
  });
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
    if (message.role === 'tool') { const status = resultStatus(message); return `<details class="tool-message"><summary>⌁ ${escapeHTML(availableTools().find(tool => tool.id === message.tool_name)?.name || message.tool_name)}<span class="tool-status ${status === 'Done' ? '' : 'failed'}">${status}</span></summary><pre class="tool-content">${escapeHTML(message.content)}</pre></details>`; }
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
  $('memories').innerHTML = memories.length ? memories.map(memory => `<div class="memory-entry"><p>${escapeHTML(memory.content)}</p><footer>${new Date(memory.created).toLocaleDateString()}<button data-id="${memory.id}" title="Delete memory" ${busy ? 'disabled' : ''}>Forget</button></footer></div>`).join('') : '<p class="empty-project">Nothing saved yet. Add a preference or project decision below.</p>';
  $('memory-form').querySelector('button').disabled = busy;
  $('auto-summary').checked = state.autoSummary !== false; $('auto-summary').disabled = busy;
  const summary = session()?.summary;
  $('saved-summary').classList.toggle('hidden', !summary);
  $('summary-content').textContent = summary?.content || '';
  $('summary-meta').textContent = summary ? `${summary.count} older messages · ${summary.method === 'excerpts' ? 'Fallback excerpts' : 'Model summary'} · ${new Date(summary.updated).toLocaleString()}. Full history remains saved.` : '';
  $('summary-clear').disabled = busy;
  $('memories').querySelectorAll('button').forEach(button => button.onclick = async () => { try { state = await invoke('memory-delete', button.dataset.id); renderMemories(); } catch {} });
}
function renderToolkit() {
  const p = project();
  $('toolkit-summary').textContent = state.mode === 'chat' ? 'You’re in Chat mode. These tools become available when you switch to Agent and open a project.' : p ? `Tools for ${p.name}. Switch off anything you don’t need.` : 'Open a project folder to use these tools in Agent mode.';
  const catalog = availableTools();
  $('tool-list').innerHTML = catalog.map(tool => `<label class="tool-toggle"><input type="checkbox" data-tool="${escapeHTML(tool.id)}" ${state.enabledTools.includes(tool.id) ? 'checked' : ''} ${busy ? 'disabled' : ''}><span><strong>${escapeHTML(tool.name)}</strong><small>${escapeHTML(tool.description)}</small>${tool.review ? '<em>REVIEW EACH TIME</em>' : ''}</span></label>`).join('');
  $('tool-list').querySelectorAll('input').forEach(input => input.onchange = async () => {
    const enabledTools = catalog.filter(tool => $('tool-list').querySelector(`[data-tool="${tool.id}"]`).checked).map(tool => tool.id);
    enabledTools.push(...state.enabledTools.filter(name => !catalog.some(tool => tool.id === name)));
    try { state = await invoke('settings', { enabledTools }); render(); } catch { renderToolkit(); }
  });
  const recent = (session()?.messages || []).filter(message => message.role === 'tool').slice(-5).toReversed();
  $('tool-activity').innerHTML = recent.length ? recent.map(message => `<div class="tool-result">${escapeHTML(message.tool_name)}<span>${resultStatus(message)}</span></div>`).join('') : '<p class="empty-project">Tool results appear here after the model uses them.</p>';
  $('manage-extensions').disabled = busy;
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
function renderModelList() {
  const query = $('model-search').value.toLowerCase(), local = state?.provider === 'ollama';
  const filtered = models.filter(model => `${model.name} ${model.displayName || ''}`.toLowerCase().includes(query));
  if (connections?.providers) { for (const item of connections.providers) providerLabels[item.id] = item.label; $('provider-select').innerHTML = connections.providers.map(item => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.label)}${item.id === 'ollama' ? ' · local' : item.id === 'chatgpt' ? ' · connected account' : ''}</option>`).join(''); }
  $('provider-select').value = state?.provider || 'ollama'; $('provider-select').disabled = busy;
  $('model-provider-heading').textContent = local ? 'OLLAMA · ON THIS MAC' : `${providerLabels[state?.provider]} · CLOUD`;
  $('model-list').innerHTML = filtered.length ? filtered.map(model => `<button class="model-row ${state?.model === model.name ? 'selected' : ''}" data-model="${escapeHTML(model.name)}" ${busy ? 'disabled' : ''}><div class="model-row-info"><strong>${escapeHTML(model.displayName || shortModel(model.name))}${state.model === model.name ? ' <span class="muted">✓</span>' : ''}</strong><span class="model-id">${escapeHTML(model.name)}</span><div class="capabilities"><span class="capability">Chat</span>${model.capabilities?.includes('tools') ? '<span class="capability tools">Tools</span>' : ''}${model.capabilities?.includes('vision') ? '<span class="capability vision">Images</span>' : ''}${!model.capabilities ? '<span class="capability">Capabilities unavailable</span>' : ''}<span class="model-context">${escapeHTML(model.details?.parameter_size || '')}${model.contextLength ? ` · ${Math.round(model.contextLength / 1024)}k max context` : ''}</span></div></div><span class="model-size">${local ? `${(model.size / 1e9).toFixed(1)} GB<br><small>on disk</small>` : '<small>Cloud</small>'}</span></button>`).join('') : `<p class="empty-project">${query ? 'No models match that search.' : local ? connected ? 'No models installed yet.' : 'Ollama is offline.' : 'Connect this provider in Connections, then refresh the model list.'}</p>`;
  $('context-size').value = String(state?.contextSize || 16384); $('context-size').disabled = busy;
  $('model-pull-form').classList.toggle('hidden', !local);
  renderDownload();
  $('model-library-info').textContent = local ? connected ? `${models.length} installed models · capabilities reported by Ollama` : 'Connect Ollama, then refresh.' : `${models.length} account models · tool and image support varies by model`;
  $('ollama-help').classList.toggle('hidden', !local || (connected && models.length > 0));
  $('model-list').querySelectorAll('button').forEach(button => button.onclick = async () => {
    const model = models.find(item => item.name === button.dataset.model), mode = model.capabilities?.includes('tools') ? state.mode : 'chat';
    try { const before = state.mode; state = await invoke('settings', { model: model.name, mode }); render(); $('models-dialog').close(); if (before !== mode) toast('Switched to Chat. This model has no confirmed tool support.'); } catch {}
  });
}
function renderDownload(progress = state?.modelDownload) {
  $('model-pull-button').disabled = busy || !!progress; $('model-pull-name').disabled = busy || !!progress;
  $('model-pull-cancel').classList.toggle('hidden', !progress);
  $('model-pull-status').textContent = progress ? `${progress.name} · ${progress.status}${progress.total ? ` · ${Math.min(100, Math.round(progress.completed / progress.total * 100))}% of current layer` : ''}` : '';
}
async function loadModels() {
  const request = ++modelRequest, provider = state.provider;
  $('connection-label').textContent = `Checking ${providerLabels[provider]}…`;
  $('connection-detail').textContent = provider === 'ollama' ? 'On this Mac · 127.0.0.1' : 'Cloud · context shared when enabled';
  try {
    const response = await api.models(); if (request !== modelRequest) return;
    models = response.models; connected = true;
    $('connection-label').textContent = models.length ? `${providerLabels[provider]} connected` : `${providerLabels[provider]} · no models`;
    $('connection-dot').classList.remove('offline'); state = await api.state();
  } catch (error) {
    if (request !== modelRequest) return;
    connected = false; models = []; $('connection-label').textContent = provider === 'ollama' ? 'Ollama offline' : `${providerLabels[provider]} not connected`;
    $('connection-dot').classList.add('offline'); if (provider !== 'ollama') toast(error.message);
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
  try { state = await invoke('settings', { provider: event.target.value }); models = []; connected = false; render(); await loadModels(); } catch { renderModelList(); }
};
function clearDraft() { streamText = ''; attachments = []; $('prompt').value = ''; sizePrompt(); $('context-note').textContent = ''; renderAttachments(); }
async function openProject() { try { state = await invoke('project-open'); if (state.opened) { clearDraft(); resetTerminal(); } render(); } catch {} }
async function switchProject(id) { try { state = await invoke('project-select', id); clearDraft(); resetTerminal(); render(); } catch {} }
async function newSession() { try { state = await invoke('session-new'); clearDraft(); $('session-search').value = ''; render(); $('prompt').focus(); } catch {} }
function resetTerminal() { terminalOpen = false; terminal?.reset(); $('terminal-panel').classList.add('hidden'); }
async function toggleTerminal() {
  if (terminalOpen) { $('terminal-panel').classList.add('hidden'); terminalOpen = false; renderStartLayout(); return; }
  if (!project()) { toast('Open a project folder to start its terminal.'); return; }
  $('terminal-panel').classList.remove('hidden'); terminalOpen = true; renderStartLayout();
  if (!terminal) {
    terminal = new Terminal({ fontFamily: 'Menlo, monospace', fontSize: 11, cursorBlink: true, scrollback: 3000,
      theme: { background: '#111215', foreground: '#ddd4df', cursor: '#e9a5bd', selectionBackground: '#513c51', black: '#1b1920', red: '#df96a5', green: '#a4c5ac', yellow: '#dbc394', blue: '#a4b0df', magenta: '#ce9cde', cyan: '#93c9cb', white: '#e7dceb', brightBlack: '#877d8b' },
    });
    fitAddon = new FitAddon.FitAddon(); terminal.loadAddon(fitAddon); terminal.open($('terminal'));
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
function showModels() { $('model-search').value = ''; renderModelList(); if (!$('models-dialog').open) $('models-dialog').showModal(); $('model-search').focus(); }
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
  $('sidebar').classList.toggle('collapsed', collapsed);
  $('sidebar-toggle').setAttribute('aria-expanded', String(!collapsed));
  $('sidebar-toggle').setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
  $('sidebar-toggle').title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  $('show-sidebar').classList.add('hidden');
}
async function toggleSidebar(collapsed = !state.ui.sidebarCollapsed) {
  if (!!state.ui.sidebarCollapsed === !!collapsed) return;
  try { state = await invoke('layout', !!collapsed); applySidebarLayout(); }
  catch { applySidebarLayout(); }
}
function toggleWorkspaceMenu() {
  const menu = $('workspace-menu');
  if (menu.matches(':popover-open')) { menu.hidePopover(); return; }
  menu.showPopover();
  const button = $('workspace-menu-toggle').getBoundingClientRect();
  const rect = menu.getBoundingClientRect();
  menu.style.left = `${Math.max(12, Math.min(button.left, innerWidth - rect.width - 12))}px`;
  menu.style.top = `${Math.max(12, button.top - rect.height - 8)}px`;
}
function palette() { if ($('palette').open) $('palette').close(); else $('palette').showModal(); }
const actions = { sidebar: toggleSidebar, archives: showArchives, open: openProject, new: newSession, terminal: toggleTerminal, connections: showConnections, tasks: showTasks, memory: () => toggleDrawer('memory'), toolkit: () => toggleDrawer('toolkit'), files: showFiles, palette, models: showModels };
$('sidebar-toggle').onclick = () => toggleSidebar(); $('show-sidebar').onclick = () => toggleSidebar(false);
$('workspace-menu-toggle').onclick = toggleWorkspaceMenu;
$('workspace-menu').addEventListener('toggle', event => $('workspace-menu-toggle').setAttribute('aria-expanded', String(event.newState === 'open')));
$('workspace-menu').addEventListener('click', event => { if (event.target.closest('button')) $('workspace-menu').hidePopover(); });
$('new-chat').onclick = newSession; $('open-project').onclick = openProject; $('refresh-models').onclick = loadModels; $('model-refresh').onclick = loadModels;
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
$('model-pull-form').onsubmit = async event => { event.preventDefault(); try { state = await invoke('model-pull', $('model-pull-name').value.trim()); renderDownload(); } catch {} };
$('model-pull-cancel').onclick = async () => { await api['model-pull-cancel'](); };
$('context-size').onchange = async event => { try { state = await invoke('settings', { contextSize: Number(event.target.value) }); render(); } catch { render(); } };
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
$('memory-form').onsubmit = async event => { event.preventDefault(); try { state = await invoke('memory-add', $('memory-input').value); $('memory-input').value = ''; renderMemories(); } catch {} };
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
  try { await invoke('chat', prompt, attachments.map(image => image.id)); $('prompt').value = ''; attachments = []; sizePrompt(); renderAttachments(); $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight; }
  catch { setBusy(false); }
};
$('prompt').oninput = sizePrompt;
$('prompt').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('composer').requestSubmit(); } };
$('stop').onclick = () => api.stop();
document.querySelectorAll('[data-prompt]').forEach(button => button.onclick = () => { $('prompt').value = button.dataset.prompt; sizePrompt(); $('prompt').focus(); if (button.dataset.project && !project()) toast('Open a project folder to explore its files.'); });
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'l') { event.preventDefault(); if (!busy) showModels(); }
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 't') { event.preventDefault(); actions.toolkit(); }
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'f') { event.preventDefault(); showFiles(); }
  if (event.key === 'Escape' && !document.querySelector('dialog[open]')) { ['memory', 'toolkit'].forEach(name => { if (!$(`${name}-drawer`).classList.contains('hidden')) toggleDrawer(name); }); }
});
function showApproval(data) {
  approvalId = data.id;
  const custom = {
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
  if (event.type === 'run-started') { streamText = ''; setBusy(true); }
  if (event.type === 'tasks') await refresh();
  if (event.type === 'connections') { connections = await api.connections(); renderConnections(); if (event.message) toast(event.message); if (event.firstPlanUse) { document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close()); $('plan-notice-dialog').showModal(); } if (state.provider !== 'ollama') await loadModels(); }
  if (event.type === 'state') { streamText = ''; await refresh(); }
  if (event.type === 'token') { streamText += event.text; if (!streamFrame) streamFrame = requestAnimationFrame(() => { streamFrame = null; renderMessages(); }); }
  if (event.type === 'phase') $('activity-label').textContent = event.value;
  if (event.type === 'extensions-changed') await refresh();
  if (event.type === 'model-download') { state.modelDownload = event; renderDownload(event); }
  if (event.type === 'model-download-done') { toast(`Downloaded ${event.name}. Choose it in the model picker.`); if (state.provider === 'ollama') await loadModels(); }
  if (event.type === 'model-download-idle') { state.modelDownload = null; renderDownload(null); }
  if (event.type === 'context') $('context-note').textContent = event.omitted > 0 ? event.summarized ? `${event.summarized} older messages summarized` : `${event.omitted} older messages outside context` : '';
  if (event.type === 'error') { toast(event.message); if (state.provider === 'chatgpt' && /usage limit/i.test(event.message)) { document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close()); $('usage-limit-dialog').showModal(); } }
  if (event.type === 'done') { streamText = ''; setBusy(false); if ($('approval-dialog').open) $('approval-dialog').close(); await refresh(); $('prompt').focus(); }
  if (event.type === 'approval') showApproval(event);
  if (event.type === 'terminal') terminal?.write(event.text);
  if (event.type === 'terminal-exit') terminal?.write(`\r\n[Shell exited: ${event.exitCode}. Hide and reopen to restart.]\r\n`);
  if (event.type === 'shortcut') actions[event.action]?.();
});
(async () => { connections = await api.connections(); await refresh(); await loadModels(); $('prompt').focus(); })().catch(error => toast(error.message));
