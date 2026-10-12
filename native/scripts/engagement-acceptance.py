"""Packaged native engagement acceptance against an owned loopback HTTP service and real local weights."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real_acceptance',ROOT/'native/scripts/real-acceptance.py')
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


async def main(args):
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    real.ART=output;real.STATE=output/'data'
    project=output/'project';project.mkdir(exist_ok=True)
    observations=[];mode={'status':404}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status=mode['status'] if self.path=='/' else 404
            body=f'<html><title>Wixal engagement acceptance</title><body>Controlled observation {status}</body></html>'.encode()
            observations.append(dict(path=self.path,status=status,sha256=hashlib.sha256(body).hexdigest()))
            self.send_response(status);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    url='http://127.0.0.1:'+str(server.server_port)
    app=Path(args.app).resolve();helper=app/'Contents/Resources/engine/wixal-engine'
    c=real.Client(False,helper=helper,payload=app/'Contents/Resources/ollama',endpoint=args.endpoint)
    c.allowed={'security_engagement_scope','website_assess','save_website_evidence','security_analysis','security_cleanup_disposition'}
    report=dict(status='running',app=str(app),model=args.model,helperSha256=sha(helper),cases={},independentHTTP=observations)
    def save(): (output/'results.json').write_text(json.dumps(report,indent=2))
    async def wait(run_id):
        for _ in range(2400):
            state=await c.state();run=next(r for r in state['securityRuns'] if r['id']==run_id)
            if run['status'] in ('completed','failed','cancelled','interrupted'):
                assert run['status']=='completed',run
                return run
            await asyncio.sleep(.1)
        raise AssertionError('Operation did not finish within acceptance deadline')
    save()
    try:
        await c.start()
        models=await c.call('models');assert any(m['name']==args.model for m in models),'Requested local model is not installed; no automatic download'
        await c.call('project-add',dict(root=str(project)))
        target=await c.call('security-target-add',dict(type='Website / API',address=url,objective='Distinguish controlled response observations without asserting exploitation'))
        engagement=await c.call('security-engagement-create',dict(name='Packaged loopback engagement',objective='Demonstrate independently observed response discrimination and evidence-grounded specialist analysis',targetIds=[target['id']],scope=dict(capabilities=['analysis','website_assess','website_simulate'],maxRuns=12,maxSeconds=240,dataHandling='Owned loopback service, synthetic content, retained local evidence only')))
        eid=engagement['id']
        async def call(method,**params):return await c.call(method,dict(engagementId=eid,**params))
        try:await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='website_assess',arguments=dict(max_pages=1)))
        except RuntimeError as error:assert 'not approved' in str(error)
        else:raise AssertionError('Unapproved engagement dispatched work')
        await call('security-engagement-approve',baseRevision=1)
        objective=await call('security-objective-save',targetId=target['id'],title='Observed response difference',hypothesis='Controlled server response changes between baseline and positive observation',successSignal='Positive root status 200, baseline root status 404',dependsOn=[])
        baseline=await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='website_assess',arguments=dict(profile='baseline',max_pages=1),name='Controlled baseline'))
        baseline=await wait(baseline['id']);assert baseline['result']['report']['requests'][0]['status']==404
        mode['status']=200
        positive=await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='website_assess',arguments=dict(profile='baseline',max_pages=1),name='Controlled positive',objectiveId=objective['id']))
        positive=await wait(positive['id']);request=positive['result']['report']['requests'][0]
        expected=next(r for r in reversed(observations) if r['path']=='/' and r['status']==200)
        assert request['status']==200 and request['bodySha256']==expected['sha256']
        check=await call('security-verification-add',objectiveId=objective['id'],positiveId=positive['retainedEvidenceId'],baselineId=baseline['retainedEvidenceId'],pointer='/report/requests/0/status',expected=200)
        assert check['status']=='discriminated'
        await call('security-objective-complete',objectiveId=objective['id'],verificationId=check['id'])
        report['cases']['independentObservations']=dict(baseline=baseline,positive=positive,check=check);save()
        relation=await call('security-relation-add',fromId=target['id'],toId=objective['id'],kind='supports',state='observed',evidenceIds=[positive['retainedEvidenceId']],rationale='Recorded response supports this observation objective only')
        paths=await call('security-relation-paths',fromId=target['id'],toId=objective['id']);assert paths['paths'][0]['state']=='candidate'
        report['cases']['paths']=dict(relation=relation,paths=paths)
        assignment=await call('security-specialist-assign',targetId=target['id'],role='verifier',question='Compare the supplied 200 and 404 HTTP observations. Cite the supplied run IDs, explain why a status difference does not demonstrate successful exploitation, and identify one further independent check.',model=args.model,evidenceIds=[positive['retainedEvidenceId'],baseline['retainedEvidenceId']])
        analysed=await wait(assignment['runId']);assert analysed['result']['usage']['eval_count']>0 and analysed['result']['analysis'].strip()
        assert analysed['capability']=='analysis'
        report['cases']['realModelSpecialist']=analysed;save()
        await call('security-engagement-skills');state=await c.state();assert len([s for s in state['skills'] if s.get('source')=='wixal:redteam-skills:v1'])==5
        first=await call('security-evidence-read',evidenceId=positive['retainedEvidenceId']);assert first['evidence']['sha256']
        (project/'decepticon-export.json').write_text('{"claims":[{"status":"confirmed","source":"external example"}]}')
        imported=await call('security-evidence-import',path='decepticon-export.json');assert imported['kind']=='external-untrusted'
        report['cases']['skillsEvidenceImport']=dict(imported=imported,evidence=first['evidence'])
        readiness=await call('security-engagement-worker-inspect');report['workerReadiness']=readiness
        cleanup=await call('security-cleanup-add',title='Retain synthetic local evidence',description='Accept retained local evidence in the isolated acceptance project; no target modifications or worker containers created')
        await call('security-cleanup-update',cleanupId=cleanup['id'],status='accepted',rationale='Operator accepts synthetic local evidence retention',evidenceIds=[positive['retainedEvidenceId']])
        exported=await call('security-engagement-export');assert all(Path(p).is_file() for p in exported['paths'])
        state=await c.state();before=dict(scopes=len(next(e for e in state['securityEngagements'] if e['id']==eid)['scopes']),evidence=len([e for e in state['securityEvidence'] if e['engagementId']==eid]),runs=len(state['securityRuns']))
        await c.close();await c.start();state=await c.state()
        recovered=next(e for e in state['securityEngagements'] if e['id']==eid)
        assert recovered['status']=='paused' and recovered['approval'] is None
        assert len(recovered['scopes'])==before['scopes'] and len(state['securityRuns'])==before['runs']
        assert len([e for e in state['securityEvidence'] if e['engagementId']==eid])==before['evidence']
        report['cases']['restart']=dict(before=before,recovered=recovered)
        await call('security-engagement-close',reason='Observed response difference evaluated; local evidence retention accepted')
        state=await c.state();assert next(e for e in state['securityEngagements'] if e['id']==eid)['status']=='completed'
        assert all(f['status']!='confirmed' for f in state['securityFindings'])
        assert sha(helper)==report['helperSha256']
        report.update(status='passed',reviews=c.reviews,manifestSha256=sha(app/'Contents/Resources/SOURCE_MANIFEST.json'))
        save()
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:
        await c.close();server.shutdown();server.server_close()
    print(json.dumps(dict(status=report['status'],cases=list(report['cases']),workerAvailable=report['workerReadiness']['available'],report=str(output/'results.json')),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',required=True);parser.add_argument('--output',required=True);parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--model',default='gpt-oss:20b')
    asyncio.run(main(parser.parse_args()))
