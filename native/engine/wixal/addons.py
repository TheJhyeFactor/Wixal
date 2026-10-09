"""Native capability library: curated packages, durable jobs and workflow packs."""
import asyncio
import copy
import os
import json
import re
import shutil
import signal
import threading
from pathlib import Path
from .storage import identity, now
from .memory import owner

CATALOG = [
 dict(id='rustscan',name='RustScan',category='Network',package='rustscan',binary='rustscan',source='https://github.com/bee-san/RustScan',description='Bounded TCP discovery with retained evidence and source-bound Nmap inspection.',adapter='network_discover'),
 dict(id='nmap',name='Nmap',category='Network',package='nmap',binary='nmap',source='https://nmap.org/',description='Host, port and service discovery.',adapter='network_scan'),
 dict(id='ffuf',name='ffuf',category='Web',package='ffuf',binary='ffuf',source='https://github.com/ffuf/ffuf',description='Bounded route discovery with a supplied wordlist.',adapter='addon_run'),
 dict(id='nuclei',name='Nuclei',category='Web',package='nuclei',binary='nuclei',source='https://docs.projectdiscovery.io/tools/nuclei/overview',description='Selected signed template checks; provide a template path.',adapter='addon_run'),
 dict(id='wireshark',name='Wireshark / TShark',category='Traffic',package='wireshark',binary='tshark',source='https://www.wireshark.org/',description='Analyse saved packet captures. Desktop app and live capture permissions are separate.',adapter='addon_run'),
 dict(id='trivy',name='Trivy',category='Software',package='trivy',binary='trivy',source='https://trivy.dev/',description='Local software vulnerability and configuration assessment.',adapter='addon_run'),
 dict(id='osv-scanner',name='OSV-Scanner',category='Software',package='osv-scanner',binary='osv-scanner',source='https://google.github.io/osv-scanner/',description='Match local dependency evidence against OSV advisories.',adapter='addon_run'),
 dict(id='testssl',name='testssl.sh',category='Network',package='testssl',binary='testssl.sh',source='https://github.com/testssl/testssl.sh',description='TLS protocol, certificate and cipher assessment.',adapter='addon_run'),
 dict(id='mitmproxy',name='mitmproxy',category='Traffic',package='mitmproxy',kind='cask',binary='mitmdump',source='https://mitmproxy.org/',description='HTTP traffic inspection and replay. Certificate/browser setup remains explicit.',adapter='setup_required'),
 dict(id='zap',name='ZAP',category='Web',package='zap',kind='cask',binary='zap.sh',paths=['/Applications/ZAP.app/Contents/Java/zap.sh'],source='https://www.zaproxy.org/',description='Web proxy, discovery and assessment. Configure authentication and an automation plan before scanning.',adapter='setup_required'),
 dict(id='metasploit',name='Metasploit Framework',category='Validation',binary='msfconsole',source='https://docs.metasploit.com/',description='Specialist module-based validation. Official installer and scoped RPC setup are required.',adapter='setup_required'),
]
PACKS = [
 dict(id='web-assessment',name='Website evidence workflow',tools=['nmap','ffuf','nuclei'],description='Map an application, research observations, validate selected hypotheses, and report.',content='Use addon_catalog to inspect readiness. Install only needed curated tools through addon_install and poll addon_job until verified. Pin all requests to the authorised target. Start with website_assess; use network_scan for selected ports. Discover bounded routes with ffuf only with a supplied wordlist. Research actual product/version evidence using web_search and http_request. Select signed Nuclei templates explicitly; do not run the entire collection. Preserve tool output and distinguish observations, candidate findings and verified impact. Use workflow_manage to save reusable stages when appropriate. Stop on scope uncertainty or missing evidence. Report limitations and retest criteria.'),
 dict(id='traffic-analysis',name='Packet capture review',tools=['wireshark'],description='Review a supplied capture without changing live network capture permissions.',content='Use addon_catalog and ensure wireshark is installed. Use addon_run with addon wireshark and a project-relative capture path. Analyse protocol summaries and extract only needed fields. Preserve the source capture and tool output. Encrypted payloads remain opaque without explicitly supplied session keys. Do not infer that missing traffic means a device is absent. Report observation time, interface context if known, and uncertainty.'),
 dict(id='software-assessment',name='Software advisory review',tools=['osv-scanner','trivy'],description='Assess a local project and investigate advisory applicability.',content='Inspect addon_catalog, install only the required scanner and wait for verified readiness. Use addon_run for osv-scanner or trivy with a project-relative directory. Preserve installed/declaration version evidence and database observations. Research vendor advisories and affected prerequisites. A package match is a candidate finding, not proof of exploitability. Do not publish secrets; redact sensitive outputs. Retain source evidence and produce a prioritised remediation and retest plan.'),
 dict(id='network-assessment',name='Network and TLS review',tools=['nmap','testssl'],description='Discover scoped services and assess TLS evidence.',content='Use network_scan against the authorised host or private subnet with bounded ports and timeout. Treat service names inferred from port numbers as uncertain. Research actual observed versions. Use addon_run with testssl for an explicitly scoped TLS host. Preserve XML/JSON output. Separate misconfiguration, version candidates and verified vulnerabilities. Do not expand to discovered hosts outside authorised scope. Save evidence and recommend focused follow-up checks.'),
]

