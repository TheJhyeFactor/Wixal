const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { browseFolder, createFolder, directory } = require('../app/project-folders.cjs');
test('folder picker lists directories, resolves paths and creates without overwriting', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-folder-test-'));
  try {
    await fs.mkdir(path.join(temp, 'Existing')); await fs.mkdir(path.join(temp, '.hidden')); await fs.writeFile(path.join(temp, 'file.txt'), 'preserve');
    const list = await browseFolder(temp); assert.deepEqual(list.folders.map(f => f.name), ['Existing']);
    assert.deepEqual((await browseFolder(temp, true)).folders.map(f => f.name), ['.hidden', 'Existing']);
    const created = await createFolder(temp, 'New project'); assert.ok((await fs.stat(created)).isDirectory());
    await assert.rejects(createFolder(temp, 'Existing'), /already exists/);
    await assert.rejects(createFolder(temp, 'file.txt'), /already exists/); assert.equal(await fs.readFile(path.join(temp, 'file.txt'), 'utf8'), 'preserve');
    for (const name of ['../escape', '.', '..', '/absolute', 'bad/name', 'bad\\name', '.hidden', 'bad\0name', '']) await assert.rejects(createFolder(temp, name));
    await assert.rejects(directory('relative/path'), /absolute/); await assert.rejects(directory(path.join(temp, 'file.txt')), /rather than a file/);
    await assert.rejects(directory(path.join(temp, 'missing')));
  } finally { await fs.rm(temp, { recursive: true, force: true }); }
});
