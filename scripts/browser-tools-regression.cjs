// Actual Chromium execution against delayed and interactive disposable loopback pages.
const { app } = require('electron');
const http = require('node:http'), assert = require('node:assert/strict');
const { executeBrowser, browserSessions, closeAllBrowsers } = require('../app/browser-tools.cjs');
const { inspectBrowser } = require('../app/browser-inspect.cjs');
app.on('window-all-closed', () => {});
app.whenReady().then(async () => {
 let posts = 0, nextHits = 0;
 const server = http.createServer((req,res) => {
  if(req.method==='POST'){ posts++;res.end('unexpected write');return; }
  if(req.url==='/redirect'){res.writeHead(302,{location:'/next'});res.end();return;}
  if(req.url==='/hold')return;
  res.setHeader('Content-Type','text/html');
  if(req.url==='/mutating'){res.end('<body><button type=button id=change>Initial control</button><script>setTimeout(()=>document.querySelector("#change").textContent="Changed control",500)</script></body>');return;}
  if(req.url==='/delayed'){res.end('<title>Delayed fixture</title><body>Loading<script>setTimeout(()=>document.body.append(" DELAYED_BROWSER_PROOF"),800)</script>');return;}
  if(req.url==='/next'){nextHits++;res.end('<title>Next page</title><body>NAVIGATION_PROOF</body>');return;}
  if(req.url==='/long'){res.end('<title>Long page</title><body>'+ 'bounded '.repeat(4000)+'FINAL_BROWSER_PROOF</body>');return;}
  if(req.url==='/404'){res.statusCode=404;res.end('<body>Not found fixture</body>');return;}
  res.end(`<title>Control fixture</title><body><h1>Control fixture heading</h1><a href="/next">Next page</a><input name="topic" placeholder="Topic"><select name="choice"><option value="a">A</option><option value="b">B</option></select><button type="button" id="reveal" onclick="document.querySelector('#result').textContent='CONTROL_PROOF'">Reveal evidence</button><button type="button" onclick="document.querySelector('#reveal').textContent='Changed control'">Change label</button><button type="button" onclick="location.href='/next'">Unexpected navigation</button><button type="button" onclick="fetch('/write',{method:'POST',body:'blocked'})">Try write</button><button disabled>Disabled action</button><form><input type="password" value="PASSWORD_CANARY" name="password"><input type="hidden" value="HIDDEN_CANARY"><button>Submit form</button></form><div id="result"></div><script>document.querySelector('[name=topic]').addEventListener('input',e=>document.querySelector('#result').textContent='Input received: '+e.target.value)</script></body>`);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
 let reviews = [], session='one';const context={root:'/fixture',store:{session:()=>({id:session})},approve:async r=>{reviews.push(r);return true;}};
 const call=async(name,args,extra={})=>{const value=await executeBrowser(name,args,{...context,...extra});return value.startsWith('User declined')?value:JSON.parse(value);};
 const ref=(page,label)=>page.controls.find(c=>c.label===label)?.ref;
 const log=text=>console.log('PASS: '+text);
 try{
  let inspected=JSON.parse(await inspectBrowser({url:base+'/delayed',wait_for:''},{approve:async()=>true}));assert.match(inspected.text,/DELAYED_BROWSER_PROOF/);assert.equal(browserSessions().length,0);log('one-shot inspection waits for delayed JavaScript and releases its browser');
  let page=await call('browser_open',{url:base+'/page'});const id=page.session_id;assert.equal(page.title,'Control fixture');assert.deepEqual(page.headings,[{level:1,text:'Control fixture heading'}]);assert.ok(!JSON.stringify(page).includes('PASSWORD_CANARY'));assert.ok(!JSON.stringify(page).includes('HIDDEN_CANARY'));assert.equal(reviews.length,1);
  let oldRef=ref(page,'Reveal evidence');page=await call('browser_action',{session_id:id,ref:oldRef,action:'click',wait_ms:0});assert.match(page.text,/CONTROL_PROOF/);await assert.rejects(call('browser_action',{session_id:id,ref:oldRef,action:'click'}),/stale/);log('reviewed control click produces new evidence and invalidates old refs');
  page=await call('browser_action',{session_id:id,ref:ref(page,'Topic'),action:'fill',value:'ordinary query',wait_ms:0});assert.match(page.text,/Input received: ordinary query/);page=await call('browser_action',{session_id:id,ref:ref(page,'choice'),action:'select',value:'b',wait_ms:0});assert.ok(page.controls.some(c=>c.kind==='select'));log('ordinary text input and option selection work without collecting form values');
  await assert.rejects(call('browser_action',{session_id:id,ref:ref(page,'password'),action:'fill',value:'do not send'}),/Credentials/);await assert.rejects(call('browser_action',{session_id:id,ref:ref(page,'Submit form'),action:'click'}),/submission/);await assert.rejects(call('browser_action',{session_id:id,ref:ref(page,'Disabled action'),action:'click'}),/disabled/);log('sensitive fields, submissions and disabled controls fail before review or execution');
  session='other';await assert.rejects(call('browser_read',{session_id:id}),/unavailable/);session='one';
  const before=nextHits;assert.match(await call('browser_action',{session_id:id,ref:ref(page,'Next page'),action:'click'},{approve:async()=>false}),/declined/);assert.equal(nextHits,before);page=await call('browser_action',{session_id:id,ref:ref(page,'Next page'),action:'click'});assert.match(page.text,/NAVIGATION_PROOF/);assert.equal(page.session_id,id);log('navigation requires review, retains the browser session and cannot cross conversations');
  await call('browser_open',{url:base+'/page',session_id:id});page=await call('browser_read',{session_id:id,wait_ms:0});page=await call('browser_action',{session_id:id,ref:ref(page,'Unexpected navigation'),action:'click',wait_ms:0});assert.match(page.blocked,/Navigation/);assert.equal(nextHits,before+1);page=await call('browser_action',{session_id:id,ref:ref(page,'Try write'),action:'click',wait_ms:200});assert.equal(posts,0);log('unreviewed scripted navigation and non-read-only network methods are blocked');
  await assert.rejects(call('browser_open',{url:base+'/redirect',session_id:id}),/Redirect needs/);await call('browser_close',{session_id:id});
  page=await call('browser_open',{url:base+'/long'});assert.equal(page.more,true);page=await call('browser_read',{session_id:page.session_id,offset:24000,max_chars:24000,wait_ms:0});assert.match(page.text,/FINAL_BROWSER_PROOF/);await call('browser_close',{session_id:page.session_id});log('large rendered pages can be read past the first chunk');
  page=await call('browser_open',{url:base+'/delayed',wait_for:'never appears',wait_ms:100});assert.equal(page.readiness.matched,false);await call('browser_close',{session_id:page.session_id});
  const abort=new AbortController();const pending=call('browser_open',{url:base+'/hold'},{signal:abort.signal});setTimeout(()=>abort.abort(),150);await assert.rejects(pending,/Stopped/);assert.equal(browserSessions().length,0);log('readiness timeout is explicit; cancellation closes the browser without retained sessions');
  page=await call('browser_open',{url:base+'/mutating',wait_ms:0});const mutatingId=page.session_id;
  await assert.rejects(call('browser_action',{session_id:mutatingId,ref:ref(page,'Initial control'),action:'click'},{approve:async()=>{await new Promise(resolve=>setTimeout(resolve,650));return true;}}),/changed since/);await call('browser_close',{session_id:mutatingId});log('a control changed during review is revalidated before execution');
  page=await call('browser_open',{url:base+'/404',wait_ms:0});assert.equal(page.status,404);assert.equal(page.state,'failed');await call('browser_close',{session_id:page.session_id});
  page=await call('browser_open',{url:base+'/page#result',wait_ms:0});assert.ok(page.url.endsWith('#result'));await call('browser_close',{session_id:page.session_id});
  for(let i=0;i<4;i++)await call('browser_open',{url:base+'/page',wait_ms:0});await assert.rejects(call('browser_open',{url:base+'/page',wait_ms:0}),/4 maximum/);closeAllBrowsers();assert.equal(browserSessions().length,0);log('HTTP failures, fragments, resource ceiling and cleanup are explicit');
  const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');const temp=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-browser-cleanup-'));
  try {
    const store=new (require('../app/store.cjs').Store)(path.join(temp,'state'));store.addProject(temp);store.data.model='fixture';let requests=0;
    await require('../app/agent.cjs').runAgent({store,prompt:`@browser_open Open ${base}/page and browser_close when finished`,details:{capabilities:['tools']},signal:new AbortController().signal,approve:async()=>true,emit:()=>{},fetcher:async()=>new Response(JSON.stringify({done:true,message:++requests===1?{content:'',tool_calls:[{function:{name:'browser_open',arguments:{url:base+'/page',wait_ms:0}}}]}:{content:'Page read. Finished.'}}))});
    const cleanup=store.session().messages.find(m=>m.tool_name==='browser_close');assert.equal(cleanup.source,'app_cleanup');assert.equal(JSON.parse(cleanup.content).state,'closed');assert.equal(browserSessions().length,0);assert.equal(store.session().messages.at(-1).content,'Page read. Finished.');log('the controller executes explicitly requested cleanup even when the model omits its final close');
  }finally{await fs.rm(temp,{recursive:true,force:true});}
  console.log('BROWSER_REGRESSION_OK: actual Chromium delayed content, clicks, inputs, select, pagination, navigation, review, isolation, credentials, submissions, redirects and cancellation.');
 }finally{closeAllBrowsers();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}).then(()=>app.quit()).catch(e=>{console.error(e);closeAllBrowsers();app.exit(1);});
