const fs = require('node:fs');
const path = require('node:path');
const documents = { terms: { title: 'Terms & Conditions', file: 'terms.md' }, privacy: { title: 'Privacy Policy', file: 'privacy.md' } };
function legalDocument(id) {
  const doc = documents[id];
  if (!Object.hasOwn(documents, id)) throw new Error('Unknown legal document.');
  return { title: doc.title, version: '2026-10-06-draft', status: 'draft', markdown: fs.readFileSync(path.join(__dirname, '../resources/legal', doc.file), 'utf8') };
}
module.exports = { legalDocument };
