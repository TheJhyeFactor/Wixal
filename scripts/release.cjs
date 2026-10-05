// Build distributable Mac files from a clean, committed checkout.
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { createReadStream } = require('node:fs');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`${command} failed: ${result.stderr || result.stdout || result.error}`);
  return result.stdout.trim();
}
async function hash(file) {
  const digest = crypto.createHash('sha256');
  for await (const chunk of createReadStream(file)) digest.update(chunk);
  return digest.digest('hex');
}
(async () => {
  if (process.platform !== 'darwin' || process.arch !== 'arm64') throw new Error('Build this release on an Apple Silicon Mac.');
  if (run('git', ['status', '--porcelain']).length) throw new Error('Commit source changes before building a release.');
  const { version } = JSON.parse(await fs.readFile(path.join(root, 'package.json'), 'utf8'));
  const app = path.join(root, 'release/Wixal-darwin-arm64/Wixal.app');
  const plist = path.join(app, 'Contents/Info.plist');
  const appVersion = run('/usr/libexec/PlistBuddy', ['-c', 'Print :CFBundleShortVersionString', plist]);
  if (appVersion !== version) throw new Error(`App version ${appVersion} does not match source ${version}. Run npm run package first.`);
  // Ad hoc signing seals the bundle; it is not Developer ID signing or notarisation.
  run('codesign', ['--force', '--deep', '--sign', '-', app]);
  run('codesign', ['--verify', '--deep', '--strict', app]);
  const output = path.join(root, 'release', `v${version}`);
  await fs.mkdir(output, { recursive: true });
  const stem = `Wixal-${version}-macOS-arm64`;
  const zip = path.join(output, `${stem}.zip`), dmg = path.join(output, `${stem}.dmg`);
  run('ditto', ['-c', '-k', '--sequesterRsrc', '--keepParent', app, zip]);
  run('unzip', ['-tq', zip]);
  const stage = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-release-'));
  try {
    run('ditto', [app, path.join(stage, 'Wixal.app')]);
    await fs.symlink('/Applications', path.join(stage, 'Applications'));
    await fs.writeFile(path.join(stage, 'Read me.txt'), `Wixal ${version}\n\nDrag Wixal.app to Applications, then open Wixal.\n\nRequires an Apple Silicon Mac with macOS 13 or newer, Ollama running locally, and an installed model. You do not need Node.js to use this download.\n\nThis early preview is not Developer ID signed or notarised. macOS may block the first launch. See the release page for Apple's instructions for opening an app from an unidentified developer.\n\nYour conversations and project memories are stored locally. File edits and model-requested commands require review. The terminal runs with your Mac user's access.\n\nRelease: https://github.com/TheJhyeFactor/Wixal/releases/tag/v${version}\n`);
    run('hdiutil', ['create', '-volname', `Wixal ${version}`, '-srcfolder', stage, '-format', 'UDZO', '-ov', dmg]);
    run('hdiutil', ['verify', dmg]);
  } finally {
    await fs.rm(stage, { recursive: true, force: true });
  }
  const files = [];
  for (const file of [dmg, zip]) files.push({ name: path.basename(file), bytes: (await fs.stat(file)).size, sha256: await hash(file) });
  await fs.writeFile(path.join(output, 'SHA256SUMS.txt'), files.map(file => `${file.sha256}  ${file.name}\n`).join(''));
  await fs.writeFile(path.join(output, 'release-info.json'), JSON.stringify({ version, sourceCommit: run('git', ['rev-parse', 'HEAD']), platform: 'darwin', arch: 'arm64', minimumMacOS: run('/usr/libexec/PlistBuddy', ['-c', 'Print :LSMinimumSystemVersion', plist]), developerIDSigned: false, notarised: false, files }, null, 2) + '\n');
  console.log(`Verified release files written to ${output}`);
})().catch(error => { console.error(error); process.exitCode = 1; });
