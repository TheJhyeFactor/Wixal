"""Bounded unauthenticated website checks with redacted, reviewed project evidence."""
import asyncio
import hashlib
import json
import re
import secrets
import ssl
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from .tools import safe_path

REFERENCES={
    'headers':'https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html',
    'framing':'https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/11-Client-side_Testing/09-Testing_for_Clickjacking',
    'xss':'https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/01-Testing_for_Reflected_Cross_Site_Scripting'}
HEADER_NAMES=('content-security-policy','x-frame-options','strict-transport-security','x-content-type-options','referrer-policy',
    'permissions-policy','cache-control','access-control-allow-origin','access-control-allow-credentials','location')


def timestamp(): return datetime.now(timezone.utc).isoformat()
def origin(url):
    parsed=urllib.parse.urlsplit(url)
    return parsed.scheme,parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80)


def website_plan(args):
    if not isinstance(args,dict) or not isinstance(args.get('url'),str): raise ValueError('Supply the authorised HTTP(S) website URL')
    parsed=urllib.parse.urlsplit(args['url'])
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an authorised HTTP(S) URL without credentials, query or fragment')
    if any(c in args['url'] for c in '\r\n'): raise ValueError('Invalid website URL')
    profile=args.get('profile','baseline')
    if profile not in ('baseline','probes'): raise ValueError('Choose baseline or probes')
    max_pages=args.get('max_pages',8)
    if type(max_pages)!=int or not 1<=max_pages<=12: raise ValueError('Assess 1–12 pages per run')
    paths=args.get('protected_paths',[])
    if not isinstance(paths,list) or len(paths)>8 or any(not isinstance(p,str) or len(p)>300 or not p.startswith('/') or p.startswith('//') or re.search(r'[\\?#\r\n]',p) or origin(urllib.parse.urljoin(args['url'],p))!=origin(args['url']) for p in paths):
        raise ValueError('Protected paths must be up to eight same-origin absolute paths without queries')
    base=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path or '/','',''))
    return dict(url=base,origin=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,'','','')),profile=profile,maxPages=max_pages,
                protectedPaths=paths,requestLimit=36,timeoutSeconds=120)


def cookie_evidence(values):
    result=[]
    for value in values:
        same=re.search(r';\s*samesite=(\w+)',value,re.I);path=re.search(r';\s*path=([^;]+)',value,re.I)
        result.append(dict(name=value.split('=',1)[0],httpOnly=bool(re.search(r';\s*httponly(?:;|$)',value,re.I)),secure=bool(re.search(r';\s*secure(?:;|$)',value,re.I)),sameSite=same[1] if same else None,path=path[1] if path else None))
    return result


async def bounded_request(url,method='GET',headers=None,limit=512*1024):
    """No redirects/cookies. Cancellation closes the active connection; body is bounded."""
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or any(c in url for c in '\r\n'):
        raise ValueError('Invalid HTTP(S) URL')
    writer=None
    async with asyncio.timeout(10):
        try:
            context=ssl.create_default_context() if parsed.scheme=='https' else None
            reader,writer=await asyncio.open_connection(parsed.hostname,parsed.port or (443 if context else 80),ssl=context,limit=1024*1024)
            path=urllib.parse.urlunsplit(('','',parsed.path or '/',parsed.query,''))
            request_headers={'Host':parsed.netloc,'User-Agent':'Wixal-Website-Assessment/0.7','Connection':'close',**(headers or {})}
            if method=='POST': request_headers['Content-Length']='0'
            if any('\r' in str(k)+str(v) or '\n' in str(k)+str(v) for k,v in request_headers.items()): raise ValueError('Invalid HTTP header')
            writer.write((f'{method} {path} HTTP/1.1\r\n'+''.join(f'{k}: {v}\r\n' for k,v in request_headers.items())+'\r\n').encode())
            await writer.drain()
            raw_headers=await reader.readuntil(b'\r\n\r\n')
            if len(raw_headers)>65536: raise ValueError('Response headers exceed their bound')
            lines=raw_headers.decode('iso-8859-1').split('\r\n');status=int(lines[0].split()[1]);response_headers={};cookies=[]
            for line in lines[1:]:
                if ':' not in line: continue
                key,value=line.split(':',1);key=key.strip().lower();value=value.strip()
                if key=='set-cookie': cookies.append(value)
                else: response_headers[key]=value
            data=bytearray();truncated=False
            if 'chunked' in response_headers.get('transfer-encoding','').lower():
                while True:
                    raw=await reader.readline()
                    if not raw: raise ValueError('Response ended inside chunk framing')
                    count=int(raw.split(b';',1)[0].strip(),16)
                    if not count: break
                    room=limit+1-len(data)
                    if count>room:
                        data.extend(await reader.readexactly(max(0,room)));truncated=True;break
                    data.extend(await reader.readexactly(count))
                    if await reader.readexactly(2)!=b'\r\n': raise ValueError('Invalid HTTP chunk framing')
                    if len(data)>limit: truncated=True;break
            else:
                count=int(response_headers['content-length']) if response_headers.get('content-length','').isdigit() else None
                while len(data)<=limit and (count is None or len(data)<count):
                    part=await reader.read(min(65536,limit+1-len(data)))
                    if not part: break
                    data.extend(part)
                truncated=len(data)>limit or count is not None and count>limit
            text=bytes(data[:limit]).decode('utf-8',errors='replace')
            return dict(url=url,method=method,status=status,contentType=response_headers.get('content-type'),bytes=min(len(data),limit),
                        truncated=truncated,bodySha256=hashlib.sha256(text.encode()).hexdigest(),body=text,
                        headers={h:response_headers.get(h) for h in HEADER_NAMES},cookies=cookie_evidence(cookies))
        finally:
            if writer:
                writer.close()
                try: await writer.wait_closed()
                except (OSError,asyncio.CancelledError): pass


