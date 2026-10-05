function requestedTools(prompt, catalog, enabled, project) {
  const names = catalog.map(t => t.function.name);
  const mentions = [...prompt.matchAll(/(?:^|\s)@([a-zA-Z][a-zA-Z0-9_]*)(?=\s|$|[.,!?])/g)].map(m => m[1]);
  const requested = [...new Set(mentions.filter(name => names.includes(name)))];
  // Other @mentions (people, packages) remain ordinary text.
  for (const name of requested) {
    if (!enabled.includes(name)) throw new Error(`@${name} is switched off. Enable it in the tool kit.`);
    if (!project && (name.startsWith('command_') || ['list_files', 'read_file', 'search_files', 'write_file', 'run_command'].includes(name))) throw new Error(`Open a project folder to use @${name}.`);
  }
  return requested;
}
module.exports = { requestedTools };
