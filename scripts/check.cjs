const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
for (const directory of ['app', 'ui', 'scripts']) for (const file of fs.readdirSync(path.join(__dirname, '..', directory))) {
  if (!/\.(?:cjs|js)$/.test(file)) continue;
  const result = spawnSync(process.execPath, ['--check', path.join(__dirname, '..', directory, file)], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
