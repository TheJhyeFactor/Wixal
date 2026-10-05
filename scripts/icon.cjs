const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');
const { execFileSync } = require('node:child_process');
const assets = path.join(__dirname, '../assets');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#3a2847"/><stop offset="1" stop-color="#17111f"/></linearGradient><linearGradient id="fox" x2=".8" y2="1"><stop stop-color="#f8c6da"/><stop offset="1" stop-color="#d08ec7"/></linearGradient></defs><rect x="24" y="24" width="976" height="976" rx="220" fill="url(#bg)"/><rect x="44" y="44" width="936" height="936" rx="200" stroke="#6c4878" stroke-width="4" fill="none"/><circle cx="642" cy="353" r="195" fill="#a77ccf" opacity=".35"/><path fill="url(#fox)" d="M215 230 439 375 585 375 809 230 745 633 512 824 279 633Z"/><path fill="#36213f" d="m280 335 120 112-90 39Zm464 0-120 112 90 39ZM305 547l143 43-61 42Zm414 0-143 43 61 42ZM466 694h92l-46 49Z"/><path stroke="#36213f" stroke-width="23" fill="none" d="m512 461-38 77 38 53 38-53Z"/><path fill="#f5b4d0" d="m167 660 13-28 13 28-13 28Zm667-208 13-28 13 28-13 28Z"/></svg>`;
(async () => {
  await fs.mkdir(path.join(assets, 'Wixal.iconset'), { recursive: true });
  await sharp(Buffer.from(svg)).png().toFile(path.join(assets, 'icon.png'));
  for (const size of [16, 32, 128, 256, 512]) for (const scale of [1, 2]) {
    await sharp(Buffer.from(svg)).resize(size * scale, size * scale).png().toFile(path.join(assets, `Wixal.iconset/icon_${size}x${size}${scale === 2 ? '@2x' : ''}.png`));
  }
  execFileSync('/usr/bin/iconutil', ['-c', 'icns', path.join(assets, 'Wixal.iconset'), '-o', path.join(assets, 'Wixal.icns')]);
  await fs.rm(path.join(assets, 'Wixal.iconset'), { recursive: true });
  console.log('Created Wixal macOS icon.');
})();
