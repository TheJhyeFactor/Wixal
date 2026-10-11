"""Actual installed WebKit cookie/expiry/logout/disconnect against an owned fixture."""
import argparse,asyncio,hashlib,http.server,json,socket,threading,time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--data',type=Path,required=True,help='Existing disposable guest native workspace; no setup state is inserted')
parser.add_argument('--app',type=Path,required=True,help='Running installed app owning the workspace')
options=parser.parse_args()
BASE=options.output.resolve();DATA=options.data.resolve();APP=options.app.resolve()
class Site(http.server.BaseHTTPRequestHandler):
    ledger=[];valid=False;serial=0;token='';online=True
    def log_message(self,*args):pass
    def response(self,status,body,cookie=None):
        self.send_response(status);self.send_header('Content-Type','text/html');self.send_header('Cache-Control','no-store')
        if cookie:self.send_header('Set-Cookie',cookie)
        payload=body.encode();self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        if not Site.online:
            self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
        authorized=Site.valid and ('wixal_test='+Site.token) in self.headers.get('Cookie','')
        Site.ledger.append(dict(method='GET',path=self.path,authorized=authorized,time=time.time()))
        form='<form method="post" action="/login"><button>Start disposable session</button></form>'
        if authorized:self.response(200,'<h1>AUTHENTICATED_FIXTURE</h1><form method="post" action="/logout"><button>End disposable session</button></form>')
        else:self.response(401,'<h1>AUTH_REQUIRED_FIXTURE</h1>'+form)
    def do_POST(self):
        Site.ledger.append(dict(method='POST',path=self.path,time=time.time()))
        if self.path=='/login':
            Site.serial+=1;Site.token='fixture-'+str(Site.serial);Site.valid=True
            self.response(200,'<h1>AUTHENTICATED_FIXTURE</h1><form method="post" action="/logout"><button>End disposable session</button></form>','wixal_test='+Site.token+'; HttpOnly; SameSite=Strict; Path=/')
        else:
            Site.valid=False;self.response(200,'<h1>LOGGED_OUT_FIXTURE</h1><a href="/private">Check private page</a>','wixal_test=; Max-Age=0; Path=/')
