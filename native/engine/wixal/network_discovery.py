"""Bounded RustScan discovery and immutable, source-owned Nmap handoff."""
import asyncio
import hashlib
import ipaddress
import json
import os
import re
import resource
import shlex
import shutil
import socket
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from .managed_tools import ADAPTER, canonical, controlled_environment, digest

DEFAULT_PORTS='22,80,443,8080,8443'


def ports(value):
    if not isinstance(value,str) or len(value)>8000 or not re.fullmatch(r'\d{1,5}(?:-\d{1,5})?(?:,\d{1,5}(?:-\d{1,5})?)*',value):raise ValueError('Invalid selected TCP ports')
    result=set()
    for part in value.split(','):
        values=list(map(int,part.split('-')));low,high=values[0],values[-1]
        if not 1<=low<=high<=65535:raise ValueError('TCP ports must be 1–65535')
        result.update(range(low,high+1))
    return sorted(result)


def target_host(target):
    if not isinstance(target,str) or not target or len(target)>500 or any(c in target for c in '\r\n\\@'):raise ValueError('Invalid discovery target')
    if '://' in target:
        parsed=urlsplit(target)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Use an authorised website origin')
        return parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80)
    try:return str(ipaddress.ip_address(target)),None
    except ValueError:
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?',target) or any(not p or len(p)>63 for p in target.split('.')):raise ValueError('Discovery requires one host; subnet discovery is not supported by this contract')
        return target.lower(),None


def authorize(plan,active):
    if active.get('_branchRoot') or active.get('reviewPolicy')=='Read only':raise ValueError('Discovery is unavailable in this task boundary')
    if not active.get('restrictTargets'):return
    allowed=active.get('authority',{}).get('targets',[])
    host,_=target_host(plan['target']);wanted=set(plan['ports']);addresses=plan['addresses']
    for rule in allowed:
        if '://' in rule:
            expected=urlsplit(rule);port=expected.port or (443 if expected.scheme=='https' else 80)
            actual=urlsplit(plan['target']) if '://' in plan['target'] else None
            if actual and actual.scheme==expected.scheme and host==expected.hostname and wanted<={port}:return
        elif '/' in rule:
            net=ipaddress.ip_network(rule,strict=False)
            if all(ipaddress.ip_address(address) in net for address in addresses):return
        elif rule.lower()==host:return
    raise ValueError('Discovery address or port coverage is outside the authorised scope')


async def plan(args,active=None):
    active=active or {};host,url_port=target_host(args['target'])
    coverage=args.get('coverage','selected');pace=args.get('pace','careful');seconds=args.get('timeout_seconds',180)
    if coverage not in ('selected','all_tcp') or pace not in ('careful','balanced') or type(seconds)!=int or not 10<=seconds<=600:raise ValueError('Invalid coverage, pace or deadline')
    if coverage=='all_tcp' and 'ports' in args:raise ValueError('All TCP coverage cannot include selected ports')
    requested=list(range(1,65536)) if coverage=='all_tcp' else ports(args.get('ports',str(url_port) if url_port else DEFAULT_PORTS))
    try:addresses=[str(ipaddress.ip_address(host))]
    except ValueError:
        values=await asyncio.get_running_loop().getaddrinfo(host,None,type=socket.SOCK_STREAM)
        addresses=sorted({str(ipaddress.ip_address(row[4][0])) for row in values})
    if not 1<=len(addresses)<=4:raise ValueError('Hostname resolution must yield 1–4 addresses')
    if coverage=='selected' and len(requested)>1024:raise ValueError('Selected-port discovery supports up to 1,024 ports; choose explicit all TCP coverage for a broader scan')
    pairs=len(requested)*len(addresses)
    if pairs>262140:raise ValueError('Discovery workload exceeds the address/port budget')
    soft,_=resource.getrlimit(resource.RLIMIT_NOFILE)
    batch=min(32 if pace=='careful' else 128,max(0,int(soft)-64))
    if batch<8:raise ValueError('Insufficient file descriptor headroom for discovery')
    result=dict(target=args['target'],addresses=addresses,ports=requested,coverage=coverage,pace=pace,batchSize=batch,attemptTimeoutMS=2000 if pace=='careful' else 1500,tries=2,timeoutSeconds=seconds,connectionPairs=pairs,retryAllowance=pairs*2,resolvedAt=time.time())
    authorize(result,active);return result


