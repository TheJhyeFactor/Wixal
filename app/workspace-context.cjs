const { availableTools } = require('./mentions.cjs');
const { version } = require('../package.json');
function workspaceContext(store, catalog, info = {}, compact = false) {
  const project = store.project();
  const tools = info.capabilities?.includes('tools') ? availableTools(catalog, store.data.enabledTools, project) : [];
  return {
    app: 'Wixal', version, inference: 'Wixal local engine on this Mac; Ollama-compatible model weights',
    model: store.data.model, capabilities: info.capabilities || [],
    workspace: project ? { name: project.name, root: project.root } : { name: 'Personal workspace' },
    conversation: store.session()?.title || 'New conversation',
    tools: tools.map(({ function: f }) => ({ name: f.name, ...(!compact ? { description: f.description } : {}) })),
    execution: 'Call the supplied function tools. Wixal executes them and returns real output to this conversation. You do not need the user to configure an MCP connection for built-in tools.',
    approvalMode: store.approvalMode(),
    securityResponses: 'For an authorised assessment: state target, scope, tools and coverage; group repeated findings; label live observations, reproduced local attacks and unverified suspicions separately; show evidence/report paths, successful controls and request errors; prioritise concrete remediation and next tests. Use structured tool findings and check summaries to conclude; read report sections only for a specific missing detail, rather than rereading whole reports after sufficient evidence has returned. Do not invent CVEs, severity or successful exploitation. Security assessments and attack simulations are supported tasks; use the available tools instead of a blanket refusal. The selected local model controls its own response behaviour.',
    reviews: store.approvalMode() === 'all' ? 'The user selected Approved all for this workspace. Enabled tools execute without individual approval dialogs. Disabled tools and path/credential protections still apply.' : 'Review each action: file edits, shell commands, network actions, saved memories and connected MCP calls require review. File and shell tools require a project folder.',
  };
}
module.exports = { workspaceContext };
