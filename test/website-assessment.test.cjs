const test = require('node:test'), assert = require('node:assert/strict'), http = require('node:http');
const { websitePlan, assessWebsite, cookieEvidence, markdownReport, boundedBody } = require('../app/website-assessment.cjs');
const { executeTool } = require('../app/tools.cjs');
test('website assessment validates a single origin, bounded crawl and explicit protected paths', () => {
 for (const url of ['file:///etc/passwd','https://user:pass@example.test/','https://example.test/?token=secret','https://example.test/#secret']) assert.throws(()=>websitePlan({url}));
 for (const protected_paths of [['//other.test/private'],['/private\\evil'],['/private?secret=1']]) assert.throws(()=>websitePlan({url:'https://example.test',protected_paths}));
 assert.throws(()=>websitePlan({url:'https://example.test',max_pages:13}));
 assert.throws(()=>websitePlan({url:'https://example.test',profile:'attack-all'}));
 assert.equal(websitePlan({url:'https://example.test'}).profile,'baseline');
});
test('GET-only website probes detect vulnerable fixtures and never retain secrets or follow other origins',async t=>{
 const hits=[];
 const server=http.createServer((req,res)=>{hits.push(req.url);const url=new URL(req.url,'http://localhost');
  if(url.pathname==='/.env'){res.setHeader('Content-Type','text/plain');return res.end('API_SECRET=DO_NOT_RETAIN_FIXTURE_SECRET');}
  if(url.pathname==='/.git/HEAD')return res.end('ref: refs/heads/main\n');
  if(url.pathname==='/redirect'){res.writeHead(302,{Location:'https://out-of-scope.invalid/'});return res.end();}
  if(url.pathname==='/api/admin'){res.writeHead(401,{'Content-Type':'application/json','Cache-Control':'no-store'});return res.end('{"error":"Sign in"}');}
  if(url.searchParams.has('next')){res.writeHead(302,{Location:url.searchParams.get('next')});return res.end();}
  res.setHeader('Content-Type','text/html');res.setHeader('Set-Cookie','fixture=DO_NOT_RETAIN_COOKIE; HttpOnly; SameSite=Strict; Path=/');res.end('<html><a href="/redirect">Redirect</a><a href="https://external.invalid/">External</a>'+ (url.searchParams.get('wixal_probe')||'')+'</html>');
 }); await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>new Promise(r=>server.close(r)));
 const url='http://127.0.0.1:'+server.address().port+'/';
 const report=await assessWebsite({url,profile:'probes',protected_paths:['/api/admin']},{delayMs:0});
 assert.ok(report.findings.some(f=>f.id==='sensitive-file-exposure'&&f.severity==='high'));
 assert.ok(report.findings.some(f=>f.id==='reflection-canary'&&f.confidence.includes('unverified')));
 assert.ok(report.findings.some(f=>f.id==='open-redirect'));assert.ok(report.cases.some(c=>c.id==='unauthenticated-access'&&c.status==='pass'));
 assert.ok(report.cases.some(c=>c.id==='redirect-scope'&&c.status==='not-followed'));
 assert.ok(report.requests.every(r=>new URL(r.url).origin===new URL(url).origin));
 assert.doesNotMatch(JSON.stringify(report)+markdownReport(report),/DO_NOT_RETAIN/);assert.ok(report.requests.length<=36);
 assert.ok(hits.some(p=>p.startsWith('/?wixal_probe=')));
});
test('security headers pass when effective and public CORS does not imply credential exposure',async()=>{
 const report=await assessWebsite({url:'https://protected.test/',max_pages:1,protected_paths:['/api/admin']},{delayMs:0,fetcher:async(url,options)=>{
  assert.equal(options.method,'GET');assert.equal(options.redirect,'manual');assert.equal(options.credentials,'omit');
  return new Response(url.includes('/api/admin')?'{}':'<html>Safe</html>',{status:url.includes('/api/admin')?401:200,headers:{'content-type':url.includes('/api/admin')?'application/json':'text/html','content-security-policy':"default-src 'self'; frame-ancestors 'none'",'strict-transport-security':'max-age=63072000','x-content-type-options':'nosniff','referrer-policy':'strict-origin-when-cross-origin','access-control-allow-origin':'*'}});
 }});
 assert.equal(report.findings.length,0);assert.ok(report.cases.some(c=>c.id==='credentialed-cors'&&c.status==='pass'));
});
test('response limits, failed requests and cancellation are explicit',async()=>{
 const bounded=await boundedBody(new Response('A'.repeat(3000)),512);assert.equal(bounded.bytes,512);assert.equal(bounded.truncated,true);
 const report=await assessWebsite({url:'https://unavailable.test/'},{fetcher:async()=>{throw new Error('fixture unavailable');},delayMs:0});assert.equal(report.summary.errors,1);
 const c=new AbortController();c.abort();await assert.rejects(assessWebsite({url:'https://example.test'},{signal:c.signal,fetcher:async()=>assert.fail('cancelled assessment made a request')}),/stopped|timed/);
 assert.deepEqual(cookieEvidence(['session=secret; HttpOnly; Secure; SameSite=Strict; Path=/']),[{name:'session',httpOnly:true,secure:true,sameSite:'Strict',path:'/'}]);
});
test('disabled website tools cannot run',async()=>{
 await assert.rejects(executeTool('website_assess',{url:'https://example.test'},{allowedTools:[]}),/switched off/);
});
test('local simulations reproduce seeded weaknesses and hardened controls without external targets',async()=>{
 const {simulateWebsite}=require('../app/website-simulation.cjs');const report=await simulateWebsite();
 assert.equal(report.summary.cases,16);assert.equal(report.summary.unexpected,0);
 assert.ok(report.cases.some(c=>c.id==='logout-replay'&&c.fixture==='vulnerable'&&!c.defenseHeld));
 assert.ok(report.cases.some(c=>c.id==='logout-replay'&&c.fixture==='hardened'&&c.defenseHeld));
 assert.match(report.limitations[0],/not findings about a production/);
});
test('native website results return grouped evidence, passed controls and remediation without requiring raw report rereads',async t=>{
 const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');const root=await fs.mkdtemp(path.join(os.tmpdir(),'wixal-website-digest-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const result=JSON.parse(await executeTool('website_assess',{url:'https://digest.test/',max_pages:2,protected_paths:['/api/admin'],report_prefix:'proof'},{root,approve:async()=>true,allowedTools:['website_assess'],fetcher:async url=>new Response(url.includes('/api/admin')?'{}':'<html><a href="/other/">Other</a></html>',{status:url.includes('/api/admin')?401:200,headers:{'content-type':url.includes('/api/admin')?'application/json':'text/html','strict-transport-security':'max-age=63072000','cache-control':'no-store'}})}));
 assert.equal(result.findings.find(f=>f.id==='frame-protection').occurrences,2);assert.match(result.findings[0].remediation,/frame-ancestors/);
 assert.equal(result.checks.find(c=>c.id==='unauthenticated-access').example.evidence.status,401);assert.equal(result.checks.find(c=>c.id==='https-hsts').count,2);
 assert.deepEqual(result.protectedPaths,['/api/admin']);assert.ok(result.limitations.length);assert.equal(result.reports.json,'proof.json');
 assert.equal(JSON.parse(await fs.readFile(path.join(root,'proof.json'),'utf8')).summary.requests,result.summary.requests);
 const {boundedToolResult}=require('../app/agent.cjs');const excerpt=JSON.parse(boundedToolResult(JSON.stringify(result),500));assert.ok(JSON.stringify(excerpt).length <= 500);assert.equal(excerpt.context_excerpt,true);assert.deepEqual(excerpt.reports,result.reports);assert.deepEqual(excerpt.summary,result.summary);
});
