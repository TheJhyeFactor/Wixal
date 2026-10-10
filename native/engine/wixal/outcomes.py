"""Controller-owned outcome checks. Model conclusions never constitute proof."""
import asyncio
import hashlib
import json
import re
from .storage import identity, now

KINDS=('file_exists','file_contains','json_equals','command_exit','tool_succeeded','tool_contains','json_matches_source')

def criteria(value):
    if value is None:return []
    if not isinstance(value,list) or len(value)>20:raise ValueError('Choose at most 20 outcome checks')
    checked=[]
    for raw in value:
        if not isinstance(raw,dict) or raw.get('kind') not in KINDS:raise ValueError('Invalid outcome check')
        row={k:v for k,v in raw.items() if k in ('kind','path','value','pointer','command','tool','label','sourcePath','sourcePointer','transform')}
        for key in ('path','pointer','command','tool','label','sourcePath','sourcePointer'):
            if key in row and (not isinstance(row[key],str) or len(row[key])>8000):raise ValueError('Invalid check '+key)
        if row['kind'].startswith('file_') or row['kind'] in ('json_equals','json_matches_source'):
            from pathlib import PurePath
            path=row.get('path','')
            if not path or PurePath(path).is_absolute() or '..' in PurePath(path).parts:raise ValueError('Checks require a project-relative path')
        if row['kind'] in ('file_contains','tool_contains') and (not isinstance(row.get('value'),str) or len(row['value'])>24000):raise ValueError('Choose text to check')
        if row['kind']=='json_equals' and ('value' not in row or len(json.dumps(row['value']))>24000):raise ValueError('Choose a bounded JSON value')
        if row['kind']=='command_exit' and not row.get('command'):raise ValueError('Choose a verification command')
        if row['kind'] in ('tool_succeeded','tool_contains') and not row.get('tool'):raise ValueError('Choose a tool outcome')
        if row['kind']=='json_matches_source':
            source=row.get('sourcePath','')
            if not source or PurePath(source).is_absolute() or '..' in PurePath(source).parts:raise ValueError('Source checks require a project-relative path')
            if row.get('transform','identity') not in ('identity','length'):raise ValueError('Unsupported source transform')
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
    pending=('running','stopped','failed','cancelled','interrupted','queued','waiting_review','needs_attention','paused')
    return not result.get('error') and result.get('exitCode') in (None,0) and result.get('state') not in pending and result.get('status') not in pending and result.get('saved') is not False

def equal(left,right):
    if isinstance(left,bool) or isinstance(right,bool):return type(left)==type(right) and left==right
    if isinstance(left,(int,float)) and isinstance(right,(int,float)):return left==right
    if type(left)!=type(right):return False
    if isinstance(left,dict):return left.keys()==right.keys() and all(equal(left[k],right[k]) for k in left)
    if isinstance(left,list):return len(left)==len(right) and all(equal(a,b) for a,b in zip(left,right))
    return left==right

def discovery_follow_up(task):
    """Check a requested chain against this task's checkpoints, never memories.

    This only returns feedback. Execution still requires a model tool call and
    all normal controller authority/review checks.
    """
    prompt=task.get('prompt','').lower()
    # Tool availability is context, not a request to perform inspection.
    prompt=re.sub(r'\b(?:rustscan\s+and\s+nmap|nmap\s+and\s+rustscan|nmap)\s+(?:are|is)\s+(?:already\s+)?installed\b','',prompt)
    if not re.search(r'\b(discover|discovery|rustscan)\b',prompt):return None
    if not re.search(r'\b(inspect|inspection|enumerate|enumeration|nmap)\b',prompt):return None
    if re.search(r"\b(?:do not|don't|without|no|skip)\b[^.!?\n]{0,160}\b(?:inspect\w*|enumerat\w*|nmap)\b",prompt):return None
    sources=[];inspections=[]
    for checkpoint in task.get('checkpoints',[]):
        result=decode(checkpoint.get('result',''))
        if checkpoint.get('status')!='finished' or not isinstance(result,dict):continue
        structured=result.get('structuredResult',{})
        if checkpoint['name']=='network_read' and result.get('state')=='completed' and structured.get('handoffEligible'):
            sources.append(result)
        if checkpoint['name']=='network_scan' and result.get('sourceSessionId'):
            inspections.append(result)
    if not sources:return None
    missing=[source['session_id'] for source in sources if not any(
        result.get('sourceSessionId')==source['session_id'] and not result.get('error')
        and (result.get('skipped') or result.get('state')=='completed' or result.get('exitCode')==0) for result in inspections)]
    return dict(check=dict(kind='requested_discovery_inspection',tool='network_scan',
                          label='Complete the inspection requested in the current task using its discovery source_session_id'),
                status='failed' if missing else 'passed',sourceSessions=missing,checked=now())

def json_pointer(value,pointer=''):
    if pointer and not pointer.startswith('/'):raise ValueError('Use a JSON pointer beginning with /')
    for component in pointer[1:].split('/') if pointer else []:
        component=component.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not re.fullmatch(r'0|[1-9][0-9]*',component):raise ValueError('Invalid array index')
            value=value[int(component)]
        else:value=value[component]
    return value

