const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');

async function importImage(file) {
  if ((await fs.stat(file)).size > 12 * 1024 * 1024) throw new Error('Images must be smaller than 12 MB.');
  const image = sharp(file, { limitInputPixels: 40000000 });
  const metadata = await image.metadata();
  if (!['png', 'jpeg', 'webp'].includes(metadata.format)) throw new Error('Choose a PNG, JPEG or WebP image.');
  const buffer = await image.rotate().resize({ width: 1600, height: 1600, fit: 'inside', withoutEnlargement: true }).png().toBuffer();
  const base64 = buffer.toString('base64');
  if (base64.length > 6 * 1024 * 1024) throw new Error('This image is too large after resizing. Try a smaller image.');
  return { name: path.basename(file), base64 };
}
module.exports = { importImage };
