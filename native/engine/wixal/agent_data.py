"""Agent record validation and permission-free workspace transfers."""
import copy
from .storage import now
from .memory import owner
from .outcomes import criteria

def validate_record(collection,row):
    if not isinstance(row,dict) or not isinstance(row.get('id'),str):raise ValueError('Invalid agent record')
    def bounded(key,maximum=24000,required=True):
        value=row.get(key,'')
        if not isinstance(value,str) or len(value)>maximum or required and not value.strip():raise ValueError('Invalid '+collection+' '+key)
    if collection=='agentProfiles':
        for key,size in [('name',100),('purpose',2000),('instructions',24000),('model',200)]:bounded(key,size)
        from .agent_authority import validate
        validate(row.get('authority'));criteria(row.get('successCriteria'))
        if row.get('reviewPolicy','Review actions') not in ('Read only','Review actions','Pre-approved actions'):raise ValueError('Invalid action policy')
        if row.get('memoryScope','Project only') not in ('Project only','Project + global preferences','Global preferences only','Memory off'):raise ValueError('Invalid memory policy')
        if not isinstance(row.get('privateNotes',''),str) or len(row.get('privateNotes',''))>2000:raise ValueError('Invalid private notes')
        if not isinstance(row.get('skills',[]),list) or any(not isinstance(s,str) for s in row.get('skills',[])):raise ValueError('Invalid agent skills')
        for key,low,high,default in [('maxTurns',1,100,20),('maxCalls',1,500,100),('timeoutSeconds',10,1800,600)]:
            value=row.get(key,default)
            if type(value)!=int or not low<=value<=high:raise ValueError('Invalid agent '+key)
    elif collection=='agentWorkflows':
        bounded('name',100);bounded('brief',required=False)
        stages=row.get('stages')
        if not isinstance(stages,list) or not 1<=len(stages)<=30:raise ValueError('Invalid workflow stages')
        for stage in stages:
            if not isinstance(stage,dict) or any(not isinstance(stage.get(k),str) or not stage[k] for k in ('id','name','agentID','goal')):raise ValueError('Invalid stage')
            criteria(stage.get('successCriteria'))
        if len({s['id'] for s in stages})!=len(stages):raise ValueError('Duplicate stage identifiers')
        from .workflow_graph import validate_graph
        validate_graph(row)
    elif collection=='skills':bounded('name',100);bounded('content')
    elif collection=='schedules':
        bounded('name',100);bounded('prompt');bounded('agentID',200);criteria(row.get('successCriteria'))
        from .agents import TIMINGS,next_calendar
        if row.get('timing') in TIMINGS:next_calendar(row,now())
        elif type(row.get('intervalSeconds'))!=int or not 60<=row['intervalSeconds']<=366*86400:raise ValueError('Invalid routine timing')
    elif collection=='workflowRuns':
        bounded('workflowId',200)
        validate_record('agentWorkflows',row.get('definition'))
        if not isinstance(row.get('stages'),list) or not isinstance(row.get('profiles'),dict):raise ValueError('Invalid workflow evidence')
        for profile in row['profiles'].values():validate_record('agentProfiles',profile)
    elif collection=='agentJobs':bounded('prompt');validate_record('agentProfiles',row.get('profile'))
    elif collection=='skillCandidates':bounded('name',100);bounded('content')

def without_authority(profile):
    profile=copy.deepcopy(profile);profile.update(authority={},reviewPolicy='Read only' if profile.get('reviewPolicy')=='Read only' else 'Review actions');return profile

def imported(collection,row,data,store):
    validate_record(collection,row)
    if row.get('owner','guest')!=owner(store):raise ValueError('This agent record belongs to another workspace identity')
    row=copy.deepcopy(row)
    if collection=='agentProfiles':row=without_authority(row)
    if collection=='agentWorkflows' and any(s['agentID'] not in {a['id'] for a in data['agentProfiles']} for s in row['stages']):raise ValueError('Workflow refers to an unavailable agent')
    if collection=='schedules':
        if row['agentID'] not in {a['id'] for a in data['agentProfiles']} or row.get('workflowID') and row['workflowID'] not in {f['id'] for f in data['agentWorkflows']}:raise ValueError('Routine refers to an unavailable agent or workflow')
        row.update(enabled=False,authority={},importedPaused=True);row.pop('lastRun',None)
        from .agents import TIMINGS,next_calendar
        row['nextRun']=next_calendar(row,now()) if row.get('timing') in TIMINGS else now()+row['intervalSeconds']*1000
    if collection=='workflowRuns':
        row['profiles']={key:without_authority(p) for key,p in row['profiles'].items()}
        if row.get('status') in ('running','waiting_review'):row['status']='interrupted'
        for stage in row['stages']:
            stage.pop('isolatedRoot',None)
            if stage.get('mergeStatus')=='pending_review':stage['mergeStatus']='unavailable_after_transfer'
    if collection=='agentJobs':row.update(status='interrupted',profile=without_authority(row['profile']),error='Imported job; inspect and explicitly resume its task')
    return row

def validate_transfer_snapshot(task):
    if isinstance(task.get('agentSnapshot'),dict):task['agentSnapshot']=without_authority(task['agentSnapshot'])
    criteria(task.get('successCriteria'))
    return task
