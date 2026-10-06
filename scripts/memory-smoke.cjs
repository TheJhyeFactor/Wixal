// Real Electron UI and IPC with deterministic model responses and disposable data.
const root = require('node:path').resolve(__dirname, '..');
const { _electron: electron } = require(root + '/node_modules/playwright');
const { Store } = require(root + '/app/store.cjs');
const fs = require('node:fs/promises'), path = require('node:path'), os = require('node:os'), assert = require('node:assert/strict');
(async () => {
 const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'wixal-memory-ui-')), folder = path.join(dir, 'Memory project'); await fs.mkdir(folder);
 const store = new Store(path.join(dir, 'data')); store.addProject(folder); store.data.setup = {completed:true,entryCompleted:true}; store.data.ui.launchAnimation = false; store.data.mode='chat'; store.data.enabledTools = []; store.data.model = 'first:test'; store.save();
 const env = {...process.env, WIXAL_DATA_DIR:path.join(dir,'data'), WIXAL_RUNTIME_MODE:'external'}; delete env.ELECTRON_RUN_AS_NODE; delete env.WIXAL_TEST_PROJECT;
 let app; const errors=[];
 try {
  app = await electron.launch({args:[root],env,...(process.env.WIXAL_APP_PATH?{executablePath:process.env.WIXAL_APP_PATH}:{})}); const page = await app.firstWindow(); page.on('pageerror', e=>errors.push(e.message));
  await app.evaluate(()=>{
   const real=globalThis.fetch; globalThis.memoryRequests=[];
   globalThis.fetch=async(target,request)=>{
    const url=String(target); if(!url.startsWith('http://127.0.0.1:11434')) return real(target,request);
    const json=data=>new Response(JSON.stringify(data));
    if(url.endsWith('/api/version'))return json({version:'fixture'});
    if(url.endsWith('/api/tags'))return json({models:[{name:'first:test',size:1e9},{name:'second:test',size:1e9}]});
    if(url.endsWith('/api/show'))return json({capabilities:['completion'],model_info:{'fixture.context_length':32768}});
    if(url.endsWith('/api/ps'))return json({models:[]});
    if(url.endsWith('/api/chat')){const body=JSON.parse(request.body);globalThis.memoryRequests.push(body);if(body.messages[0].content.startsWith('Summarize') && globalThis.holdSummary) await new Promise((_resolve,reject)=>request.signal.addEventListener('abort',()=>reject(new Error('Stopped')),{once:true}));return json({message:{content:body.messages[0].content.startsWith('Summarize')?'Goal: sapphire. Decision: preserve files. Remaining: fix tests.':'SAPPHIRE_REPLY'},done:true,eval_count:5});}
    return json({});
   };
  });
  await page.reload(); await page.locator('#prompt:not([disabled])').waitFor(); await page.locator('#launch-screen').waitFor({state:'hidden'});
  await page.click('#model-button'); await page.click('#model-refresh'); await page.locator('[data-model="first:test"]').click();
  await page.click('#header-memory'); await page.selectOption('#project-memory-mode','both'); await page.selectOption('#project-memory-size','8000');
  await page.fill('#memory-input','sapphire project decision: preserve files'); await page.click('#memory-save'); await page.locator('#memories [data-edit]').waitFor();
  await page.click('#memories [data-edit]'); await page.fill('#memory-input','sapphire project decision: preserve source files'); await page.click('#memory-save'); await page.waitForFunction(()=>document.querySelector('#memories').textContent.includes('source files'));
  await page.click('#global-memory-details summary'); await page.fill('#global-memory-input','Prefer concise Australian English.'); await page.locator('#global-memory-form button[type="submit"]').click();
  let value=await page.evaluate(()=>window.wixal.state()); assert.equal(value.globalMemory,'Prefer concise Australian English.');assert.equal(value.projects[0].memorySize,8000);
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1380,900));
  await page.locator('#memory-drawer').evaluate(el => el.scrollTop = 0);
  await page.screenshot({path:'/tmp/wixal-memory-desktop.png',animations:'disabled'});
  await page.locator('#global-memory-input').scrollIntoViewIfNeeded(); await page.screenshot({path:'/tmp/wixal-global-memory.png',animations:'disabled'});
  await page.click('#close-memory'); await page.fill('#prompt','Remember goal sapphire and file constraints.');await page.click('#send');await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('SAPPHIRE_REPLY'));
  value=await page.evaluate(()=>window.wixal.state());const sourceId=value.activeSession;
  await page.click('#model-button');await page.locator('[data-model="second:test"]').click();
  value=await page.evaluate(()=>window.wixal.state());assert.equal(value.activeSession,sourceId);assert.equal(value.model,'second:test');
  await page.fill('#prompt','Continue sapphire');await page.click('#send');await page.waitForFunction(()=>!document.querySelector('#prompt').disabled);
  const reqs=await app.evaluate(()=>globalThis.memoryRequests);assert.equal(reqs.at(-1).model,'second:test');assert.match(JSON.stringify(reqs.at(-1).messages),/Remember goal sapphire/);
  await page.click('#context-new-chat');await page.locator('#handoff-dialog[open]').waitFor();await page.screenshot({path:'/tmp/wixal-handoff.png',animations:'disabled'});await app.evaluate(()=>globalThis.holdSummary=true);await page.click('#handoff-summary');await page.locator('#handoff-stop').waitFor();await page.click('#handoff-stop');await page.locator('#handoff-empty:not([disabled])').waitFor();value=await page.evaluate(()=>window.wixal.state());assert.equal(value.activeSession,sourceId);await app.evaluate(()=>globalThis.holdSummary=false);await page.click('#handoff-summary');await page.locator('#handoff-dialog').waitFor({state:'hidden'});
  value=await page.evaluate(()=>window.wixal.state());assert.notEqual(value.activeSession,sourceId);assert.equal(value.sessions.find(s=>s.id===value.activeSession).messages.length,1);assert.match(value.sessions.find(s=>s.id===value.activeSession).messages[0].content,/Remaining: fix tests/);assert.equal(value.sessions.find(s=>s.id===sourceId).messages.length,4);
  await page.fill('#prompt','x'.repeat(15000));await page.locator('#context-warning').waitFor();assert.match(await page.textContent('#context-usage-label'),/input tokens/);
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(920,700));await page.screenshot({path:'/tmp/wixal-context-compact.png',animations:'disabled'});
  await page.fill('#prompt','');await page.click('#context-new-chat');await page.click('#handoff-empty');value=await page.evaluate(()=>window.wixal.state());assert.equal(value.sessions.find(s=>s.id===value.activeSession).messages.length,0);
  await page.click('#open-project');await page.locator('#project-dialog[open]').waitFor();await page.selectOption('#folder-memory-mode','project');await page.selectOption('#folder-memory-size','48000');let other = path.join(dir, 'New memory project'); await fs.mkdir(other); other = await fs.realpath(other); await page.fill('#folder-path', other); await page.locator('#folder-path-form button[type="submit"]').click(); await page.waitForFunction(path => document.querySelector('#folder-path').value === path && !document.querySelector('#folder-open').disabled, other); await page.click('#folder-open'); value=await page.evaluate(()=>window.wixal.state()); assert.equal(value.projects.at(-1).memoryMode,'project'); assert.equal(value.projects.at(-1).memorySize,48000);
  await page.reload();await page.locator('#prompt:not([disabled])').waitFor();value=await page.evaluate(()=>window.wixal.state());assert.equal(value.globalMemory,'Prefer concise Australian English.');assert.equal(value.projects[0].memoryMode,'both');assert.equal(value.memories[0].content,'sapphire project decision: preserve source files');
  assert.deepEqual(errors,[]);console.log('PASS: project scope/capacity, editable saved notes, guest global profile, restart persistence, model switching in same chat, AI summary injection, original history retained, fresh chat, filling meter and warning, project setup controls, desktop and compact screenshots, zero renderer errors.');
 } finally {if(app)await app.close();await fs.rm(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
