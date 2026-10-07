import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source = await readFile(new URL('../src/analytics.js', import.meta.url), 'utf8');
function setup(saved = null) {
  const listeners = new Map(), windowListeners = new Map(), elements = new Map(), scripts = [], storage = new Map();
  if (saved) storage.set('wixal-site-analytics-v1', saved);
  for (const selector of ['[data-analytics-choice]', '[data-analytics-allow]', '[data-analytics-deny]', '[data-analytics-close]', '[data-privacy-settings]']) {
    elements.set(selector, { hidden: true, focus() {}, addEventListener(name, fn) { this[name] = fn; }, querySelector(selector) { return elements.get(selector); } });
  }
  const document = { title: 'Download — Wixal', referrer: 'https://example.com/source?private=secret#fragment', cookie: 'wixal_ga=123; unrelated=keep', head: { append(script) { scripts.push(script); } }, createElement() { return {}; }, querySelector(selector) { return selector === 'meta[name="ga-measurement-id"]' ? { content: 'G-C6ZMWP9EX9' } : elements.get(selector); }, querySelectorAll() { return [elements.get('[data-privacy-settings]')]; }, addEventListener(name, fn) { listeners.set(name, fn); } };
  const window = { addEventListener(name, fn) { windowListeners.set(name, fn); } };
  vm.runInNewContext(source, { document, window, location: { hostname: 'thejhyefactor.github.io', origin: 'https://thejhyefactor.github.io', pathname: '/Wixal/download/' }, localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) }, URL });
  const commands = () => (window.dataLayer || []).map(args => Array.from(args));
  const click = href => listeners.get('click')({ target: { closest: () => ({ href }) } });
  return { elements, scripts, commands, click, document, window, windowListeners };
}
const page = setup();
assert.equal(page.scripts.length, 0, 'No Google tag before opt-in');
page.elements.get('[data-analytics-deny]').click();
assert.equal(page.scripts.length, 0, 'No Google tag after decline');
page.elements.get('[data-privacy-settings]').click();
assert.equal(page.elements.get('[data-analytics-choice]').hidden, false);
page.elements.get('[data-analytics-allow]').click();
page.elements.get('[data-analytics-allow]').click();
assert.equal(page.scripts.length, 1);
assert.equal(page.commands().filter(c => c[0] === 'event' && c[1] === 'page_view').length, 1);
const config = page.commands().find(c => c[0] === 'config')[2];
assert.equal(config.page_referrer, 'https://example.com/source');
assert.equal(config.page_location, 'https://thejhyefactor.github.io/Wixal/download/');
page.click('https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.3/Wixal-0.7.3-macOS-arm64.dmg');
page.click('https://example.com/other.zip');
assert.equal(page.commands().filter(c => c[1] === 'file_download').length, 1);
page.elements.get('[data-analytics-deny]').click();
page.click('https://github.com/TheJhyeFactor/Wixal/releases/download/v0.7.3/Wixal-0.7.3-macOS-arm64.zip');
assert.equal(page.commands().filter(c => c[1] === 'file_download').length, 1, 'Revocation stops events');
assert.equal(page.window['ga-disable-G-C6ZMWP9EX9'], true);
assert.equal(setup('deny').scripts.length, 0);
const returning = setup('allow');
assert.equal(returning.scripts.length, 1);
returning.windowListeners.get('storage')({ key: 'wixal-site-analytics-v1', newValue: 'deny' });
assert.equal(returning.window['ga-disable-G-C6ZMWP9EX9'], true);
console.log('Analytics checks passed: opt-in, decline, returning consent, revocation, cross-tab changes, URL cleaning, and one download event per click.');
