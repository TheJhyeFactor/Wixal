// Render new vector colourways of the existing Wixal Dock mark. Run from any cwd.
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');
const directory = path.resolve(__dirname, '../../assets/icon-variants');
const palettes = {
  cloud: ['#E0EDFA','#B6CCDF','#7D9ABA','#263C59','#1E304A','#ECF5FF','#3379BC'],
  paper: ['#F9F3E8','#DDD0BD','#B5A38C','#594635','#372B22','#FFF9EE','#9A7750'],
  dune: ['#E7CFB0','#CFAF8B','#A47854','#53392B','#39271D','#FFF0DB','#9E512E'],
  graphite: ['#646B77','#393E46','#24282F','#EEF0F4','#BCC6D6','#DCE3ED','#A8BAD8'],
  forest: ['#447257','#244E3B','#132D21','#DCEFE0','#A6D9B8','#D8F3DF','#D1B789'],
  aurora: ['#3B7882','#22545C','#193039','#DBFFF6','#8DE3D5','#C7FFF2','#B8A0EF'],
  obsidian: ['#34373D','#1E2024','#0B0C0E','#F2CFA3','#C78950','#EAD7C0','#FFE5C2']
};
async function main() {
  const template = await fs.readFile(path.join(directory,'sakura.svg'),'utf8');
  const originals = ['#f6c1d3','#bf749b','#714766','#fffaf7','#f5e5eb','#ffe2ec','#ffd9e8'];
  for (const [name,colours] of Object.entries(palettes)) {
    let svg = template.replace('Wixal sakura app icon', `Wixal ${name} app icon`);
    originals.forEach((colour,index) => { svg = svg.replaceAll(colour,colours[index]); });
    svg = svg.replaceAll('#ffe5ef',colours[5]);
    await fs.writeFile(path.join(directory,`${name}.svg`),svg);
    await sharp(Buffer.from(svg)).png().toFile(path.join(directory,`${name}.png`));
  }
  console.log(`Rendered ${Object.keys(palettes).length} matching icons; existing Sakura, Midnight, Pearl and Copper retained.`);
}
main().catch(error => { console.error(error); process.exitCode=1; });