def definitions():
    def tool(name,description,properties,required):return dict(type='function',function=dict(name=name,description=description,parameters=dict(type='object',properties=properties,required=required,additionalProperties=False)))
    string=lambda **kw:dict(type='string',**kw)
    return [tool('addon_discover','Research additional Homebrew core packages by a simple program name. Returns registry metadata and a candidate; does not install or grant execution authority.',dict(query=string(maxLength=80)),['query']),tool('addon_catalog','Discover curated installable programs, readiness, workflow packs, and installation policy. Choose only capabilities needed for the workload.',dict(query=string(maxLength=200)),[]),
      tool('addon_install','Install one curated package, verify its executable, and return a durable job ID. Poll addon_job. Installation does not grant target or tool authority.',dict(id=string(),reason=string(maxLength=2000),provider=string(enum=['managed','external_homebrew']),channel=string(enum=['preview','stable'])),['id','reason']),
      tool('addon_job','Read or stop an installation job owned by this conversation.',dict(id=string(),action=string(enum=['read','stop']),wait_seconds=dict(type='integer',minimum=0,maximum=5)),['id']),
      tool('addon_run','Run a structured installed add-on profile. Returns a command session; poll command_read and save evidence. Network targets must stay within task authority.',dict(id=string(enum=['ffuf','nuclei','wireshark','trivy','osv-scanner','testssl']),target=string(maxLength=2000),path=string(maxLength=1000),template=string(maxLength=1000),timeout_seconds=dict(type='integer',minimum=10,maximum=600)),['id']),
      tool('addon_workflow','Install a bundled reusable instruction pack as a loadable skill. Workflow instructions do not grant tool permissions.',dict(id=string()),['id'])]

