const {_electron:electron}=require('playwright'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-website-ui-')),project=path.join(temp,'project');await fs.mkdir(project);
 const server=http.createServer((_req,res)=>{res.setHeader('Content-Type','text/html');res.end('<html><h1>Website UI fixture</h1></html>');});await new Promise(r=>server.listen(0,'127.0.0.1',r));const url='http://127.0.0.1:'+server.address().port+'/';
 const seed = new (require('../app/store.cjs').Store)(path.join(temp, 'state')); seed.data.setup = { completed: true, entryCompleted: true }; seed.data.ui.launchAnimation = false; seed.save();
 const env={...process.env,WIXAL_RUNTIME_MODE:'external',WIXAL_DATA_DIR:path.join(temp,'state'),WIXAL_TEST_PROJECT:project};delete env.ELECTRON_RUN_AS_NODE;let app;
 try{
  app=await electron.launch({args:[root],env,...(process.env.WIXAL_APP_PATH?{executablePath:process.env.WIXAL_APP_PATH}:{})});const page=await app.firstWindow(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.locator('#prompt').waitFor();
  await app.evaluate((_app,url)=>{const real=globalThis.fetch;globalThis.websiteRequests=[];globalThis.fetch=async(target,opts)=>{if(!String(target).startsWith('http://127.0.0.1:11434'))return real(target,opts);const json=d=>new Response(JSON.stringify(d));if(String(target).endsWith('/api/tags'))return json({models:[{name:'website:test',size:1e9,digest:'website'}]});if(String(target).endsWith('/api/show'))return json({capabilities:['tools'],model_info:{'fixture.context_length':32768}});if(String(target).endsWith('/api/ps'))return json({models:[]});const body=JSON.parse(opts.body);globalThis.websiteRequests.push(body);const last=body.messages.at(-1);return json({done:true,message:last.role==='tool'?{content:'Website evidence saved. Frame protection needs review.'}:{content:'',tool_calls:[{function:{name:'website_assess',arguments:{url,profile:'probes',max_pages:1,report_prefix:'ui-proof'}}}]}});};},url);
  await page.click('#model-button');await page.click('#model-refresh');await page.locator('[data-model="website:test"]').click();await page.selectOption('#approval-mode','all');
  const events=[];await page.exposeFunction('recordWebsiteEvent',e=>events.push(e));await page.evaluate(()=>window.wixal.onEvent(e=>window.recordWebsiteEvent(e)));
  await page.click('#header-tools');await page.fill('#website-target',url);await page.selectOption('#website-profile','probes');await page.fill('#website-report','ui-proof');await page.click('#website-run');
  const deadline=Date.now()+30000;while(Date.now()<deadline&&!events.some(e=>e.type==='done')){assert.equal(events.find(e=>e.type==='error'),undefined);await new Promise(r=>setTimeout(r,100));}
  assert.ok(events.some(e=>e.type==='done'));assert.equal(events.filter(e=>e.type==='approval').length,0);
  const report=JSON.parse(await fs.readFile(path.join(project,'ui-proof.json'),'utf8'));assert.equal(report.target,url);assert.ok(report.findings.some(f=>f.id==='frame-protection'));assert.ok((await fs.readFile(path.join(project,'ui-proof.md'),'utf8')).includes('Website assessment'));
  const requests=await app.evaluate(()=>globalThis.websiteRequests);assert.match(requests[0].messages.at(-1).content,/Use website_assess/);assert.ok(requests[0].tools.some(t=>t.function.name==='website_assess'));assert.deepEqual(errors,[]);
  await page.click('#header-tools');await page.locator('#website-target').waitFor();await page.locator('#website-target').scrollIntoViewIfNeeded();await fs.mkdir(path.join(root,'artifacts'),{recursive:true});await page.screenshot({animations:'disabled',path:path.join(root,'artifacts/website-assessment-0.7.6.png')});
  console.log('WEBSITE_UI_OK: form, enabled local-model tools, real GET probes, saved JSON/Markdown evidence and Approved all without dialogs.');
 }finally{if(app)await app.close();await new Promise(r=>server.close(r));await fs.rm(temp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
