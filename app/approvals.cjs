// Approval mode is set by the human through the app, never by model arguments.
function createApprover(store, review, emit = () => {}) {
  return async request => {
    if (store.approvalMode() !== 'all') {
      const allowed = await review(request);
      if (!allowed || store.approvalMode() !== 'all') return allowed;
    }
    const entry = { tool: request.name, projectId: store.data.activeProject, sessionId: store.data.activeSession, created: Date.now(), mode: 'all' };
    store.data.actionApprovals ??= []; store.data.actionApprovals.push(entry); store.data.actionApprovals = store.data.actionApprovals.slice(-200);
    store.save(); emit({ type: 'auto-approved', ...entry }); return true;
  };
}
module.exports = { createApprover };
