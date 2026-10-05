const { app } = require('electron');
app.on('window-all-closed', () => {});
const http = require('node:http');
const assert = require('node:assert/strict');
const { inspectBrowser } = require('../app/browser-inspect.cjs');
app.whenReady().then(async () => {
  const server = http.createServer((request, response) => {
    if (request.url === '/redirect') { response.writeHead(302, { location: '/page' }); response.end(); return; }
    response.setHeader('Content-Type', 'text/html');
    response.end('<title>Inspection fixture</title><body><a href="/next">Next</a><form><input name="account"><input type="password" value="do-not-collect"></form><script>document.body.append("Rendered by JavaScript");console.error("fixture console evidence")</script></body>');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  try {
    const result = JSON.parse(await inspectBrowser({ url: url + '/page' }, { approve: async () => true }));
    assert.match(result.text, /Rendered by JavaScript/);
    assert.equal(result.title, 'Inspection fixture');
    assert.equal(result.links[0].url, url + '/next');
    assert.equal(result.forms[0].fields[0].name, 'account');
    assert.ok(!JSON.stringify(result).includes('do-not-collect'));
    assert.ok(result.console.some(line => line.includes('fixture console evidence')));
    await assert.rejects(inspectBrowser({ url: url + '/redirect' }, { approve: async () => true }), /Redirect needs/);
    assert.match(await inspectBrowser({ url }, { approve: async () => false }), /declined/);
    console.log('BROWSER_TOOLS_SMOKE_OK: real rendered DOM, links, forms, console, redirect review, decline');
  } finally { await new Promise(resolve => server.close(resolve)); }
}).then(() => app.quit()).catch(error => { console.error(error); app.exit(1); });
