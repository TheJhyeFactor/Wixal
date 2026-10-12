"""Optional per-operation Linux containers with owned lifecycle and typed scan contracts."""
import asyncio
import ipaddress
import json
import os
import re
import shutil
from pathlib import Path
from . import engagement_evidence as evidence
from .engagement_policy import addresses, live
from .network_discovery import ports

IMAGE='wixal-security-worker:v1'


class LinuxWorker:
    def __init__(self,manager):self.manager=manager

    def executable(self):return shutil.which('docker')

    def socket(self):
        configured=self.manager.store.data.get('securityWorkerConfig',{}).get('socket') if self.manager else None
        if configured:return 'unix://'+configured
        for path in (Path.home()/'.docker/run/docker.sock',Path('/var/run/docker.sock')):
            if path.exists():return 'unix://'+str(path)
        return None

    async def command(self,*args,seconds=10):
        executable=self.executable();endpoint=self.socket()
        if not executable or not endpoint:raise ValueError('A local Docker Linux runtime is required; no runtime is installed or downloaded automatically')
        process=await asyncio.create_subprocess_exec(executable,'--host',endpoint,*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env={'PATH':'/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin','HOME':str(Path.home())})
        try:
            async with asyncio.timeout(seconds):out,err=await process.communicate()
        except BaseException:
            if process.returncode is None:process.kill()
            await process.wait();raise
        if process.returncode:raise ValueError(err.decode(errors='replace')[:2000] or 'Docker operation failed')
        if len(out)>512000:raise ValueError('Docker metadata exceeds bound')
        return out.decode()

    async def configure(self,path):
        import stat
        if not isinstance(path,str) or not path.startswith('/') or len(path)>1000:raise ValueError('Select a local absolute Unix socket path')
        candidate=Path(path).resolve(strict=True);info=candidate.stat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid not in (os.getuid(),0):raise ValueError('Select an owned local Docker Unix socket')
        if not await self.manager.workspace.service.ask('review',dict(name='security_worker_runtime',socket=str(candidate),permission='Typed reviewed worker operations only; no remote daemon or arbitrary shell')):raise ValueError('Worker runtime was not approved')
        self.manager.store.data['securityWorkerConfig']=dict(socket=str(candidate))
        self.manager.store.data['securityWorkerReadiness']=dict(available=False,error='Runtime changed; inspect image readiness')
        self.manager.workspace.publish();return self.manager.store.data['securityWorkerConfig']

    async def inspect(self):
        try:
            if (await self.command('info','--format','{{.OSType}}')).strip()!='linux':raise ValueError('Worker requires a Linux daemon')
            image=(await self.command('image','inspect',IMAGE,'--format','{{.Id}}')).strip()
            if not re.fullmatch(r'sha256:[0-9a-f]{64}',image):raise ValueError('Worker image identity is invalid')
            result=dict(available=True,imageId=image,image=IMAGE,mode='Typed ports/services scan; dedicated container and network; no host mounts')
        except (ValueError,OSError,TimeoutError) as error:result=dict(available=False,error=str(error),image=IMAGE)
        self.manager.store.data['securityWorkerReadiness']=result
        self.manager.workspace.publish();return result

    def invocation(self,run,resolved):
        parsed=[str(ipaddress.ip_address(a)) for a in resolved]
        if any(ipaddress.ip_address(a).is_loopback or ipaddress.ip_address(a).is_link_local or ipaddress.ip_address(a).is_multicast or ipaddress.ip_address(a).is_unspecified for a in parsed):raise ValueError('Linux worker needs explicit reachable lab IPs; host loopback cannot be translated silently')
        requested=ports(run['arguments'].get('ports','22,80,443,8080,8443'))
        profile=run['arguments'].get('profile','ports')
        if len(requested)>1024 or profile not in ('ports','services'):raise ValueError('Linux worker supports 1–1,024 selected ports and ports/services profiles')
        return dict(addresses=parsed,ports=requested,profile=profile,seconds=run['arguments'].get('timeout_seconds',180),engagementId=run['engagementId'],runId=run['id'],scopeRevision=run['scopeRevision'])

    async def owned(self,kind,name,run):
        value=json.loads(await self.command(kind,'inspect',name))[0]
        labels=value.get('Config',{}).get('Labels',{}) if kind=='container' else value.get('Labels',{})
        if labels.get('wixal.engagement')!=run['engagementId'] or labels.get('wixal.run')!=run['id']:raise ValueError('Worker object ownership mismatch')
        return value

    async def cleanup(self,run):
        results=[]
        for kind,key in (('container','workerContainer'),('network','workerNetwork')):
            name=run.get(key)
            if not name:continue
            try:
                await self.owned(kind,name,run)
                await self.command(kind,'rm',*(['--force'] if kind=='container' else []),name)
                results.append(dict(kind=kind,name=name,removed=True))
            except ValueError as error:
                # Missing objects are only accepted after a separate successful list.
                listing=(await self.command(kind,'ls','--all','--filter','name='+name,'--format','{{.Names}}')).strip() if kind=='container' else None
                if kind=='network':
                    remaining=await self.command('network','ls','--filter','name='+name,'--format','{{.Name}}')
                    if remaining.strip():raise
                elif listing:raise
                results.append(dict(kind=kind,name=name,absent=True))
        return results

    async def execute(self,run,approve):
        live();ready=await self.inspect()
        if not ready['available']:raise ValueError(ready['error'])
        resolved=await addresses(run['address']);config=self.invocation(run,resolved)
        if not await self.manager.workspace.service.ask('review',dict(name='security_linux_worker',imageId=ready['imageId'],contract=config,scopeRevision=run['scopeRevision'])):raise ValueError('Linux worker execution was not approved')
        live()
        from .storage import now
        run['workerApproval']=dict(imageId=ready['imageId'],configSha256=evidence.digest(config),scopeRevision=run['scopeRevision'],created=now())
        run['effectState']='running'
        self.manager.event(self.manager.get(run['engagementId']),'worker_approved',dict(runId=run['id'],approval=run['workerApproval']))
        suffix=run['id'].replace('-','');container='wixal-run-'+suffix;network='wixal-net-'+suffix
        run.update(workerContainer=container,workerNetwork=network,workerImageId=ready['imageId'],environment='linux-container',workerCleanup='pending')
        self.manager.workspace.publish()
        process=None
        try:
            await self.command('network','create','--label','wixal.engagement='+run['engagementId'],'--label','wixal.run='+run['id'],'--opt','com.docker.network.bridge.enable_icc=false',network)
            live()
            argv=[self.executable(),'--host',self.socket(),'run','--rm','--interactive','--name',container,'--label','wixal.engagement='+run['engagementId'],'--label','wixal.run='+run['id'],'--network',network,'--dns','127.0.0.1','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=16m','--cap-drop','ALL','--cap-add','NET_ADMIN','--cap-add','SETUID','--cap-add','SETGID','--cap-add','SETPCAP','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--cpus','1',ready['imageId']]
            process=await asyncio.create_subprocess_exec(*argv,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,env={'PATH':'/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin','HOME':str(Path.home())})
            process.stdin.write(evidence.canonical(config));await process.stdin.drain();process.stdin.close()
            data=bytearray()
            while chunk:=await process.stdout.read(65536):
                live();data.extend(chunk)
                run['output']=bytes(data[-100000:]).decode(errors='replace')
                if len(data)>2*1024*1024:raise ValueError('Worker output exceeded 2 MB; operation stopped')
            code=await process.wait();first,_,raw=bytes(data).partition(b'\n')
            receipt=json.loads(first)
            if receipt.get('kind')!='enforcement-receipt' or receipt.get('configSha256')!=evidence.digest(config) or receipt.get('scopeRevision')!=run['scopeRevision'] or receipt.get('engagementId')!=run['engagementId'] or receipt.get('runId')!=run['id']:raise ValueError('Worker enforcement receipt is absent or mismatched')
            run['enforcementReceipt']=receipt
            if code:raise ValueError('Linux worker failed; inspect retained operation state')
            from .nmap_results import parse
            services=parse(raw)
            return dict(services=services,output=raw.decode(errors='replace'),enforcementReceipt=receipt,imageId=ready['imageId'],limitations=['Container-scoped observation; execution does not prove exploitation.'])
        finally:
            if process and process.returncode is None:process.kill();await process.wait()
            try:run['workerCleanup']=await asyncio.shield(self.cleanup(run))
            except (ValueError,OSError,TimeoutError) as error:run['workerCleanup']=dict(status='unknown',error=str(error))
            self.manager.workspace.publish()
