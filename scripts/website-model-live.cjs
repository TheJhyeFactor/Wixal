const {_electron:electron}=require('playwright'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-website-native-'));
 const project=path.resolve(process.env.WIXAL_WEBSITE_EVIDENCE||path.join(root,'artifacts/assessments/jhye.dev-2026-10-06/native-wixal'));await fs.mkdir(project,{recursive:true});
 const env={...process.env,WIXAL_DATA_DIR:path.join(temp,'state'),WIXAL_TEST_PROJECT:project};delete env.ELECTRON_RUN_AS_NODE;delete env.WIXAL_RUNTIME_MODE;let app;
 try{
  app=await electron.launch({args:[root],env,...(process.env.WIXAL_APP_PATH?{executablePath:process.env.WIXAL_APP_PATH}:{})});const page=await app.firstWindow();await page.locator('#prompt').waitFor();
  const model=process.env.WIXAL_WEBSITE_MODEL||'orcarouter/Qwen3.8-27B-Uncensored:iq4_xs';await page.evaluate(model=>window.wixal['model-select'](model),model);
  await page.evaluate(()=>window.wixal.settings({mode:'agent',contextSize:8192,autoSummary:false}));await page.evaluate(()=>window.wixal['approval-mode']('all'));await page.reload();await page.locator('#prompt').waitFor();
  const events=[];await page.exposeFunction('recordNativeWebsiteEvent',e=>events.push(e));await page.evaluate(()=>window.wixal.onEvent(e=>window.recordNativeWebsiteEvent(e)));
  await page.fill('#prompt', 'I own and authorise testing https://jhye.dev/. Use website_assess with url https://jhye.dev/, profile probes, max_pages 2, protected_paths ["/privileged/api/session","/privileged/api/admin/posts","/privileged/api/admin/media"], report_prefix jhye-dev-live. Then use website_simulate with report_prefix attack-simulations. Use the structured findings and check summaries as evidence; read report sections only for a specific missing detail. Give a concise professional assessment of at most 450 words with scope, grouped findings, passed controls, evidence report paths, limitations, remediation and concrete next tests. Clearly distinguish live findings from local fixture attacks.');await page.click('#send');
  const deadline=Date.now()+1200000;
  while(Date.now()<deadline&&!events.some(e=>e.type==='done')){const error=events.find(e=>e.type==='error');if(error)throw Error(error.message);if(events.some(e=>e.type==='approval'))throw Error('Approved all opened a dialog');await new Promise(r=>setTimeout(r,250));}
  assert.ok(events.some(e=>e.type==='done'),'Native model assessment timed out');
  const state=await page.evaluate(()=>window.wixal.state());assert.equal(state.localRuntime.mode,'managed');assert.equal(state.model,model);
  const messages=state.sessions.find(s=>s.id===state.activeSession).messages;assert.ok(messages.some(m=>m.tool_name==='website_assess'),'The local model did not call the website tool');assert.ok(messages.some(m=>m.tool_name==='website_simulate'),'The local model did not run simulations');
  const live=JSON.parse(await fs.readFile(path.join(project,'jhye-dev-live.json'),'utf8')),simulation=JSON.parse(await fs.readFile(path.join(project,'attack-simulations.json'),'utf8'));
  assert.equal(live.target,'https://jhye.dev/');assert.equal(live.summary.errors,0);assert.equal(simulation.summary.unexpected,0);assert.equal(simulation.summary.cases,18);
  const answer=messages.findLast(m=>m.role==='assistant'&&m.content)?.content;assert.ok(answer);assert.match(answer,/local|fixture|simulat/i);assert.match(answer,/jhye-dev-live|attack-simulations/);
  await fs.writeFile(path.join(project,'model-response.md'),`# Actual Wixal local-model response\n\nModel: ${model}\n\nEngine: Wixal bundled local engine; context 8192; Approved all.\n\n${answer}\n`);
  const appVersion=await app.evaluate(({app})=>app.getVersion());
  await fs.writeFile(path.join(project,'execution.json'),JSON.stringify({model,appVersion,engine:state.localRuntime.mode,approvalMode:state.approvalMode,finished:new Date().toISOString(),tools:messages.filter(m=>m.role==='tool').map(m=>({name:m.tool_name,failed:m.content.startsWith('Error:')})),live:live.summary,simulation:simulation.summary,approvalDialogs:events.filter(e=>e.type==='approval').length},null,2)+'\n');
  console.log('NATIVE_WEBSITE_OK '+JSON.stringify({model,live:live.summary,simulation:simulation.summary,approvals:0}));
 }finally{if(app)await app.close();await fs.rm(temp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
