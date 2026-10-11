"""Real-model acceptance of Hermes-inspired tools through the packaged JSON-line helper.

Only disposable local fixtures are used. No gateway, credentials or external targets.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import uuid


async def main(args):
    base=Path(args.output).resolve();base.mkdir(parents=True,exist_ok=True)
    root=base/'project';root.mkdir(exist_ok=True)
    marker='HERMES-NATIVE-PROOF-7319'
    (root/'evidence.txt').write_text(marker+'\n')
    (root/'numbers.csv').write_text('item,value\na,3\nb,7\nc,11\n')
    (root/'totals.json').write_text('{"total":21}\n')
    skill=root/'snapshot-procedure';(skill/'references').mkdir(parents=True,exist_ok=True)
    (skill/'SKILL.md').write_text('# Snapshot procedure\nRead references/evidence.md to obtain the retained marker.\n')
    support=skill/'references/evidence.md';support.write_text(marker+'\n')
    app=Path(args.app).resolve();helper=app/'Contents/Resources/engine/wixal-engine'
    helper_sha=hashlib.sha256(helper.read_bytes()).hexdigest()
    events=[];outcomes=[]
    process=await asyncio.create_subprocess_exec(str(helper),'--data',str(base/'data'),'--runtime',str(app/'Contents/Resources/ollama'),'--endpoint',args.endpoint,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=32*1024*1024)
    stderr=asyncio.create_task(process.stderr.read())
    async def call(method,params=None):
        identifier=uuid.uuid4().hex
        process.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await process.stdin.drain()
        while True:
            raw=await asyncio.wait_for(process.stdout.readline(),args.timeout)
            if not raw:raise RuntimeError('Packaged helper exited before responding')
            row=json.loads(raw);events.append(row)
            if row['event']=='review':raise RuntimeError('Read-only acceptance unexpectedly requested action review')
            if row['event']=='response' and row['data']['id']==identifier:
                if row['data'].get('error'):raise RuntimeError(row['data']['error'])
                return row['data']['result']
    try:
        await call('project-add',dict(root=str(root)))
        await call('settings',dict(model=args.model,enabledTools=[]))
        await call('skill-add',dict(path=str(skill/'SKILL.md')))
        support.write_text('EXTERNAL CONTENT CHANGED AFTER IMPORT\n')
        await call('agent-save',dict(id='proof',name='Native proof agent',purpose='Verify actual tool results',instructions='Perform the requested local task using tools. Copy exact markers from evidence. Follow each requested step and verify independently. Never invent a tool result.',model=args.model,reviewPolicy='Review actions',memoryScope='Memory off',skills=[]))
        cases=[
            ('skill-snapshot','Use @load_skill to read skill snapshot-procedure, then its supporting file references/evidence.md. Report the exact retained marker. Do not read the external skill source files.',[dict(kind='tool_contains',tool='load_skill',value=marker)]),
            ('durable-plan-and-evidence','Use @todo_list to create a two-step checklist: inspect the marker and retrieve its retained evidence. Use @read_file on evidence.txt. Use @tool_result_read without checkpoint_id to list saved checkpoints, then use the returned read_file checkpoint_id to read its full saved output. Mark both checklist steps completed after doing them. Report the exact marker.',[dict(kind='tool_contains',tool='read_file',value=marker),dict(kind='tool_contains',tool='tool_result_read',value=marker)]),
            ('isolated-child','Use @delegate_task to ask a read-only child to read evidence.txt and return its exact marker. Supply explicit context naming evidence.txt and the expected output. Report the child result.',[dict(kind='tool_contains',tool='delegate_task',value=marker)]),
            ('keyword-discovery','Use @workspace_info with query "read project text file" to discover a reader, then use the discovered read_file tool to read evidence.txt. Report the exact marker.',[dict(kind='tool_contains',tool='read_file',value=marker)]),
            ('csv-source-verification','Use @verify_json to check totals.json pointer /total against numbers.csv sourcePointer /value with transform sum. Report the independently checked total.',[dict(kind='tool_succeeded',tool='verify_json'),dict(kind='json_equals',path='totals.json',pointer='/total',value=21)]),
        ]
        for name,prompt,checks in cases:
            try:
                task=await call('agent-run',dict(id='proof',prompt=prompt,successCriteria=checks))
                passed=task['status']=='completed' and task.get('verification',{}).get('status')=='passed' and (str(21) if name=='csv-source-verification' else marker) in task.get('result','')
                if name=='durable-plan-and-evidence':passed=passed and bool(task.get('plan',{}).get('todos')) and all(t['status']=='completed' for t in task['plan']['todos'])
                if name=='isolated-child':
                    children=[json.loads(c['result']) for c in task['checkpoints'] if c['name']=='delegate_task' and c['status']=='finished']
                    passed=passed and bool(children) and children[-1]['status']=='completed' and any(c['name']=='read_file' for c in children[-1]['checkpoints']) and not set(children[-1]['tools'])&{'http_request','web_search','write_file','delegate_task'}
                outcomes.append(dict(name=name,passed=bool(passed),task=task))
            except Exception as error:outcomes.append(dict(name=name,passed=False,error=str(error)))
            print(name,'PASS' if outcomes[-1]['passed'] else 'FAIL',flush=True)
    finally:
        process.stdin.close()
        await asyncio.wait_for(process.stdout.read(),30);await asyncio.wait_for(process.wait(),30)
        (base/'helper-stderr.log').write_bytes(await stderr)
        (base/'events.json').write_text(json.dumps(events,indent=2))
        unchanged=helper_sha==hashlib.sha256(helper.read_bytes()).hexdigest()
        report=dict(status='passed' if len(outcomes)==5 and all(r['passed'] for r in outcomes) and unchanged else 'failed',app=str(app),model=args.model,helperSha256=helper_sha,helperUnchanged=unchanged,outcomes=outcomes)
        (base/'results.json').write_text(json.dumps(report,indent=2))
    return report['status']=='passed'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',required=True);parser.add_argument('--output',required=True);parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--timeout',type=int,default=240)
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
