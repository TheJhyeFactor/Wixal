// Render the same editable vectors into GIFs for GitHub, where SVG motion varies.
const sharp = require('sharp');
const path = require('node:path');
const { svg, lockup, banner, palette, root } = require('./graphics.cjs');
async function gif(name, frames, w, h, delay) {
  await sharp(Buffer.concat(frames), { raw: { width: w, height: h * frames.length, channels: 3, pageHeight: h } }).gif({ delay, loop: 0, colours: 128, dither: .15 }).toFile(path.join(root, name));
}
(async () => {
  const hero = [], logo = [], delays = [];
  for (let i = 0; i <= 50; i++) {
    const progress = i / 50;
    hero.push(await sharp(Buffer.from(await banner(progress))).resize(1152, 387).flatten({background:palette.ink}).raw().toBuffer());
    logo.push(await sharp(Buffer.from(svg(760, 240, `<rect width="760" height="240" rx="14" fill="${palette.ink}"/><g transform="translate(100 17) scale(1.28)">${lockup(palette.paper, palette.pink, progress)}</g>`, 'Wixal logo reveal'))).flatten({background:palette.ink}).raw().toBuffer());
    delays.push(i === 0 ? 350 : i === 50 ? 2200 : 40);
  }
  await gif('assets/motion/github-hero.gif', hero, 1152, 387, delays);
  await gif('assets/motion/logo-reveal.gif', logo, 760, 240, delays);
  console.log('Rendered the GitHub header GIF and logo reveal GIF.');
})().catch(error => { console.error(error); process.exitCode = 1; });
