const { chromium }=require('playwright'),http=require('node:http'),fs=require('node:fs/promises'),path=require('node:path');
(async()=>{
 const target=process.argv[2],out=process.argv[3]; if(!target||!out)throw Error('Usage: node scripts/website-browser-assess.cjs https://authorised.site /report/prefix');
 const origin=new URL(target);if(origin.protocol!=='https:'||origin.username||origin.password)throw Error('Use an authorised HTTPS origin.');
 const browser=await chromium.launch({channel:'chrome',headless:true}); const context=await browser.newContext({viewport:{width:1280,height:900}}); const cases=[];
 const htmlEscape=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const framePaths=['/','/privileged/login/'];
 const server=http.createServer((_req,res)=>{res.setHeader('Content-Type','text/html');res.end(`<html><title>Wixal framing simulation</title><style>body{background:#18191d;color:#eee;font:16px system-ui;padding:24px}iframe{background:white;width:47%;height:650px;border:2px solid #e9a5bd;margin-right:2%}p{color:#bbb}</style><h1>Cross-origin framing simulation</h1><p>Local test page embedding the authorised site. No overlay, interaction or authentication.</p>${framePaths.map(p=>`<iframe title="${htmlEscape(p)}" src="${htmlEscape(new URL(p,origin).href)}"></iframe>`).join('')}</html>`);});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
  const page=await context.newPage(); await page.goto('http://127.0.0.1:'+server.address().port,{waitUntil:'load',timeout:20000});
  for(const route of framePaths){const frame=page.frames().find(f=>f.url()===new URL(route,origin).href);let heading=null;try{heading=await frame?.locator('h1').first().textContent({timeout:5000});}catch{}
   cases.push({id:'cross-origin-framing',target:new URL(route,origin).href,status:heading?'reproduced':'not-reproduced',evidence:{frameLoaded:!!heading,heading,authenticated:false,interaction:false,impact:'Framing capability only; no malicious user interaction demonstrated'}});
  }
  await fs.mkdir(path.dirname(out),{recursive:true});await page.screenshot({path:out+'-framing.png',fullPage:true});
  const probePage=await context.newPage();const payload='<script>globalThis.__wixalAttackProof="BENIGN_CANARY"</script>';
  for(const route of ['/','/privileged/story/']){
   const url=new URL(route,origin);url.searchParams.set(route.includes('story')?'slug':'wixal_probe',payload);
   let loadError=null;try{await probePage.goto(url.href,{waitUntil:'load',timeout:20000});}catch(e){loadError=e.message.split('\n')[0];}
   await probePage.waitForTimeout(1500);
   const proof=await probePage.evaluate(()=>({executed:globalThis.__wixalAttackProof==='BENIGN_CANARY',title:document.title}));
   cases.push({id:'browser-query-xss-canary',target:url.href,status:proof.executed?'reproduced':loadError?'inconclusive':'not-reproduced',evidence:{...proof,loadError}});
  }
  await fs.writeFile(out+'.json',JSON.stringify({target:origin.origin,finished:new Date().toISOString(),cases,scope:'Fresh anonymous browser context; local attacker page; no form submission or overlays.'},null,2)+'\n',{mode:0o600});cases.forEach(c=>console.log(c.status+' '+c.id+' '+c.target));
 }finally{await context.close();await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
