"""Actual Hub download/inference and scoped API/Keychain acceptance in an owned lab."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)


async def main(args):
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True);real.ART=output;real.STATE=output/'data'
    project=output/'project';project.mkdir(exist_ok=True)
    app=Path(args.app).resolve();helper=app/'Contents/Resources/engine/wixal-engine';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(status='running',app=str(app),helperSha256=sha(helper),cases={})
    def save():(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def milestone(name,value):report['cases'][name]=value;save();print(name+' passed',flush=True)
    observations=[];synthetic='WIXAL-OWNED-API-TOKEN-20261012';cred=None;c=None;created_model=False;name=None
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            authenticated=self.headers.get('Authorization')=='Bearer '+synthetic
            body=dict(private=True,echo=synthetic) if authenticated else dict(error='denied',private=False)
            status=200 if authenticated else 403
            raw=json.dumps(body).encode();observations.append(dict(path=self.path,status=status,authenticated=authenticated,time=int(__import__('time').time()*1000),sha256=hashlib.sha256(raw).hexdigest()))
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    c=real.Client(False,helper=helper,payload=app/'Contents/Resources/ollama',endpoint=args.endpoint)
    c.allowed={'security_engagement_scope','security_credential_lease','security_api_observe','security_analysis','security_cleanup_disposition'}
    try:
        await c.start();await c.call('project-add',dict(root=str(project)))
        installed=await c.call('models')
        catalog=(await c.call('model-status'))['catalog'];selected=next(m for m in catalog if m['repo']=='Qwen/Qwen3-0.6B-GGUF')
        name=selected['name'];created_model=not any(m['name']==name for m in installed)
        result=await c.call('model-pull',dict(name=name))
        job=next(j for j in result['downloads'] if j['name']==name)
        for _ in range(1800):
            status=await c.call('model-status');job=next(j for j in status['downloads'] if j['id']==job['id'])
            if job['state'] in ('completed','failed'):break
            await asyncio.sleep(.2)
        assert job['state']=='completed',job
        cached=real.STATE/'local-runtime/huggingface'/(job['sha256']+'.gguf')
        assert cached.stat().st_size==job['size'] and sha(cached)==job['sha256']
        model=next(m for m in await c.call('models') if m['name']==name)
        assert model['provenance']['revision']==job['revision'];assert model['provenance']['sha256']==job['sha256']
        milestone('huggingFaceDownloadImport',dict(job=job,installed=model,bytes=cached.stat().st_size,localFileSha256=sha(cached)))
        await c.call('model-use',dict(name=name));await c.call('session-new')
        answer=await c.chat('Reply with exactly: LOCAL MODEL READY')
        assert 'LOCAL MODEL READY' in answer['answer'],answer
        milestone('huggingFaceLocalInference',answer)
        target=await c.call('security-target-add',dict(type='Website / API',address='http://127.0.0.1:'+str(server.server_port),objective='Owned access-boundary fixture; no live third-party target'))
        engagement=await c.call('security-engagement-create',dict(name='HF and API acceptance',objective='Verify owned API access separation, evidence and specialist roles',targetIds=[target['id']],scope=dict(capabilities=['api_observe','analysis'],maxRuns=16,maxSeconds=180)))
        eid=engagement['id']
        async def call(method,**params):return await c.call(method,dict(engagementId=eid,**params))
        await call('security-engagement-approve',baseRevision=1)
        cred=await call('security-credential-save',targetId=target['id'],label='Synthetic owned API identity',secret=synthetic,seconds=600)
        async def wait(run_id):
            for _ in range(1800):
                run=next(r for r in (await c.state())['securityRuns'] if r['id']==run_id)
                if run['status'] in ('completed','failed','cancelled','interrupted'):
                    assert run['status']=='completed',run;return run
                await asyncio.sleep(.1)
            raise AssertionError('Run exceeded acceptance deadline')
        runs=[]
        for identity in (cred['id'],''):
            assignment=await call('security-specialist-operate',role='recon_operator',capability='api_observe',targetId=target['id'],question='Observe owned private endpoint under declared identity',arguments=dict(paths=['/private'],credentialId=identity))
            runs.append(await wait(assignment['runId']))
        assert observations[0]['status']==200 and observations[1]['status']==403 and len(observations)==2,observations
        assert synthetic not in json.dumps(await c.state())
        for run in runs:
            retained=await call('security-evidence-read',evidenceId=run['retainedEvidenceId'])
            assert synthetic not in retained['content']
        milestone('keychainScopedApi',dict(credential=cred,runs=runs,independentServer=observations))
        objective=await call('security-objective-save',targetId=target['id'],title='Owner/anonymous separation',hypothesis='Only owner receives the private signal',successSignal='Owner 200/private true; anonymous 403 without private signal',dependsOn=[])
        contract=await call('security-contract-validator-save',objectiveId=objective['id'],validator='api_access_boundary',config=dict(path='/private',pointer='/private',expected=True,allowedIdentityId=cred['id'],deniedIdentityId='anonymous'))
        check=await call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[r['retainedEvidenceId'] for r in runs]);assert check['status']=='validated'
        await call('security-objective-complete',objectiveId=objective['id'],verificationId=check['id'])
        milestone('deterministicAccessValidation',check)
        specialists=[]
        for role in ('planner','recon_analyst','researcher','verifier','reporter'):
            assignment=await call('security-specialist-assign',role=role,targetId=target['id'],evidenceIds=[runs[1]['retainedEvidenceId']],model=args.specialist_model,question='Inspect only the supplied anonymous API observation. Return JSON only with keys observed_status (integer), private_observed (boolean), and limitation (short string). Do not infer exploitation or unseen access.')
            run=await wait(assignment['runId']);text=run['result']['analysis'].strip()
            if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
            parsed=json.loads(text)
            assert parsed['observed_status']==403 and parsed['private_observed'] is False,run
            assert run['result']['usage']['eval_count']>0
            specialists.append(dict(role=role,run=run,answer=parsed));print(role+' real-model role passed',flush=True)
        milestone('fiveSpecialistRoles',dict(model=args.specialist_model,roles=specialists,qualification='One held-out anonymous-observation case per role, actual weights; not broad model quality qualification'))
        telemetry=dict(sensor='Owned fixture HTTP server',starts=runs[0]['started']-1,ends=runs[1]['finished']+1,events=[dict(time=observations[i]['time'],runId=runs[i]['id'],type='http_request') for i in (0,1)])
        (project/'telemetry.json').write_text(json.dumps(telemetry));sensor=await call('security-telemetry-import',path='telemetry.json')
        correlation=await call('security-telemetry-correlate',runId=runs[0]['id'],telemetryId=sensor['id'],eventType='http_request');assert correlation['status']=='observed'
        milestone('defensiveCorrelation',correlation)
        (project/'external.json').write_text(json.dumps(dict(findings=[dict(title='External unverified example',status='confirmed')],commands=['never executed'])))
        imported=await call('security-engagement-structured-import',path='external.json');assert imported['claims'][0]['wixalState']=='unverified_external_claim'
        assert all(f['status']!='confirmed' for f in (await c.state())['securityFindings'])
        milestone('structuredUntrustedImport',imported)
        await call('security-credential-revoke',credentialId=cred['id']);cred=None
        exported=await call('security-engagement-export');assert all(Path(p).is_file() for p in exported['paths'])
        before=await c.state();await c.close();await c.start();after=await c.state()
        assert len(before['securityRuns'])==len(after['securityRuns']) and next(e for e in after['securityEngagements'] if e['id']==eid)['status']=='paused'
        assert next(x for x in after['securityCredentials'] if x['engagementId']==eid)['revoked']
        milestone('restartAndExport',dict(runCount=len(after['securityRuns']),paths=exported['paths']))
        await call('security-engagement-close',reason='Owned access-boundary requirement validated; synthetic credential revoked')
        report.update(status='passed',reviews=c.reviews);save()
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:
        if c:
            if cred:
                try:await c.call('security-credential-revoke',dict(engagementId=cred['engagementId'],credentialId=cred['id']))
                except Exception:pass
            if created_model and name:
                try:
                    await c.call('model-unload',dict(name=name))
                    await c.call('model-delete',dict(name=name))
                except Exception:pass
            await c.close()
        server.shutdown();server.server_close()
    assert sha(helper)==report['helperSha256']
    print(json.dumps(dict(status=report['status'],cases=list(report['cases']),report=str(output/'results.json')),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',required=True);parser.add_argument('--output',required=True);parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--specialist-model',default='gpt-oss:20b');asyncio.run(main(parser.parse_args()))
