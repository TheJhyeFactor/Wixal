const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const motion = require('../ui/launch-motion.js');

test('splash preserves the exact original Wixal wordmark geometry', () => {
  const original = fs.readFileSync(path.join(__dirname, '../assets/logo/wordmark.svg'), 'utf8');
  const html = fs.readFileSync(path.join(__dirname, '../ui/index.html'), 'utf8');
  const splash = html.slice(html.indexOf('<dialog id="launch-screen"'), html.indexOf('</dialog>'));
  const geometry = svg => [...svg.matchAll(/<(path|ellipse|circle)\b[^>]*>/g)].map(([tag, type]) => {
    return { type, values: [...tag.matchAll(/\b(d|cx|cy|r|rx|ry)="([^"]+)"/g)].map(([, key, value]) => [key, value]) };
  });
  assert.deepEqual(geometry(splash), geometry(original));
  assert(splash.includes('viewBox="0 0 436 160"'));
  assert(splash.includes('aria-label="Wixal"'));
});

test('single launch motion is bounded and skips when reduced motion is requested', () => {
  let canceled = 0;
  const scene = { getAnimations: () => [{ cancel() { canceled++; } }], dataset: {} };
  assert.deepEqual(motion.play(scene, { reduced: true }), []);
  assert.equal(canceled, 1);
  assert.equal(motion.select, undefined);
  assert.equal(motion.variants, undefined);
  assert(motion.duration <= 2200);
});