async def assess_website(args,on_case=lambda *_:None,delay=.2):
    plan=website_plan(args);started=timestamp();cases=[];findings=[];requests=[];pages=[];seen=set();queue=[plan['url']]
    def check(case_id,status,target,evidence):
        row=dict(id=case_id,status=status,target=target,evidence=evidence);cases.append(row);on_case(row)
    def finding(fid,severity,title,target,evidence,remediation,confidence='confirmed configuration'):
        findings.append(dict(id=fid,severity=severity,title=title,url=target,evidence=evidence,remediation=remediation,confidence=confidence))
    async def request(target,headers=None):
        if origin(target)!=origin(plan['url']): raise ValueError('Assessment request left the authorised origin')
        if len(requests)>=plan['requestLimit']: raise ValueError('Assessment request limit reached')
        if requests and delay: await asyncio.sleep(delay)
        try: result=await bounded_request(target,headers=headers)
        except Exception as error:
            requests.append(dict(url=target,method='GET',error=str(error)));raise
        requests.append({k:v for k,v in result.items() if k!='body'})
        return result
    async with asyncio.timeout(plan['timeoutSeconds']):
        while queue and len(pages)<plan['maxPages']:
            target=queue.pop(0)
            if target in seen: continue
            seen.add(target)
            try:
                r=await request(target);pages.append(target);h=r['headers']
                check('http-response','observed' if r['status']<400 else 'needs-review',target,dict(status=r['status'],bytes=r['bytes'],truncated=r['truncated']))
                if 300<=r['status']<400:
                    location=urllib.parse.urljoin(target,h.get('location') or '')
                    if origin(location)==origin(plan['url']) and not urllib.parse.urlsplit(location).query: queue.insert(0,location)
                    else: check('redirect-scope','not-followed',target,dict(location=location))
                    continue
                if r['status']!=200 or 'text/html' not in (r['contentType'] or ''): continue
                csp=h['content-security-policy'] or '';meta=bool(re.search(r'<meta\s[^>]*http-equiv\s*=\s*[\"\']?content-security-policy',r['body'],re.I))
                framed=bool(re.search(r"(?:^|;)\s*frame-ancestors\s+(?:'none'|'self')\s*(?:;|$)",csp,re.I)) or (h['x-frame-options'] or '').lower() in ('deny','sameorigin')
                check('frame-protection','pass' if framed else 'fail',target,dict(csp=csp or None,xFrameOptions=h['x-frame-options']))
                if not framed: finding('frame-protection','medium','Page has no restrictive frame protection',target,'No restrictive frame-ancestors or DENY/SAMEORIGIN response header observed. Browser impact requires a framing test.',"Set Content-Security-Policy: frame-ancestors 'none' on HTML responses.")
                check('content-security-policy','observed' if csp or meta else 'missing',target,dict(responsePolicy=csp or None,metaPolicy=meta))
                if not csp and not meta: finding('content-security-policy','low','Content Security Policy is absent',target,'No enforced response-header or meta CSP observed. This alone does not establish XSS.','Validate a policy for actual script/style/image sources, starting with Report-Only.')
                for header,expected in (('x-content-type-options','nosniff'),('referrer-policy',None)):
                    present=(h[header] or '').lower()==expected if expected else bool(h[header]);check(header,'pass' if present else 'missing',target,h[header])
                    if not present: finding(header,'low','Missing or ineffective '+header,target,'Observed value: '+(h[header] or '(absent)'),'Set an explicit '+header+' response policy.')
                check('https-hsts','pass' if target.startswith('https:') and re.search(r'max-age=[1-9]\d*',h['strict-transport-security'] or '',re.I) else 'needs-review',target,dict(protocol=urllib.parse.urlsplit(target).scheme,hsts=h['strict-transport-security']))
                for cookie in r['cookies']:
                    if not cookie['httpOnly'] or target.startswith('https:') and not cookie['secure'] or not cookie['sameSite']:
                        finding('cookie-attributes','needs-triage','A response cookie needs attribute review',target,cookie,'Determine whether this cookie carries a session. Apply HttpOnly, Secure and appropriate SameSite to authentication cookies.','cookie purpose unknown')
                start=urllib.parse.urlsplit(plan['url'])
                for match in re.finditer(r'<a\b[^>]*\bhref=[\"\']([^\"\']+)[\"\']',r['body'],re.I):
                    link=urllib.parse.urljoin(target,match[1].replace('&amp;','&'));parts=urllib.parse.urlsplit(link)
                    if origin(link)==origin(plan['url']) and not parts.query and not parts.fragment and (start.path=='/' or parts.path.startswith(start.path)) and not re.search(r'\.(png|jpg|pdf|zip|svg|webp)$',parts.path,re.I) and link not in seen and len(queue)<100: queue.append(link)
            except (OSError,ValueError,TimeoutError) as error: check('request-error','error',target,str(error))
        for path in plan['protectedPaths']:
            target=urllib.parse.urljoin(plan['origin'],path)
            try:
                r=await request(target)
                check('unauthenticated-access','pass' if r['status'] in (401,403) else 'needs-review',target,dict(status=r['status'],contentType=r['contentType'],noStore='no-store' in (r['headers']['cache-control'] or '').lower()))
                if r['status']==200 and 'application/json' in (r['contentType'] or ''):
                    finding('unauthenticated-access','needs-triage','Protected path returned JSON without authentication',target,dict(status=r['status'],bodySha256=r['bodySha256']),'Verify whether this response contains protected data or is intentionally public.','protected-path semantics require validation')
                cors=await request(target,{'Origin':'https://wixal-probe.invalid'})
                check('credentialed-cors','fail' if cors['headers']['access-control-allow-origin']=='https://wixal-probe.invalid' and cors['headers']['access-control-allow-credentials']=='true' else 'pass',target,dict(origin=cors['headers']['access-control-allow-origin'],credentials=cors['headers']['access-control-allow-credentials']))
            except (OSError,ValueError,TimeoutError) as error: check('protected-path-error','error',target,str(error))
        if plan['profile']=='probes':
            marker='WIXAL_'+secrets.token_hex(8);payload=f"<script>globalThis.__wixalProbe='{marker}'</script>"
            target=plan['url']+'?'+urllib.parse.urlencode({'wixal_probe':payload})
            try:
                r=await request(target);raw=payload in r['body']
                check('reflection-canary','needs-review' if raw else 'inconclusive' if r['truncated'] else 'no-reflection-observed',target,dict(marker=marker,rawMarkupReflected=raw,truncated=r['truncated']))
                if raw: finding('reflection-canary','needs-triage','Raw canary markup was reflected',target,dict(marker=marker,bodySha256=r['bodySha256']),'Validate HTML context and execution in an isolated browser before claiming XSS.','reflection observed; execution unverified')
            except (OSError,ValueError,TimeoutError) as error: check('reflection-canary','error',target,str(error))
            for path in ('/.env','/.git/HEAD'):
                target=urllib.parse.urljoin(plan['origin'],path)
                try:
                    r=await request(target)
                    signature=bool(re.search(r'^ref: refs/heads/',r['body'],re.M)) if path=='/.git/HEAD' else bool(re.search(r'^(?:[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*)\s*=',r['body'],re.M))
                    exposed=r['status']==200 and signature and 'text/html' not in (r['contentType'] or '')
                    check('sensitive-file-exposure','fail' if exposed else 'inconclusive' if r['truncated'] else 'no-exposure-observed',target,dict(status=r['status'],matchedSignature=signature,bodySha256=r['bodySha256'],truncated=r['truncated']))
                    if exposed: finding('sensitive-file-exposure','high','Sensitive file signature returned over HTTP',target,dict(status=r['status'],bodySha256=r['bodySha256'],contents='REDACTED'),'Remove the file from served assets. Rotate exposed secrets and inspect access logs.')
                except (OSError,ValueError,TimeoutError) as error: check('sensitive-file-exposure','error',target,str(error))
            target=plan['url']+'?'+urllib.parse.urlencode({'next':'https://wixal-probe.invalid/'})
            try:
                r=await request(target);destination=urllib.parse.urljoin(target,r['headers']['location']) if r['headers']['location'] else None
                external=300<=r['status']<400 and destination and origin(destination)==origin('https://wixal-probe.invalid')
                check('open-redirect-canary','fail' if external else 'no-redirect-observed',target,dict(status=r['status'],destination=destination))
                if external: finding('open-redirect','medium','Untrusted next parameter controls an external redirect',target,dict(status=r['status'],destination=destination),'Allow only validated relative or explicitly permitted redirect destinations.')
            except (OSError,ValueError,TimeoutError) as error: check('open-redirect-canary','error',target,str(error))
    return dict(schema=1,target=plan['url'],profile=plan['profile'],started=started,finished=timestamp(),scope=plan,requests=requests,cases=cases,findings=findings,references=REFERENCES,
                limitations=['Unauthenticated GET checks only; no writes or login attempts.','Reflection is not proven code execution. Missing headers are configuration findings.','Same-origin crawl; redirects outside the origin are not followed.','Bodies are hashed, not saved. Cookie values are omitted.'],
                summary=dict(requests=len(requests),pages=len(pages),cases=len(cases),findings=len(findings),errors=sum(c['status']=='error' for c in cases)))


