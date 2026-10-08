"""Packaged security workflow acceptance using real loopback HTTP/Nmap and local weights."""
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import time
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'artifacts/native/security-workspace'; ART.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py')
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
real.ART=ART;real.STATE=ART/'workspace'

async def main():
    models=real.STATE/'local-runtime/models'
    if not models.exists():
        models.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['cp','-cR',str(ROOT/'artifacts/native/real-acceptance/workspace/local-runtime/models'),str(models)],check=True)
    c=real.Client('--source' in sys.argv);c.allowed.update({'website_assess','save_website_evidence','command_start','security_analysis','web_search','http_request','read_file','list_files'})
    requests=[]
    async def serve(reader,writer):
        try:
            request=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),2)
            parts=request.split(b' ')
            if len(parts)<2:return
            requests.append(parts[1].decode(errors='replace'))
            body=b'<html><title>Wixal native security acceptance</title><body>Loopback service</body></html>'
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
            await writer.drain()
        except (asyncio.IncompleteReadError, TimeoutError, ConnectionError):pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except ConnectionError:pass
    server=await asyncio.start_server(serve,'127.0.0.1',0)
    port=server.sockets[0].getsockname()[1]
    report=dict(status='running',scope='Packaged IPC, real loopback HTTP and Nmap, real local model; no external attack',cases={})
    path=ART/'acceptance.json'
    def save():path.write_text(json.dumps(report,indent=2))
    async def wait(ids):
        async with asyncio.timeout(300):
            while True:
                runs=(await c.state())['securityRuns']
                rows=[r for r in runs if r['id'] in ids]
                if len(rows)==len(ids) and all(r['status'] in ('completed','failed','cancelled') for r in rows):return rows
                await asyncio.sleep(.2)
    save()
    try:
        await c.start()
        await c.call('project-add',dict(root=str(ART)))
        await c.call('settings',dict(enabledTools=[d['function']['name'] for d in (await c.call('hello'))['tools']]))
        target=await c.call('security-target-add',dict(type='Website / API',address=f'http://127.0.0.1:{port}',objective='Validate packaged security evidence'))
        await c.call('security-queue-settings',dict(limit=2,paused=True))
        first=await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='network_scan',arguments=dict(profile='web',ports=str(port)),name='Real loopback Nmap'))
        second=await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='website_assess',arguments=dict(profile='baseline',max_pages=1),name='Real loopback website'))
        await c.call('security-queue-settings',dict(paused=False))
        rows=await wait([first['id'],second['id']])
        assert all(r['status']=='completed' for r in rows),rows
        scan=next(r for r in rows if r['id']==first['id'])
        assert any(s['port']==str(port) and s['state']=='open' for s in scan['result']['services']),scan
        website=next(r for r in rows if r['id']==second['id'])
        assert website['result']['report']['requests'][0]['status']==200,website
        expected_body=b'<html><title>Wixal native security acceptance</title><body>Loopback service</body></html>'
        assert website['result']['report']['requests'][0]['bodySha256']==hashlib.sha256(expected_body).hexdigest()
        assert max(r['started'] for r in rows)<min(r['finished'] for r in rows),'Runs did not overlap'
        report['cases']['parallelRecon']=dict(runs=rows,httpRequests=len(requests),overlap=True);save()
        analysis=await c.call('security-run-add',dict(targetId=target['id'],stage='Research',capability='analysis',model='gemma3:1b',prompt='Identify the observed service and HTTP response evidence. Explain two limits. Do not invent successful exploitation.',dependency=second['id'],name='Real model evidence review'))
        row=(await wait([analysis['id']]))[0]
        assert row['status']=='completed',row
        assert row['result']['usage']['eval_count']>0,row
        assert row['result']['analysis'].strip(),row
        report['cases']['modelAnalysis']=row;save()
        state=await c.state()
        discoveries=[d for d in state['securityDiscoveries'] if d['targetId']==target['id']]
        findings=[f for f in state['securityFindings'] if f['targetId']==target['id']]
        assert any(d['kind']=='service' for d in discoveries)
        assert findings
        await c.call('security-finding-update',dict(id=findings[0]['id'],status='inconclusive',notes='Observed configuration; impact requires validation'))
        source=await c.call('security-run-add',dict(targetId=target['id'],stage='Research',capability='research',model='gemma3:1b',prompt='Explain the observed HTTP content and limits; this local source is not an advisory.',arguments=dict(urls=[target['address']])))
        researched=(await wait([source['id']]))[0]
        assert researched['status']=='completed',researched
        record=next(r for r in (await c.state())['securityResearch'] if r['runId']==source['id'])
        assert record['status']==200 and record['contentSHA256']
        assert record['applicability']=='needs_evidence'
        report['cases']['retrievedSource']=dict(source=record,usage=researched['result']['usage']);save()
        proposal=await c.call('security-run-add',dict(targetId=target['id'],stage='Research',capability='planner',model='gemma3:1b',prompt='Propose exactly one analysis step in the Research stage, with no dependencies. Its prompt should explain the uncertainty in the observed website evidence. Use capability analysis.'))
        proposed=(await wait([proposal['id']]))[0]
        assert proposed['status']=='completed',proposed
        assert proposed['result']['planId']
        report['cases']['realModelPlan']=proposed;save()
        folder=ART/('software-audit-'+str(port));folder.mkdir(exist_ok=True)
        manifest=(ROOT/'package.json').read_bytes();(folder/'package.json').write_bytes(manifest)
        software=await c.call('security-target-add',dict(type='Software',address=folder.name+'/package.json',objective='Inspect actual Wixal declared dependencies'))
        inspected=await c.call('security-run-add',dict(targetId=software['id'],stage='Recon',capability='software_inventory'))
        inventory=(await wait([inspected['id']]))[0]
        assert inventory['status']=='completed' and inventory['result']['components'],inventory
        report['cases']['actualSoftwareManifest']=dict(run=inventory,sourceSHA256=hashlib.sha256(manifest).hexdigest());save()
        plan=await c.call('security-plan-save',dict(targetId=target['id'],name='Real evidence join',nodes=[
            dict(id='a',name='Website evidence',stage='Recon',capability='website_assess',arguments=dict(max_pages=1),dependencies=[]),
            dict(id='b',name='Port evidence',stage='Recon',capability='network_scan',arguments=dict(profile='ports',ports=str(port)),dependencies=[]),
            dict(id='join',name='Joined evidence review',stage='Research',capability='analysis',arguments={},prompt='Explain both collected observations and their limits',dependencies=['a','b'],condition=dict(kind='http_status',value='200')),
            dict(id='skip',name='Unobserved branch',stage='Attacks',capability='website_assess',arguments=dict(max_pages=1),dependencies=['a','b'],condition=dict(kind='http_status',value='599'))
        ]))
        active=await c.call('security-plan-run',dict(id=plan['id'],model='gemma3:1b'))
        async with asyncio.timeout(240):
            while True:
                state=await c.state();rows=[r for r in state['securityRuns'] if r.get('planId')==plan['id']]
                if rows and all(r['status'] in ('completed','failed','skipped','cancelled') for r in rows):break
                await asyncio.sleep(.2)
        assert all(r['status']=='completed' for r in rows if r['nodeId']!='skip'),rows
        assert next(r for r in rows if r['nodeId']=='skip')['status']=='skipped'
        exported=await c.call('security-report-export',dict(targetId=target['id']))
        assert all(Path(p).is_file() for p in exported['paths'])
        report['cases']['graphJoinAndBranch']=dict(planId=plan['id'],runs=rows,report=exported);save()
        report.update(status='passed',execution='source' if c.source else 'packaged',helperSHA256=None if c.source else hashlib.sha256(c.helper.read_bytes()).hexdigest(),finished=time.time())
    except BaseException as error:
        report.update(status='failed',error=str(error));raise
    finally:
        save();await c.close();server.close();await server.wait_closed()
    print(json.dumps(dict(status=report['status'],report=str(path),cases=list(report['cases']))))

asyncio.run(main())
