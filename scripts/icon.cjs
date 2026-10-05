const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');
const { execFileSync } = require('node:child_process');
const assets = path.join(__dirname, '../assets');
(async () => {
  const svg = await fs.readFile(path.join(assets, 'app-icon.svg'));
  await fs.mkdir(path.join(assets, 'Wixal.iconset'), { recursive: true });
  await sharp(Buffer.from(svg)).png().toFile(path.join(assets, 'icon.png'));
  for (const size of [16, 32, 128, 256, 512]) for (const scale of [1, 2]) {
    await sharp(Buffer.from(svg)).resize(size * scale, size * scale).png().toFile(path.join(assets, `Wixal.iconset/icon_${size}x${size}${scale === 2 ? '@2x' : ''}.png`));
  }
  execFileSync('/usr/bin/iconutil', ['-c', 'icns', path.join(assets, 'Wixal.iconset'), '-o', path.join(assets, 'Wixal.icns')]);
  await fs.rm(path.join(assets, 'Wixal.iconset'), { recursive: true });
  console.log('Created Wixal macOS icon.');
})();
