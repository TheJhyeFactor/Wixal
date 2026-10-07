"""Eight control tests against two disposable loopback HTTP fixtures only."""
import asyncio
import html
import json
import secrets
import urllib.parse
from .website import assess_website,bounded_request,timestamp

class WebsiteFixture:
    def __init__(self,hardened):
        self.hardened=hardened
        self.token=secrets.token_hex(24)
        self.valid=True
        self.writes=0
        self.attempts={}
        self.writers=set()
        self.tasks=set()
        self.origin=None
        self.server=None
    async def __aenter__(self):
        self.server=await asyncio.start_server(self.handle,'127.0.0.1',0,limit=65536)
        self.origin=f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}'
        return self
    async def __aexit__(self,*args):
        self.server.close();await self.server.wait_closed()
        for writer in list(self.writers): writer.close()
        current=asyncio.current_task()
        tasks=[task for task in self.tasks if task is not current]
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        self.token='';self.valid=False;self.attempts.clear()
    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task);self.writers.add(writer)
        try:
            async with asyncio.timeout(5):
                raw=await reader.readuntil(b'\r\n\r\n')
                lines=raw.decode('iso-8859-1').split('\r\n')
                method,target,_=lines[0].split(' ',2)
                headers=dict((k.strip().lower(),v.strip()) for line in lines[1:] if ':' in line for k,v in [line.split(':',1)])
                parts=urllib.parse.urlsplit(target)
                query=urllib.parse.parse_qs(parts.query)
                authenticated=headers.get('cookie')=='lab_session='+self.token and self.valid
                status,content_type,body=200,'application/json',{}
                response_headers={'Cache-Control':'no-store','Connection':'close'}
                if self.hardened: response_headers.update({'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
                if parts.path=='/api/admin':
                    status=401 if self.hardened and not authenticated else 200;body={'labOnly':True}
                elif parts.path=='/write':
                    if not authenticated: status=401
                    elif self.hardened and headers.get('origin')!=self.origin: status=403
                    else: self.writes+=1;body={'writes':self.writes}
                elif parts.path=='/logout':
                    if self.hardened: self.valid=False
                elif parts.path=='/login':
                    address=writer.get_extra_info('peername')[0]
                    key=address if self.hardened else headers.get('x-forwarded-for',address)
                    count=self.attempts.get(key,0);self.attempts[key]=count+1;status=429 if count>=8 else 401
                elif parts.path in ('/.env','/.git/HEAD'):
                    if self.hardened: status=404
                    else:
                        content_type='text/plain';body='LAB_SECRET=SYNTHETIC_CANARY_ONLY' if parts.path=='/.env' else 'ref: refs/heads/lab'
                elif query.get('next') and not self.hardened:
                    status=302;response_headers['Location']=query['next'][0];body=''
                else:
                    content_type='text/html'
                    value=query.get('wixal_probe',[''])[0]
                    mode='hardened' if self.hardened else 'vulnerable'
                    body=f'<html><title>Wixal {mode} lab</title><body>{html.escape(value) if self.hardened else value}</body></html>'
                body=(json.dumps(body) if content_type=='application/json' else body).encode()
                response_headers.update({'Content-Type':content_type,'Content-Length':str(len(body))})
                labels={200:'OK',302:'Found',401:'Unauthorized',403:'Forbidden',404:'Not Found',429:'Too Many Requests'}
                writer.write((f'HTTP/1.1 {status} {labels[status]}\r\n'+''.join(f'{k}: {v}\r\n' for k,v in response_headers.items())+'\r\n').encode()+body)
                await writer.drain()
        except (OSError,ValueError,asyncio.IncompleteReadError): pass
        finally:
            writer.close()
            try: await writer.wait_closed()
            except (OSError,asyncio.CancelledError): pass
            self.writers.discard(writer);self.tasks.discard(task)


async def simulate_website(browser_probe=None,on_case=lambda *_:None):
    cases=[];started=timestamp()
    async with asyncio.timeout(120):
        for hardened in (False,True):
            mode='hardened' if hardened else 'vulnerable'
            def record(case_id,defended,evidence):
                expected=defended if hardened else not defended
                row=dict(id=case_id,fixture=mode,status='expected-result' if expected else 'unexpected-result',defenseHeld=bool(defended),evidence=evidence)
                cases.append(row);on_case(row)
            async with WebsiteFixture(hardened) as fixture:
                report=await assess_website(dict(url=fixture.origin,profile='probes',max_pages=1,protected_paths=['/api/admin']),delay=0)
                for case_id in ('frame-protection','reflection-canary','sensitive-file-exposure','open-redirect','unauthenticated-access'):
                    observed=any(f['id']==case_id for f in report['findings'])
                    record(case_id,not observed,dict(findingObserved=observed))
                cookie={'Cookie':'lab_session='+fixture.token}
                csrf=await bounded_request(fixture.origin+'/write',method='POST',headers={**cookie,'Origin':'https://wixal-attacker.invalid'})
                record('cross-origin-write',csrf['status']==403,dict(status=csrf['status'],writes=fixture.writes))
                statuses=[]
                for _ in range(9):
                    response=await bounded_request(fixture.origin+'/login',method='POST',headers={'X-Forwarded-For':'198.51.100.9'})
                    statuses.append(response['status'])
                spoof=await bounded_request(fixture.origin+'/login',method='POST',headers={'X-Forwarded-For':'198.51.100.10'})
                record('forwarded-header-throttle',spoof['status']==429,dict(statuses=statuses,spoofedHeaderStatus=spoof['status']))
                await bounded_request(fixture.origin+'/logout',method='POST',headers=cookie)
                replay=await bounded_request(fixture.origin+'/api/admin',headers=cookie)
                record('logout-replay',replay['status']==401,dict(status=replay['status']))
                if browser_probe:
                    payload='<script>document.body.append("WIXAL_XSS_EXECUTED")</script>'
                    target=fixture.origin+'/?'+urllib.parse.urlencode({'wixal_probe':payload})
                    result=await browser_probe(target)
                    text=result.get('text','')
                    record('browser-script-execution','WIXAL_XSS_EXECUTED' not in text or '<script>' in text,dict(visibleText=text[:300],scriptExecuted=text.strip()=='WIXAL_XSS_EXECUTED'))
    return dict(schema=1,target='disposable loopback fixtures',profile='attack-simulation',started=started,finished=timestamp(),cases=cases,findings=[],references={},
                summary=dict(cases=len(cases),expected=sum(c['status']=='expected-result' for c in cases),unexpected=sum(c['status']=='unexpected-result' for c in cases)),
                limitations=['These are deliberately vulnerable and hardened local fixtures, not findings about a production website.','Synthetic session tokens and canary secrets only. No external target or credentials are used.'])


def simulation_markdown(report):
    rows='\n'.join(f"| {c['id']} | {c['fixture']} | {c['defenseHeld']} | {c['status']} | {json.dumps(c['evidence']).replace('|',chr(92)+'|')} |" for c in report['cases'])
    return '# Wixal website attack simulations\n\n'+'\n\n'.join(report['limitations'])+'\n\n| Test | Fixture | Defense held | Validation | Evidence |\n| --- | --- | --- | --- | --- |\n'+rows+f"\n\n{report['summary']['expected']}/{report['summary']['cases']} expected results; {report['summary']['unexpected']} unexpected results.\n"
