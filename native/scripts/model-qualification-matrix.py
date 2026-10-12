"""Actual installed-helper model workloads; per-case independent checks, no user workspace edits."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)


async def qualify(args,model,index):
    base=Path(args.output).resolve()/('model-'+str(index));base.mkdir(parents=True,exist_ok=True)
    root=base/'project';root.mkdir(exist_ok=True);real.ART=base;real.STATE=base/'data'
    (root/'evidence.txt').write_text('Deployment marker WX-7319. Daily count 17.\n')
    (root/'bug.py').write_text('def add(a, b):\n    return a - b\n')
    (root/'test_bug.py').write_text('import unittest\nfrom bug import add\nclass AddTest(unittest.TestCase):\n def test_add(self):\n  for a,b in [(2,3),(-2,3),(0,0),(1.5,2.25),(-8,-2)]: self.assertEqual(add(a,b),a+b)\n')
    for i in range(1,9):(root/f'part-{i}.txt').write_text(('Retained task evidence. '*65)+f'\nPART-{i}-VALUE={i*2}\n')
    (root/'ledger.csv').write_text('part,value\n'+''.join(f'{i},{i*2}\n' for i in range(1,9)))
    app=Path(args.app);helper=app/'Contents/Resources/engine/wixal-engine';digest=hashlib.sha256(helper.read_bytes()).hexdigest()
    c=real.Client(False,helper=helper,payload=app/'Contents/Resources/ollama',endpoint=args.endpoint)
    def approve(details):
        if details.get('name')=='command_start':return details.get('command')=='python3 -m unittest test_bug.py' and Path(details.get('root','')).resolve()==root
        if details.get('name') in ('write_file','edit_file'):
            try:Path(details['path']).resolve().relative_to(root);return True
            except (ValueError,KeyError):return False
        if details.get('name')=='http_request':return details.get('method','GET')=='GET' and details.get('url','').startswith(args.lab+'/rest/products/search?q=')
        return False
    c.review_policy=approve;outcomes=[]
    report=dict(model=model,app=str(app),helperSha256=digest,status='running',outcomes=outcomes)
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    async def attempt(name,prompt,checks,validate):
        start=time.monotonic()
        try:
            task=await c.call('agent-run',dict(id='proof',prompt=prompt,successCriteria=checks),timeout=1000)
            passed=task['status']=='completed' and task.get('verification',{}).get('status')=='passed' and validate(task)
            outcomes.append(dict(name=name,passed=bool(passed),seconds=round(time.monotonic()-start,2),task=task))
        except Exception as error:outcomes.append(dict(name=name,passed=False,seconds=round(time.monotonic()-start,2),error=str(error)))
        save();print(model,name,'PASS' if outcomes[-1]['passed'] else 'FAIL',flush=True)
    try:
        await c.start();await c.call('project-add',dict(root=str(root)));await c.call('settings',dict(model=model,contextSize=4096,enabledTools=[],autoSummary=True))
        await c.call('agent-save',dict(id='proof',name='Qualification agent',purpose='Complete actual local workloads',instructions='Use the explicitly requested tools with valid schemas. Inspect actual evidence, make focused changes and verify. Never invent success. Shell review permits only python3 -m unittest test_bug.py; use write_file or edit_file for changes.',model=model,reviewPolicy='Review actions',memoryScope='Memory off',skills=[],maxTurns=30,maxCalls=40,timeoutSeconds=900))
        await attempt('tool-evidence','Use @read_file to inspect evidence.txt. Report the exact deployment marker and count with its source.',[dict(kind='tool_contains',tool='read_file',value='WX-7319')],lambda t:'WX-7319' in t['result'] and '17' in t['result'])
        def coding(task):
            result=subprocess.run(['python3','-m','unittest','test_bug.py'],cwd=root,capture_output=True)
            return result.returncode==0 and any(c['name']=='run_command' and 'OK' in c.get('result','') for c in task['checkpoints'])
        await attempt('coding-repair','Use @read_file on bug.py and test_bug.py. Use @run_command with exactly python3 -m unittest test_bug.py to confirm the defect. Fix bug.py using @write_file or @edit_file, then rerun that exact test command. Report the actual test outcome.',[dict(kind='command_exit',command='python3 -m unittest test_bug.py')],coding)
        def continuation(task):
            todos=task.get('plan',{}).get('todos',[])
            paths={c.get('arguments',{}).get('path') for c in task['checkpoints'] if c['name']=='read_file' and c['status']=='finished'}
            return len(todos)>=3 and all(t['status']=='completed' for t in todos) and all(f'part-{i}.txt' in paths for i in range(1,9)) and json.loads((root/'long-result.json').read_text())=={'total':72} and any(c['name']=='tool_result_read' and 'PART-8-VALUE=16' in c.get('result','') for c in task['checkpoints'])
        await attempt('long-task-checklist-evidence','Use @todo_list to create three checklist steps: inspect all eight parts, recover retained evidence, and save/verify the total. Read part-1.txt through part-8.txt using @read_file, one file per call. Each file ends with its numeric value. Use @tool_result_read to list checkpoints, then read the retained part-8.txt checkpoint and its exact marker. Sum the eight values, write long-result.json with numeric key total using @write_file, then @verify_json path long-result.json pointer /total against sourcePath ledger.csv sourcePointer /value transform sum. Mark the three checklist steps completed only after doing them. Report the total.',[dict(kind='json_equals',path='long-result.json',pointer='/total',value=72),dict(kind='tool_succeeded',tool='verify_json')],continuation)
        control=args.lab+'/rest/products/search?q=WIXAL-NONEXISTENT-CONTROL-8427'
        probe=args.lab+'/rest/products/search?q=WIXAL-NONEXISTENT-CONTROL-8427%27%20OR%20id%3D1%29%29--'
        actual=[]
        for url in (control,probe):
            with urllib.request.urlopen(url,timeout=10) as response:actual.append(len(json.load(response)['data']))
        assert actual[0]==0 and actual[1]>0,actual
        def security(task):
            result=json.loads((root/'security-result.json').read_text())
            calls=[c for c in task['checkpoints'] if c['name']=='http_request' and c['status']=='finished']
            return result.get('control_count')==actual[0] and result.get('probe_count')==actual[1] and result.get('code_execution_proven') is False and {control,probe}<={c['arguments'].get('url') for c in calls}
        await attempt('juice-shop-security-analysis',f'Authorized disposable local OWASP Juice Shop lab only. Use @http_request GET on each exact URL: {control} and {probe}. Compare the lengths of their JSON data arrays. Use @write_file to save security-result.json with integer control_count and probe_count and boolean code_execution_proven=false. Explain that the changed query result supports a SQL query manipulation observation and does not establish code execution. Do not contact other targets.',[dict(kind='json_equals',path='security-result.json',pointer='/control_count',value=actual[0]),dict(kind='json_equals',path='security-result.json',pointer='/probe_count',value=actual[1]),dict(kind='json_equals',path='security-result.json',pointer='/code_execution_proven',value=False)],security)
    except Exception as error:report['error']=str(error)
    finally:
        if hasattr(c,'child'):await c.close()
        report['helperUnchanged']=hashlib.sha256(helper.read_bytes()).hexdigest()==digest
        report['status']='passed' if len(outcomes)==4 and all(o['passed'] for o in outcomes) and report['helperUnchanged'] else 'partial'
        save()
    return report


async def main(args):
    models=json.loads(Path(args.models).read_text());results=[];out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    for i,model in enumerate(models,1):
        results.append(await qualify(args,model['name'] if isinstance(model,dict) else model,i))
        (out/'matrix.json').write_text(json.dumps(dict(status='passed' if len(results)==len(models) and all(r['status']=='passed' for r in results) else 'partial',results=results),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--endpoint',required=True);p.add_argument('--lab',required=True);p.add_argument('--models',required=True);p.add_argument('--output',required=True)
    asyncio.run(main(p.parse_args()))