def parse(stdout,invocation,complete=True):
    observations={};warnings=[];valid=True;requested=set(invocation['ports'])
    for line in stdout.splitlines():
        if not line.strip():continue
        match=re.fullmatch(r'\s*(\S+)\s*->\s*\[([\d,\s]*)\]\s*',line)
        if not match:
            warnings.append(line[:500]);valid=False;continue
        try:
            address=str(ipaddress.ip_address(match[1]));values=[] if not match[2].strip() else [int(v.strip()) for v in match[2].split(',')]
            if address not in invocation['addresses'] or any(p not in requested for p in values):raise ValueError('Result escapes the pinned address/port set')
            observations.setdefault(address,set()).update(values)
        except ValueError as error:warnings.append(str(error));valid=False
    hosts=[dict(host=host,ports=sorted(observations.get(host,set()))) for host in invocation['addresses']]
    result=dict(schemaVersion=1,scanner='RustScan',parserRevision=1,invocation=invocation,hosts=hosts,services=[dict(host=h['host'],port=str(p),protocol='tcp',state='open',service={}) for h in hosts for p in h['ports']],warnings=warnings[:100],coverage='completed_attempts' if complete and valid else 'partial' if not complete else 'indeterminate',handoffEligible=bool(complete and valid),interpretation='Observed open TCP ports only. No open ports detected does not establish host absence, closed ports or service safety.')
    result['resultSha256']=canonical(result);return result


class SocketBudget:
    def __init__(self):self.used=0;self.condition=asyncio.Condition()
    async def acquire(self,count):
        async with self.condition:
            await self.condition.wait_for(lambda:self.used+count<=256);self.used+=count
    async def release(self,count):
        async with self.condition:self.used-=count;self.condition.notify_all()


def executable(tools):
    manager=getattr(tools.store,'addons',None)
    if manager and manager.managed.snapshot()['provider']=='managed':return manager.managed.acquire('network discovery')
    path=manager.external_executable(manager.spec('rustscan')) if manager else shutil.which('rustscan')
    if not path:raise ValueError('RustScan is unavailable. Install a compatible package in Tools or select direct Nmap.')
    child=subprocess_version(path)
    if not re.fullmatch(r'rustscan 2\.(3|4)\.\d+',child):raise ValueError('Unsupported external RustScan CLI version')
    return dict(path=str(Path(path).resolve()),provider='external_homebrew',version=child.split()[-1],executableSha256=digest(path),adapter=ADAPTER)


def subprocess_version(path):
    import subprocess
    with tempfile.TemporaryDirectory(prefix='wixal-tool-verify-') as home:
        result=subprocess.run([path,'--version'],capture_output=True,timeout=10,cwd=home,env=controlled_environment(home))
        if result.returncode or len(result.stdout)>4096:raise ValueError('External executable readiness failed')
        return result.stdout.decode().strip()


async def start(tools,args,session):
    from .agent_context import profile
    invocation=await plan(args,profile.get() or {})
    manager=getattr(tools.store,'addons',None)
    budget=getattr(manager,'socket_budget',None)
    if budget is None:
        budget=getattr(tools,'socket_budget',None) or SocketBudget();tools.socket_budget=budget
    await budget.acquire(invocation['batchSize'])
    handle=None;home=None
    try:
        acquisition=asyncio.create_task(asyncio.to_thread(executable,tools))
        try:handle=await asyncio.shield(acquisition)
        except asyncio.CancelledError:
            handle=await acquisition
            raise
        home=Path(tempfile.mkdtemp(prefix='wixal-rustscan-'));config=home/'empty.toml';config.write_text('')
        argv=[handle['path'],'--config-path',str(config),'--no-config','--scripts','none','--greppable','--no-banner','--addresses',','.join(invocation['addresses']),*(['--range','1-65535'] if invocation['coverage']=='all_tcp' else ['--ports',','.join(map(str,invocation['ports']))]),'--batch-size',str(invocation['batchSize']),'--timeout',str(invocation['attemptTimeoutMS']),'--tries','2']
        invocation.update(executable={k:v for k,v in handle.items() if k!='lease'},argv=argv,adapterRevision=1)
        async def finished(job):
            try:
                raw=Path(job['evidence']['stdoutPath']).read_text(errors='replace')
                result=parse(raw,invocation,complete=job['state']=='completed' and job['exitCode']==0 and not job['evidence']['incomplete'])
                result.update(evidence=job['evidence'],termination=job['reason'],exitCode=job['exitCode'])
                result['resultSha256']=canonical({k:v for k,v in result.items() if k!='resultSha256'})
                job['structuredResult']=result
            finally:
                if handle.get('lease'):manager.managed.release(handle['lease'])
                await budget.release(invocation['batchSize']);shutil.rmtree(home)
        result=await tools.start_command(shlex.join(argv),invocation['timeoutSeconds'],session,argv=argv,assessment=dict(capability='network_discover',target=invocation['target'],addresses=invocation['addresses'],ports=invocation['ports'],connectionPairs=invocation['connectionPairs'],retryAllowance=invocation['retryAllowance'],executable=invocation['executable']),environment=controlled_environment(home),on_finished=finished,retain_evidence=True)
        if isinstance(result,dict):
            job=tools.jobs[result['session_id']]
            if handle.get('lease'):manager.managed.bind_lease(handle['lease'],job['child'].pid)
            result.update(coverage=invocation['coverage'],addresses=invocation['addresses'],connectionPairs=invocation['connectionPairs'],retryAllowance=invocation['retryAllowance'],executable=invocation['executable'],read='network_read',stop='network_stop')
            return result
        raise ValueError(result)
    except BaseException:
        if handle and handle.get('lease'):manager.managed.release(handle['lease'])
        await budget.release(invocation['batchSize'])
        if home:shutil.rmtree(home)
        raise