def markdown_report(report):
    def cell(value): return str(value if value is not None else '').replace('|','\\|').replace('\r',' ').replace('\n',' ')
    rows='\n'.join(f"| {cell(f['severity'])} | {cell(f['title'])} | {cell(f['url'])} | {cell(f['confidence'])} |" for f in report['findings']) or '| — | No findings in these checks | — | Limited coverage |'
    details='\n'.join(f"### {f['id']}: {f['title']}\n\nEvidence: {json.dumps(f['evidence'])}\n\nRemediation: {f['remediation']}\n" for f in report['findings'])
    cases='\n'.join(f"| {cell(c['id'])} | {cell(c['status'])} | {cell(c['target'])} | {cell(json.dumps(c['evidence']))} |" for c in report['cases'])
    return f"# Website assessment: {report['target']}\n\nStarted: {report['started']}\n\nFinished: {report['finished']}\n\nProfile: {report['profile']}; {report['summary']['requests']} GET requests; {report['summary']['errors']} request errors.\n\n## Findings\n\n| Severity | Finding | Target | Confidence |\n| --- | --- | --- | --- |\n{rows}\n\n{details}\n## Test cases\n\n| Case | Result | Target | Evidence |\n| --- | --- | --- | --- |\n{cases}\n\n## Limits\n\n"+'\n'.join('- '+s for s in report['limitations'])+'\n'


