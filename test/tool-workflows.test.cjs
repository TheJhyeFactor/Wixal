const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs/promises'), path = require('node:path'), os = require('node:os');
const { definitions, executeTool } = require('../app/tools.cjs');
const { initialTools, loadCategory } = require('../app/tool-catalog.cjs');
const { boundedToolResult } = require('../app/tool-evidence.cjs');
const { executeNetwork, searchResults, boundedResponse } = require('../app/network.cjs');
const { Store } = require('../app/store.cjs');
const { runAgent } = require('../app/agent.cjs');
const names = tools => tools.map(t => t.function.name);
test('tool category discovery reduces inference payload and preserves disabled permissions', () => {
 const web = initialTools(definitions,'@browser_open inspect https://jhye.dev',['browser_open']);
 assert.ok(names(web).includes('browser_action')); assert.ok(!names(web).includes('network_scan'));
 const command = initialTools(definitions,'@command_start run printf proof',['command_start']); assert.ok(names(command).includes('command_read'));
 assert.ok(JSON.stringify(web).length < JSON.stringify(definitions).length * .65);
 const allowed = definitions.filter(t => !['write_file','browser_action'].includes(t.function.name));
 assert.ok(!names(loadCategory(allowed,'web')).includes('browser_action'));
 assert.ok(!names(loadCategory(allowed,'files')).includes('write_file'));
 assert.throws(() => loadCategory(allowed,'invented'),/Choose/);
});
test('workspace discovery changes schemas for the next model call and keeps the full permission boundary', async t => {
 const root = await fs.mkdtemp(path.join(os.tmpdir(),'wixal-tool-category-')); t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store = new Store(path.join(root,'state')); store.addProject(root); store.data.model='fixture'; store.data.enabledTools=names(definitions).filter(n=>n!=='browser_action');
 let requests=0;
 await runAgent({store,prompt:'Tell me what you can do',details:{capabilities:['tools']},signal:new AbortController().signal,emit:()=>{},approve:async()=>true,fetcher:async(_url,request)=>{
  const body=JSON.parse(request.body); requests++;
  if(requests===1){assert.ok(!names(body.tools).includes('browser_read'));return new Response(JSON.stringify({done:true,message:{content:'',tool_calls:[{function:{name:'workspace_info',arguments:{category:'web'}}}]}}));}
  assert.ok(names(body.tools).includes('browser_read')); assert.ok(!names(body.tools).includes('browser_action'));
  assert.equal(JSON.parse(body.messages.at(-1).content).loaded_category,'web');
  return new Response(JSON.stringify({done:true,message:{content:'Browser tools discovered.'}}));
 }});assert.equal(requests,2);
});
test('structured excerpts retain whole browser refs and source URLs without changing saved results',()=>{
 for(const limit of [350,500,2000,6000]){
  const result={session_id:'session-proof',snapshot_id:'snapshot-proof',url:'https://jhye.dev/',state:'completed',next_offset:24000,more:true,text:'long evidence '.repeat(3000),controls:[{ref:'snapshot-proof:e1',label:'Work',url:'https://jhye.dev/work/'}],results:[{title:'Jhye Dev',url:'https://jhye.dev/work/',snippet:'verified page'}]};
  const saved=JSON.stringify(result),excerpt=boundedToolResult(saved,limit),value=JSON.parse(excerpt);
  assert.ok(excerpt.length<=limit);assert.equal(value.session_id,'session-proof');assert.ok(value.next_offset<=24000);assert.ok(value.next_offset>0);assert.equal(value.context_excerpt,true);
  for(const item of [...(value.controls||[]),...(value.results||[])])assert.equal(item.url,'https://jhye.dev/work/');
  assert.equal(JSON.stringify(result),saved);
 }
});
test('search handles attribute order, entities, snippets, duplicates and credential URLs',()=>{
 const raw='<a href="https://jhye.dev/work/?a=1&amp;b=2" class="other result__a">Jhye &amp; work</a><a class="result__snippet" href="#">Actual project &#x65;vidence</a><a class="result__a" href="https://jhye.dev/work/?a=1&amp;b=2">duplicate</a><a class="result__a" href="https://user:secret@jhye.dev/">unsafe</a>';
 assert.deepEqual(searchResults(raw,'https://html.duckduckgo.com/'),[{title:'Jhye & work',url:'https://jhye.dev/work/?a=1&b=2',snippet:'Actual project evidence'}]);
});
test('search distinguishes an empty result from a challenge and never fabricates a source',async()=>{
 const base={approve:async()=>true};
 const value=JSON.parse(await executeNetwork('web_search',{query:'jhye.dev'},{...base,fetcher:async()=>new Response('<div>No results found</div>')}));assert.equal(value.state,'no_results');assert.deepEqual(value.results,[]);
 for(const status of [202,403,429])await assert.rejects(executeNetwork('web_search',{query:'jhye.dev'},{...base,fetcher:async()=>new Response('challenge',{status})}),/blocked/);
 await assert.rejects(executeNetwork('web_search',{query:'jhye.dev'},{...base,fetcher:async()=>new Response('<form id="challenge-form">captcha</form>')}),/blocked/);
});
test('HTTP pagination reads later evidence, reports byte limits, and rejects repeated write pagination',async()=>{
 const content='a'.repeat(26000)+'JHYE_END_PROOF',base={approve:async()=>true,fetcher:async()=>new Response(content,{headers:{'Content-Type':'Text/Plain'}})};
 const first=JSON.parse(await executeNetwork('http_request',{url:'https://jhye.dev/'},base));assert.equal(first.next_offset,24000);assert.equal(first.more,true);
 const next=JSON.parse(await executeNetwork('http_request',{url:'https://jhye.dev/',offset:first.next_offset},base));assert.match(next.content,/JHYE_END_PROOF/);assert.equal(next.more,false);
 await assert.rejects(executeNetwork('http_request',{url:'https://jhye.dev/',method:'POST',offset:1,body:'{}'},base),/Pagination/);
 const text=await boundedResponse(new Response('a'.repeat(1100000)));assert.equal(text.indexOf('[Response truncated'),1048577);assert.match(text,/1 MB/);
});
test('cancellation during approval performs no HTTP request and invalid arguments do not reach handlers',async()=>{
 const controller=new AbortController();let hits=0;
 await assert.rejects(executeNetwork('http_request',{url:'https://jhye.dev/'},{signal:controller.signal,approve:async()=>{controller.abort();return true;},fetcher:async()=>{hits++;return new Response('unexpected');}}),/Stopped/);assert.equal(hits,0);
 for(const name of ['website_assess','browser_open','list_files'])await assert.rejects(executeTool(name,null,{}),/Invalid tool arguments/);
});
test('exact edits and directory creation retain review, containment and concurrent-change protection',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-file-tools-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const context={root,approve:async()=>true};
 await fs.writeFile(path.join(root,'proof.txt'),'before unique after');
 await executeTool('edit_file',{path:'proof.txt',old_text:'unique',new_text:'edited'},context);assert.equal(await fs.readFile(path.join(root,'proof.txt'),'utf8'),'before edited after');
 await assert.rejects(executeTool('edit_file',{path:'proof.txt',old_text:'e',new_text:'x'},context),/exactly once/);
 await assert.rejects(executeTool('edit_file',{path:'proof.txt',old_text:'edited',new_text:'changed'},{...context,approve:async()=>{await fs.writeFile(path.join(root,'proof.txt'),'human edit');return true;}}),/changed during review/);assert.equal(await fs.readFile(path.join(root,'proof.txt'),'utf8'),'human edit');
 await executeTool('make_directory',{path:'reports'},context);assert.ok((await fs.stat(path.join(root,'reports'))).isDirectory());
 await assert.rejects(executeTool('make_directory',{path:'../outside'},context),/outside/);
 await assert.rejects(executeTool('make_directory',{path:'reports'},context),/already exists/);
 assert.match(await executeTool('make_directory',{path:'declined'},{...context,approve:async()=>false}),/declined/);await assert.rejects(fs.stat(path.join(root,'declined')));
});
test('file search includes supported large text, pages full matches and reports limits',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-search-files-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 await fs.writeFile(path.join(root,'large.txt'),'x'.repeat(300000)+'\nLARGE_FILE_PROOF');assert.match(await executeTool('search_files',{query:'LARGE_FILE_PROOF'},{root}),/large.txt:2:/);
 await fs.writeFile(path.join(root,'many.txt'),Array.from({length:1500},(_,i)=>'MATCH_PROOF '+i+' text '.repeat(20)).join('\n'));
 const first=await executeTool('search_files',{query:'MATCH_PROOF'},{root});const offset=Number(first.match(/next offset: (\d+)/)?.[1]);assert.ok(offset>0);
 const second=await executeTool('search_files',{query:'MATCH_PROOF',offset},{root});assert.match(second,new RegExp('many.txt:'+ (offset+1)+': MATCH_PROOF '+offset));assert.ok(!second.includes('many.txt:1:'));
});
test('new browser and file tools inherit existing opt-in once and preserve later disabled choices',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-tool-migration-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));let store=new Store(root);
 store.data.enabledTools=['workspace_info','browser_inspect','write_file'];store.data.toolsDefaultsVersion=2;delete store.data.browserToolsVersion;delete store.data.fileToolsVersion;store.save();store=new Store(root);
 assert.ok(store.data.enabledTools.includes('browser_action'));assert.ok(store.data.enabledTools.includes('edit_file'));
 store.data.enabledTools=['workspace_info'];store.save();store=new Store(root);assert.deepEqual(store.data.enabledTools,['workspace_info']);
});
test('advertised schema rejects missing, wrong-type, unknown and out-of-range arguments before approval',async()=>{
 let reviews=0;const context={root:'/tmp',approve:async()=>{reviews++;return true;}};
 for(const [name,args]of [['http_request',{}],['browser_action',{session_id:'x',ref:'x',action:'delete'}],['web_search',{query:'jhye.dev',limit:20}],['read_file',{path:4}],['write_file',{path:'x',content:'x',unknown:true}]])await assert.rejects(executeTool(name,args,context),/required|must be|range|supported argument/);
 assert.equal(reviews,0);
});
test('a declined action ends tool execution for the turn, including already generated follow-up mutations',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-decline-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const store=new Store(path.join(root,'state'));store.addProject(root);store.data.model='fixture';store.data.enabledTools=['write_file'];let requests=0,reviews=0;
 await runAgent({store,prompt:'Write two files',details:{capabilities:['tools']},signal:new AbortController().signal,emit:()=>{},approve:async()=>{reviews++;return false;},fetcher:async(_url,request)=>{
  const body=JSON.parse(request.body);requests++;
  if(requests===1)return new Response(JSON.stringify({done:true,message:{content:'',tool_calls:['one','two'].map(path=>({function:{name:'write_file',arguments:{path,content:'declined'}}}))}}));
  assert.equal(body.tools,undefined);return new Response(JSON.stringify({done:true,message:{content:'The edit was declined; neither file was created.'}}));
 }});assert.equal(reviews,1);for(const file of ['one','two'])await assert.rejects(fs.stat(path.join(root,file)));
});
test('three identical failed calls receive a conclusion request without an unbounded retry loop',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-failure-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const store=new Store(path.join(root,'state'));store.addProject(root);store.data.model='fixture';store.data.enabledTools=['read_file'];let requests=0;
 await runAgent({store,prompt:'Read absent.txt',details:{capabilities:['tools']},signal:new AbortController().signal,emit:()=>{},approve:async()=>true,fetcher:async(_url,request)=>{
  const body=JSON.parse(request.body);requests++;
  if(requests<=3)return new Response(JSON.stringify({done:true,message:{content:'',tool_calls:[{function:{name:'read_file',arguments:{path:'absent.txt'}}}]}}));
  assert.equal(body.tools,undefined);assert.match(body.messages[0].content,/failed three times/);return new Response(JSON.stringify({done:true,message:{content:'The file does not exist.'}}));
 }});assert.equal(requests,4);assert.equal(store.session().messages.filter(m=>m.role==='tool').length,3);
});
test('search results about CAPTCHA are evidence, not a challenge false positive',async()=>{
 const result=JSON.parse(await executeNetwork('web_search',{query:'jhye.dev captcha'},{approve:async()=>true,fetcher:async()=>new Response('<a class="result__a" href="https://jhye.dev/">CAPTCHA research</a><a class="result__snippet" href="https://jhye.dev/">How CAPTCHA works</a>')}));assert.equal(result.state,'completed');assert.equal(result.results[0].title,'CAPTCHA research');
});
test('a large MCP catalog can discover one later tool without loading every schema or enabling a disabled tool',()=>{
 const {loadNamed}=require('../app/tool-catalog.cjs');const external=Array.from({length:80},(_,i)=>({function:{name:'mcp_fixture_'+i,parameters:{type:'object',properties:{}}}}));const available=[...definitions,...external];
 const initial=loadCategory(available,'external');assert.equal(initial.filter(t=>t.function.name.startsWith('mcp_')).length,8);const later=loadNamed(available,'mcp_fixture_79');assert.ok(names(later).includes('mcp_fixture_79'));assert.ok(later.length<=2);assert.throws(()=>loadNamed(available,'mcp_disabled'),/not enabled/);
});
test('a bare nominated domain loads web schemas without requiring an at-mention',()=>{
 assert.ok(names(initialTools(definitions,'Read jhye.dev and follow its Work page',[])).includes('browser_open'));
});
test('controller cleanup requires a closure request and respects keeping a session open',()=>{
 const {browserCloseRequested}=require('../app/tool-intent.cjs');assert.equal(browserCloseRequested('Close the browser session'),true);assert.equal(browserCloseRequested('@browser_open Open jhye.dev and browser_close when finished'),true);assert.equal(browserCloseRequested('What does browser_close do?'),false);assert.equal(browserCloseRequested('Read the browser page and do not close the session'),false);assert.equal(browserCloseRequested('Keep the browser session open'),false);
});
test('bounded page text exposes a real continuation offset for evidence omitted from model context',()=>{
 const source={session_id:'one',snapshot_id:'two',url:'https://jhye.dev/work/',offset:0,next_offset:8000,total_characters:8000,more:false,text:'real project evidence '.repeat(380)};
 const excerpt=JSON.parse(boundedToolResult(JSON.stringify(source),2000));assert.equal(excerpt.more,true);assert.equal(excerpt.next_offset,excerpt.text.length);assert.ok(excerpt.text.length<source.text.length);assert.equal(source.more,false);assert.equal(source.next_offset,8000);
});
test('idle context previews use bounded evidence while retaining full original chat history',()=>{
 const {previewHistory}=require('../app/agent.cjs');const {usage}=require('../app/memory.cjs');
 const messages=[{role:'user',content:'Read the website'}];for(let i=0;i<6;i++){messages.push({role:'assistant',content:'',tool_calls:[{function:{name:'browser_read',arguments:{session_id:'one'}}}]},{role:'tool',tool_name:'browser_read',content:JSON.stringify({session_id:'one',text:'live evidence '.repeat(4000),url:'https://jhye.dev/',next_offset:56000})});}messages.push({role:'assistant',content:'Read actual evidence.'});
 const original=JSON.stringify(messages),preview=previewHistory(messages,[],8192,'App context '.repeat(500));assert.ok(usage(preview,[],8192).used<=usage(preview,[],8192).inputLimit);assert.ok(JSON.stringify(preview).length<original.length*.15);assert.equal(JSON.stringify(messages),original);
});
