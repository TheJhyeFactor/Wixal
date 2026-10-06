// Read-only live evidence from the user's nominated test site, through actual tools.
const { app } = require('electron');
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), os = require('node:os'), path = require('node:path');
const { executeTool } = require('../app/tools.cjs');
const { closeAllBrowsers } = require('../app/browser-tools.cjs');
const { Store } = require('../app/store.cjs');
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-jhye-tools-')); const store=new Store(path.join(root,'state'));store.addProject(root);
 const reviews=[], context={root,store,approve:async request=>{reviews.push(request);return true;},signal:new AbortController().signal};
 const call=async(name,args)=>JSON.parse(await executeTool(name,args,context));
 try{
  let page=await call('browser_open',{url:'https://jhye.dev/',wait_ms:2000});
  assert.equal(new URL(page.url).hostname,'jhye.dev');assert.equal(page.status,200);assert.match(page.text,/Jhye|software|developer/i);assert.ok(page.links.length);const id=page.session_id;
  console.log('PASS live jhye.dev rendered homepage:',JSON.stringify({title:page.title,status:page.status,characters:page.total_characters,links:page.links.map(l=>({text:l.text,url:l.url})).slice(0,12)}));
  let destination=page.controls.find(c=>c.kind==='a' && /^https:\/\/jhye\.dev\/(work|about|contact)\/?/.test(c.url) && !new URL(c.url).hash);
  assert.ok(destination,'The real site must provide a same-origin content link.');
  page=await call('browser_action',{session_id:id,ref:destination.ref,action:'click',wait_ms:2000});assert.equal(page.status,200);assert.equal(page.url,destination.url);assert.ok(page.text.length>100);
  console.log('PASS live reviewed link navigation:',JSON.stringify({title:page.title,url:page.url,characters:page.total_characters}));
  page=await call('browser_read',{session_id:id,wait_ms:0});assert.ok(page.controls.every(c=>c.ref.startsWith(page.snapshot_id+':')));await call('browser_close',{session_id:id});
  const http=await call('http_request',{url:'https://jhye.dev/'});assert.equal(http.status,200);assert.match(http.content,/Jhye|software|developer/i);assert.equal(http.url,'https://jhye.dev/');console.log('PASS live HTTP homepage:',http.status,http.total_chars);
  const search=await call('web_search',{query:'jhye.dev',limit:5});assert.equal(search.state,'completed');assert.ok(search.results.length);assert.ok(search.results.some(r=>new URL(r.url).hostname==='jhye.dev'));console.log('PASS live search sources:',JSON.stringify(search.results));
  const assessment=await call('website_assess',{url:'https://jhye.dev/',profile:'baseline',max_pages:2,report_prefix:'jhye-live-baseline'});assert.equal(assessment.target,'https://jhye.dev/');assert.equal(assessment.summary.errors,0);assert.ok(assessment.summary.requests>0);assert.ok((await fs.stat(path.join(root,'jhye-live-baseline.json'))).size>0);console.log('PASS live bounded GET baseline and saved evidence:',JSON.stringify(assessment.summary));
  assert.ok(reviews.filter(r=>r.name==='browser_open').length===2);
  console.log('JHYE_TOOLS_LIVE_OK: actual Chromium homepage, reviewed content link, fresh refs, cleanup, HTTP, search and bounded GET assessment. No form submission or site writes.');
 }finally{closeAllBrowsers();await fs.rm(root,{recursive:true,force:true});}
}).then(()=>app.quit()).catch(e=>{console.error(e);closeAllBrowsers();app.exit(1);});
