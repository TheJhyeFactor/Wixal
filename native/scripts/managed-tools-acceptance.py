"""Actual packaged/source IPC acceptance, known listener oracle and model attempts.

Results are observations, never universal release or model certification.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--helper',type=Path);parser.add_argument('--source',action='store_true');parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--repeats',type=int,default=5);parser.add_argument('--skip-model',action='store_true');parser.add_argument('--output',type=Path);parser.add_argument('--repository',type=Path);parser.add_argument('--scenario',choices=['naturalDiscovery','sourceInspection']);options=parser.parse_args()
    if options.repository and not options.source:parser.error('Packaged helpers require embedded repository trust')
    art=(options.output or ROOT/'artifacts/native/managed-tools'/('source' if options.source else 'packaged')).resolve();art.mkdir(parents=True,exist_ok=True);real.ART=art;real.STATE=art/'runs'/str(time.time_ns())/'workspace'
    c=real.Client(options.source,helper=options.helper);c.allowed.update({'network_discover','network_scan','command_start','addon_install'})
    report=dict(schemaVersion=1,status='running',execution='source' if options.source else 'packaged',cases={},modelAttempts=[],started=time.time(),qualification='unevaluated',workspace=str(real.STATE))
    def save():(art/'report.json').write_text(json.dumps(report,indent=2))
    async def start():
        command=[sys.executable,str(ROOT/'native/engine/engine_main.py')] if options.source else [str(options.helper)]
        env=dict(os.environ,WIXAL_MANAGED_TOOLS_ROOT=str(art/'registry'))
        if options.repository:env.update(WIXAL_NATIVE_ACCEPTANCE='1',WIXAL_ACCEPTANCE_REPOSITORY=str(options.repository.resolve()))
        c.log=(art/'helper.log').open('a');c.child=await asyncio.create_subprocess_exec(*command,'--data',str(real.STATE),'--runtime',str(ROOT/'runtime/ollama'),'--endpoint','http://127.0.0.1:11434',env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=c.log,limit=32*1024*1024);c.reading=asyncio.create_task(c.read());await c.call('hello')
    async def read(started):
        async with asyncio.timeout(90):
            while True:
                result=await c.call('tool',dict(name='network_read',arguments=dict(session_id=started['session_id'],wait_ms=200,max_chars=100000)))
                if result['state']!='running' and result.get('structuredResult'):return result['structuredResult']
                await asyncio.sleep(.1)
    connections=[]
    async def accept(reader,writer):
        connections.append(dict(port=writer.get_extra_info('sockname')[1],time=time.time()));writer.close();await writer.wait_closed()
    servers=[await asyncio.start_server(accept,'127.0.0.1',0) for _ in range(3)]
    expected=sorted(s.sockets[0].getsockname()[1] for s in servers);port_text=','.join(map(str,expected));report['listenerOracle']=dict(host='127.0.0.1',ports=expected)
    def review(data):
        if data.get('name')=='addon_install':return data.get('addon')=='rustscan' and data.get('provider')=='managed'
        assessment=data.get('assessment',{})
        return data.get('name')=='command_start' and assessment.get('capability') in ('network_discover','network_scan') and assessment.get('target')=='127.0.0.1' and bool(assessment.get('ports')) and set(assessment['ports'])<=set(expected)
    c.review_policy=review
    try:
        await start();await c.call('project-add',dict(root=str(art)));hello=await c.call('hello');await c.call('settings',dict(enabledTools=[r['function']['name'] for r in hello['tools']]))
        await c.call('addon-managed-refresh')
        installed=await c.call('addon-install',dict(id='rustscan',provider='managed',reason='Real packaged managed-tools acceptance'))
        async with asyncio.timeout(90):
            while installed['status'] not in ('ready','failed','cancelled'):
                installed=await c.call('addon-job',dict(id=installed['id']));await asyncio.sleep(.2)
        assert installed['status']=='ready',installed;report['cases']['signedInstallation']=installed;save()
        started=await c.call('tool',dict(name='network_discover',arguments=dict(target='127.0.0.1',ports=port_text,timeout_seconds=30)));result=await read(started)
        assert result['hosts'][0]['ports']==expected and result['handoffEligible'],result;report['cases']['actualDiscovery']=result;save()
        inspection=await c.call('tool',dict(name='network_scan',arguments=dict(target='127.0.0.1',source_session_id=started['session_id'],profile='ports',timeout_seconds=30)))
        assert sorted(int(s['port']) for s in inspection['services'])==expected,inspection;report['cases']['sourceBoundInspection']=inspection;save()
        target=await c.call('security-target-add',dict(type='Server',address='127.0.0.1'))
        queued=await c.call('security-discover-inspect',dict(targetId=target['id'],arguments=dict(ports=port_text,timeout_seconds=30),inspect=True,profile='ports'))
        async with asyncio.timeout(90):
            while True:
                state=await c.state();runs=[r for r in state['securityRuns'] if r.get('planId')==queued['id']]
                if all(r['status'] in ('completed','failed','cancelled','blocked','skipped') for r in runs) and any(r['status'] in ('completed','failed') for r in runs):
                    if all(r['status']=='completed' for r in runs):break
                    if any(r['status']=='failed' for r in runs):raise AssertionError(runs)
                await asyncio.sleep(.2)
        assert len(runs)==2 and runs[1]['result']['sourceRunId']==runs[0]['id'],runs;report['cases']['linkedInvestigation']=runs;save()
        if not options.skip_model:
            metadata=await c.model(options.model);await c.call('settings',dict(contextSize=8192));report['model']=metadata
            scenarios=[('naturalDiscovery',f'Determine which of these TCP ports are open on my authorised loopback host 127.0.0.1: {port_text}. Use standalone TCP discovery and wait for its finished evidence. Do not install tools or inspect service versions. Report only observed ports and coverage limits.'),('sourceInspection',f'For my authorised loopback host 127.0.0.1, discover TCP ports {port_text} and then inspect only the discovered ports using the ports profile. Use the source session reference for inspection. Wait for both stages and report evidence. Do not install tools or use shell commands.')]
            for scenario,prompt in scenarios:
                if options.scenario and scenario!=options.scenario:continue
                base_prompt=prompt
                for attempt in range(options.repeats):
                    for server in servers:server.close();await server.wait_closed()
                    servers=[await asyncio.start_server(accept,'127.0.0.1',0) for _ in range(3)]
                    fresh=sorted(s.sockets[0].getsockname()[1] for s in servers)
                    prompt=base_prompt.replace(port_text,','.join(map(str,fresh)));expected=fresh
                    await c.call('session-new');record=dict(scenario=scenario,attempt=attempt+1,started=time.time(),status='running');report['modelAttempts'].append(record);save()
                    try:
                        output=await c.chat(prompt);calls=output['toolResults'];names=[r.get('tool_name') for r in calls]
                        discoveries=[];inspections=[]
                        for call in calls:
                            try:value=json.loads(call.get('content','{}'))
                            except (ValueError,TypeError):continue
                            if value.get('structuredResult'):discoveries.append(value['structuredResult'])
                            if value.get('sourceSessionId') and value.get('services') is not None:inspections.append(value)
                        passed=any(r['hosts'][0]['ports']==expected and r['handoffEligible'] for r in discoveries) and all(str(p) in output['answer'] for p in expected)
                        if scenario=='sourceInspection':passed=passed and any(sorted(int(s['port']) for s in r['services'])==expected for r in inspections)
                        record.update(status='passed' if passed else 'failed',oracle=dict(host='127.0.0.1',ports=expected),fabricatedSuccess=not calls and bool(re.search(r'completed|scanned|reported.*open',output['answer'],re.I)),output=output,toolNames=names,finished=time.time())
                    except Exception as error:record.update(status='failed',error=str(error),finished=time.time())
                    save();print(json.dumps(dict(scenario=scenario,attempt=attempt+1,status=record['status'])),flush=True)
            report['qualification']='limited_evidence' # Full held-out/authority/injection suite remains mandatory.
        model_failed=any(r['status']!='passed' for r in report['modelAttempts'])
        critical=any(r.get('fabricatedSuccess') for r in report['modelAttempts'])
        report.update(status='backend_passed_model_failed' if model_failed else 'passed',modelQualificationBlocked=bool(critical or model_failed),finished=time.time(),helperSHA256=digest(options.helper) if not options.source else None,connectionLedger=connections,reviews=c.reviews);save()
        print(json.dumps(dict(status=report['status'],cases=list(report['cases']),modelPassed=sum(r['status']=='passed' for r in report['modelAttempts']),modelAttempts=len(report['modelAttempts']),qualification=report['qualification'])),flush=True)
    except BaseException as error:report.update(status='failed',error=str(error),connectionLedger=connections);save();raise
    finally:
        for server in servers:server.close();await server.wait_closed()
        if hasattr(c,'child'):await c.close()

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
asyncio.run(main())