async def execute_website(tools,name,args,session_id):
    if name=='website_assess': website_plan(args)
    elif name=='website_simulate':
        if set(args)-{'report_prefix','browser'}: raise ValueError('Simulations accept no target. They use disposable loopback fixtures only')
    else: raise ValueError('Unknown website workflow')
    if not await tools.approve(dict(name=name,**args)): return 'User declined this website assessment.'
    def observe(kind, value):
        observer = getattr(tools, 'assessment_observer', None)
        if observer: observer(session_id, kind, value)
    def on_case(case):
        observe('case', case)
        tools.emit('assessment-case',dict(sessionId=session_id,name=name,case=case))
    if name=='website_simulate':
        from .simulation import simulate_website,simulation_markdown
        async def browser_probe(url):
            if not tools.host: raise ValueError('Browser validation requires the native desktop')
            if not await tools.approve(dict(name='browser_inspect',url=url)): raise ValueError('Browser validation declined')
            return await tools.host('browser',dict(name='browser_inspect',args=dict(url=url,max_chars=300,wait_ms=100),owner=session_id))
        report=await simulate_website(browser_probe=browser_probe if args.get('browser') else None,on_case=on_case)
        markdown=simulation_markdown(report);prefix=args.get('report_prefix','website-simulation')
    else:
        report=await assess_website(args,on_case);markdown=markdown_report(report);prefix=args.get('report_prefix','website-assessment')
    # Preserve completed observations even if Stop is pressed during save review.
    observe('report', report)
    root=(tools.store.project() or {}).get('root')
    if root: root=str(Path(root).resolve(strict=True))
    if not isinstance(prefix,str) or not prefix.strip(): raise ValueError('Choose an unused report prefix')
    paths=[safe_path(root,prefix+suffix,True) for suffix in ('.json','.md')]
    if any(path.exists() for path in paths): raise ValueError('Choose an unused report prefix')
    if not await tools.approve(dict(name='save_website_evidence',paths=[str(p) for p in paths],content=markdown)): return dict(report=report,saved=False)
    for path in paths:
        if safe_path(root,str(path.relative_to(Path(root))),True)!=path or path.exists(): raise ValueError('Choose an unused report prefix')
    written=[]
    try:
        for path,content in zip(paths,(json.dumps(report,indent=2),markdown)):
            with path.open('x') as stream: stream.write(content)
            written.append(path)
    except BaseException:
        for path in written: path.unlink(missing_ok=True)
        raise
    return dict(report=report,paths=[str(p) for p in paths],saved=True,summary=report['summary'],findings=report['findings'])
