"""Controller-owned outcome checks. Model conclusions never constitute proof."""
import asyncio
import hashlib
import json
from .storage import identity, now

KINDS=('file_exists','file_contains','json_equals','command_exit','tool_succeeded','tool_contains')

def criteria(value):
    if value is None:return []
    if not isinstance(value,list) or len(value)>20:raise ValueError('Choose at most 20 outcome checks')
    checked=[]
    for raw in value:
        if not isinstance(raw,dict) or raw.get('kind') not in KINDS:raise ValueError('Invalid outcome check')
        row={k:v for k,v in raw.items() if k in ('kind','path','value','pointer','command','tool','label')}
        for key in ('path','pointer','command','tool','label'):
            if key in row and (not isinstance(row[key],str) or len(row[key])>8000):raise ValueError('Invalid check '+key)
        if row['kind'].startswith('file_') or row['kind']=='json_equals':
            from pathlib import PurePath
            path=row.get('path','')
            if not path or PurePath(path).is_absolute() or '..' in PurePath(path).parts:raise ValueError('Checks require a project-relative path')
        if row['kind'] in ('file_contains','tool_contains') and (not isinstance(row.get('value'),str) or len(row['value'])>24000):raise ValueError('Choose text to check')
        if row['kind']=='json_equals' and ('value' not in row or len(json.dumps(row['value']))>24000):raise ValueError('Choose a bounded JSON value')
        if row['kind']=='command_exit' and not row.get('command'):raise ValueError('Choose a verification command')
        if row['kind'] in ('tool_succeeded','tool_contains') and not row.get('tool'):raise ValueError('Choose a tool outcome')
        checked.append(row)
    return checked

def decode(value):
    if not isinstance(value,str):return value
    try:return json.loads(value)
    except (ValueError,TypeError):return value

def successful(checkpoint):
    result=checkpoint.get('resolvedOutcome',decode(checkpoint.get('result','')))
    if checkpoint.get('status')!='finished':return False
    if isinstance(result,str):return not result.startswith(('User declined','Not executed:'))
    if not isinstance(result,dict):return True
    return not result.get('error') and result.get('exitCode') in (None,0) and result.get('state') not in ('running','stopped') and result.get('saved') is not False

def equal(left,right):
    if isinstance(left,bool) or isinstance(right,bool):return type(left)==type(right) and left==right
    if isinstance(left,(int,float)) and isinstance(right,(int,float)):return left==right
    if type(left)!=type(right):return False
    if isinstance(left,dict):return left.keys()==right.keys() and all(equal(left[k],right[k]) for k in left)
    if isinstance(left,list):return len(left)==len(right) and all(equal(a,b) for a,b in zip(left,right))
    return left==right

async def verify(store,tools,task,checks=None):
    checks=criteria(task.get('successCriteria',[]) if checks is None else checks)
    rows=[]
    settled={}
    for checkpoint in task.get('checkpoints',[]):
        result=decode(checkpoint.get('result',''))
        if isinstance(result,dict) and result.get('session_id') and result.get('state') in ('completed','stopped'):settled[result['session_id']]=result
    for checkpoint in task.get('checkpoints',[]):
        result=decode(checkpoint.get('result',''))
        if isinstance(result,dict) and result.get('session_id') in settled:checkpoint['resolvedOutcome']=settled[result['session_id']]
    for check in checks:
        row=dict(check=check,status='failed',checked=now())
        try:
            kind=check['kind']
            if kind in ('file_exists','file_contains','json_equals'):
                from .tools import safe_path
                path=safe_path((store.project() or {}).get('root'),check['path'])
                if not path.is_file() or path.stat().st_size>4*1024*1024:raise ValueError('Artifact is missing or exceeds 4 MB')
                raw=path.read_bytes();row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                if kind=='file_contains' and check['value'] not in raw.decode():raise ValueError('Required text is absent')
                if kind=='json_equals':
                    value=json.loads(raw)
                    for component in check.get('pointer','').strip('/').split('/') if check.get('pointer') else []:
                        component=component.replace('~1','/').replace('~0','~')
                        value=value[int(component)] if isinstance(value,list) else value[component]
                    row['actual']=value
                    if not equal(value,check['value']):raise ValueError('JSON value differs from the required result')
            elif kind=='command_exit':
                # Uses the same controller review and scoped background authority as every action.
                checkpoint=dict(id=identity(),name='verification_command',arguments=dict(command=check['command']),status='started',created=now())
                task['checkpoints'].append(checkpoint);store.save()
                try:
                    result=await tools.start_command(check['command'],120,task['sessionId'])
                    if not isinstance(result,dict):raise ValueError(str(result))
                    job=tools.jobs[result['session_id']];await job['collector']
                    result=await tools.read_job(dict(session_id=job['id'],wait_ms=0),task['sessionId'])
                    checkpoint.update(status='finished',result=json.dumps(result),finished=now());row['evidence']=result
                    if result['exitCode']!=0 or result['state']!='completed':raise ValueError('Verification command did not pass')
                finally:
                    if checkpoint['status']=='started':checkpoint.update(status='interrupted',result='Verification did not finish; inspect current state',finished=now())
                    store.save()
            else:
                matching=[c for c in task['checkpoints'] if c['name']==check['tool']]
                if not matching or not successful(matching[-1]):raise ValueError('No successful final outcome for the required tool')
                if kind=='tool_contains' and check['value'] not in matching[-1].get('result',''):raise ValueError('Required evidence is absent from the tool result')
                row['checkpointId']=matching[-1]['id']
            row['status']='passed'
        except (ValueError,OSError,KeyError,IndexError,TypeError,UnicodeError) as error:row['error']=str(error)
        rows.append(row)
    latest={}
    for checkpoint in task.get('checkpoints',[]):
        # Corrected arguments can recover; later unrelated command success cannot hide a failed command.
        key=checkpoint['name']
        if key in ('run_command','command_start','verification_command'):key+=':'+json.dumps(checkpoint.get('arguments',{}).get('command',''),sort_keys=True)
        latest[key]=checkpoint
    def recovered_schema(checkpoint):
        result=decode(checkpoint.get('result',''))
        return checkpoint.get('status')=='error' and isinstance(result,dict) and result.get('inputs') and any(c['name']==result.get('toolMatch',checkpoint['name']) and successful(c) for c in task.get('checkpoints',[])[task['checkpoints'].index(checkpoint)+1:])
    unresolved=[c['id'] for c in latest.values() if not successful(c) and not recovered_schema(c)]
    status='failed' if any(r['status']=='failed' for r in rows) else 'needs_attention' if unresolved else 'passed' if rows else 'unverified'
    report=dict(status=status,checked=now(),checks=rows,unresolved=unresolved,note='Passed checks cover the explicit criteria only.' if status=='passed' else 'No independent success criteria were supplied.' if status=='unverified' else 'Inspect failed checks or unresolved tool outcomes.')
    task['verification']=report
    if task.get('status')=='completed' and status in ('failed','needs_attention'):task.update(status='needs_attention',error=report['note'])
    if task.get('status')=='needs_attention' and status=='passed' and task.get('result'):task.update(status='completed');task.pop('error',None)
    store.save();return report