async def main():
    BASE.mkdir(exist_ok=False);(BASE/'acceptance-script.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',started=time.time(),scope='Disposable owned HTTP cookie session in actual installed ephemeral WebKit; no third-party provider/account qualification',cases=[])
    for key,path in [('helperSha256',APP/'Contents/Resources/engine/wixal-engine'),('sourceManifestSha256',APP/'Contents/Resources/SOURCE_MANIFEST.json'),('acceptanceScriptSha256',Path(__file__))]:report[key]=hashlib.sha256(path.read_bytes()).hexdigest()
    reader,writer=await asyncio.open_unix_connection((DATA/'engine.sock').resolve(),limit=32*1024*1024);pending={};counter=0;reviews=[];pages=[];server=None;original=None;validation=None
    def save():report.update(reviews=reviews,ledger=Site.ledger);(BASE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    async def call(method,params=None):
        nonlocal counter
        counter+=1;key='browser-recovery-'+str(counter);future=asyncio.get_running_loop().create_future();pending[key]=future
        writer.write((json.dumps(dict(id=key,method=method,params=params or {}))+'\n').encode());await writer.drain();data=await asyncio.wait_for(future,60)
        if data.get('error'):raise RuntimeError(data['error'])
        return data['result']
    # Respond acknowledgements cannot block the event reader.
    async def read_events():
        while line:=await reader.readline():
            item=json.loads(line);event=item['event'];data=item['data']
            if event=='response':
                future=pending.pop(data['id'],None)
                if future and not future.done():future.set_result(data)
            elif event=='review':
                approved=(data.get('name')=='browser_open' and str(data.get('url','')).startswith(origin+'/')) or (data.get('name')=='browser_action' and data.get('session_id') in pages)
                reviews.append(dict(name=data.get('name'),approved=approved))
                asyncio.create_task(call('respond',dict(id=data['id'],value=approved)))
    async def tool(name,args):
        result=await call('tool',dict(name=name,arguments=args))
        report.setdefault('observations',[]).append(dict(name=name,result=result))
        return result
    def start(port):
        s=http.server.ThreadingHTTPServer(('127.0.0.1',port),Site);threading.Thread(target=s.serve_forever,daemon=True).start();return s
    async def open_page(existing=None):
        result=await tool('browser_open',dict(url=origin+'/private',interactive=True,**({'session_id':existing} if existing else {})))
        if result['session_id'] not in pages:pages.append(result['session_id'])
        return result
    async def click(page,label):
        control=next(c for c in page['controls'] if c['label']==label)
        return await tool('browser_action',dict(session_id=page['session_id'],ref=control['ref'],action='click'))
    reading=None
    try:
        server=start(0);port=server.server_port;origin=f'http://127.0.0.1:{port}';reading=asyncio.create_task(read_events())
        state=(await call('hello'))['state'];original=dict(projectId=state.get('activeProject'),sessionId=state.get('activeSession'),mode=state.get('mode'),approvalMode=state.get('approvalMode'));report['originalWorkspace']=original
        selected=next((p for p in state['projects'] if p['id']==original['projectId']),{}); original['approvalMode']=selected.get('approvalMode',state.get('personalApprovalMode','review')); assert original['approvalMode']=='review',original
        await call('session-new');validation=(await call('hello'))['state']['activeSession'];report['validationSession']=validation
        page=await open_page();assert 'AUTH_REQUIRED_FIXTURE' in page['text'],page
        page=await click(page,'Start disposable session');assert 'AUTHENTICATED_FIXTURE' in page['text'],page
        page=await open_page(page['session_id']);assert 'AUTHENTICATED_FIXTURE' in page['text'] and Site.ledger[-1]['authorized'],page
        report['cases'].append(dict(id='cookie-authenticated-navigation',status='passed'));save()
        Site.valid=False;page=await open_page(page['session_id']);assert 'AUTH_REQUIRED_FIXTURE' in page['text'] and not Site.ledger[-1]['authorized'],page
        report['cases'].append(dict(id='server-expiry-visible',status='passed'));save()
        page=await click(page,'Start disposable session');page=await click(page,'End disposable session');assert 'LOGGED_OUT_FIXTURE' in page['text'],page
        page=await open_page(page['session_id']);assert 'AUTH_REQUIRED_FIXTURE' in page['text'] and not Site.ledger[-1]['authorized'],page
        report['cases'].append(dict(id='logout-removes-usable-session',status='passed'));save()
        Site.online=False;await asyncio.to_thread(server.shutdown);server.server_close();server=None;count=len(Site.ledger);error=None
        try:await open_page(page['session_id'])
        except RuntimeError as failure:error=str(failure)
        assert error and len(Site.ledger)==count,dict(error=error,ledger=Site.ledger)
        report['cases'].append(dict(id='network-loss-errors-without-success',status='passed',error=error));save()
        Site.online=True;server=start(port);page=await open_page(page['session_id']);assert 'AUTH_REQUIRED_FIXTURE' in page['text'],page
        report['cases'].append(dict(id='network-reconnect-visible',status='passed'));save()
        page=await click(page,'Start disposable session');assert 'AUTHENTICATED_FIXTURE' in page['text'],page
        closed=page['session_id'];await tool('browser_close',dict(session_id=closed));pages.remove(closed)
        page=await open_page();assert 'AUTH_REQUIRED_FIXTURE' in page['text'] and not Site.ledger[-1]['authorized'],page
        report['cases'].append(dict(id='closed-page-cookie-isolation',status='passed'));save()
        assert all(r['approved'] for r in reviews) and reviews, reviews
        report.update(status='passed',modelInference=False,thirdPartyProviderQualification=False)
    except BaseException as error:report.update(status='failed',error=str(error)[:4000]);raise
    finally:
        for identifier in list(pages):
            try:await tool('browser_close',dict(session_id=identifier))
            except BaseException as error:report.setdefault('cleanupErrors',[]).append(str(error))
        if original:
            await call('project-select',dict(id=original['projectId']))
            if original['sessionId']:await call('session-select',dict(id=original['sessionId']))
            if validation:await call('session-archive',dict(id=validation))
            final=(await call('hello'))['state'];report['workspaceRestored']=final.get('activeProject')==original['projectId'] and final.get('activeSession')==original['sessionId'];assert report['workspaceRestored']
        if server:await asyncio.to_thread(server.shutdown);server.server_close()
        report['finished']=time.time();save();writer.close();await writer.wait_closed()
        if reading:reading.cancel()
    print(json.dumps(dict(status=report['status'],cases=report['cases'],workspaceRestored=report['workspaceRestored'])))
asyncio.run(main())