class Addons:
    def __init__(self,service):
        self.service=service;self.store=service.store;self.tasks={};self.children={};self.lock=asyncio.Lock();self.versions={}
        from .managed_tools import PackageRegistry
        from .network_discovery import SocketBudget
        self.managed=PackageRegistry();self.socket_budget=SocketBudget();self.managed_cancellations={}
        self.store.data.setdefault('addonPolicy',dict(automaticInstall=True))
        self.store.data.setdefault('addonJobs',[])
        self.store.data.setdefault('addonCandidates',[])
        for job in self.store.data['addonJobs']:
            if job['status'] in ('queued','running','waiting_review'):job.update(status='interrupted',error='Engine restarted; inspect package state before retrying')
    def publish(self):self.store.save();self.service.emit('state',self.store.data)
    def spec(self,identifier):
        row=next((r for r in [*CATALOG,*self.store.data['addonCandidates']] if r['id']==identifier and (r.get('owner') is None or r['owner']==owner(self.store))),None)
        if not row:raise ValueError('Choose a curated add-on from addon_catalog')
        return row
    def external_executable(self,row):
        candidates=[shutil.which(row['binary']),'/opt/homebrew/bin/'+row['binary'],'/usr/local/bin/'+row['binary'],*row.get('paths',[])]
        return next((p for p in candidates if p and Path(p).is_file() and os.access(p,os.X_OK)),None)
    def executable(self,row):
        if row['id']=='rustscan' and self.managed.snapshot()['provider']=='managed':
            try:return self.managed.resolve()['path']
            except (ValueError,OSError):return None
        return self.external_executable(row)
    def snapshot(self,query=''):
        rows=[]
        for spec in [*CATALOG,*[r for r in self.store.data['addonCandidates'] if r['owner']==owner(self.store)]]:
            if query and query.lower() not in str(spec).lower():continue
            path=self.executable(spec);row=dict(spec,path=path,installed=bool(path),integration=spec['adapter'],installable=bool(spec.get('package')),registry=('Homebrew core' if spec.get('kind')!='cask' else 'Homebrew cask') if spec.get('package') else 'Official installer')
            row['version']=self.versions.get(spec['id'],'')
            row['registryURL']='https://formulae.brew.sh/'+('cask/' if spec.get('kind')=='cask' else 'formula/')+spec.get('package','') if spec.get('package') else spec['source']
            row.update(provider='specialist_installer' if not spec.get('package') else 'external_homebrew',packageVerified=False,capabilityReady=bool(path and self.versions.get(spec['id']) and spec['adapter']!='setup_required'),modelEvaluation='unevaluated',readiness='setup_required' if path else 'not_installed')
            if spec['id']=='rustscan':
                managed=self.managed.snapshot();row.update(managed=managed,provider=managed['provider'],externalPath=self.external_executable(spec),managedInstallable=managed['configured'])
                if managed['provider']=='managed':
                    row.update(registry='Wixal managed preview',packageVerified=bool(path),capabilityReady=bool(path),version=(managed['active'] or {}).get('version',''),registryURL=spec['source'])
            if row['capabilityReady']:row['readiness']='ready'
            rows.append(row)
        packs=[]
        for pack in PACKS:
            skill=next((s for s in self.store.data['skills'] if s.get('addonPack')==pack['id'] and s.get('owner','guest')==owner(self.store)),None)
            packs.append(dict(pack,installed=bool(skill),skillId=(skill or {}).get('id'),category={'web-assessment':'Web','traffic-analysis':'Traffic','software-assessment':'Software','network-assessment':'Network'}[pack['id']],kind='workflow'))
        return dict(owner=owner(self.store),scope='global',packages=rows,workflows=packs,policy=self.store.data['addonPolicy'],brew=shutil.which('brew') or next((p for p in ('/opt/homebrew/bin/brew','/usr/local/bin/brew') if Path(p).is_file()),None),jobs=[j for j in self.store.data['addonJobs'] if j.get('owner')==owner(self.store)])
    async def install(self,args,tools,session,manual=False):
        row=self.spec(args.get('id'));reason=args.get('reason','').strip()
        if not reason or len(reason)>2000:raise ValueError('Provide why this package is needed')
        from .agent_context import profile
        active=profile.get() or {}
        if active.get('reviewPolicy')=='Read only' or active.get('_branchRoot'):raise ValueError('Package installation is unavailable in this task boundary')
        provider=args.get('provider',self.managed.snapshot()['provider'] if row['id']=='rustscan' else 'external_homebrew')
        if provider=='managed':
            if row['id']!='rustscan':raise ValueError('This tool has no managed contract yet')
            return await self.install_managed(args,tools,session,manual)
        if not row.get('package'):raise ValueError('This tool requires its official installer and specialist setup: '+row['source'])
        if path:=self.executable(row):
            version=await self.verify(row,path)
            return dict(status='ready',path=path,id=row['id'],version=version)
        if any(j['addon']==row['id'] and j['status'] in ('queued','running','waiting_review') for j in self.store.data['addonJobs']):raise ValueError('An installation of this package is already pending')
        brew=self.snapshot()['brew']
        if not brew:raise ValueError('Homebrew is required. Install it from https://brew.sh and retry; Wixal does not alter system permissions.')
        job=dict(id=identity(),addon=row['id'],owner=owner(self.store),session=session,projectId=(tools.store.project() or {}).get('id'),status='waiting_review',created=now(),reason=reason,source=row['source'],registry='https://formulae.brew.sh/'+('cask/' if row.get('kind')=='cask' else 'formula/')+row['package'],output='')
        self.store.data['addonJobs'].append(job);self.store.data['addonJobs']=self.store.data['addonJobs'][-200:];self.publish()
        # One global preference covers approved catalogue recipes; discoveries still ask.
        automatic=self.store.data['addonPolicy']['automaticInstall'] and row['id'] in {r['id'] for r in CATALOG}
        if not manual and not automatic and not await tools.approve(dict(name='addon_install',addon=row['id'],package=row['package'],source=job['registry'],reason=reason,installationReview=True)):
            job.update(status='declined',finished=now());self.publish();return dict(job)
        if job['status']=='cancelled':return dict(job)
        job['status']='queued';self.publish()
        self.tasks[job['id']]=asyncio.create_task(self.collect(job,row,brew))
        return dict(job)
    async def install_managed(self,args,tools,session,manual=False,artifact=None):
        if not self.managed.client:raise ValueError('Managed repository is not configured in this build')
        if args.get('channel',self.managed.configuration['channel'])!=self.managed.configuration['channel']:raise ValueError('This channel has no embedded trust configuration')
        job=dict(id=identity(),addon='rustscan',provider='managed',owner=owner(self.store),session=session,projectId=(tools.store.project() or {}).get('id'),status='waiting_review',stage='requested',created=now(),reason=args.get('reason','Managed RustScan maintenance'),output='')
        self.store.data['addonJobs'].append(job);self.publish()
        if not manual and not self.store.data['addonPolicy']['automaticInstall'] and not await tools.approve(dict(name='addon_install',addon='rustscan',provider='managed',installationReview=True,reason=job['reason'])):
            job.update(status='declined',finished=now());self.publish();return dict(job)
        cancel=threading.Event();self.managed_cancellations[job['id']]=cancel
        async def collect():
            worker=None
            try:
                job['status']='running';self.publish()
                loop=asyncio.get_running_loop()
                worker=asyncio.create_task(asyncio.to_thread(self.managed.install,job,cancel,lambda:loop.call_soon_threadsafe(self.publish),artifact))
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                cancel.set()
                if worker:await asyncio.gather(worker,return_exceptions=True)
                if job['status']!='ready':job.update(status='cancelled',error='Cancelled before activation; prior package remains selected')
            except Exception as error:
                if job.get('status')=='ready':job['warning']='Activation committed; post-commit receipt cleanup failed: '+str(error)
                else:job.update(status='failed',error=str(error))
            finally:
                job['finished']=now();self.managed.persist_job(job);self.tasks.pop(job['id'],None);self.managed_cancellations.pop(job['id'],None);self.publish()
        self.tasks[job['id']]=asyncio.create_task(collect());return dict(job)

    async def collect(self,job,row,brew):
        child=None
        try:
            async with self.lock:
                job.update(status='running',started=now());self.publish()
                operation=job.get('operation','install')
                argv=[brew,operation,*(['--cask'] if row.get('kind')=='cask' else []),('homebrew/cask/' if row.get('kind')=='cask' else 'homebrew/core/')+row['package']]
                job['argv']=argv
                child=await asyncio.create_subprocess_exec(*argv,stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,start_new_session=True,env={**os.environ,'HOMEBREW_NO_AUTO_UPDATE':'1','HOMEBREW_NO_ENV_HINTS':'1'})
                self.children[job['id']]=child
                async with asyncio.timeout(1200):
                    while chunk:=await child.stdout.read(8192):
                        job['output']=(job['output']+chunk.decode('utf-8',errors='replace'))[-64000:];self.publish()
                    job['exitCode']=await child.wait()
                path=self.executable(row)
                if operation!='uninstall' and path and job['exitCode']==0 and row['id'] in {r['id'] for r in CATALOG}:job['version']=await self.verify(row,path)
                status=('removed' if not path else 'failed') if operation=='uninstall' else ('ready' if path and row['adapter']!='setup_required' else 'setup_required')
                job.update(status=status if job['exitCode']==0 else 'failed',path=path)
                if operation=='uninstall':self.versions.pop(row['id'],None)
                if job['status']=='failed':job['error']='Installation or executable verification failed. Inspect retained output; system setup may be required.'
        except asyncio.CancelledError:job.update(status='cancelled');raise
        except Exception as error:job.update(status='failed',error=str(error))
        finally:
            if child and child.returncode is None:
                try:os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:await asyncio.wait_for(child.wait(),3)
                except TimeoutError:
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    await child.wait()
            self.children.pop(job['id'],None);self.tasks.pop(job['id'],None);job['finished']=now();self.publish()
    async def job(self,args,session=None):
        job=next((j for j in self.store.data['addonJobs'] if j['id']==args.get('id') and j['owner']==owner(self.store) and (session is None or j['session']==session)),None)
        if not job:raise ValueError('Installation belongs to another conversation or owner')
        from .agent_context import profile
        if args.get('action')=='stop' and (profile.get() or {}).get('reviewPolicy')=='Read only':raise ValueError('Read-only tasks cannot stop installations')
        if args.get('action')=='stop' and job['status']=='waiting_review':job.update(status='cancelled',finished=now());self.publish()
        if args.get('action')=='stop' and job['id'] in self.tasks:
            task=self.tasks[job['id']];task.cancel();await asyncio.gather(task,return_exceptions=True)
            if job['status'] in ('queued','waiting_review'):job.update(status='cancelled',finished=now());self.publish()
        if session is not None and args.get('action','read')=='read' and job['status'] in ('queued','running'):
            async with asyncio.timeout(args.get('wait_seconds',3)+.5):
                for _ in range(args.get('wait_seconds',3)*5):
                    if job['status'] not in ('queued','running'):break
                    await asyncio.sleep(.2)
        return copy.deepcopy(job)
    def workflow(self,identifier):
        pack=next((p for p in PACKS if p['id']==identifier),None)
        if not pack:raise ValueError('Unknown workflow pack')
        existing=next((s for s in self.store.data['skills'] if s.get('addonPack')==identifier and s.get('owner','guest')==owner(self.store)),None)
        if existing:return existing
        row=dict(id=identity(),name=pack['name'],description=pack['description'],content=pack['content'],addonPack=identifier,owner=owner(self.store),source='Wixal bundled workflow',created=now(),versions=[])
        self.store.data['skills'].append(row);self.publish();return row
    async def verify(self,row,path):
        if row['adapter']=='setup_required' or row['id'].startswith('core:'):return 'Detected executable; specialist setup required'
        flag={'ffuf':'-V','nuclei':'-version'}.get(row['id'],'--version')
        child=await asyncio.create_subprocess_exec(path,flag,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        try:
            output,_=await asyncio.wait_for(child.communicate(),10)
            if child.returncode!=0 or not output.strip():raise ValueError('Executable readiness check failed')
            version=output.decode(errors='replace')[:500].strip();self.versions[row['id']]=version;return version
        finally:
            if child.returncode is None:child.kill();await child.wait()
    async def discover(self,query):
        if not isinstance(query,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9-]{0,79}',query):raise ValueError('Use a simple Homebrew program name, without a URL, tap or command')
        brew=self.snapshot()['brew']
        if not brew:raise ValueError('Homebrew is required to query its registry')
        child=await asyncio.create_subprocess_exec(brew,'info','--json=v2','--formula','homebrew/core/'+query.lower(),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            output,error=await asyncio.wait_for(child.communicate(),30)
            if child.returncode or len(output)>1024*1024:raise ValueError('No verified core formula metadata returned: '+error.decode(errors='replace')[:1000])
            values=json.loads(output).get('formulae',[])
            if len(values)!=1 or values[0].get('tap')!='homebrew/core':raise ValueError('Only official Homebrew core metadata can become a candidate')
            metadata=values[0];name=metadata['name']
            if not re.fullmatch(r'[a-z0-9][a-z0-9@+_.-]{0,99}',name):raise ValueError('Invalid registry package name')
            existing=next((r for r in CATALOG if r.get('package')==name),None)
            if existing:return self.spec(existing['id'])
            source=metadata.get('homepage','')
            if not source.startswith('https://'):raise ValueError('Candidate must have an HTTPS project homepage')
            row=dict(id='core:'+name,name=name,category='Discovered',package=name,binary=name,source=source,description=metadata.get('desc',''),adapter='command_start',owner=owner(self.store),registryVersion=metadata.get('versions',{}).get('stable'),license=metadata.get('license'),metadataSource='https://formulae.brew.sh/formula/'+name)
            self.store.data['addonCandidates']=[r for r in self.store.data['addonCandidates'] if r['id']!=row['id'] or r['owner']!=row['owner']]+[row]
            self.store.data['addonCandidates']=self.store.data['addonCandidates'][-50:];self.publish();return row
        finally:
            if child.returncode is None:child.kill();await child.wait()
    async def dispatch(self,method,args):
        if method=='addon-managed-refresh':return await asyncio.to_thread(self.managed.refresh)
        if method=='addon-provider':
            if args.get('id')!='rustscan':raise ValueError('Only RustScan has a managed provider')
            await asyncio.to_thread(self.managed.select_provider,args.get('provider'));return self.snapshot('rustscan')
        if method=='addon-rollback':return await asyncio.to_thread(self.managed.rollback,args.get('artifact'))
        if method=='addon-manage' and args.get('id')=='rustscan' and self.managed.snapshot()['provider']=='managed':
            operation=args.get('operation')
            if operation=='uninstall':return await asyncio.to_thread(self.managed.remove)
            if operation not in ('upgrade','reinstall'):raise ValueError('Choose update, repair or removal')
            artifact=(self.managed.snapshot()['active'] or {}).get('sha256') if operation=='reinstall' else None
            return await self.install_managed(dict(reason='Managed '+operation),self.service.tools,'native-library',manual=True,artifact=artifact)
        if method=='addon-manage':
            row=self.spec(args.get('id'));operation=args.get('operation')
            if operation not in ('upgrade','reinstall','uninstall'):raise ValueError('Choose update, repair or removal')
            if not row.get('package'):raise ValueError('Manage this program using its official installer: '+row['source'])
            if any(j['addon']==row['id'] and j['status'] in ('queued','running','waiting_review') for j in self.store.data['addonJobs']):raise ValueError('This program already has a pending operation')
            brew=self.snapshot()['brew']
            if not brew:raise ValueError('Homebrew is required to manage this program')
            job=dict(id=identity(),addon=row['id'],owner=owner(self.store),session='native-library',projectId=None,operation=operation,status='queued',created=now(),reason={'upgrade':'Update installed program','reinstall':'Repair installed program','uninstall':'Remove program globally'}[operation],source=row['source'],registry='https://formulae.brew.sh/'+('cask/' if row.get('kind')=='cask' else 'formula/')+row['package'],output='')
            self.store.data['addonJobs'].append(job);self.store.data['addonJobs']=self.store.data['addonJobs'][-200:];self.publish()
            self.tasks[job['id']]=asyncio.create_task(self.collect(job,row,brew));return dict(job)
        if method=='addon-workflow-remove':
            pack=next((p for p in PACKS if p['id']==args.get('id')),None)
            if not pack:raise ValueError('Unknown workflow pack')
            self.store.data['skills']=[s for s in self.store.data['skills'] if not (s.get('addonPack')==pack['id'] and s.get('owner','guest')==owner(self.store))]
            self.publish();return dict(status='removed',id=pack['id'])
        if method=='addon-verify':
            row=self.spec(args.get('id'));path=self.executable(row)
            if not path:raise ValueError('Executable not found')
            return dict(id=row['id'],path=path,version=await self.verify(row,path))
        if method=='addon-discover':return await self.discover(args.get('query'))
        if method=='addon-catalog':return self.snapshot(args.get('query',''))
        if method=='addon-policy':
            value=args.get('automaticInstall')
            if type(value)!=bool:raise ValueError('Choose an installation policy')
            self.store.data['addonPolicy']['automaticInstall']=value;self.publish();return self.store.data['addonPolicy']
        if method=='addon-install':return await self.install(args,self.service.tools,'native-library',manual=True)
        if method=='addon-job':return await self.job(args)
        if method=='addon-workflow':return self.workflow(args.get('id'))
        raise ValueError('Unknown library action')
    async def close(self):
        tasks=list(self.tasks.values())
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