def source_result(tools,args,session):
    if args.get('source_run_id') and args.get('source_session_id'):raise ValueError('Choose one immutable discovery source')
    reference=args.get('source_run_id');source=None
    if reference:
        project=(tools.store.project() or {}).get('id')
        source=next((r for r in tools.store.data.get('securityRuns',[]) if r['id']==reference and r['projectId']==project and r['address']==args['target'] and r['capability']=='network_discover' and r['status']=='completed'),None)
        if not source:raise ValueError('Discovery source belongs to another project/target or did not complete')
        if getattr(tools,'security_target_id',source['targetId'])!=source['targetId']:raise ValueError('Discovery source belongs to another investigation target')
        result=source.get('result',{})
    else:
        job=tools.jobs.get(args.get('source_session_id'))
        if not job or job['owner']!=session or job['projectId']!=(tools.store.project() or {}).get('id') or job['state']!='completed':raise ValueError('Discovery session belongs to another conversation/project or did not complete')
        result=job.get('structuredResult',{})
        if result.get('invocation',{}).get('target')!=args['target']:raise ValueError('Discovery target cannot change')
    if not result.get('handoffEligible') or result.get('resultSha256')!=canonical({k:v for k,v in result.items() if k!='resultSha256'}):raise ValueError('Discovery evidence is partial, malformed or has changed')
    if 'ports' in args:raise ValueError('Source-bound inspection derives ports; conflicting manual ports are forbidden')
    if args.get('profile','services')=='discovery':raise ValueError('Inspection requires a port inspection profile')
    return result


async def inspect(tools,args,session):
    from .tools import scan_plan
    from .agent_context import profile
    result=source_result(tools,args,session);mapping=[]
    for host in result['hosts']:
        selected=host['ports']
        if args.get('profile')=='ssh':selected=[p for p in selected if p==22]
        for offset in range(0,len(selected),256):mapping.append(dict(target=host['host'],ports=','.join(map(str,selected[offset:offset+256])),profile=args.get('profile','services')))
    if not mapping:return dict(state='completed',services=[],sourceResultSha256=result['resultSha256'],skipped=True,reason='No open ports detected for the selected profile')
    authorize(result['invocation'],profile.get() or {})
    path=shutil.which('nmap') or ('/opt/homebrew/bin/nmap' if Path('/opt/homebrew/bin/nmap').exists() else None)
    if not path:raise ValueError('Nmap is required for inspection; discovery evidence remains available')
    end=time.monotonic()+args.get('timeout_seconds',180);outputs=[];services=[];evidence=[]
    for bound in mapping:
        remaining=int(end-time.monotonic())
        if remaining<1:raise ValueError('Shared inspection deadline exhausted')
        bound['timeout_seconds']=remaining;argv=[path,*scan_plan(bound)]
        started=await tools.start_command(shlex.join(argv),remaining,session,argv=argv,assessment=dict(capability='network_scan',target=args['target'],addresses=[bound['target']],ports=ports(bound['ports']),sourceRunId=args.get('source_run_id'),sourceSessionId=args.get('source_session_id'),sourceResultSha256=result['resultSha256']),environment=controlled_environment(Path(path).parent),retain_evidence=True)
        if not isinstance(started,dict):raise ValueError(str(started))
        job=tools.jobs[started['session_id']]
        await job['collector']
        raw=Path(job['evidence']['stdoutPath']).read_text(errors='replace');outputs.append(raw);evidence.append(job['evidence'])
        if job['state']!='completed' or job['exitCode']!=0 or job['evidence']['incomplete']:
            return dict(state='failed',coverage='partial',error='Inspection failed or incomplete; raw evidence retained',services=services,evidence=evidence,sourceRunId=args.get('source_run_id'),sourceSessionId=args.get('source_session_id'),sourceResultSha256=result['resultSha256'],output='\n'.join(outputs)[-100000:])
        import xml.etree.ElementTree as ET
        xml=ET.fromstring(raw)
        for host in xml.findall('host'):
            address=host.find('address')
            for p in host.findall('./ports/port'):
                if address is None or address.get('addr')!=bound['target'] or int(p.get('portid')) not in ports(bound['ports']):raise ValueError('Inspection result escapes source binding')
                state=p.find('state');service=p.find('service')
                services.append(dict(host=address.get('addr'),port=p.get('portid'),protocol=p.get('protocol'),state=state.get('state','') if state is not None else '',service=dict(service.attrib) if service is not None else {}))
    return dict(state='completed',services=services,sourceResultSha256=result['resultSha256'],sourceRunId=args.get('source_run_id'),sourceSessionId=args.get('source_session_id'),invocations=mapping,evidence=evidence,output='\n'.join(outputs)[-100000:])
