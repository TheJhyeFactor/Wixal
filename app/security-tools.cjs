const fs = require('node:fs/promises');
const { constants } = require('node:fs');
const net = require('node:net');
const profiles = {
  discovery: { label: 'Host discovery', description: 'Find responding hosts on a local subnet or individual target.', args: ['-sn', '-PS22,80,443'], ports: null, intensity: 'Discovery' },
  ports: { label: 'TCP ports', description: 'TCP connect scan with reasons for port states.', args: ['-sT', '-Pn'], ports: '22,53,80,443,445,3389,8080,8443', intensity: 'Active port scan' },
  services: { label: 'Service versions', description: 'Identify services on open TCP ports using light version probes.', args: ['-sT', '-Pn', '-sV', '--version-light'], ports: '22,53,80,443,445,3389,8080,8443', intensity: 'Active service probes' },
  web: { label: 'Web configuration', description: 'Page titles, response headers and security-header observations.', args: ['-sT', '-Pn', '-sV', '--version-light', '--script', 'http-title,http-headers,http-security-headers'], ports: '80,443,8080,8443', intensity: 'Web requests' },
  tls: { label: 'TLS configuration', description: 'Certificate details and supported protocols/ciphers. Makes repeated TLS connections.', args: ['-sT', '-Pn', '-sV', '--version-light', '--script', 'ssl-cert,ssl-enum-ciphers'], ports: '443,8443', intensity: 'Intrusive TLS enumeration' },
  ssh: { label: 'SSH configuration', description: 'Host keys and supported SSH algorithms.', args: ['-sT', '-Pn', '-sV', '--version-light', '--script', 'ssh-hostkey,ssh2-enum-algos'], ports: '22', intensity: 'SSH handshakes' },
  enumeration: { label: 'Web path enumeration', description: 'Check known web paths with Nmap HTTP fingerprints for an authorised assessment.', args: ['-sT', '-Pn', '-sV', '--version-light', '--script', 'http-enum'], ports: '80,443,8080,8443', intensity: 'Intrusive path enumeration' },
  checks: { label: 'Selected vulnerability checks', description: 'TLS POODLE, cookie flags and security-header checks. Treat findings as unverified evidence.', args: ['-sT', '-Pn', '-sV', '--version-light', '--script', 'ssl-poodle,http-cookie-flags,http-security-headers'], ports: '80,443,8080,8443', intensity: 'Active vulnerability checks' },
};
async function scannerPath() {
  for (const file of ['/opt/homebrew/bin/nmap', '/usr/local/bin/nmap', '/usr/bin/nmap']) {
    try { await fs.access(file, constants.X_OK); return file; } catch {}
  }
  return null;
}
async function securityInventory() {
  return { scanner: 'Nmap', executable: await scannerPath(), installed: !!(await scannerPath()), profiles: Object.entries(profiles).map(([id, p]) => ({ id, label: p.label, description: p.description, intensity: p.intensity, ports: p.ports })), website: { tool: 'website_assess', simulation: 'website_simulate', profiles: ['baseline', 'probes'], note: 'Built-in same-origin GET checks; no scanner installation needed.' }, workflow: ['website_assess', 'network_scan', 'network_read', 'network_stop', 'command_save_output'], note: 'Use targets authorised by the user. Port states and script observations are evidence, not proof of exploitation or compromise.' };
}
function scanPlan(args) {
  if (!args || typeof args.target !== 'string' || !args.target.trim()) throw new Error('Supply an authorised IP, hostname, website URL or local subnet.');
  let target = args.target.trim(), urlPort;
  if (/^https?:\/\//i.test(target)) {
    const url = new URL(target); if (url.username || url.password) throw new Error('Do not include credentials in a scan URL.');
    target = url.hostname.replace(/^\[|\]$/g, ''); urlPort = url.port || (url.protocol === 'https:' ? '443' : '80');
  }
  const [host, prefix, extra] = target.split('/');
  if (extra !== undefined || !host || host.length > 253) throw new Error('Use one target per scan.');
  const ip = net.isIP(host);
  if (!ip && (/^[0-9.]+$/.test(host) || !/^(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$/.test(host) || host.split('.').some(label => !label || label.length > 63 || label.startsWith('-') || label.endsWith('-')))) throw new Error('Invalid scan target. Shell syntax, option flags and target lists are not accepted.');
  if (prefix !== undefined) {
    if (ip !== 4 || !/^\d{1,2}$/.test(prefix) || Number(prefix) < 24 || Number(prefix) > 32) throw new Error('Local IPv4 subnet scans support /24 through /32, at most 256 addresses.');
    const [a, b] = host.split('.').map(Number);
    if (!(a === 10 || a === 127 || a === 192 && b === 168 || a === 172 && b >= 16 && b <= 31)) throw new Error('Subnet scanning requires a local/private network. Use individual authorised public targets.');
  }
  const profile = args.profile || 'services';
  if (!Object.hasOwn(profiles, profile)) throw new Error('Choose a supported scan profile.');
  const preset = profiles[profile];
  const seconds = args.timeout_seconds ?? 180;
  if (!Number.isInteger(seconds) || seconds < 10 || seconds > 600) throw new Error('Scan timeout must be 10–600 seconds.');
  const ports = args.ports || urlPort || preset.ports;
  if (ports && (typeof ports !== 'string' || !/^\d{1,5}(?:-\d{1,5})?(?:,\d{1,5}(?:-\d{1,5})?)*$/.test(ports) || ports.length > 500)) throw new Error('Ports must be numbers or ranges, such as 22,80,443 or 8000-8100.');
  if (ports) for (const range of ports.split(',')) { const [start, end = start] = range.split('-').map(Number); if (start < 1 || end > 65535 || end < start) throw new Error('Ports must be in the range 1–65535.'); }
  const argv = [...(ip === 6 ? ['-6'] : []), ...preset.args, '-n', '--reason', '-T3', '--max-retries', '1', '--host-timeout', `${seconds}s`, '--script-timeout', '30s', ...(preset.ports && ports ? ['-p', ports] : []), '-oX', '-', target];
  return { target, profile, label: preset.label, intensity: preset.intensity, ports: preset.ports ? ports : null, seconds, argv };
}
async function executeSecurity(name, args, context) {
  if (name === 'security_tools') return JSON.stringify(await securityInventory());
  const { executeCommandSession } = require('./command-sessions.cjs');
  if (name === 'network_read') return executeCommandSession('command_read', args, context);
  if (name === 'network_stop') return executeCommandSession('command_stop', args, context);
  const plan = scanPlan(args), executable = await scannerPath();
  if (!executable) throw new Error('Nmap is not installed. Install it with Homebrew (brew install nmap), then refresh the security tools.');
  const started = await executeCommandSession('command_start', { command: `${executable} ${plan.argv.join(' ')}`, timeout_seconds: plan.seconds }, { ...context, executable, argv: plan.argv, approvalName: 'network_scan', assessment: { target: plan.target, profile: plan.profile, intensity: plan.intensity, ports: plan.ports } });
  if (started.startsWith('User declined')) return started;
  const result = JSON.parse(started);
  return JSON.stringify({ ...result, target: plan.target, profile: plan.profile, intensity: plan.intensity, ports: plan.ports, read_with: 'network_read', report_with: 'command_save_output', interpretation: 'Nmap output is scan evidence. Verify suspected vulnerabilities before declaring them confirmed.' });
}
module.exports = { profiles, securityInventory, scanPlan, executeSecurity };
