"""Candidates earn promotion through independently checked repeated executions."""
import copy
from .storage import identity, now
from .memory import owner

def manage(agents,method,params):
    from .agents import text
    store=agents.store
    if method=='skill-propose':
        candidate=dict(id=identity(),owner=owner(store),name=text(params.get('name'),'skill name',100),description=text(params.get('description',''),'description',2000,False),content=text(params.get('content'),'skill content'),created=now(),status='candidate',evaluations=[])
        store.data['skillCandidates'].append(candidate);store.save();agents.service.emit('state',store.data);return candidate
    if method=='skill-rollback':
        skill=next((s for s in store.data['skills'] if s['id']==params.get('id')),None)
        if not skill or skill.get('owner','guest')!=owner(store):raise ValueError('Skill is unavailable for this owner')
        versions=skill.get('versions',[]);index=params.get('version',len(versions)-1)
        if type(index)!=int or not 0<=index<len(versions):raise ValueError('Choose an available version')
        previous=copy.deepcopy(versions[index]);versions.append(dict(content=skill['content'],description=skill.get('description',''),created=now(),reason='Before rollback'))
        skill.update(content=previous['content'],description=previous.get('description',''),versions=versions[-10:],updated=now());store.save();agents.service.emit('state',store.data);return skill
    candidate=agents.find('skillCandidates',params['id'])
    evidence=candidate.get('evaluations',[])
    if len(evidence)<2 or any(e.get('status')!='passed' for e in evidence[-2:]):raise ValueError('A candidate requires two passing evaluations before promotion')
    if any(e.get('baselineFailures',0)==0 and e.get('candidateFailures',0)>0 for e in evidence[-2:]):raise ValueError('The candidate regresses against its baseline')
    existing=next((s for s in store.data['skills'] if s['name']==candidate['name']),None)
    if existing and existing.get('owner','guest')!=owner(store):raise ValueError('Skill belongs to another owner')
    versions=copy.deepcopy((existing or {}).get('versions',[]))
    if existing:versions.append(dict(content=existing['content'],description=existing.get('description',''),created=now(),reason='Before evaluated promotion'))
    value=dict(id=(existing or {}).get('id',identity()),owner=owner(store),name=candidate['name'],description=candidate['description'],content=candidate['content'],versions=versions[-10:],created=(existing or {}).get('created',now()),updated=now(),source='Evaluated agent procedure',evaluationIds=[e['id'] for e in evidence[-2:]])
    if existing:existing.clear();existing.update(value)
    else:store.data['skills'].append(value)
    candidate.update(status='promoted',promoted=now());store.save();agents.service.emit('state',store.data);return value

async def evaluate(agents,params):
    from .outcomes import criteria
    candidate=agents.find('skillCandidates',params['id']);profile=copy.deepcopy(agents.find('agentProfiles',params['agentID']))
    cases=params.get('cases',[])
    if not isinstance(cases,list) or not 1<=len(cases)<=5:raise ValueError('Choose 1–5 real evaluation cases')
    for case in cases:
        if not isinstance(case,dict) or not isinstance(case.get('prompt'),str) or not criteria(case.get('successCriteria')):raise ValueError('Each case needs a prompt and independent success checks')
    if profile['reviewPolicy']=='Read only':
        if any(c['kind']=='command_exit' for case in cases for c in case['successCriteria']):raise ValueError('Read-only skill evaluation cannot run commands')
        if any(not any(c['kind'] in ('tool_succeeded','tool_contains') for c in case['successCriteria']) for case in cases):raise ValueError('Read-only evaluations require real tool evidence checks')
    original=next((s for s in agents.store.data['skills'] if s['name']==candidate['name']),None)
    # Replace only this skill in standing instructions; never expose candidate changes as established skill memory.
    profile['skills']=[s for s in profile.get('skills',[]) if s!=candidate['name']]
    rows=[]
    for case in cases:
        item={}
        for label,content in [('baseline',(original or {}).get('content','')),('candidate',candidate['content'])]:
            snapshot=copy.deepcopy(profile);snapshot['instructions']+='\nProcedure under evaluation:\n'+content
            if profile['reviewPolicy']=='Read only':
                task=await agents.run(profile['id'],case['prompt'],params.get('projectId',agents.store.data['activeProject']),'Skill evaluation',snapshot=snapshot,checks=case['successCriteria'])
                item[label]=dict(taskId=task['id'],verification=task.get('verification'),status=task['status'])
            else:
                from .workflow_graph import child_run
                evaluation_id=identity()
                branch=dict(id=evaluation_id,owner=owner(agents.store),projectId=params.get('projectId',agents.store.data['activeProject']),definition=dict(brief=case['prompt'],name='Skill evaluation'),profiles={profile['id']:snapshot},stages=[])
                stage=dict(id=identity(),name=label,agentID=profile['id'],goal=case['prompt'],output='Verified case outcome',isolation='Isolated changes',successCriteria=case['successCriteria'])
                entry=await child_run(agents,branch,stage)
                item[label]=dict(taskId=entry['taskId'],verification=entry.get('verification'),status=entry['status'],isolatedRoot=entry.get('isolatedRoot'),changes=entry.get('changes',[]))
        rows.append(item)
    failures=lambda label:sum(row[label].get('verification',{}).get('status')!='passed' for row in rows)
    report=dict(id=identity(),created=now(),cases=rows,baselineFailures=failures('baseline'),candidateFailures=failures('candidate'),status='passed' if failures('candidate')==0 else 'failed')
    candidate['evaluations'].append(report);candidate['evaluations']=candidate['evaluations'][-20:];agents.store.save();agents.service.emit('state',agents.store.data);return report
