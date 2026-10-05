const { _electron: electron } = require('playwright');
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
async function main() {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-connections-ui-')), project = path.join(temp, 'Connection demo');
  await fs.mkdir(project); await fs.writeFile(path.join(project, 'README.md'), '# Connection demo\nFixture project only.');
  const env = { ...process.env, WIXAL_DATA_DIR: path.join(temp, 'data'), WIXAL_TEST_PROJECT: project }; delete env.ELECTRON_RUN_AS_NODE;
  let app, transport, client;
  try {
    app = await electron.launch({ args: [root], env, ...(process.env.WIXAL_APP_PATH ? { executablePath: process.env.WIXAL_APP_PATH } : {}) });
    const page = await app.firstWindow(), errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.locator('#connection-label').filter({ hasText: 'Ollama connected' }).waitFor({ timeout: 20000 });
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    async function capture(name, dialog) {
      await page.locator('#toast').waitFor({ state: 'hidden', timeout: 12000 });
      if (dialog) await page.locator(dialog).evaluate(element => { element.scrollTop = 0; });
      await page.screenshot({ path: path.join(root, `artifacts/${name}.png`), animations: 'disabled' });
    }
    await page.click('#connections-button');
    await page.fill('#api-key-input', 'sk-wixal-smoke-fixture'); await page.locator('#api-key-form button').click();
    await page.locator('#api-key-status').filter({ hasText: 'saved securely' }).waitFor(); assert.equal(await page.inputValue('#api-key-input'), '');
    const snapshot = await page.evaluate(() => window.wixal.connections()); assert.equal(snapshot.apiKeySaved, true); assert.doesNotMatch(JSON.stringify(snapshot), /sk-wixal/);
    assert.doesNotMatch(await fs.readFile(path.join(temp, 'data/credentials.enc'), 'utf8'), /sk-wixal/);
    console.log('PASS: UI saved an API key through real macOS encryption and returned no secret in snapshots');
    await page.locator('[data-cloud]').check(); await page.locator('[data-share]').check(); await page.check('#companion-enabled');
    await page.locator('#companion-status').filter({ hasText: 'running' }).waitFor();
    const connections = await page.evaluate(() => window.wixal.connections());
    transport = new StdioClientTransport({ command: process.execPath, args: [connections.companion.helperPath, connections.companion.connectionFile] });
    client = new Client({ name: 'wixal-smoke', version: '1.0.0' }); await client.connect(transport);
    const specs = await client.listTools(); assert.equal(specs.tools.length, 6); assert.equal(specs.tools.some(t => t.name === 'run_command'), false);
    const projects = JSON.parse((await client.callTool({ name: 'list_projects', arguments: {} })).content[0].text); assert.equal(projects.length, 1);
    const read = await client.callTool({ name: 'read_project_file', arguments: { projectId: projects[0].id, path: 'README.md' } }); assert.match(read.content[0].text, /Fixture project/);
    const queued = JSON.parse((await client.callTool({ name: 'create_task', arguments: { projectId: projects[0].id, title: 'A task from ChatGPT', prompt: 'Use write_file to create companion-proof.txt containing wixal-companion-proof.' } })).content[0].text);
    await page.locator('#task-count').filter({ hasText: '1' }).waitFor(); await assert.rejects(fs.access(path.join(project, 'companion-proof.txt')));
    console.log('PASS: real MCP stdio client discovered tools, read the shared project and queued a task without executing it');
    // External inference is simulated here. The app, controller, file write and review UI are real.
    await app.evaluate((_electron, appRoot) => {
      globalThis.wixalOriginalFetch = globalThis.fetch;
      globalThis.wixalRequests = [];
      globalThis.fetch = async (url, options) => {
        if (String(url) === 'https://api.openai.com/v1/models') return new Response(JSON.stringify({ data: [{ id: 'gpt-6-fixture' }], models: [{ slug: 'gpt-6-fixture', display_name: 'Fixture ChatGPT model', visibility: 'list' }] }));
        if (String(url) === 'https://api.openai.com/v1/responses') {
          const request = JSON.parse(options.body); globalThis.wixalRequests.push(request);
          const output = request.input.some(i => i.type === 'function_call_output') ? [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: request.input.some(i => i.type === 'function_call_output' && i.output.startsWith('User declined')) ? 'You declined the file edit. No file was changed.' : 'The reviewed file was saved.' }] }] : [{ type: 'function_call', name: 'write_file', call_id: 'call_smoke', ...(request.tools[0]?.type === 'namespace' ? { namespace: 'wixal' } : {}), arguments: JSON.stringify({ path: request.input.some(i => JSON.stringify(i).includes('companion-proof')) ? 'companion-proof.txt' : 'openai-proof.txt', content: 'wixal-companion-proof' }) }];
          return new Response(`data: ${JSON.stringify({ type: 'response.completed', response: { output, usage: { output_tokens: 10 } } })}\n\n`);
        }
        return globalThis.wixalOriginalFetch(url, options);
      };
      const { ChatGPTAuth } = process.mainModule.require(`${_electron.app.getAppPath()}/app/chatgpt-auth.cjs`);
      globalThis.wixalOriginalAuthStart = ChatGPTAuth.prototype.start;
      ChatGPTAuth.prototype.start = async function(id) {
        this.fetcher = async (url, request) => {
          if (String(url).includes('openid-configuration')) return new Response(JSON.stringify({ issuer: 'https://auth.openai.com', jwks_uri: 'https://auth.openai.com/.well-known/jwks.json', revocation_endpoint: 'https://auth.openai.com/revoke' }));
          if (String(url).includes('jwks.json')) return new Response(JSON.stringify(globalThis.wixalJwks));
          if (String(url).endsWith('/revoke')) return new Response('');
          globalThis.wixalTokenRequest = new URLSearchParams(request.body).get('grant_type'); return new Response(JSON.stringify(globalThis.wixalTokens));
        };
        return globalThis.wixalOriginalAuthStart.call(this, id);
      };
    }, root);
    await page.click('[data-close="connections-dialog"]'); await page.click('#model-button'); await page.selectOption('#provider-select', 'openai');
    await page.locator('.model-row').filter({ hasText: 'gpt-6-fixture' }).waitFor(); await page.locator('.model-row').click();
    await page.click('#tasks-button'); await page.locator('[data-task-start]').click();
    await page.locator('#approval-dialog[open]').waitFor(); assert.match(await page.locator('#approval-title').textContent(), /companion-proof/);
    await page.click('#approve'); await page.locator('#activity-label').filter({ hasText: 'Ready' }).waitFor();
    assert.equal(await fs.readFile(path.join(project, 'companion-proof.txt'), 'utf8'), 'wixal-companion-proof');
    const status = JSON.parse((await client.callTool({ name: 'get_task_status', arguments: { taskId: queued.id } })).content[0].text);
    assert.equal(status.status, 'completed'); assert.equal(status.outcomes[0].status, 'done');
    console.log('PASS: simulated OpenAI inference used the real review UI to write a file; MCP returned the completed task and tool outcome');
    // Sign the fixture ID token; the application still performs full JWKS verification.
    const { generateKeyPair, exportJWK, SignJWT } = await import('jose'); const keys = await generateKeyPair('RS256'); const jwk = await exportJWK(keys.publicKey); jwk.kid = 'smoke';
    await app.evaluate(({ shell }) => { globalThis.wixalOriginalOpenExternal = shell.openExternal; shell.openExternal = async url => { globalThis.wixalAuthUrl = url; }; });
    await page.click('#connections-button'); await page.click('#chatgpt-sign-in');
    const url = new URL(await app.evaluate(() => globalThis.wixalAuthUrl));
    const idToken = await new SignJWT({ sub: 'wixal-fixture-account', email: 'fixture@example.com', nonce: url.searchParams.get('nonce') }).setProtectedHeader({ alg: 'RS256', kid: 'smoke' }).setIssuer('https://auth.openai.com').setAudience('oaiapp_smoke').setIssuedAt().setExpirationTime('5m').sign(keys.privateKey);
    await app.evaluate((_electron, fixture) => { globalThis.wixalJwks = { keys: [fixture.jwk] }; globalThis.wixalTokens = { id_token: fixture.idToken, access_token: 'fixture-access', refresh_token: 'fixture-refresh', token_type: 'Bearer', expires_in: 3600, scope: 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct' }; }, { jwk, idToken });
    const callback = new URL(url.searchParams.get('redirect_uri')); callback.search = new URLSearchParams({ state: url.searchParams.get('state'), code: 'fixture-code', client_id: 'oaiapp_smoke' });
    assert.equal((await fetch(callback)).status, 200); await page.locator('#plan-notice-dialog[open]').waitFor(); await page.click('#plan-notice-dismiss'); await page.locator('.account-row').filter({ hasText: 'fixture@example.com' }).waitFor();
    assert.equal(await app.evaluate(() => globalThis.wixalTokenRequest), 'authorization_code');
    console.log('PASS: sign-in button completed real loopback/PKCE flow with a signed fixture identity verified through JWKS');
    await capture('wixal-connections', '#connections-dialog');
    await page.click('[data-close="connections-dialog"]'); await page.click('#model-button'); await page.selectOption('#provider-select', 'chatgpt');
    await page.locator('.model-row').filter({ hasText: 'Fixture ChatGPT model' }).waitFor(); await page.locator('.model-row').click();
    await page.click('#new-chat'); await page.fill('#prompt', 'Create openai-proof.txt using write_file.'); await page.click('#send');
    await page.locator('#approval-dialog[open]').waitFor(); await page.click('#decline');
    await page.locator('#activity-label').filter({ hasText: 'Ready' }).waitFor(); await assert.rejects(fs.access(path.join(project, 'openai-proof.txt')));
    const requests = await app.evaluate(() => globalThis.wixalRequests.map(request => ({ store: request.store, stream: request.stream, tools: request.tools?.[0]?.type, hasToolOutput: request.input.some(i => i.type === 'function_call_output') })));
    assert.equal(requests.at(-1).tools, 'namespace'); assert.ok(requests.at(-1).hasToolOutput); assert.ok(requests.every(r => r.store === false && r.stream));
    console.log('PASS: ChatGPT account catalog, namespaced tools, stateless continuation and declined edits through the app UI');
    await page.click('#tasks-button'); await capture('wixal-tasks', '#tasks-dialog'); await page.click('[data-close="tasks-dialog"]');
    await page.reload(); await page.locator('#connection-label').filter({ hasText: 'ChatGPT connected' }).waitFor();
    const afterReload = await page.evaluate(() => window.wixal.state()); assert.equal(afterReload.tasks[0].status, 'completed'); assert.equal(afterReload.provider, 'chatgpt');
    await page.click('#connections-button'); await page.locator('[data-account-out]').click(); await page.locator('.account-row').filter({ hasText: 'Signed out' }).waitFor();
    await page.locator('[data-share]').uncheck(); const denied = await client.callTool({ name: 'get_task_status', arguments: { taskId: queued.id } }); assert.equal(denied.isError, true);
    await page.uncheck('#companion-enabled'); assert.equal((await page.evaluate(() => window.wixal.connections())).companion.running, false);
    await page.click('#remove-api-key'); await page.locator('#api-key-status').filter({ hasText: 'No key saved' }).waitFor();
    await page.click('[data-close="connections-dialog"]'); await page.click('#model-button'); await page.selectOption('#provider-select', 'ollama'); await page.locator('.model-row').first().waitFor(); await page.click('[data-close="models-dialog"]');
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(920, 640)); await page.click('#connections-button');
    await capture('wixal-connections-compact', '#connections-dialog');
    assert.deepEqual(errors, []);
    console.log('PASS: reload persistence, sign-out, key removal, sharing revocation, companion pause and no renderer exceptions');
  } finally { await client?.close(); await transport?.close(); await app?.close(); await fs.rm(temp, { recursive: true, force: true }); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