def unsupported_artifact_claim(task):
    if not any(c.get('name') in ('write_file','edit_file') and successful(c) for c in task.get('checkpoints',[])):return False
    text=re.sub(r'```.*?```','',task.get('result',''),flags=re.S)
    for sentence in re.split(r'[.!?\n]',text):
        if re.search(r"\b(?:not|unverified|cannot|can't|unable|failed|unavailable|unconfirmed|never)\b",sentence,re.I):continue
        if re.search(r'\b(?:verified|validated)\b',sentence,re.I):return True
    return False

async def verify(store,tools,task,checks=None):
    checks=criteria(task.get('successCriteria',[]) if checks is None else checks)
    rows=[]
    settled={}
    for checkpoint in task.get('checkpoints',[]):
        result=decode(checkpoint.get('result',''))
        if isinstance(result,dict) and result.get('session_id') and result.get('state') in ('completed','stopped','failed'):settled[result['session_id']]=result
    for checkpoint in task.get('checkpoints',[]):
        result=decode(checkpoint.get('result',''))
        if isinstance(result,dict) and result.get('session_id') in settled:checkpoint['resolvedOutcome']=settled[result['session_id']]
    for check in checks:
        row=dict(check=check,status='failed',checked=now())
        try:
            kind=check['kind']
            if kind in ('file_exists','file_contains','json_equals','json_matches_source'):
                from .tools import safe_path
                path=safe_path((store.project() or {}).get('root'),check['path'])
                if not path.is_file() or path.stat().st_size>4*1024*1024:raise ValueError('Artifact is missing or exceeds 4 MB')
                raw=path.read_bytes();row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                if kind=='file_contains' and check['value'] not in raw.decode():raise ValueError('Required text is absent')
                if kind in ('json_equals','json_matches_source'):
                    value=json_pointer(json.loads(raw),check.get('pointer',''))
                    row['actual']=value
                    expected=check.get('value')
                    if kind=='json_matches_source':
                        source=safe_path((store.project() or {}).get('root'),check['sourcePath'])
                        if source==path:raise ValueError('Verification requires a separate source artifact')
                        if not source.is_file() or source.stat().st_size>4*1024*1024:raise ValueError('Source is missing or exceeds 4 MB')
                        source_raw=source.read_bytes()
                        expected=json_pointer(json.loads(source_raw),check.get('sourcePointer',''))
                        if check.get('transform')=='length':
                            if not isinstance(expected,(list,dict)):raise ValueError('Length requires a JSON array or object')
                            expected=len(expected)
                        row.update(expected=expected,sourceSha256=hashlib.sha256(source_raw).hexdigest())
                    if not equal(value,expected):raise ValueError('JSON value differs from the required result')
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
                candidates=[matching[-1]]
                if kind=='tool_contains' and check['tool']=='read_file':
                    # Different files are independent evidence. A later read
                    # of the same canonical path supersedes its earlier bytes.
                    from .tools import safe_path
                    latest_reads={}
                    for checkpoint in matching:
                        path=checkpoint.get('arguments',{}).get('path')
                        key=str(safe_path((store.project() or {}).get('root'),path)) if path else None
                        latest_reads[key]=checkpoint
                    candidates=list(reversed(list(latest_reads.values())))
                for candidate in candidates:
                    if not successful(candidate):continue
                    result=candidate.get('resolvedOutcome',decode(candidate.get('result','')))
                    evidence=(str(result['output'])+json.dumps(result.get('structuredResult',{}),ensure_ascii=False)) if isinstance(result,dict) and 'output' in result else json.dumps(result,ensure_ascii=False) if not isinstance(result,str) else result
                    if kind!='tool_contains' or check['value'] in evidence:
                        row['checkpointId']=candidate['id'];break
                else:raise ValueError('Required evidence is absent from the final tool result for each file')
            row['status']='passed'
        except (ValueError,OSError,KeyError,IndexError,TypeError,UnicodeError) as error:row['error']=str(error)
        rows.append(row)
    from .network_claims import check as network_claim_check,evidence_quote
    contradiction=network_claim_check(task)
    if contradiction:rows.append(contradiction)
    quote=evidence_quote(task)
    if quote:rows.append(quote)
    if hasattr(tools,'catalog'):
        from .agent_context import available_names
        from .context_policy import eligible
        from .network_claims import availability_claim
        available=eligible(tools.catalog(),available_names(tools,store),store.project())
        availability=availability_claim(task,[t['function']['name'] for t in available])
        if availability:rows.append(availability)
    follow_up=discovery_follow_up(task)
    if follow_up:rows.append(follow_up)
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
    if not rows and unsupported_artifact_claim(task):
        rows.append(dict(check=dict(kind='artifact_verification_claim'),status='failed',error='The saved artifact has no independent source checks. Use verify_json for every required field or explicitly report that the artifact remains unverified.',checked=now()))
    status='failed' if any(r['status']=='failed' for r in rows) else 'needs_attention' if unresolved else 'passed' if rows else 'unverified'
    report=dict(status=status,checked=now(),checks=rows,unresolved=unresolved,note='Passed checks cover the explicit criteria only.' if status=='passed' else 'No independent success criteria were supplied.' if status=='unverified' else 'Inspect failed checks or unresolved tool outcomes.')
    task['verification']=report
    if task.get('status')=='completed' and status in ('failed','needs_attention'):task.update(status='needs_attention',error=report['note'])
    if task.get('status')=='needs_attention' and status=='passed' and task.get('result'):task.update(status='completed');task.pop('error',None)
    store.save();return report
