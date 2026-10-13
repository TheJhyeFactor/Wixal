"""Actual local-model tool utilisation and packaged IPC on synthetic local data."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real_acceptance',ROOT/'native/scripts/real-acceptance.py')
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)


async def main(args):
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    real.ART=output;real.STATE=output/'data';project=output/'project';project.mkdir(exist_ok=True)
    helper=Path(args.app)/'Contents/Resources/engine/wixal-engine' if args.app else None
    payload=Path(args.app)/'Contents/Resources/ollama' if args.app else ROOT/'runtime/ollama'
    c=real.Client(not bool(args.app),helper=helper,payload=payload,endpoint=args.endpoint)
    c.allowed|={'cyber_manage','cyber_sensor_enroll','cyber_sensor_start','security_engagement_scope','security_analysis'}
    report=dict(status='running',model=args.model,source=not bool(args.app),cases=[],reviews=[])
    if helper:report['helperSha256']=hashlib.sha256(helper.read_bytes()).hexdigest()
    def save():(output/'results.json').write_text(json.dumps(report,indent=2))
    async def action(name,**values):return await c.call('security-cyber-manage',dict(engagementId=eid,action=name,parameters=values))
    async def model_case(name,prompt,tool,action_name):
        await c.call('session-new')
        result=await c.call('chat',dict(text=prompt),timeout=600)
        state=await c.state();task=next(t for t in reversed(state['tasks']) if t['sessionId']==state['activeSession'])
        checkpoints=[p for p in task['checkpoints'] if p['name']==tool and p.get('arguments',{}).get('action')==action_name]
        row=dict(name=name,status=result['status'],checkpoints=checkpoints,
                 messages=[m for s in state['sessions'] if s['id']==state['activeSession'] for m in s['messages'] if m['role']=='assistant'])
        report['cases'].append(row);save()
        assert result['status']=='completed',row
        assert any(p['status']=='finished' for p in checkpoints),row
        return state
    save()
    try:
        await c.start()
        models=await c.call('models');assert any(m['name']==args.model for m in models),'Requested local weights are unavailable; no downloads performed'
        await c.call('project-add',dict(root=str(project)))
        await c.call('settings',dict(mode='agent',model=args.model,contextSize=16384,enabledTools=['workspace_info','cyber_read','cyber_manage','load_skill']))
        target=await c.call('security-target-add',dict(type='Server',address='127.0.0.1',objective='Synthetic local evidence only'))
        engagement=await c.call('security-engagement-create',dict(name='CYBER-ADAPTATION-7319',objective='Inspect synthetic retained evidence and produce an unverified observation report',targetIds=[target['id']]))
        eid=engagement['id']
        (project/'fixture.json').write_text(json.dumps(dict(observation='Synthetic status change; no vulnerability proved',token='synthetic-secret-do-not-export')))
        ref=await c.call('security-evidence-import',dict(engagementId=eid,path='fixture.json'))
        await model_case('discover','Use cyber_read with action catalog. State the exact name and ID of the current project engagement. Do not call other actions.','cyber_read','catalog')
        await model_case('planning','Use cyber_read action dossier for engagement '+eid+'. Identify three missing planning fields. Do not modify anything.','cyber_read','dossier')
        draft=dict(targetId=target['id'],title='Synthetic observation 7319',resultKind='observation',confidence='low',evidenceIds=[ref['id']],
                   description='Synthetic retained observation only',impact='No impact demonstrated',assumptions='External fixture assertions are unverified',
                   counterevidence='No independently collected target response is supplied',confidenceRationale='Synthetic imported evidence only',
                   severityChangeConditions='Independent target evidence would be needed',remediation='No remediation claim is supported',retestPlan='Collect comparable permitted observations first')
        state=await model_case('finding-draft','Use cyber_manage action finding_save for engagement '+eid+' with parameters_json containing exactly this object: '+json.dumps(draft)+'. Save once. Do not score or confirm it.','cyber_manage','finding_save')
        findings=[f for f in state['securityFindings'] if f.get('engagementId')==eid]
        assert len(findings)==1 and findings[0]['verificationState']=='unverified' and findings[0]['title']==draft['title']
        await model_case('report-export','Use cyber_manage action export for engagement '+eid+' with parameters_json {"includeEvidence":false}. Return the actual saved paths. Do not use file tools.','cyber_manage','export')
        archives=list(project.glob('cyber-*.zip'));assert len(archives)==1
        with zipfile.ZipFile(archives[0]) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            for name,info in manifest['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==info['sha256']
            assert b'synthetic-secret-do-not-export' not in b' '.join(archive.read(n) for n in archive.namelist())
        (project/'service.log').write_text('{"message":"authentication failed", "status":401}\n{"message":"healthy", "status":200}\n')
        sensor=await action('sensor_enroll',path='service.log',targetId=target['id'])
        await c.call('security-engagement-approve',dict(engagementId=eid,baseRevision=1))
        await action('sensor_start',sensorId=sensor['id'])
        for _ in range(100):
            state=await c.state()
            if any(i.get('engagementId')==eid for i in state['securityIncidents']):break
            await asyncio.sleep(.1)
        assert len([i for i in state['securityIncidents'] if i.get('engagementId')==eid])==1
        await action('sensor_stop',sensorId=sensor['id'])
        await model_case('defensive-lead','Use cyber_read action sensors for engagement '+eid+'. State incident count, its status and the coverage limitation. Do not claim compromise or block anything.','cyber_read','sensors')
        async def specialist_case(name,role,reference):
            assignment=await c.call('security-specialist-assign',dict(engagementId=eid,targetId=target['id'],role=role,
                question='Describe only the supplied observations, cite the evidence identity, and explain the coverage and verification limitations.',model=args.model,evidenceIds=[reference]))
            for _ in range(3000):
                state=await c.state();run=next(r for r in state['securityRuns'] if r['id']==assignment['runId'])
                if run['status'] in ('completed','failed','cancelled','interrupted'):break
                await asyncio.sleep(.1)
            assert run['status']=='completed',run
            assert run['result']['usage']['eval_count']>0 and run['result']['analysis'].strip()
            report['cases'].append(dict(name=name,status='completed',run=run));save()
        state=await c.state();sensor=next(s for s in state['securitySensors'] if s['id']==sensor['id'])
        await specialist_case('defensive-specialist','defensive_analyst',sensor['lastEvidenceId'])
        (project/'sample.bin').write_bytes(b'\x7fELFsynthetic-static-evidence-7319\0')
        binary=await action('binary_triage',path='sample.bin',targetId=target['id'])
        await specialist_case('binary-specialist','binary_analyst',binary['id'])
        state=await c.state();before=dict(findings=len(state['securityFindings']),incidents=len(state['securityIncidents']),evidence=len(state['securityEvidence']))
        await c.close();await c.start();state=await c.state()
        assert len(state['securityFindings'])==before['findings'] and len(state['securityIncidents'])==before['incidents'] and len(state['securityEvidence'])==before['evidence']
        assert next(e for e in state['securityEngagements'] if e['id']==eid)['status']=='paused'
        assert all(s['status']=='paused' for s in state['securitySensors'])
        report['restart']=dict(status='passed',counts=before)
        if helper:assert hashlib.sha256(helper.read_bytes()).hexdigest()==report['helperSha256']
        report.update(status='passed',reviews=c.reviews);save()
    except BaseException as error:report.update(status='failed',error=str(error),reviews=c.reviews);save();raise
    finally:await c.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app');parser.add_argument('--model',required=True);parser.add_argument('--endpoint',required=True);parser.add_argument('--output',required=True)
    asyncio.run(main(parser.parse_args()))
