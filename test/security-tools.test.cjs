const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const https = require('node:https');
const { execFileSync } = require('node:child_process');
const { Store } = require('../app/store.cjs');
const { executeTool } = require('../app/tools.cjs');
const { profiles, scanPlan, securityInventory } = require('../app/security-tools.cjs');
const { createApprover } = require('../app/approvals.cjs');
async function setup(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-security-lab-')); t.after(() => fs.rm(root, { recursive: true, force: true }));
  const store = new Store(path.join(root, 'state')); store.addProject(root); store.setApprovalMode('all');
  const context = { root: await fs.realpath(root), store, allowedTools: ['network_scan', 'network_read', 'network_stop', 'command_save_output'], approve: createApprover(store, async () => assert.fail('Approved all should not open a review dialog')) };
  return context;
}
test('scan profiles validate targets/ports and keep scanner arguments separate from shell code', () => {
  for (const profile of Object.keys(profiles)) { const plan = scanPlan({ target: 'https://example.test:8443/path', profile }); assert.equal(plan.target, 'example.test'); assert.ok(plan.argv.includes('example.test')); assert.ok(!plan.argv.includes('vuln')); }
  assert.equal(scanPlan({ target: '192.168.1.0/24', profile: 'discovery' }).ports, null);
  assert.equal(scanPlan({ target: 'https://[::1]:8443', profile: 'tls' }).argv[0], '-6');
  for (const target of ['-oN evil', '127.0.0.1; touch bad', '$(id)', '127.0.0.1 192.168.1.1', '999.999.999.999', 'example..test', '8.8.8.0/24', '10.0.0.0/8', 'https://user:secret@example.test']) assert.throws(() => scanPlan({ target }));
  for (const ports of ['0', '65536', '500-400', '80;id', '--script vuln']) assert.throws(() => scanPlan({ target: '127.0.0.1', ports }));
  assert.throws(() => scanPlan({ target: '127.0.0.1', profile: '__proto__' }), /supported/);
});
test('approval mode persists by workspace, respects revocation and never crosses into another project', async t => {
  const context = await setup(t); let reviews = 0;
  const approve = createApprover(context.store, async () => (++reviews, false));
  assert.equal(await approve({ name: 'network_scan' }), true); assert.equal(reviews, 0);
  const reloaded = new Store(path.dirname(context.store.file)); assert.equal(reloaded.approvalMode(), 'all');
  context.store.setApprovalMode('review'); assert.equal(await approve({ name: 'run_command' }), false); assert.equal(reviews, 1);
  context.store.addProject(path.join(context.root, 'state')); assert.equal(context.store.approvalMode(), 'review');
  context.store.selectProject(null); assert.equal(context.store.approvalMode(), 'review');
  assert.throws(() => context.store.setApprovalMode('invented'), /Choose/);
});
test('real loopback web scan returns XML evidence, saves a report, and disabled scans cannot run', async t => {
  if (!(await securityInventory()).installed) return t.skip('Nmap is required for the real scanner fixture');
  const context = await setup(t);
  const server = http.createServer((_req, res) => { res.setHeader('Server', 'Wixal-Lab'); res.end('<html><title>Wixal local scan fixture</title><body>Local test only</body></html>'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); t.after(() => new Promise(resolve => server.close(resolve)));
  await assert.rejects(executeTool('network_scan', { target: '127.0.0.1' }, { ...context, allowedTools: [] }), /switched off/);
  const started = JSON.parse(await executeTool('network_scan', { target: `http://127.0.0.1:${server.address().port}`, profile: 'web', timeout_seconds: 60 }, context));
  let result; const deadline = Date.now() + 65000;
  do { result = JSON.parse(await executeTool('network_read', { session_id: started.session_id, wait_ms: 1000 }, context)); } while (result.state === 'running' && Date.now() < deadline);
  assert.equal(result.state, 'completed'); assert.equal(result.exitCode, 0); assert.match(result.output, /state="open"/); assert.match(result.output, /Wixal local scan fixture/);
  await executeTool('command_save_output', { session_id: started.session_id, path: 'scan-evidence.json' }, context);
  const report = JSON.parse(await fs.readFile(path.join(context.root, 'scan-evidence.json'), 'utf8'));
  assert.match(report.output, /Wixal local scan fixture/);
  assert.equal(report.assessment.profile, 'web'); assert.equal(report.assessment.target, '127.0.0.1');
  assert.match(report.command, /nmap/); assert.ok(report.started && report.finished);
  assert.equal(context.store.data.actionApprovals.filter(a => a.tool === 'network_scan').length, 1);
});
test('real loopback TLS scan extracts certificate evidence from a disposable HTTPS service', async t => {
  if (!(await securityInventory()).installed) return t.skip('Nmap is required for the real TLS fixture');
  const context = await setup(t), cert = path.join(context.root, 'fixture-cert.pem'), key = path.join(context.root, 'fixture-key.pem');
  execFileSync('/usr/bin/openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-keyout', key, '-out', cert, '-subj', '/CN=wixal-lab.local'], { stdio: 'ignore' });
  const server = https.createServer({ key: await fs.readFile(key), cert: await fs.readFile(cert) }, (_req, res) => res.end('<title>Wixal TLS fixture</title>'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); t.after(() => new Promise(resolve => server.close(resolve)));
  const started = JSON.parse(await executeTool('network_scan', { target: `https://127.0.0.1:${server.address().port}`, profile: 'tls', timeout_seconds: 90 }, context));
  let result; const deadline = Date.now() + 95000;
  do { result = JSON.parse(await executeTool('network_read', { session_id: started.session_id, wait_ms: 1000 }, context)); } while (result.state === 'running' && Date.now() < deadline);
  assert.equal(result.state, 'completed'); assert.equal(result.exitCode, 0); assert.match(result.output, /wixal-lab.local/); assert.match(result.output, /ssl-cert/); assert.doesNotMatch(result.output, /BEGIN PRIVATE KEY/);
});
test('a started network scan can be cancelled and cannot be read from another workspace', async t => {
  if (!(await securityInventory()).installed) return t.skip('Nmap is required for cancellation fixture');
  const context = await setup(t);
  const started = JSON.parse(await executeTool('network_scan', { target: '127.0.0.0/24', profile: 'ports', timeout_seconds: 20 }, context));
  await assert.rejects(executeTool('network_read', { session_id: started.session_id }, { ...context, root: path.dirname(context.root) }), /unavailable/);
  await executeTool('network_stop', { session_id: started.session_id }, context);
  const result = JSON.parse(await executeTool('network_read', { session_id: started.session_id, wait_ms: 100 }, context));
  assert.equal(result.state, 'stopped'); assert.equal(result.reason, 'cancelled');
});
