// Wixal's vector identity. The symbol and wordmark are paths, not font glyphs.
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const palette = { ink: '#17191f', paper: '#f4f0e9', pink: '#ecabc5', muted: '#acaeb9', line: '#343641' };
const symbolPath = 'M9 19H25L41 66L54 31H68L82 66L98 19H114L92 87Q91 91 86 91H79Q74 91 73 87L61 54L49 87Q47 91 42 91H35Q31 91 29 87Z';
const foldPath = 'M82 66L98 19H114L92 87Q91 91 86 91H79Q74 91 73 87L68 73Z';
const glyphs = [
  '<path d="M4 9 12 36Q13 39 14 36L24 15 34 36Q35 39 36 36L44 9"/>',
  '<path d="M63 9v29"/><circle cx="63" cy="-7" r="4" fill="currentColor" stroke="none"/>',
  '<path d="m82 9 26 29m0-29-26 29"/>',
  '<ellipse cx="136" cy="24" rx="14" ry="15"/><path d="M150 9v29"/>',
  '<path d="M171-9v40q0 7 8 7"/>'
];
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
const clamp = n => Math.max(0, Math.min(1, n));
const ease = n => 1 - (1 - clamp(n)) ** 3;
function symbol(color = palette.paper, accent = palette.pink, progress = 1) {
  return `<g class="symbol" opacity="${ease(progress * 2)}" transform="translate(0 ${8 * (1 - ease(progress * 2))})"><path d="${symbolPath}" fill="${color}"/><path class="fold" d="${foldPath}" fill="${accent}" opacity="${ease((progress - .2) * 2)}"/></g>`;
}
function wordmark(color = palette.paper, progress = 1) {
  return `<g fill="none" stroke="${color}" color="${color}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">${glyphs.map((g, i) => `<g class="letter letter-${i}" opacity="${ease((progress - .15 - i * .12) * 4)}">${g}</g>`).join('')}</g>`;
}
function lockup(color = palette.paper, accent = palette.pink, progress = 1) {
  return `<g transform="translate(8 32) scale(1.16)">${symbol(color, accent, progress)}</g><g transform="translate(175 58) scale(2.12)">${wordmark(color, progress)}</g>`;
}
function svg(w, h, body, title) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="title"><title id="title">${title}</title>${body}</svg>\n`;
}
const text = (x, y, value, size = 16, fill = palette.paper, extra = '') => `<text x="${x}" y="${y}" font-family="Helvetica,Arial,sans-serif" font-size="${size}" fill="${fill}" ${extra}>${value}</text>`;
const mono = (x, y, value, size = 12, fill = palette.muted, extra = '') => `<text x="${x}" y="${y}" font-family="Menlo,monospace" font-size="${size}" fill="${fill}" ${extra}>${value}</text>`;
async function save(name, contents) { await fs.mkdir(path.dirname(path.join(root, name)), { recursive: true }); await fs.writeFile(path.join(root, name), contents); }
async function exportSvg(name, contents) { await save(`${name}.svg`, contents); await sharp(Buffer.from(contents)).png().toFile(path.join(root, `${name}.png`)); }
async function banner(progress = 1) {
  const embedded = (await sharp(path.join(root, 'docs/screenshots/workspace.png')).resize(542, 394).png().toBuffer()).toString('base64');
  return svg(1280, 430, `<rect width="1280" height="430" rx="16" fill="${palette.ink}"/><path d="M48 382h1184" stroke="${palette.line}"/>${mono(62, 57, 'A WORKSPACE FOR YOUR MAC', 11, palette.pink, 'letter-spacing="2"')}<g transform="translate(54 92) scale(.95)">${lockup(palette.paper, palette.pink, progress)}</g>${text(62, 271, 'Local models. Real project files.', 27, palette.paper, 'letter-spacing="-.6"')}${text(62, 306, 'A conversation, your tools, and a terminal in one place.', 16, palette.muted)}${mono(62, 409, 'MACOS / APPLE SILICON / EARLY PREVIEW', 10)}<g opacity="${ease(progress)}"><rect x="694" y="31" width="544" height="396" rx="9" fill="#252731" stroke="#4a4353"/><clipPath id="app"><rect x="695" y="32" width="542" height="394" rx="8"/></clipPath><image x="695" y="32" width="542" height="394" href="data:image/png;base64,${embedded}" clip-path="url(#app)"/></g>`, 'Wixal: local models, real project files. A workspace for your Mac.');
}
async function build() {
  await save('assets/mark.svg', svg(124, 110, symbol(), 'Wixal folded W symbol'));
  await save('assets/logo/wordmark.svg', svg(195, 60, `<g transform="translate(5 15)">${wordmark()}</g>`, 'Wixal wordmark'));
  await exportSvg('assets/logo/wixal', svg(580, 160, lockup(), 'Wixal logo'));
  await exportSvg('assets/logo/wixal-dark', svg(580, 160, lockup(palette.ink, '#b76888'), 'Wixal logo for light backgrounds'));
  await exportSvg('assets/logo/wixal-mono', svg(580, 160, lockup(palette.paper, palette.paper), 'Wixal single colour logo'));
  await exportSvg('assets/logo/symbol', svg(124, 110, symbol(), 'Wixal logo symbol'));
  const animatedStyle = `<style>.symbol{animation:symbol-in .7s ease-out both}.fold{animation:fold-in 1.1s ease-out both}.letter{animation:letter-in .5s ease-out both}.letter-0{animation-delay:.25s}.letter-1{animation-delay:.38s}.letter-2{animation-delay:.51s}.letter-3{animation-delay:.64s}.letter-4{animation-delay:.77s}@keyframes symbol-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}@keyframes fold-in{from{opacity:0}to{opacity:1}}@keyframes letter-in{from{opacity:0}to{opacity:1}}@media(prefers-reduced-motion:reduce){*{animation:none!important}}</style>`;
  await save('assets/motion/logo-reveal.svg', svg(580, 160, animatedStyle + lockup(), 'Animated Wixal logo reveal'));
  await exportSvg('assets/repo-banner', await banner());
  await exportSvg('assets/social-card', svg(1280, 640, `<rect width="1280" height="640" fill="${palette.ink}"/><path d="M64 566h1152" stroke="${palette.line}"/>${mono(70, 91, 'WIXAL / MACOS', 13, palette.pink, 'letter-spacing="2"')}<g transform="translate(52 178) scale(1.22)">${lockup()}</g>${text(72, 422, 'Local models. Real project files.', 40, palette.paper, 'letter-spacing="-1"')}${text(72, 478, 'A conversation, your tools, and a terminal in one place.', 23, palette.muted)}${mono(72, 607, 'github.com/TheJhyeFactor/Wixal', 14)}<g transform="translate(947 202) scale(1.85)">${symbol('#343641', '#766070')}</g>`, 'Wixal: a workspace for local AI on Mac'));
  await save('assets/app-icon.svg', svg(1024, 1024, `<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#34303c"/><stop offset="1" stop-color="${palette.ink}"/></linearGradient></defs><rect x="24" y="24" width="976" height="976" rx="220" fill="url(#bg)"/><rect x="43" y="43" width="938" height="938" rx="201" fill="none" stroke="#64566d" stroke-width="3"/><g transform="translate(132 182) scale(6.15)">${symbol()}</g>`, 'Wixal app icon'));
  for (const [name, body] of Object.entries(icons)) await save(`assets/icons/${name}.svg`, svg(24, 24, `<g fill="none" stroke="#d3b4cc" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${body}</g>`, `${name} icon`));
  const tiles = [['model', 'Choose your model', 'Use your Ollama library.'], ['folder', 'Open your project', 'Read and search real files.'], ['review', 'Review each change', 'Approve edits and commands.'], ['terminal', 'Keep working', 'Use the built-in zsh terminal.']];
  await save('assets/workflow.svg', svg(1280, 180, `<rect width="1280" height="180" rx="12" fill="${palette.ink}"/>${tiles.map(([ic, heading, sub], i) => { const x = 30 + i * 316; return `${i ? `<path d="M${x - 18} 32v116" stroke="${palette.line}"/>` : ''}<g transform="translate(${x} 33)" fill="none" stroke="${palette.pink}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${icons[ic]}</g>${text(x, 95, heading, 20, palette.paper)}${text(x, 126, sub, 14, palette.muted)}`; }).join('')}`, 'Choose a model, open a project, review changes, and use the terminal'));
  // Preserve the illustration as an optional accent inside the app.
  await sharp(path.join(root, 'assets/artwork/night-shrine.png')).resize(960).webp({ quality: 88 }).toFile(path.join(root, 'assets/artwork/night-shrine.webp'));
  console.log('Built the Wixal symbol, outlined wordmark, logo variants, icon, and page graphics.');
}
module.exports = { svg, symbol, lockup, banner, save, palette, ease, root };
if (require.main === module) build().catch(error => { console.error(error); process.exitCode = 1; });
