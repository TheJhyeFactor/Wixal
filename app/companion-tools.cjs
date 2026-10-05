const { z } = require('zod');
const projectId = z.string().min(1).max(100);
const toolSpecs = [
  { name: 'list_projects', description: 'List only the local projects explicitly shared with ChatGPT in Wixal.', schema: {} },
  { name: 'get_project_context', description: 'Get a shared project name and file list. Saved memory is included only if separately enabled.', schema: { projectId } },
  { name: 'read_project_file', description: 'Read a text file in a shared Wixal project. Credential paths and external symlinks are blocked.', schema: { projectId, path: z.string().min(1).max(1000) } },
  { name: 'search_project', description: 'Search for literal text in a shared project.', schema: { projectId, query: z.string().min(1).max(300) } },
  { name: 'create_task', description: 'Queue a task in Wixal for local user review and start. This does not execute commands or change files. Return the task ID and wait for the user to start it.', schema: { projectId, title: z.string().min(1).max(120), prompt: z.string().min(1).max(16000) }, writes: true },
  { name: 'get_task_status', description: 'Get task state, completed response and actual tool outcomes. A queued task has not executed.', schema: { taskId: z.string().min(1).max(100) } },
];
function registerTools(server, call) {
  for (const spec of toolSpecs) server.registerTool(spec.name, { description: spec.description, inputSchema: spec.schema,
    annotations: { readOnlyHint: !spec.writes, destructiveHint: false, idempotentHint: !spec.writes, openWorldHint: false } }, async args => {
    try { const result = await call(spec.name, args); return { content: [{ type: 'text', text: JSON.stringify(result) }] }; }
    catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
  });
}
module.exports = { toolSpecs, registerTools };
