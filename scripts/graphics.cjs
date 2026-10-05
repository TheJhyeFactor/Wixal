// Editable vector assets; illustration source is preserved in assets/artwork.
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const ink = '#191a20', cream = '#f1eee9', pink = '#e9a5bd', muted = '#b3afb9';
const lettermark = '<path d="m17 27 12 45 17-33 17 33 12-45" fill="none" stroke="#eee9e5" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="M68 81h17" stroke="#e9a5bd" stroke-width="6" stroke-linecap="round"/>';
const text = (x, y, value, size = 16, fill = cream, extra = '') => `<text x="${x}" y="${y}" font-family="Helvetica,Arial,sans-serif" font-size="${size}" fill="${fill}" ${extra}>${value}</text>`;
const mono = (x, y, value, size = 12, fill = muted, extra = '') => `<text x="${x}" y="${y}" font-family="Menlo,monospace" font-size="${size}" fill="${fill}" ${extra}>${value}</text>`;
const svg = (w, h, body, title) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="title"><title id="title">${title}</title>${body}</svg>\n`;
const icons = {
  folder: '<path d="M3 7V5a1 1 0 0 1 1-1h6l2 3h8a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M3 9h18"/>',
  tools: '<path d="m5 19 9-9M14 10a5 5 0 0 0 6-6l-3 3-3-3 3-3a5 5 0 0 0-6 6L2 16a2 2 0 0 0 3 3Z"/>',
  memory: '<path d="m12 2 9 10-9 10L3 12Z"/><path d="m12 7 4 5-4 5-4-5Z"/>',
  terminal: '<rect x="2" y="3" width="20" height="18" rx="3"/><path d="m6 8 4 4-4 4m7 0h5"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  build: '<path d="M12 4v16M4 12h16"/>',
  model: '<path d="m12 2 9 5v10l-9 5-9-5V7Z"/><path d="m3 7 9 5 9-5M12 12v10"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="2"/><path d="m3 17 5-5 4 4 4-7 5 8"/>',
  review: '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6Z"/><path d="m7 12 3 3 7-7"/>'
};
async function save(name, data) { await fs.mkdir(path.dirname(path.join(root, name)), { recursive: true }); await fs.writeFile(path.join(root, name), data); }
async function render(name, data) { await save(`${name}.svg`, data); await sharp(Buffer.from(data)).png().toFile(path.join(root, `${name}.png`)); }
(async () => {
  await save('assets/mark.svg', svg(100, 100, lettermark, 'Wixal lettermark'));
  for (const [name, body] of Object.entries(icons)) await save(`assets/icons/${name}.svg`, svg(24, 24, `<g fill="none" stroke="#d3b4cc" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${body}</g>`, `${name} icon`));
  const artwork = path.join(root, 'assets/artwork/night-shrine.png');
  await sharp(artwork).resize(960).webp({ quality: 88 }).toFile(path.join(root, 'assets/artwork/night-shrine.webp'));
  const embedded = (await sharp(artwork).resize(780).png().toBuffer()).toString('base64');
  const backdrop = `<rect width="1280" height="500" rx="16" fill="${ink}"/><defs><linearGradient id="fade"><stop stop-color="${ink}"/><stop offset="1" stop-color="${ink}" stop-opacity="0"/></linearGradient><clipPath id="frame"><rect width="1280" height="500" rx="16"/></clipPath></defs><g clip-path="url(#frame)"><image x="540" y="-10" width="780" height="520" href="data:image/png;base64,${embedded}"/><rect x="540" width="180" height="500" fill="url(#fade)"/></g>`;
  await render('assets/repo-banner', svg(1280, 500, `${backdrop}${mono(62, 72, 'WIXAL', 13, pink, 'letter-spacing="3"')}${text(59, 161, 'Local AI,', 58, cream, 'font-weight="600" letter-spacing="-2"')}${text(59, 226, 'at home on your Mac.', 52, cream, 'font-weight="600" letter-spacing="-2"')}${text(62, 291, 'Ollama, your project files, and a terminal.', 19, muted)}${text(62, 321, 'Together in one workspace.', 19, muted)}<path d="M62 376h56" stroke="${pink}" stroke-width="2"/>${mono(62, 413, 'macOS · Apple Silicon · Early preview', 12)}`, 'Wixal: local AI, at home on your Mac. Ollama, project files, and a terminal together in one workspace.'));
  await render('assets/social-card', svg(1280, 640, `<rect width="1280" height="640" fill="${ink}"/><image x="555" y="60" width="780" height="520" href="data:image/png;base64,${embedded}"/><defs><linearGradient id="fade"><stop stop-color="${ink}"/><stop offset="1" stop-color="${ink}" stop-opacity="0"/></linearGradient></defs><rect x="555" y="60" width="170" height="520" fill="url(#fade)"/>${mono(65, 90, 'WIXAL', 14, pink, 'letter-spacing="3"')}${text(61, 232, 'Local AI,', 73, cream, 'font-weight="600" letter-spacing="-2"')}${text(61, 314, 'at home on', 73, cream, 'font-weight="600" letter-spacing="-2"')}${text(61, 396, 'your Mac.', 73, cream, 'font-weight="600" letter-spacing="-2"')}${text(65, 465, 'Ollama. Project files. A real terminal.', 19, muted)}${mono(65, 568, 'github.com/TheJhyeFactor/Wixal', 14)}`, 'Wixal GitHub social preview'));
  await save('assets/app-icon.svg', svg(1024, 1024, `<defs><linearGradient id="icon-bg" x2="1" y2="1"><stop stop-color="#35303e"/><stop offset="1" stop-color="#191a20"/></linearGradient></defs><rect x="24" y="24" width="976" height="976" rx="220" fill="url(#icon-bg)"/><rect x="44" y="44" width="936" height="936" rx="200" fill="none" stroke="#6c5b71" stroke-width="3"/><g transform="translate(110 70) scale(8.2)">${lettermark}</g>`, 'Wixal macOS app icon'));
  const tiles = [['model', 'Choose your model', 'Use your Ollama library.'], ['folder', 'Open your project', 'Read and search real files.'], ['review', 'Review each change', 'Approve edits and commands.'], ['terminal', 'Keep working', 'Use the built-in zsh terminal.']];
  await save('assets/workflow.svg', svg(1280, 180, `<rect width="1280" height="180" rx="12" fill="${ink}"/>${tiles.map(([ic, heading, sub], i) => { const x = 30 + i * 316; return `${i ? `<path d="M${x - 18} 32v116" stroke="#3b3741"/>` : ''}<g transform="translate(${x} 33)" fill="none" stroke="${pink}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${icons[ic]}</g>${text(x, 95, heading, 20, cream, 'font-weight="500"')}${text(x, 126, sub, 14, muted)}`; }).join('')}`, 'Choose your model, open your project, review each change, and keep working in the terminal'));
  const orbit = `<style>.orbit{transform-origin:32px 32px;animation:orbit 3s linear infinite}@keyframes orbit{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.orbit{animation:none}}</style><circle cx="32" cy="32" r="22" fill="none" stroke="#49414f" stroke-width="1.5"/><g class="orbit"><path d="M32 10a22 22 0 0 1 22 22" fill="none" stroke="${pink}" stroke-width="2" stroke-linecap="round"/></g><path d="m23 25 7 7-7 7m12 0h7" fill="none" stroke="#ded4dd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
  await save('assets/motion/working.svg', svg(64, 64, orbit, 'Local work in progress'));
  console.log('Built Wixal lettermark, SVG icons, working animation, app icon, banner, social card, and workflow.');
})().catch(error => { console.error(error); process.exitCode = 1; });
