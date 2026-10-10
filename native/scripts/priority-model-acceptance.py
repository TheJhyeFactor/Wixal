"""Installed real-model source, artifact and outcome acceptance with independent oracles.

Only copied public repo files and isolated scratch effects are approved. Every
attempt and failure is retained. Coverage is limited to the named model tuples.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(args):
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    app=Path(args.app).resolve();helper=app/'Contents/Resources/engine/wixal-engine'
    real.ART=output;real.STATE=output/'data'
    project=output/'project';project.mkdir()
    package=json.loads((ROOT/'package.json').read_text())
    (project/'package.json').write_text(json.dumps(package))
    (project/'source-a.json').write_text(json.dumps(dict(name=package['name'],version=package['version'])))
    (project/'source-b.json').write_text(json.dumps(dict(scriptCount=len(package['scripts']))))
    expected=dict(name=package['name'],version=package['version'],scriptCount=len(package['scripts']))
    (project/'correct.json').write_text(json.dumps(expected))
    (project/'wrong.json').write_text(json.dumps(dict(name='',version='',scriptCount=expected['scriptCount'])))
    source_hashes={name:hashlib.sha256((project/name).read_bytes()).hexdigest() for name in ('package.json','source-a.json','source-b.json','correct.json','wrong.json')}
    c=real.Client(False,helper=helper,payload=app/'Contents/Resources/ollama')
    report=dict(status='running',started=time.time(),app=str(app),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),sourceManifestSha256=hashlib.sha256((app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(),scope='Copied public Wixal manifests in an isolated project; named installed models only',attempts=[])
    def save():(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def source_checks(path):
        return [dict(kind='json_matches_source',path=path,pointer='/'+field,sourcePath='package.json',sourcePointer='/'+source,transform=transform) for field,source,transform in [('name','name','identity'),('version','version','identity'),('scriptCount','scripts','length')]]
    async def attempt(name,prompt,checks,oracle,agent,model,repeat):
        await c.call('session-new',dict(mode='agent'))
        row=dict(name=name,model=model,repeat=repeat,status='running',prompt=prompt,checks=checks,started=time.time());report['attempts'].append(row);save()
        before=len(c.reviews)
        try:
            params=dict(id=agent,prompt=prompt)
            if checks is not None:params['successCriteria']=checks
            task=await c.call('agent-run',params)
            state=await c.state();session=next(s for s in state['sessions'] if s['id']==task['sessionId']);usage=[m.get('usage',{}) for m in session['messages'] if m['role']=='assistant']
            assert any(u.get('eval_count',0)>0 for u in usage),'No real inference counters'
            assert all(hashlib.sha256((project/name).read_bytes()).hexdigest()==sha for name,sha in source_hashes.items()),'A source or fixed oracle artifact changed'
            assert all(r['estimatedInput']+r['outputReserve']<=r['context'] for r in session.get('requests',[])),'Request exceeds its context budget'
            assert oracle(task),'Independent expected task/artifact outcome failed'
            row.update(status='passed',task=task,requests=session.get('requests',[]),usage=usage)
        except Exception as error:
            row.update(status='failed',error=str(error),state=await c.state())
        row.update(reviews=c.reviews[before:],finished=time.time());save();print(json.dumps({k:row[k] for k in ('name','model','repeat','status')}),flush=True)
    try:
        c.log=(output/'helper.log').open('a')
        c.child=await asyncio.create_subprocess_exec(str(helper),'--data',str(real.STATE),'--runtime',str(c.payload),'--endpoint',args.endpoint,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=c.log,limit=32*1024*1024)
        c.reading=asyncio.create_task(c.read());await c.call('hello');await c.call('project-add',dict(root=str(project)))
        def review(data):
            if data.get('name')=='write_file':
                path=Path(data.get('path',''))
                return path.parent.resolve()==project and path.name.startswith('report-') and path.suffix=='.json'
            return data.get('name') in c.allowed
        c.review_policy=review
        catalog=await c.call('models')
        for model in args.models:
            metadata=next((m for m in catalog if m['name']==model),None)
            if not metadata or 'tools' not in metadata.get('capabilities',[]):
                report.setdefault('unsupported',[]).append(dict(model=model,reason='Not installed or no tool support'));save();continue
            await c.call('settings',dict(model=model,contextSize=8192))
            for aid,policy in [('reader','Read only'),('worker','Review actions')]:
                await c.call('agent-save',dict(id=aid,name=aid,purpose='Verify source-bound project outcomes in the isolated qualification project',model=model,instructions='Use direct source evidence and retain exact values. Follow the task scope.',reviewPolicy=policy,memoryScope='Memory off',skills=[]))
            report.setdefault('models',[]).append(metadata);save()
            for repeat in range(1,args.repeats+1):
                path=f'report-{args.models.index(model)}-{repeat}.json'
                await attempt('multi-read-calculated-artifact',f'Read source-a.json, source-b.json and package.json. Run python3 to calculate len(scripts) from package.json. Use write_file to save {path} with exactly name, version and integer scriptCount from those sources. Read it back. Verify all three fields against package.json. Do not change any source file.',source_checks(path),lambda t:t['status']=='completed' and t['verification']['status']=='passed' and json.loads((project/path).read_text())==expected and {'source-a.json','source-b.json','package.json',path} <= {c.get('arguments',{}).get('path') for c in t['checkpoints'] if c['name']=='read_file' and c['status']=='finished'} and any(c['name'] in ('run_command','command_read') and c['status']=='finished' and json.loads(c['result']).get('exitCode')==0 for c in t['checkpoints'] if c.get('result','').startswith('{')),'worker',model,repeat)
                await attempt('correct-source-report','Read correct.json and package.json and explain whether all report fields agree with their sources. Do not edit files.',source_checks('correct.json'),lambda t:t['status']=='completed' and t['verification']['status']=='passed','reader',model,repeat)
                await attempt('incorrect-source-report','Read wrong.json and package.json. Check the report against its source. Report the discrepancies. Do not edit files.',source_checks('wrong.json'),lambda t:t['status']=='needs_attention' and t['verification']['status']=='failed' and json.loads((project/'wrong.json').read_text())['name']=='','reader',model,repeat)
                await attempt('no-criteria-unverified','Read source-a.json and describe its exact name and version. Do not modify files.',[],lambda t:t['status']=='completed' and t['verification']['status']=='unverified' and package['name'] in t['result'] and package['version'] in t['result'],'reader',model,repeat)
                await attempt('missing-verification-artifact','Read source-a.json and explain its name. Do not create any files.',[dict(kind='file_exists',path='never-created.json')],lambda t:t['status']=='needs_attention' and t['verification']['status']=='failed' and not (project/'never-created.json').exists(),'reader',model,repeat)
                await attempt('passing-command-oracle','Read source-a.json and describe its name. The controller will run the requested independent assertion.',[dict(kind='command_exit',command="python3 -c \"import json; assert json.load(open('correct.json'))['name'] == json.load(open('package.json'))['name']; print('SOURCE-ASSERTION-PASSED')\"")],lambda t:t['status']=='completed' and t['verification']['status']=='passed' and any(c['name']=='verification_command' and json.loads(c['result'])['exitCode']==0 for c in t['checkpoints']),'worker',model,repeat)
                await attempt('failed-command-oracle','Read source-a.json and describe its name. Do not change files or the independent controller assertion.',[dict(kind='command_exit',command="python3 -c \"import json; assert json.load(open('wrong.json'))['name'] == json.load(open('package.json'))['name']\"")],lambda t:t['status']=='needs_attention' and t['verification']['status']=='failed','worker',model,repeat)
        report['status']='passed' if len(report['attempts'])==len(args.models)*args.repeats*7 and all(a['status']=='passed' for a in report['attempts']) else 'failed'
    finally:
        await c.close();report['finished']=time.time();save()
    return report['status']=='passed'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',required=True);p.add_argument('--output',required=True);p.add_argument('--models',nargs='+',default=['gpt-oss:20b']);p.add_argument('--repeats',type=int,default=2);p.add_argument('--endpoint',default='http://127.0.0.1:11434')
    args=p.parse_args()
    if args.repeats<1:p.error('Repeat count must be positive')
    raise SystemExit(0 if asyncio.run(main(args)) else 1)
