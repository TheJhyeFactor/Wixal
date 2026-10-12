"""Installed-helper qualification with a real model and disposable local files."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import uuid


async def main(args):
    base=Path(args.output).resolve();base.mkdir(parents=True,exist_ok=True)
    root=base/'project';root.mkdir(exist_ok=True)
    marker='WIXAL-RUN-CONTROL-8427'
    (root/'evidence.txt').write_text(marker+'\n')
    helper=Path(args.app).resolve()/'Contents/Resources/engine/wixal-engine'
    digest=hashlib.sha256(helper.read_bytes()).hexdigest()
    events=[];results=[]
    process=await asyncio.create_subprocess_exec(str(helper),'--data',str(base/'data'),'--runtime',str(Path(args.app)/'Contents/Resources/ollama'),'--endpoint',args.endpoint,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=32*1024*1024)
    stderr=asyncio.create_task(process.stderr.read())
    async def call(method,params=None):
        identifier=uuid.uuid4().hex
        process.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await process.stdin.drain()
        while True:
            raw=await asyncio.wait_for(process.stdout.readline(),300)
            if not raw:raise RuntimeError('Installed helper exited before responding')
            row=json.loads(raw);events.append(row)
            if row['event']=='review':raise RuntimeError('Read-only acceptance unexpectedly requested review')
            if row['event']=='response' and row['data']['id']==identifier:
                if row['data'].get('error'):raise RuntimeError(row['data']['error'])
                return row['data']['result']
    try:
        project=await call('project-add',dict(root=str(root)))
        await call('settings',dict(model=args.model,contextSize=4096,enabledTools=[]))
        cases=[
            ('reserved-conclusion',2,5,'Use @read_file to read evidence.txt once. Then report its exact marker. Do not use other tools.', 'completed'),
            ('call-limit-conclusion',5,1,'Use @read_file to read evidence.txt once. Then report its exact marker. Do not use other tools.', 'completed'),
            ('unfinished-checklist',2,5,'Use @todo_list to create one pending step with id work and content Unfinished acceptance work, revision 0. Leave it pending. Then explain that it remains unfinished. Do not do any other work.', 'needs_attention'),
            ('unchanged-evidence-loop',8,10,'Use @read_file on evidence.txt with exactly the same arguments in six separate consecutive tool turns. Call only read_file, one call per turn. Then report its marker. Follow controller limits if they stop the repeated reads.', 'paused'),
        ]
        for name,turns,calls,prompt,expected in cases:
            await call('agent-save',dict(id=name,name=name,purpose='Qualify run controls',instructions='Use the requested tools, obey controller limits, report only saved evidence.',model=args.model,reviewPolicy='Read only',memoryScope='Memory off',skills=[],maxTurns=turns,maxCalls=calls,timeoutSeconds=300))
            try:
                checks=[dict(kind='tool_contains',tool='read_file',value=marker)] if name!='unfinished-checklist' else []
                task=await call('agent-run',dict(id=name,projectId=project['activeProject'],prompt=prompt,successCriteria=checks))
                passed=task['status']==expected
                if expected=='completed':passed=passed and task.get('verification',{}).get('status')=='passed' and marker in task.get('result','') and task['runBudget']['closing'] and task['runBudget']['callsUsed']==1
                if name=='unfinished-checklist':passed=passed and task['verification']['status']=='failed' and task['plan']['todos'][0]['status']=='pending'
                if name=='unchanged-evidence-loop':passed=passed and task.get('stopReason')=='no_progress' and task['runBudget']['callsUsed']==3 and marker in task.get('result','')
                results.append(dict(name=name,passed=bool(passed),task=task))
            except Exception as error:results.append(dict(name=name,passed=False,error=str(error)))
            print(name,'PASS' if results[-1]['passed'] else 'FAIL',flush=True)
    finally:
        process.stdin.close()
        await asyncio.wait_for(process.stdout.read(),30);await asyncio.wait_for(process.wait(),30)
        (base/'helper-stderr.log').write_bytes(await stderr)
        (base/'events.json').write_text(json.dumps(events,indent=2))
        unchanged=digest==hashlib.sha256(helper.read_bytes()).hexdigest()
        report=dict(status='passed' if len(results)==4 and all(r['passed'] for r in results) and unchanged else 'failed',app=args.app,model=args.model,helperSha256=digest,helperUnchanged=unchanged,outcomes=results)
        (base/'results.json').write_text(json.dumps(report,indent=2))
    return report['status']=='passed'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',required=True);parser.add_argument('--output',required=True);parser.add_argument('--endpoint',required=True);parser.add_argument('--model',required=True)
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
