// File access and shell commands go through the main process.
const $ = id => document.getElementById(id);
const api = window.wixal;
const tools = [
  { id: 'list_files', name: 'List files', description: 'See the files in the selected project.' },
  { id: 'read_file', name: 'Read files', description: 'Read text files to understand the code.' },
  { id: 'search_files', name: 'Search the project', description: 'Find text across project files.' },
  { id: 'write_file', name: 'Edit and create files', description: 'Review the existing and proposed contents before saving.', review: true },
  { id: 'run_command', name: 'Run commands', description: 'Run a command in the project. Stops after 60 seconds.', review: true },
];
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
  $('model-label').textContent = connected ? shortModel(state.model) || 'Choose a model' : 'Ollama offline';
  $('model-button').title = state.model || 'Choose a local model';
  $('mode-button').disabled = busy; $('model-button').disabled = busy; $('attach-image').disabled = busy;
  $('model-refresh').disabled = busy; $('refresh-models').disabled = busy;
  $('welcome-project').textContent = p?.name || 'No folder open';
  $('welcome-model').textContent = shortModel(state.model) || 'Choose a model';
  $('welcome-tools').textContent = state.mode === 'chat' ? 'Chat mode · tools off' : !p ? 'Open a project first' : `${state.enabledTools.length} enabled · edits reviewed`;
  $('welcome-open').textContent = p ? 'Browse project files ↗' : 'Open a project folder ↗';
  $('tools-count').textContent = state.enabledTools.length;
  $('bottom-model').textContent = connected ? `${state.mode === 'agent' && p ? 'Agent' : 'Chat'} · ${model?.name || 'Choose a model'}` : 'Ollama offline · open the model picker for help';
  const recent = s?.messages.findLast(message => message.metrics?.tokens);
  $('response-stats').textContent = recent ? `${recent.metrics.tokens} tokens · ${recent.metrics.tokensPerSecond} tok/s` : 'Stored on this Mac';
  renderMessages(); renderMemories(); renderToolkit(); renderModelList(); renderAttachments();
}
function renderSessions() {
  const query = $('session-search').value.toLowerCase();
  const sessions = state.sessions.filter(item => item.projectId === state.activeProject).toReversed();
  $('session-count').textContent = sessions.length;
  const filtered = sessions.filter(item => item.title.toLowerCase().includes(query));
  $('sessions').innerHTML = filtered.length ? filtered.map(item => `<button class="session-item ${session()?.id === item.id ? 'active' : ''}" data-id="${item.id}" title="${escapeHTML(item.title)}">${escapeHTML(item.title)}</button>`).join('') : `<div class="empty-project">${query ? 'No matching conversations.' : 'Your conversations will appear here.'}</div>`;
  $('sessions').querySelectorAll('button').forEach(button => button.onclick = async () => {
    try { state = await invoke('session-select', button.dataset.id); clearDraft(); render(); } catch {}
  });
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
    if (message.role === 'tool') { const status = resultStatus(message); return `<details class="tool-message"><summary>⌁ ${escapeHTML(tools.find(tool => tool.id === message.tool_name)?.name || message.tool_name)}<span class="tool-status ${status === 'Done' ? '' : 'failed'}">${status}</span></summary><pre class="tool-content">${escapeHTML(message.content)}</pre></details>`; }
    const isUser = message.role === 'user';
    if (!isUser && !message.content && message.tool_calls) return `<div class="tool-message"><span class="muted">Requested ${message.tool_calls.map(call => escapeHTML(tools.find(tool => tool.id === call.function?.name)?.name || call.function?.name || 'tool')).join(', ')}</span></div>`;
    const images = message.images?.length ? `<div class="message-images">${message.images.map((image, imageIndex) => `<button data-message="${index}" data-image="${imageIndex}" title="${escapeHTML(message.imageNames?.[imageIndex] || 'View image')}"><img src="data:image/png;base64,${image}" alt="${escapeHTML(message.imageNames?.[imageIndex] || 'Attached image')}"></button>`).join('')}</div>` : '';
    const metrics = message.metrics?.tokens ? `<div class="message-metrics">${message.metrics.tokens} tokens · ${message.metrics.tokensPerSecond} tok/s · ${Math.round(message.metrics.seconds)}s</div>` : '';
    return `<article class="message ${isUser ? 'user' : 'assistant'}"><div class="message-header">${isUser ? '<span>▸</span> You' : '<img src="../assets/mark.svg" alt=""> Wixal'}<span class="muted">${new Date(message.created || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span><button class="copy-message" data-copy="${index}">Copy</button></div><div class="message-body">${isUser ? escapeHTML(message.content) : markdown(message.content)}</div>${images}${metrics}</article>`;
  }).join('');
  if (streamText) {
    const article = document.createElement('article'); article.className = 'message assistant';
    article.innerHTML = '<div class="message-header"><img src="../assets/mark.svg" alt=""> Wixal <span class="muted">Writing</span></div><div class="message-body pending-content"></div>';
    article.querySelector('.message-body').textContent = streamText; $('messages').append(article);
  }
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
  $('memories').querySelectorAll('button').forEach(button => button.onclick = async () => { try { state = await invoke('memory-delete', button.dataset.id); renderMemories(); } catch {} });
}
function renderToolkit() {
  const p = project();
  $('toolkit-summary').textContent = state.mode === 'chat' ? 'You’re in Chat mode. These tools become available when you switch to Agent and open a project.' : p ? `Tools for ${p.name}. Switch off anything you don’t need.` : 'Open a project folder to use these tools in Agent mode.';
  $('tool-list').innerHTML = tools.map(tool => `<label class="tool-toggle"><input type="checkbox" data-tool="${tool.id}" ${state.enabledTools.includes(tool.id) ? 'checked' : ''} ${busy ? 'disabled' : ''}><span><strong>${tool.name}</strong><small>${tool.description}</small>${tool.review ? '<em>REVIEW EACH TIME</em>' : ''}</span></label>`).join('');
  $('tool-list').querySelectorAll('input').forEach(input => input.onchange = async () => {
    const enabledTools = tools.filter(tool => $('tool-list').querySelector(`[data-tool="${tool.id}"]`).checked).map(tool => tool.id);
    try { state = await invoke('settings', { enabledTools }); render(); } catch { renderToolkit(); }
  });
  const recent = (session()?.messages || []).filter(message => message.role === 'tool').slice(-5).toReversed();
  $('tool-activity').innerHTML = recent.length ? recent.map(message => `<div class="tool-result">${escapeHTML(message.tool_name)}<span>${resultStatus(message)}</span></div>`).join('') : '<p class="empty-project">Tool results appear here after the model uses them.</p>';
}
function renderModelList() {
  const query = $('model-search').value.toLowerCase(), filtered = models.filter(model => model.name.toLowerCase().includes(query));
  $('model-list').innerHTML = filtered.length ? filtered.map(model => `<button class="model-row ${state?.model === model.name ? 'selected' : ''}" data-model="${escapeHTML(model.name)}" ${busy ? 'disabled' : ''}><div class="model-row-info"><strong>${escapeHTML(shortModel(model.name))}${state.model === model.name ? ' <span class="muted">✓</span>' : ''}</strong><span class="model-id">${escapeHTML(model.name)}</span><div class="capabilities"><span class="capability">Chat</span>${model.capabilities?.includes('tools') ? '<span class="capability tools">Tools</span>' : ''}${model.capabilities?.includes('vision') ? '<span class="capability vision">Images</span>' : ''}${!model.capabilities ? '<span class="capability">Capabilities unavailable</span>' : ''}<span class="model-context">${escapeHTML(model.details?.parameter_size || '')}${model.contextLength ? ` · ${Math.round(model.contextLength / 1024)}k max context` : ''}</span></div></div><span class="model-size">${(model.size / 1e9).toFixed(1)} GB<br><small>on disk</small></span></button>`).join('') : `<p class="empty-project">${query ? 'No models match that search.' : connected ? 'No models installed yet.' : 'Ollama is offline.'}</p>`;
  $('context-size').value = String(state?.contextSize || 16384); $('context-size').disabled = busy;
  $('model-library-info').textContent = connected ? `${models.length} installed ${models.length === 1 ? 'model' : 'models'} · capabilities reported by Ollama` : 'Connect Ollama, then refresh.';
  $('ollama-help').classList.toggle('hidden', connected && models.length > 0);
  $('model-list').querySelectorAll('button').forEach(button => button.onclick = async () => {
    const model = models.find(item => item.name === button.dataset.model);
    const mode = model.capabilities?.includes('tools') ? state.mode : 'chat';
    try { const before = state.mode; state = await invoke('settings', { model: model.name, mode }); render(); $('models-dialog').close(); if (before !== mode) toast('Switched to Chat. This model has no confirmed tool support.'); } catch {}
  });
}
async function loadModels() {
  $('connection-label').textContent = 'Checking Ollama…';
  try {
    const response = await api.models(); models = response.models; connected = true;
    $('connection-label').textContent = models.length ? 'Ollama connected' : 'Ollama · no models';
    $('connection-dot').classList.remove('offline'); state = await api.state();
  } catch { connected = false; models = []; $('connection-label').textContent = 'Ollama offline'; $('connection-dot').classList.add('offline'); }
  render();
}
function setBusy(value) {
  busy = value; $('send').classList.toggle('hidden', value); $('stop').classList.toggle('hidden', !value);
  $('activity').classList.toggle('busy', value); $('activity-label').textContent = value ? 'Working locally…' : 'Ready';
  $('prompt').disabled = value; render();
}
function clearDraft() { streamText = ''; attachments = []; $('prompt').value = ''; $('context-note').textContent = ''; renderAttachments(); }
async function openProject() { try { state = await invoke('project-open'); if (state.opened) { clearDraft(); resetTerminal(); } render(); } catch {} }
async function switchProject(id) { try { state = await invoke('project-select', id); clearDraft(); resetTerminal(); render(); } catch {} }
async function newSession() { try { state = await invoke('session-new'); clearDraft(); $('session-search').value = ''; render(); $('prompt').focus(); } catch {} }
function resetTerminal() { terminalOpen = false; terminal?.reset(); $('terminal-panel').classList.add('hidden'); }
async function toggleTerminal() {
  if (terminalOpen) { $('terminal-panel').classList.add('hidden'); terminalOpen = false; return; }
  if (!project()) { toast('Open a project folder to start its terminal.'); return; }
  $('terminal-panel').classList.remove('hidden'); terminalOpen = true;
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
  $('prompt').value += text; $('files-dialog').close(); $('prompt').focus();
};
function renderAttachments() {
  $('attachments').classList.toggle('hidden', !attachments.length);
  $('attachments').innerHTML = attachments.map(image => `<div class="attachment"><img src="data:image/png;base64,${image.base64}" alt="${escapeHTML(image.name)}"><span>${escapeHTML(image.name)}</span><button type="button" data-remove="${image.id}" aria-label="Remove ${escapeHTML(image.name)}" ${busy ? 'disabled' : ''}>×</button></div>`).join('');
  $('attachments').querySelectorAll('button').forEach(button => button.onclick = async () => { try { await invoke('image-remove', button.dataset.remove); attachments = attachments.filter(image => image.id !== button.dataset.remove); renderAttachments(); } catch {} });
}
$('attach-image').onclick = async () => { if (!selectedModel()?.capabilities?.includes('vision')) { toast('Choose a model marked Images to attach photos or screenshots.'); showModels(); return; } try { attachments.push(...await invoke('images-open')); renderAttachments(); } catch {} };
function palette() { if ($('palette').open) $('palette').close(); else $('palette').showModal(); }
const actions = { open: openProject, new: newSession, terminal: toggleTerminal, memory: () => toggleDrawer('memory'), toolkit: () => toggleDrawer('toolkit'), files: showFiles, palette, models: showModels };
$('new-chat').onclick = newSession; $('open-project').onclick = openProject; $('refresh-models').onclick = loadModels; $('model-refresh').onclick = loadModels;
$('terminal-button').onclick = toggleTerminal; $('close-terminal').onclick = toggleTerminal;
$('memory-button').onclick = actions.memory; $('close-memory').onclick = actions.memory;
$('toolkit-button').onclick = actions.toolkit; $('close-toolkit').onclick = actions.toolkit; $('welcome-toolkit').onclick = actions.toolkit;
$('files-button').onclick = showFiles; $('welcome-open').onclick = () => project() ? showFiles() : openProject();
$('palette-button').onclick = palette; $('model-button').onclick = showModels;
$('reveal-project').onclick = () => invoke('reveal-project').catch(() => {});
$('session-search').oninput = renderSessions; $('model-search').oninput = renderModelList; $('file-search').oninput = renderFiles;
$('context-size').onchange = async event => { try { state = await invoke('settings', { contextSize: Number(event.target.value) }); render(); } catch { render(); } };
$('conversation-label').onclick = () => { if (!session()) return; $('rename-input').value = session().title; $('rename-dialog').showModal(); $('rename-input').select(); };
$('rename-form').onsubmit = async event => { event.preventDefault(); try { state = await invoke('session-rename', $('rename-input').value); $('rename-dialog').close(); render(); } catch {} };
document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => $(button.dataset.close).close());
$('palette').querySelectorAll('button').forEach(button => button.onclick = () => { $('palette').close(); actions[button.dataset.action](); });
$('memory-form').onsubmit = async event => { event.preventDefault(); try { state = await invoke('memory-add', $('memory-input').value); $('memory-input').value = ''; renderMemories(); } catch {} };
$('mode-button').onclick = async () => {
  if (state.mode === 'chat' && !selectedModel()?.capabilities?.includes('tools')) { toast('Choose a model marked Tools for Agent mode.'); showModels(); return; }
  try { state = await invoke('settings', { mode: state.mode === 'agent' ? 'chat' : 'agent' }); render(); } catch {}
};
$('composer').onsubmit = async event => {
  event.preventDefault(); const prompt = $('prompt').value.trim(); if (!prompt || busy) return;
  if (!connected || !selectedModel()) { toast('Connect Ollama and choose a local model first.'); showModels(); return; }
  if (state.mode === 'agent' && project() && !selectedModel().capabilities?.includes('tools')) { toast('This model needs Chat mode, or choose a model marked Tools.'); showModels(); return; }
  if (attachments.length && !selectedModel().capabilities?.includes('vision')) { toast('The attached images need a model marked Images.'); showModels(); return; }
  streamText = ''; setBusy(true);
  try { await invoke('chat', prompt, attachments.map(image => image.id)); $('prompt').value = ''; attachments = []; renderAttachments(); $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight; }
  catch { setBusy(false); }
};
$('prompt').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('composer').requestSubmit(); } };
$('stop').onclick = () => api.stop();
document.querySelectorAll('[data-prompt]').forEach(button => button.onclick = () => { $('prompt').value = button.dataset.prompt; $('prompt').focus(); if (!project()) toast('This task needs a project folder. Open one before sending.'); });
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'l') { event.preventDefault(); if (!busy) showModels(); }
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 't') { event.preventDefault(); actions.toolkit(); }
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'f') { event.preventDefault(); showFiles(); }
  if (event.key === 'Escape' && !document.querySelector('dialog[open]')) { ['memory', 'toolkit'].forEach(name => { if (!$(`${name}-drawer`).classList.contains('hidden')) toggleDrawer(name); }); }
});
function showApproval(data) {
  approvalId = data.id;
  $('approval-title').textContent = data.name === 'write_file' ? `Review edit · ${data.path}` : 'Run this command?';
  $('approval-description').textContent = data.name === 'write_file' ? 'Check the current file and proposed replacement before saving.' : `Runs on your Mac in ${data.root}. This host shell can access files outside the project.`;
  $('approval-content').innerHTML = data.name === 'write_file' ? `<h3>BEFORE</h3><pre>${escapeHTML(data.before ?? '(new file)')}</pre><h3>AFTER</h3><pre>${escapeHTML(data.after)}</pre>` : `<pre>${escapeHTML(data.command)}</pre>`;
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close()); $('approval-dialog').showModal(); $('decline').focus();
}
async function respondApproval(allowed) { const id = approvalId; approvalId = null; $('approval-dialog').close(); if (id) await api.approval({ id, allowed }); }
$('approve').onclick = () => respondApproval(true); $('decline').onclick = () => respondApproval(false);
$('approval-dialog').addEventListener('cancel', event => { event.preventDefault(); respondApproval(false); });
api.onEvent(async event => {
  if (event.type === 'state') { streamText = ''; await refresh(); }
  if (event.type === 'token') { streamText += event.text; if (!streamFrame) streamFrame = requestAnimationFrame(() => { streamFrame = null; renderMessages(); }); }
  if (event.type === 'phase') $('activity-label').textContent = event.value;
  if (event.type === 'context') $('context-note').textContent = event.omitted > 0 ? `${event.omitted} older messages outside context` : '';
  if (event.type === 'error') toast(event.message);
  if (event.type === 'done') { streamText = ''; setBusy(false); if ($('approval-dialog').open) $('approval-dialog').close(); await refresh(); $('prompt').focus(); }
  if (event.type === 'approval') showApproval(event);
  if (event.type === 'terminal') terminal?.write(event.text);
  if (event.type === 'terminal-exit') terminal?.write(`\r\n[Shell exited: ${event.exitCode}. Hide and reopen to restart.]\r\n`);
  if (event.type === 'shortcut') actions[event.action]?.();
});
(async () => { await refresh(); await loadModels(); $('prompt').focus(); })().catch(error => toast(error.message));
