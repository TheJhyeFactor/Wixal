"""Real local-model workloads with independent artifact checks and retained evidence.

Never uses the user's workspace database. Writes only inside the supplied output
folder, and only allows reviewed fixture operations there. No external targets.
"""
import copy
import subprocess
import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.service import Service
from wixal.scheduling import run_due
from wixal.storage import now

async def main(args):
    base=Path(args.output).resolve();base.mkdir(parents=True,exist_ok=True)
    root=base/'project';root.mkdir(exist_ok=True)
    (root/'evidence.txt').write_text('The scheduled deployment marker is WX-7319.\nThe expected daily count is 17.\n')
    (root/'numbers.csv').write_text('item,value\na,3\nb,7\nc,11\n')
    (root/'bug.py').write_text('def add(a, b):\n    return a - b\n')
    (root/'test_bug.py').write_text('import unittest\nfrom bug import add\nclass AddTest(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(2,3),5)\n')
    events=[]
    def emit(event,data):
        events.append(dict(event=event,data=copy.deepcopy(data)))
        if event=='review':asyncio.create_task(service.dispatch('respond',dict(id=data['id'],value=True)))
    payload=Path(__file__).resolve().parents[2]/'runtime/ollama'
    service=Service(base/'engine',payload,emit,args.endpoint)
    outcomes=[]
    try:
        await service.dispatch('project-add',dict(root=str(root)))
        await service.dispatch('settings',dict(model=args.model,enabledTools=[]))
        for identifier,name,policy in [('review','Project reviewer','Read only'),('code','Code assistant','Review actions')]:
            await service.dispatch('agent-save',dict(id=identifier,name=name,purpose='Complete and verify fixture tasks',instructions='Use tools to inspect the actual fixture files. Work until the requested result is produced and verified. Do not invent observations. For a review, cite sources. For changes, inspect first, make the focused change, then verify.',model=args.model,reviewPolicy=policy,memoryScope='Project only',skills=[]))
        async def attempt(name,action,verify):
            start=time.monotonic();before=len(events)
            try:
                result=await asyncio.wait_for(action(),args.timeout)
                passed=verify(result);outcomes.append(dict(name=name,passed=bool(passed),duration=round(time.monotonic()-start,2),result=result))
            except Exception as error:outcomes.append(dict(name=name,passed=False,duration=round(time.monotonic()-start,2),error=str(error)))
            (base/'results.json').write_text(json.dumps(dict(model=args.model,endpoint=args.endpoint,outcomes=outcomes,status='running'),indent=2,ensure_ascii=False))
            print(name,'PASS' if outcomes[-1]['passed'] else 'FAIL',outcomes[-1]['duration'],flush=True)
        initial=hashlib.sha256((root/'evidence.txt').read_bytes()).hexdigest()
        await attempt('read-only-evidence',lambda:service.dispatch('agent-run',dict(id='review',prompt='Inspect evidence.txt and report the exact deployment marker and daily count with a file reference. Do not change files.',successCriteria=[dict(kind='tool_contains',tool='read_file',value='WX-7319')])),
                      lambda task: task['status']=='completed' and 'WX-7319' in task.get('result','') and '17' in task.get('result','') and any(c['name']=='read_file' and 'WX-7319' in c.get('result','') for c in task['checkpoints']) and hashlib.sha256((root/'evidence.txt').read_bytes()).hexdigest()==initial)
        await attempt('data-report',lambda:service.dispatch('agent-run',dict(id='code',prompt='Inspect numbers.csv. Calculate the sum of the value column, write a JSON file totals.json with the numeric key total, and verify its contents.',successCriteria=[dict(kind='json_equals',path='totals.json',pointer='/total',value=21)])),
                      lambda task:task['status']=='completed' and json.loads((root/'totals.json').read_text())=={'total':21} and any(c['name'] in ('write_file','run_command','command_start') for c in task['checkpoints']))
        await attempt('code-fix-and-test',lambda:service.dispatch('agent-run',dict(id='code',prompt='Inspect bug.py and test_bug.py. Run the test to confirm the defect, correct add so it adds two numbers, then rerun the test and report the real result.',successCriteria=[dict(kind='command_exit',command='python3 -m unittest test_bug.py')])),
                      lambda task:task['status']=='completed' and subprocess.run([sys.executable,'-m','unittest','test_bug.py'],cwd=root,capture_output=True).returncode==0 and any('OK' in c.get('result','') and c['name'] in ('run_command','command_read') for c in task['checkpoints']))
        flow=await service.dispatch('workflow-save',dict(id='flow',name='Inspect and produce report',brief='Produce an accurate evidence report',stages=[dict(id='inspect',name='Inspect',agentID='review',goal='Read evidence.txt and report its exact marker and count',output='Evidence with source reference',successCriteria=[dict(kind='tool_contains',tool='read_file',value='WX-7319')]),dict(id='report',name='Produce artifact',agentID='code',goal='Use previous stage evidence to write workflow-report.txt containing the exact deployment marker and count. Verify by reading the saved file.',output='Verified report file',requiresReview=True,successCriteria=[dict(kind='file_contains',path='workflow-report.txt',value='WX-7319')])]))
        await attempt('workflow-handoff',lambda:service.dispatch('workflow-run',dict(id=flow['id'])),lambda run:run['status']=='completed' and len(run['stages'])==2 and 'WX-7319' in (root/'workflow-report.txt').read_text() and '17' in (root/'workflow-report.txt').read_text())
        schedule=await service.dispatch('agent-schedule-save',dict(id='routine',name='Scheduled evidence review',agentID='review',prompt='Read evidence.txt and report the exact deployment marker and count.',timing='Every hour',successCriteria=[dict(kind='tool_contains',tool='read_file',value='WX-7319')]))
        schedule['nextRun']=now()-1000
        await attempt('scheduled-tool-run',lambda:run_due(service,True),lambda result:result and schedule.get('lastRun',{}).get('status')=='completed' and any('WX-7319' in c.get('result','') for c in service.store.data['tasks'][-1]['checkpoints']))
        service.tools.host=None # Headless HTTP controls; browser controls require the macOS host.
        await attempt('local-security-tool-run',lambda:service.dispatch('agent-run',dict(id='code',prompt='Run the disposable local website security simulation. Save reports with prefix agents-security-lab. Inspect the generated JSON report and explain its actual expected and unexpected control results. Do not access external targets.',successCriteria=[dict(kind='json_equals',path='agents-security-lab.json',pointer='/summary/unexpected',value=0)])),lambda task: task['status']=='completed' and (root/'agents-security-lab.json').exists() and json.loads((root/'agents-security-lab.json').read_text())['summary']['unexpected']==0 and json.loads((root/'agents-security-lab.json').read_text())['summary']['expected']>=16 and any(c['name']=='website_simulate' for c in task['checkpoints']))
        (base/'events.json').write_text(json.dumps(events,indent=2,ensure_ascii=False))
    finally:await service.close()
    passed=all(row['passed'] for row in outcomes)
    (base/'results.json').write_text(json.dumps(dict(model=args.model,endpoint=args.endpoint,outcomes=outcomes,status='passed' if passed else 'failed'),indent=2,ensure_ascii=False))
    return passed

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--output',required=True);parser.add_argument('--timeout',type=int,default=360)
    args=parser.parse_args();raise SystemExit(0 if asyncio.run(main(args)) else 1)
