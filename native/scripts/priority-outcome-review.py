"""Regrade retained isolated attempts after correcting the agent-session observer.

Raw reports remain unchanged. Only the specific parent-session counter error can
be regraded; other failures remain failures. No model response is regenerated.
"""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def review(raw):
    package=json.loads((ROOT/'package.json').read_text())
    expected=dict(name=package['name'],version=package['version'],scriptCount=len(package['scripts']))
    source_sha=hashlib.sha256(json.dumps(package).encode()).hexdigest()
    outcomes=[]
    for row in raw['attempts']:
        result=dict(name=row['name'],model=row['model'],repeat=row['repeat'],rawStatus=row['status'],rawError=row.get('error'),status=row['status'])
        if row.get('error')!='No real inference counters':outcomes.append(result);continue
        try:
            state=row['state'];task=next(t for t in reversed(state['tasks']) if t.get('prompt')==row['prompt'] and t.get('agentSnapshot',{}).get('model')==row['model'])
            session=next(s for s in state['sessions'] if s['id']==task['sessionId'])
            usage=[m.get('usage',{}) for m in session['messages'] if m['role']=='assistant']
            assert any(u.get('eval_count',0)>0 for u in usage),'Agent session lacks actual inference counters'
            assert all(q['estimatedInput']+q['outputReserve']<=q['context'] for q in session.get('requests',[])),'Context budget exceeded'
            rows=task['verification']['checks'];status=task['verification']['status'];name=row['name']
            if name in ('multi-read-calculated-artifact','correct-source-report'):
                assert task['status']=='completed' and status=='passed','Actual task was not verified'
                fields={c['check'].get('pointer'):c for c in rows if c['check']['kind']=='json_matches_source' and c['check'].get('sourcePath')=='package.json'}
                for field,value in expected.items():
                    check=fields['/'+field]
                    assert check['status']=='passed' and check['actual']==value and check['expected']==value and check['sourceSha256']==source_sha,'Source oracle differs'
                if name=='multi-read-calculated-artifact':
                    path=row['checks'][0]['path']
                    reads={c.get('arguments',{}).get('path') for c in task['checkpoints'] if c['name']=='read_file' and c['status']=='finished'}
                    assert {'source-a.json','source-b.json','package.json',path}<=reads,'Requested reads are missing'
                    saved=next(c for c in reversed(task['checkpoints']) if c['name']=='write_file' and c['status']=='finished' and c['arguments'].get('path')==path)
                    assert json.loads(saved['arguments']['content'])==expected,'Saved content differs'
                    commands=[json.loads(c['result']) for c in task['checkpoints'] if c['name'] in ('run_command','command_read') and c['status']=='finished' and c.get('result','').startswith('{')]
                    assert any(c.get('exitCode')==0 and str(expected['scriptCount']) in c.get('output','') for c in commands),'No successful actual calculation result'
            elif name=='incorrect-source-report':
                assert task['status']=='needs_attention' and status=='failed','Incorrect report did not retain a failed check'
                fields={c['check'].get('pointer'):c for c in rows if c['check']['kind']=='json_matches_source' and c['check'].get('sourcePath')=='package.json'}
                assert all(fields['/'+key]['actual']=='' and fields['/'+key]['expected']==expected[key] and fields['/'+key]['status']=='failed' and fields['/'+key]['sourceSha256']==source_sha for key in ('name','version')),'Incorrect source fields were not independently rejected'
                assert not any(c['name']=='write_file' for c in task['checkpoints']),'Negative artifact was modified'
            elif name=='no-criteria-unverified':
                assert task['status']=='completed' and status=='unverified' and not rows,'Missing criteria acquired verified status'
                assert package['name'] in task['result'] and package['version'] in task['result'],'Source facts missing'
            elif name=='missing-verification-artifact':
                assert task['status']=='needs_attention' and status=='failed' and any(c['check']['kind']=='file_exists' and c['status']=='failed' for c in rows),'Unavailable evidence was accepted'
            elif name=='passing-command-oracle':
                assert task['status']=='completed' and status=='passed' and any(c['check']['kind']=='command_exit' and c['status']=='passed' and c['evidence']['exitCode']==0 and 'SOURCE-ASSERTION-PASSED' in c['evidence']['output'] for c in rows),'Actual passing command evidence missing'
            elif name=='failed-command-oracle':
                assert task['status']=='needs_attention' and status=='failed' and any(c['check']['kind']=='command_exit' and c['status']=='failed' and c['evidence']['exitCode']!=0 for c in rows),'Actual failed command evidence missing'
            else:raise ValueError('Unknown case cannot be regraded')
            result.update(status='passed',taskId=task['id'],sessionId=session['id'],taskStatus=task['status'],verification=task['verification'],usage=usage,requests=session.get('requests',[]),reason='Graded the agent task session instead of the restored parent session')
        except (AssertionError,KeyError,StopIteration,ValueError) as error:result.update(status='failed',reviewError=str(error))
        outcomes.append(result)
    return outcomes

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();data=a.raw.read_bytes();raw=json.loads(data)
    if raw['status']=='running' or any(r['status']=='running' for r in raw['attempts']):p.error('Wait for the raw execution to finish')
    outcomes=review(raw)
    result=dict(status='passed' if len(outcomes)==28 and all(r['status']=='passed' for r in outcomes) else 'failed',rawReport=str(a.raw.resolve()),rawReportSha256=hashlib.sha256(data).hexdigest(),gradingScriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),helperSha256=raw['helperSha256'],sourceManifestSha256=raw['sourceManifestSha256'],models=raw.get('models',[]),outcomes=outcomes,note='Original report retained; corrected session observer grading only. Other failures are not overridden.')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],passed=sum(r['status']=='passed' for r in outcomes),attempts=len(outcomes))))
    raise SystemExit(0 if result['status']=='passed' else 1)
