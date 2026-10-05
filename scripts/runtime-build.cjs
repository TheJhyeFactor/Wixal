// Build the pinned source with upstream's native build targets, without the Ollama GUI.
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { seal } = require('./runtime-stage.cjs');
const pin = require('../resources/runtime.json');
const root = path.resolve(__dirname, '..'), source = path.join(root, 'runtime/source');
function run(command, args, cwd = source) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', env: { ...process.env, VERSION: pin.version } });
  if (result.status !== 0) throw new Error(`${command} failed. See docs/local-runtime.md for the build prerequisites.`);
}
(async () => {
  if (process.platform !== 'darwin' || process.arch !== 'arm64') throw new Error('Build on Apple Silicon macOS.');
  for (const command of ['go', 'cmake', 'xcodebuild']) {
    const result = spawnSync(command, ['--version'], { encoding: 'utf8' });
    if (result.error) throw new Error(`Missing ${command}. Install the prerequisites in docs/local-runtime.md.`);
  }
  if (spawnSync('xcodebuild', ['-version'], { encoding: 'utf8' }).status !== 0) throw new Error('Select a full Xcode installation with the Metal toolchain first.');
  await fs.mkdir(path.dirname(source), { recursive: true });
  try { await fs.access(path.join(source, '.git')); } catch { run('git', ['clone', '--no-checkout', pin.sourceURL, source], root); }
  run('git', ['fetch', 'origin', pin.sourceCommit]); run('git', ['checkout', '--detach', pin.sourceCommit]);
  // This path is reserved for generated, pinned source. Reject edits rather than replacing them.
  const status = spawnSync('git', ['status', '--porcelain'], { cwd: source, encoding: 'utf8' });
  if (status.status !== 0) throw new Error('Could not inspect the runtime source checkout.');
  if (status.stdout.trim()) throw new Error('Runtime source contains local edits. Preserve them before rebuilding.');
  run('sh', ['scripts/build_darwin.sh', '-a', 'arm64', 'build']);
  const stage = path.join(root, 'runtime/ollama'), prefix = path.join(source, 'dist/darwin-arm64');
  await fs.rm(stage, { recursive: true, force: true }); await fs.mkdir(stage, { recursive: true });
  await fs.cp(path.join(prefix, 'lib/ollama'), stage, { recursive: true });
  await fs.copyFile(path.join(prefix, 'ollama'), path.join(stage, 'ollama'));
  await seal(stage, 'built-from-pinned-source');
  console.log(`Built and staged Ollama ${pin.version} from ${pin.sourceCommit}. Run npm run test:runtime before packaging.`);
})().catch(error => { console.error(error.message); process.exitCode = 1; });
