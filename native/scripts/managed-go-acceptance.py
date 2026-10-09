"""Actual controlled-source package installs, leased ffuf and project advisory scans."""
import argparse
import asyncio
import hashlib
import json
import importlib.util
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'native/engine'))
from wixal.service import Service
from wixal.managed_tools import PackageRegistry,digest

async def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--helper',type=Path,help='Actual packaged helper with embedded trust');p.add_argument('--nuclei-template',type=Path,required=True,help='Explicit pinned official signed HTTP template');o=p.parse_args()
    art=o.output.resolve();art.mkdir(parents=True,exist_ok=False);project=art/'project';project.mkdir()
    for name in ('package.json','package-lock.json'):(project/name).write_bytes((ROOT/name).read_bytes())
    requests=[];hold=asyncio.Event()
    async def serve(reader,writer):
        try:
            raw=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),5);route=raw.split(b' ')[1].decode();requests.append(dict(route=route,time=time.time()))
            await hold.wait();body=b'controlled loopback route' if route=='/known' else b'missing';status=b'200 OK' if route=='/known' else b'404 Not Found'
            writer.write(b'HTTP/1.1 '+status+b'\r\nContent-Type: text/html\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);await writer.drain()
        except (TimeoutError,ConnectionError,asyncio.IncompleteReadError):pass
        finally:writer.close();await writer.wait_closed()
    server=await asyncio.start_server(serve,'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
    def emit(event,data):
        if event=='review':asyncio.create_task(service.dispatch('respond',dict(id=data['id'],value=data.get('name')=='command_start')))
    registry=PackageRegistry(art/'registry',json.loads(o.repository.read_text()))
    if o.helper:
        spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'));real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
        service=real.Client(False,helper=o.helper);service.review_policy=lambda data:data.get('name')=='command_start' and data.get('assessment',{}).get('capability') in ('addon:ffuf','addon:nuclei','addon:trivy','addon:osv-scanner')
        service.log=(art/'helper.log').open('a');service.child=await asyncio.create_subprocess_exec(str(o.helper),'--data',str(art/'workspace'),'--runtime',str(ROOT/'runtime/ollama'),'--endpoint','http://127.0.0.1:11434',env=dict(os.environ,WIXAL_MANAGED_TOOLS_ROOT=str(art/'registry')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=service.log,limit=32*1024*1024);service.reading=asyncio.create_task(service.read());dispatch=service.call
    else:
        service=Service(art/'workspace',ROOT/'runtime/ollama',emit,'http://127.0.0.1:11434');service.addons.managed=registry;dispatch=service.dispatch
    report=dict(status='running',cases={},requestLedger=requests,execution='actual packaged helper' if o.helper else 'actual source engine and controlled-source executables',helperSha256=digest(o.helper) if o.helper else None,started=time.time())
    def save():(art/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    async def completed(started):
        if o.helper:
            async with asyncio.timeout(330):
                while True:
                    result=await dispatch('tool',dict(name='command_read',arguments=dict(session_id=started['session_id'],wait_ms=200,max_chars=100000)))
                    if result['state']!='running':return result
                    await asyncio.sleep(.1)
        job=service.tools.jobs[started['session_id']];await job['collector']
        return await service.tools.read_job(dict(session_id=job['id'],max_chars=100000),service.store.session()['id'])
    try:
        await dispatch('project-add',dict(root=str(project)));hello=await dispatch('hello',{})
        await dispatch('settings',dict(enabledTools=[x['function']['name'] for x in hello['tools']]))
        for tool in ['ffuf','nuclei','trivy','osv-scanner']:
            job=await dispatch('addon-install',dict(id=tool,provider='managed',reason='Verify controlled-source package readiness'))
            while job['status'] not in ('ready','failed','cancelled'):
                await asyncio.sleep(.1);job=await dispatch('addon-job',dict(id=job['id']))
            assert job['status']=='ready',job
            report['cases'][tool+'Install']=dict(status='passed',receipt=job,executable=registry.resolve(tool));save()
        import shutil
        external=shutil.which('ffuf');external_hash=digest(external) if external else None
        (project/'words.txt').write_text('known\nmissing\n')
        started=await dispatch('tool',dict(name='addon_run',arguments=dict(id='ffuf',target=f'http://127.0.0.1:{port}',path='words.txt',timeout_seconds=30)))
        async with asyncio.timeout(10):
            while not requests:await asyncio.sleep(.02)
        try:registry.remove(tool='ffuf')
        except ValueError as error:assert 'lease' in str(error)
        else:raise AssertionError('Managed ffuf removal was allowed during its active run')
        hold.set();result=await completed(started)
        assert result['exitCode']==0 and '/known' in result['output'] and '200' in result['output'],result
        assert requests and {r['route'] for r in requests}=={'/known','/missing'},requests
        report['cases']['ffufActualRoutesAndLease']=dict(status='passed',result=result,oracle=requests);save()
        assert not external or digest(external)==external_hash
        template=project/'selected-template.yaml';template.write_bytes(o.nuclei_template.read_bytes())
        before=len(requests)
        started=await dispatch('tool',dict(name='addon_run',arguments=dict(id='nuclei',target=f'http://127.0.0.1:{port}/known',template=template.name,timeout_seconds=60)))
        result=await completed(started)
        assert result['exitCode']==0 and 'http-missing-security-headers' in result['output'] and len(requests)>before,result
        assert all(r['route']=='/known' for r in requests[before:]),requests[before:]
        report['cases']['nucleiActualSignedHTTPTemplate']=dict(status='passed',result=result,templateSha256=digest(template),oracle=requests[before:]);save()
        for tool in ['osv-scanner','trivy']:
            started=await dispatch('tool',dict(name='addon_run',arguments=dict(id=tool,path='.',timeout_seconds=300)))
            result=await completed(started)
            assert result['exitCode'] in (0,1) and ('results' in result['output'].lower() if tool=='osv-scanner' else 'results' in result['output'].lower() or 'artifactname' in result['output'].lower()),result
            report['cases'][tool+'ActualProject']=dict(status='passed',result=result,inputs={name:digest(project/name) for name in ('package.json','package-lock.json')});save()
        report.update(status='passed',finished=time.time());save();print(json.dumps(dict(status=report['status'],cases=list(report['cases']))))
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:hold.set();server.close();await server.wait_closed();await service.close()
asyncio.run(main())
