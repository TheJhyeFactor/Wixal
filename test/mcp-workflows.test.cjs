const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {Extensions}=require('../app/extensions.cjs');
async function server(t,mode){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-mcp-workflows-'));const extensions=new Extensions();t.after(async()=>{await extensions.close();await fs.rm(root,{recursive:true,force:true});});
 const file=path.join(root,'server.cjs'),sdk=path.resolve(__dirname,'../node_modules/@modelcontextprotocol/sdk/dist/cjs');
 await fs.writeFile(file,`const {Server}=require(${JSON.stringify(sdk+'/server/index.js')}); const {StdioServerTransport}=require(${JSON.stringify(sdk+'/server/stdio.js')}); const {ListToolsRequestSchema,CallToolRequestSchema}=require(${JSON.stringify(sdk+'/types.js')});const mode=${JSON.stringify(mode)};const s=new Server({name:'fixture',version:'1'},{capabilities:{tools:{}}}); const tool=name=>({name,inputSchema:{type:'object',properties:{text:{type:'string'},delay:{type:'integer',minimum:0,maximum:2000}},required:['text'],additionalProperties:false}});s.setRequestHandler(ListToolsRequestSchema,async r=>mode==='duplicate'?{tools:[tool('echo'),tool('echo')]}:mode==='repeat'?{tools:[],nextCursor:'again'}:mode==='overflow'?{tools:Array.from({length:81},(_,i)=>tool('tool'+i))}:r.params.cursor?{tools:[tool('second')]}:{tools:[tool('echo')],nextCursor:'second-page'});s.setRequestHandler(CallToolRequestSchema,async r=>{if(r.params.arguments.delay)await new Promise(resolve=>setTimeout(resolve,r.params.arguments.delay));return r.params.arguments.text==='failure'?{isError:true,content:[{type:'text',text:'fixture failure'}]}:r.params.arguments.text==='image'?{content:[{type:'image',data:'aW1hZ2U=',mimeType:'image/png'}]}:{content:[{type:'text',text:r.params.arguments.text}]};});s.connect(new StdioServerTransport());`);
 return {extensions,root,config:{id:'fixture-'+mode,name:'Fixture',command:process.execPath,args:[file]}};
}
test('real MCP paginated catalog, schema validation, server errors, artifact labels and cancellation',async t=>{
 const {extensions,root,config}=await server(t,'pages');await extensions.connect(config,root);assert.equal(extensions.definitions().length,2);const name=extensions.definitions()[0].function.name;
 let approvals=0;const context={allowedTools:[name],approve:async()=>{approvals++;return true;}};
 await assert.rejects(extensions.execute(name,{text:42},context),/must be string/);assert.equal(approvals,0);
 assert.equal(await extensions.execute(name,{text:'real MCP proof'},context),'real MCP proof');
 assert.equal(await extensions.execute(name,{text:'failure'},context),'Error: fixture failure');assert.match(await extensions.execute(name,{text:'image'},context),/image result omitted/);
 const abort=new AbortController();const pending=extensions.execute(name,{text:'cancelled',delay:1000},{...context,signal:abort.signal});setTimeout(()=>abort.abort(),100);await assert.rejects(pending);
 await extensions.disconnect(config.id);assert.deepEqual(extensions.definitions(),[]);await assert.rejects(extensions.execute(name,{text:'after disconnect'},context),/disconnected/);
});
for(const mode of ['duplicate','repeat','overflow'])test(`MCP rejects ${mode} catalog and cleans up its process`,async t=>{
 const {extensions,root,config}=await server(t,mode);await assert.rejects(extensions.connect(config,root),mode==='duplicate'?/duplicate/:mode==='repeat'?/repeated/:/80 tools/);assert.deepEqual(extensions.snapshot(),[]);
});
