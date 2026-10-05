import { readFile, readdir, stat } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import assert from 'node:assert/strict';

const root = resolve(import.meta.dirname, '../dist');
const base = process.env.BASE_PATH || '/';
async function files(dir) {
  const entries = await readdir(dir, {withFileTypes:true});
  return (await Promise.all(entries.map(e => e.isDirectory() ? files(resolve(dir,e.name)) : resolve(dir,e.name)))).flat();
}
const htmlFiles = (await files(root)).filter(file=>file.endsWith('.html'));
const documents = new Map(await Promise.all(htmlFiles.map(async file=>[file,await readFile(file,'utf8')])));
let checked = 0;
for (const [file,html] of documents) {
  assert.match(html, /<html lang="en">/);
  assert.equal((html.match(/<h1[ >]/g)||[]).length,1,`${file}: expected one h1`);
  assert.match(html, /name="viewport"/);
  for (const match of html.matchAll(/(?:href|src)="([^"\s]+)"/g)) {
    const value = match[1];
    if (/^https?:/.test(value)) continue;
    const [path,hash] = value.split('#');
    const target = !path ? file : resolve(root, path.startsWith(base) ? path.slice(base.length) : path.replace(/^\//,''));
    const actual = (await stat(target)).isDirectory() ? resolve(target,'index.html') : target;
    if (hash && actual.endsWith('.html')) {
      const targetHtml = documents.get(actual) || await readFile(actual,'utf8');
      assert.ok(targetHtml.includes(`id="${hash}"`), `Missing fragment ${value} in ${file}`);
    }
    checked++;
  }
  for (const match of html.matchAll(/aria-controls="([^"]+)"/g)) assert.ok(html.includes(`id="${match[1]}"`), `Missing ARIA target in ${file}`);
}
console.log(`Checked ${htmlFiles.length} HTML documents and ${checked} local asset, page, and fragment links.`);
