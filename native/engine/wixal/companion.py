"""Explicitly enabled, authenticated loopback companion; remote tasks only queue."""
import asyncio
import json
import os
import secrets
import time
from pathlib import Path
from .storage import identity, now
from .tools import safe_path, sensitive, SKIP

SPECS=[('list_projects','List explicitly shared projects',{}),('get_project_context','Read shared project file list',{'projectId':100}),('read_project_file','Read a text file in a shared project',{'projectId':100,'path':1000}),('search_project','Search literal text in a shared project',{'projectId':100,'query':300}),('create_task','Queue work for the user to start in Wixal',{'projectId':100,'title':120,'prompt':16000}),('get_task_status','Read shared task state and actual outcomes',{'taskId':100})]

class Companion:
    def __init__(self,service):
        self.service=service;self.server=None;self.endpoint=None;self.token=None;self.file=service.store.directory/'wixal-connection.json';self.clients=set();self.requests=[]
        # Never migrate or automatically restore an enabled companion.
        service.store.data.setdefault('companion',dict(sharedProjects=[],shareMemory=False))
        service.store.data['companion']['enabled']=False
        try: self.file.unlink()
        except FileNotFoundError: pass

    def snapshot(self):
        saved=self.service.store.data['companion']
        return dict(running=bool(self.server),enabled=bool(self.server),endpoint=self.endpoint,connectionFile=str(self.file) if self.server else None,sharedProjects=saved.get('sharedProjects',[]),shareMemory=bool(saved.get('shareMemory')),command=self.command() if self.server else '')

    def command(self):
        import shlex,sys
        executable=Path(sys.executable)
        if getattr(sys,'frozen',False): return shlex.quote(str(executable))+' --companion '+shlex.quote(str(self.file))
        entry=Path(__file__).resolve().parents[1]/'engine_main.py'
        return shlex.quote(str(executable))+' '+shlex.quote(str(entry))+' --companion '+shlex.quote(str(self.file))

    def project(self,id):
        if not self.server or id not in self.service.store.data['companion'].get('sharedProjects',[]): raise ValueError('This project is not shared. Enable it in Wixal.')
        project=next((p for p in self.service.store.data['projects'] if p['id']==id),None)
        if not project: raise ValueError('Unknown project.')
        return project

    def files(self,project):
        root=Path(project['root']).resolve(strict=True);result=[]
        for folder,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in SKIP and not sensitive(d) and not (Path(folder)/d).is_symlink() and len(Path(folder).relative_to(root).parts)<6)
            for file in sorted(files):
                path=Path(folder)/file;relative=str(path.relative_to(root))
                if not path.is_symlink() and not sensitive(relative): result.append(relative)
                if len(result)>=1200:return result
        return result

    def read(self,project,path):
        file=safe_path(project['root'],path)
        if not file.is_file() or file.stat().st_size>1024*1024: raise ValueError('Choose a text file smaller than 1 MB.')
        return file.read_text()[:24000]

    async def call(self,name,args):
        spec=next((s for s in SPECS if s[0]==name),None)
        if not self.server or not spec: raise ValueError('Companion is paused or the tool is unknown.')
        if not isinstance(args,dict) or set(args)!=set(spec[2]): raise ValueError('Invalid companion arguments.')
        for key,limit in spec[2].items():
            if not isinstance(args[key],str) or not args[key].strip() or len(args[key])>limit: raise ValueError('Invalid '+key+'.')
        if name=='list_projects': return [dict(id=p['id'],name=p['name']) for p in self.service.store.data['projects'] if p['id'] in self.service.store.data['companion'].get('sharedProjects',[])]
        if name=='get_task_status':
            task=next((t for t in self.service.store.data['tasks'] if t['id']==args['taskId']),None)
            if not task: raise ValueError('Unknown task.')
            self.project(task.get('projectId'));return {key:task.get(key) for key in ('id','title','status','result','outcomes','error','updated')}
        project=self.project(args['projectId'])
        required={'get_project_context':'list_files','read_project_file':'read_file','search_project':'search_files'}.get(name)
        if required and required not in self.service.store.data['enabledTools']: raise ValueError('Enable '+required+' in Wixal before sharing this action.')
        if name=='create_task':
            if sum(t['status']=='queued' for t in self.service.store.data['tasks'])>=100: raise ValueError('Task inbox is full.')
            task=dict(id=identity(),projectId=project['id'],title=args['title'].strip(),prompt=args['prompt'].strip(),source='ChatGPT',status='queued',created=now(),updated=now(),checkpoints=[])
            self.service.store.data['tasks'].append(task);self.service.store.save();self.service.emit('state',self.service.store.data)
            return dict(id=task['id'],status='queued',message='Queued. The user must start this task in Wixal.')
        if name=='get_project_context':
            result=dict(id=project['id'],name=project['name'],files=await asyncio.to_thread(self.files,project))
            if self.service.store.data['companion'].get('shareMemory'): result['memories']=[m['content'] for m in self.service.store.data['memories'] if m.get('projectId')==project['id']]
        elif name=='read_project_file': result=dict(projectId=project['id'],result=await asyncio.to_thread(self.read,project,args['path']))
        else:
            results=[]
            for path in await asyncio.to_thread(self.files,project):
                try: content=await asyncio.to_thread(self.read,project,path)
                except (OSError,UnicodeError,ValueError):continue
                for number,line in enumerate(content.splitlines(),1):
                    if args['query'].casefold() in line.casefold():results.append(dict(path=path,line=number,text=line[:500]))
                    if len(results)>=100:break
                if len(results)>=100:break
            result=dict(projectId=project['id'],result=results)
        self.project(project['id']) # Recheck revocation after asynchronous reads.
        return result

    async def handle(self,reader,writer):
        self.clients.add(writer)
        async def respond(status,value):
            body=json.dumps(value).encode();writer.write(('HTTP/1.1 '+str(status)+' Response\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: '+str(len(body))+'\r\n\r\n').encode()+body);await writer.drain()
        try:
            header=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),10)
            if len(header)>8192: return await respond(413,dict(error='Headers too large.'))
            lines=header.decode('ascii').split('\r\n');headers={}
            for line in lines[1:]:
                if not line:continue
                key,value=line.split(':',1);key=key.lower()
                if key in headers:return await respond(400,dict(error='Duplicate header.'))
                headers[key]=value.strip()
            if not self.server or headers.get('host')!=self.endpoint.split('//')[1] or 'origin' in headers or 'sec-fetch-site' in headers:return await respond(403,dict(error='Local paired clients only.'))
            if not secrets.compare_digest(headers.get('authorization',''),'Bearer '+(self.token or '')):return await respond(401,dict(error='Pairing required.'))
            if lines[0]!='POST /bridge HTTP/1.1':return await respond(404,dict(error='Not found.'))
            self.requests=[t for t in self.requests if t>time.monotonic()-60];self.requests.append(time.monotonic())
            if len(self.requests)>120:return await respond(429,dict(error='Slow down companion requests.'))
            size=int(headers.get('content-length','0'))
            if not 0<size<=24000 or 'transfer-encoding' in headers:return await respond(413,dict(error='Invalid request size.'))
            data=json.loads(await asyncio.wait_for(reader.readexactly(size),15))
            if set(data)!= {'name','args'}: raise ValueError('Invalid companion request.')
            result=await self.call(data['name'],data['args']);await respond(200,dict(result=result))
        except (ValueError,KeyError,UnicodeError,OSError,asyncio.IncompleteReadError,asyncio.LimitOverrunError,TimeoutError) as error:
            try: await respond(400,dict(error=str(error)[:300]))
            except OSError:pass
        finally:
            self.clients.discard(writer);writer.close();await writer.wait_closed()

    async def start(self):
        if self.server:return self.snapshot()
        self.token=secrets.token_urlsafe(32);self.server=await asyncio.start_server(self.handle,'127.0.0.1',0,limit=8193)
        self.endpoint='http://127.0.0.1:'+str(self.server.sockets[0].getsockname()[1])
        try:
            temp=self.file.with_suffix('.tmp');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'w') as output:json.dump(dict(endpoint=self.endpoint,token=self.token),output)
            temp.replace(self.file)
        except BaseException:await self.stop();raise
        return self.snapshot()

    async def stop(self):
        server=self.server;self.server=None;self.token=None;self.endpoint=None
        for writer in list(self.clients):writer.close()
        if server:server.close();await server.wait_closed()
        try:self.file.unlink()
        except FileNotFoundError:pass
        return self.snapshot()

    async def dispatch(self,method,params):
        if not method.startswith('companion-'):return False,None
        if method=='companion-start':await self.start()
        elif method in ('companion-stop','companion-revoke'):await self.stop()
        elif method=='companion-settings':
            ids=params.get('sharedProjects',[])
            if not isinstance(ids,list) or set(ids)-{p['id'] for p in self.service.store.data['projects']}:raise ValueError('Unknown shared project.')
            if not isinstance(params.get('shareMemory',False),bool):raise ValueError('Invalid memory preference.')
            self.service.store.data['companion'].update(sharedProjects=ids,shareMemory=params.get('shareMemory',False))
        else:raise ValueError('Unknown companion action.')
        self.service.store.data['companion'].update(self.snapshot());return True,self.snapshot()
