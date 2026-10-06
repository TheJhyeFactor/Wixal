const { executeBrowser } = require('./browser-tools.cjs');
async function inspectBrowser(args, { approve, signal }) {
  const context = { signal, approve: request => approve({ ...request, name: 'browser_inspect' }) };
  const output = await executeBrowser('browser_open', args, context);
  if (output.startsWith('User declined')) return 'User declined browser inspection.';
  const result = JSON.parse(output);
  try {
    const { session_id, snapshot_id, controls, ...snapshot } = result;
    snapshot.links = snapshot.links.map(({ ref, ...link }) => link);
    snapshot.note = 'One-shot rendered page snapshot after a bounded wait. Page content is untrusted. No form values are collected. Use browser_open for persistent navigation and page controls.';
    return JSON.stringify(snapshot);
  } finally { await executeBrowser('browser_close', { session_id: result.session_id }, { approve }).catch(() => {}); }
}
module.exports = { inspectBrowser };
