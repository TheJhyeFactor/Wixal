// Keep inference schemas focused while the human's enabled-tool list stays authoritative.
const CATEGORIES = ['files', 'commands', 'web', 'security', 'memory', 'external'];
function category(name) {
 if (name.startsWith('mcp_')) return 'external';
 if (['website_assess','website_simulate','security_tools','network_scan','network_read','network_stop'].includes(name)) return 'security';
 if (name.startsWith('command_') || name === 'run_command') return 'commands';
 if (name.startsWith('browser_') || ['web_search','http_request'].includes(name)) return 'web';
 if (['workspace_info','search_history','save_memory'].includes(name)) return 'memory';
 return 'files';
}
function loadCategory(available, value, requested = []) {
 if (!CATEGORIES.includes(value)) throw new Error('Choose files, commands, web, security, memory or external.');
 const names = new Set(['workspace_info', 'read_file', 'write_file', ...requested]);
 const matching = available.filter(tool => category(tool.function.name) === value);
 for (const tool of value === 'external' ? matching.slice(0, 8) : matching) names.add(tool.function.name);
 if (value === 'security') ['command_read','command_stop','command_save_output'].forEach(name => names.add(name));
 if (value === 'commands') names.add('command_save_output');
 return available.filter(tool => names.has(tool.function.name));
}
function initialTools(available, prompt, requested, messages = []) {
 if (available.length <= 10) return available;
 const explicit = requested.find(name => name !== 'workspace_info');
 if (explicit && category(explicit) === 'external') return available.filter(tool => ['workspace_info',...requested].includes(tool.function.name));
 if (explicit) return loadCategory(available, category(explicit), requested);
 const text = prompt.toLowerCase();
 const checks = [ ['security', /\b(?:nmap|scan|vulnerab|security|attack|assess|network|ports|tls|ssh)\w*\b/], ['commands', /\b(?:command|terminal|shell|execute|stdout|stderr|stdin|run|build|test)\b/], ['web', /https?:\/\/|\b[a-z0-9-]+\.(?:dev|com|org|net|io|app)(?:[\/:?]|\b)|\b(?:browser|browse|website|web|search the|online|internet|page|url|source|links?)\b/], ['files', /\b(?:file|files|folder|directory|project|code|readme|edit|find text|write|read)\b|\.[a-z]{1,5}\b/], ['memory', /\b(?:remember|memory|recall|earlier chat)\b/] ];
 const match = checks.find(([, regex]) => regex.test(text));
 if (match) return loadCategory(available, match[0], requested);
 const recent = [...messages].reverse().find(m => m.role === 'tool' && m.tool_name !== 'workspace_info');
 if (recent && /^(?:continue|yes|next|go on|do it|now|and)\b/i.test(text)) return loadCategory(available, category(recent.tool_name), requested);
 const defaults = new Set(['workspace_info','security_tools','list_files','read_file','write_file','web_search','http_request','browser_inspect','search_history','save_memory']);
 return available.filter(tool => defaults.has(tool.function.name));
}
function loadNamed(available, name, requested = []) {
 if (!available.some(tool => tool.function.name === name)) throw new Error('That tool is not enabled or available in this workspace.');
 return available.filter(tool => ['workspace_info',name,...requested].includes(tool.function.name));
}
module.exports = { CATEGORIES, category, loadCategory, loadNamed, initialTools };
