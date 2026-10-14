"""Real-model workspace checks through frozen IPC in disposable storage.

Reviews are approved only for this suite's scratch project. No installed user
workspace, LaunchAgent, account, remote node or network target is modified.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store, now


async def main(args):
    base=args.output.resolve();base.mkdir(parents=True,exist_ok=False)
    project=base/'project';project.mkdir()
    (project/'evidence.txt').write_text('EVIDENCE-WORKSPACE-42\n')
    (project/'calc.py').write_text('def total(values):\n    return 0\n')
    skill=project/'audit-proof.md';skill.write_text('# Audit proof\nUse read_file on evidence.txt. Report the exact evidence marker without changing files.\n')
    helper=args.app/'Contents/Resources/engine/wixal-engine'
    runtime=args.app/'Contents/Resources/ollama'
    command=[str(helper),'--data',str(base/'data'),'--runtime',str(runtime),'--endpoint',args.endpoint]
    process=await asyncio.create_subprocess_exec(*command,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=32*1024*1024)
    stderr=asyncio.create_task(process.stderr.read());events=[];outcomes=[]
    async def call(method,params=None):
        request=uuid.uuid4().hex
        process.stdin.write((json.dumps(dict(id=request,method=method,params=params or {}))+'\n').encode());await process.stdin.drain()
        async with asyncio.timeout(420):
            while True:
                line=await process.stdout.readline()
                if not line:raise RuntimeError('Helper exited before response')
                event=json.loads(line);events.append(event)
                if event['event']=='review':
                    process.stdin.write((json.dumps(dict(id=uuid.uuid4().hex,method='respond',params=dict(id=event['data']['id'],value=True)))+'\n').encode());await process.stdin.drain()
                if event['event']=='response' and event['data']['id']==request:
                    if 'error' in event['data']:raise RuntimeError(event['data']['error'])
                    return event['data']['result']
    def retain(name,passed,result):
        outcomes.append(dict(name=name,passed=bool(passed),result=result))
        (base/'results.json').write_text(json.dumps(dict(model=args.model,helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),outcomes=outcomes),indent=2))
        print(json.dumps(dict(name=name,passed=bool(passed))),flush=True)
    async def save(identifier,**extra):
        value=dict(id=identifier,name=identifier,purpose='Disposable workspace acceptance',instructions='Use tools to complete the requested task. Preserve exact evidence markers. Never claim a tool succeeded without its result.',model=args.model,reviewPolicy='Review actions',memoryScope='Memory off',skills=[],maxTurns=18,maxCalls=35,timeoutSeconds=360)
        value.update(extra);return await call('agent-save',value)
    try:
        await call('project-add',dict(root=str(project)))
        await call('settings',dict(model=args.model,contextSize=16384,enabledTools=[]))
        await call('skill-add',dict(path=str(skill)))
        await save('reviewer',reviewPolicy='Read only',skills=['audit-proof'],toolGroups=['files','memory'])
        await save('coordinator',toolGroups=['files','commands','memory'])
        readiness=await call('agent-readiness',dict(id='reviewer'))
        retain('configuration-readiness',readiness['ready'] and readiness['qualification']=='untested',readiness)
        task=await call('agent-run',dict(id='reviewer',prompt='Load the audit-proof skill using load_skill, then follow its procedure by reading evidence.txt. Report the exact marker.',successCriteria=[dict(kind='tool_succeeded',tool='load_skill'),dict(kind='tool_contains',tool='read_file',value='EVIDENCE-WORKSPACE-42')]))
        retain('skill-and-source-evidence',task['status']=='completed' and task.get('verification',{}).get('status')=='passed',task)
        task=await call('agent-run',dict(id='coordinator',prompt='Delegate a read-only specialist assignment using delegate_task with agent_id reviewer. Ask it to read evidence.txt and return its exact marker. Pass the file path explicitly as context. Use the saved specialist, then report its evidence.',successCriteria=[dict(kind='tool_contains',tool='delegate_task',value='EVIDENCE-WORKSPACE-42')]))
        state=(await call('hello'))['state']
        children=[x for x in state.get('agentDelegations',[]) if x.get('parentTaskId')==task['id']]
        passed=task.get('verification',{}).get('status')=='passed' and any(c.get('agentId')=='reviewer' and c['status']=='completed' and any(p['name']=='read_file' and 'EVIDENCE-WORKSPACE-42' in p.get('result','') for p in c['checkpoints']) for c in children)
        retain('saved-specialist-handoff',passed,dict(task=task,children=children))
        command_text='/usr/bin/python3 -c "import calc; assert calc.total([2,3,5]) == 10; print(\'TOTAL_OK\')"'
        task=await call('agent-run',dict(id='coordinator',prompt='Read calc.py. Fix total(values) so it returns the sum of values. Then run this exact test command: '+command_text+'. Report the actual test result.',successCriteria=[dict(kind='file_contains',path='calc.py',value='sum(values)'),dict(kind='command_exit',command=command_text)]))
        retain('reviewed-edit-and-test',task['status']=='completed' and task.get('verification',{}).get('status')=='passed',task)
        await call('agent-schedule-save',dict(id='workspace-routine',name='Evidence routine',agentID='reviewer',prompt='Read evidence.txt and report the exact marker.',intervalSeconds=60,enabled=True,successCriteria=[dict(kind='tool_contains',tool='read_file',value='EVIDENCE-WORKSPACE-42')]))
        node=await call('security-engagement-worker-inspect')
        retain('actual-worker-readiness',isinstance(node.get('available'),bool) and ('imageId' in node if node['available'] else bool(node.get('error'))),node)
    finally:
        process.stdin.close()
        await asyncio.wait_for(process.stdout.read(),30);await asyncio.wait_for(process.wait(),30)
        (base/'stderr.log').write_bytes(await stderr)
        (base/'events.json').write_text(json.dumps(events,indent=2))
    store=Store(base/'data')
    schedule=next(s for s in store.data['schedules'] if s['id']=='workspace-routine')
    schedule['nextRun']=now()-1000;store.save();store.close()
    background=await asyncio.create_subprocess_exec(str(helper),'--background',*command[1:],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await asyncio.wait_for(background.communicate(),420)
    (base/'background.log').write_bytes(out+err)
    store=Store(base/'data')
    try:
        schedule=next(s for s in store.data['schedules'] if s['id']=='workspace-routine')
        run=next((t for t in store.data['tasks'] if t['id']==schedule.get('lastRun',{}).get('taskId')),{} )
        retain('closed-desktop-scheduled-evidence',background.returncode==0 and run.get('source')=='Background schedule' and run.get('verification',{}).get('status')=='passed',dict(schedule=schedule,task=run))
    finally:store.close()
    result=dict(status='passed' if all(o['passed'] for o in outcomes) else 'failed',model=args.model,app=str(args.app),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),outcomes=outcomes,limitations=['One model and bounded tasks, not broad qualification','Worker inspection does not start a VM or execute a scan','Background helper invoked directly; sleep/wake and LaunchAgent timing not qualified'])
    (base/'results.json').write_text(json.dumps(result,indent=2));return result['status']=='passed'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--endpoint',default='http://127.0.0.1:11589')
    parser.add_argument('--model',default='hf/unsloth/qwen3.5-9b-q4_k_m:03b74727a860')
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
