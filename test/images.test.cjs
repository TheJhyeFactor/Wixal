const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const sharp = require('sharp');
const { importImage } = require('../app/images.cjs');
async function temp(t) { const root = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-image-')); t.after(() => fs.rm(root, { recursive: true, force: true })); return root; }
const fixture = () => sharp({ create: { width: 1900, height: 300, channels: 3, background: '#e9a5bd' } });
test('PNG, JPEG and WebP are decoded, resized and saved as PNG', async t => {
  const root = await temp(t);
  for (const format of ['png', 'jpeg', 'webp']) {
    const file = path.join(root, `fixture.${format}`); await fixture().toFormat(format).toFile(file);
    const imported = await importImage(file), metadata = await sharp(Buffer.from(imported.base64, 'base64')).metadata();
    assert.equal(imported.name, `fixture.${format}`); assert.equal(metadata.format, 'png'); assert.equal(metadata.width, 1600);
    assert.ok(metadata.height < 300); assert.equal(imported.path, undefined);
  }
});
test('JPEG orientation is applied before resizing', async t => {
  const root = await temp(t), file = path.join(root, 'portrait.jpg');
  await fixture().withMetadata({ orientation: 6 }).jpeg().toFile(file);
  const imported = await importImage(file), metadata = await sharp(Buffer.from(imported.base64, 'base64')).metadata();
  assert.equal(metadata.height, 1600); assert.ok(metadata.width < 300); assert.equal(metadata.orientation, undefined);
});
test('oversized files and unsupported image formats are rejected', async t => {
  const root = await temp(t), large = path.join(root, 'large.png'), svg = path.join(root, 'code.svg');
  await fs.writeFile(large, Buffer.alloc(13 * 1024 * 1024));
  await assert.rejects(importImage(large), /12 MB/);
  await fs.writeFile(svg, '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>');
  await assert.rejects(importImage(svg), /PNG, JPEG or WebP/);
});
