"""Bounded immutable engagement evidence, claims and non-executing graph traversal."""
import copy
import hashlib
import json
from collections import deque
from .storage import identity, now
from .tools import safe_path

COLLECTIONS=('securityEngagements','securityObjectives','securityRelations','securityVerifications','securityCleanup','securityAssignments','securityEvidence','securityEngagementEvents')
ROLES={'planner':'Develop prerequisite-based hypotheses and candidate checks from retained evidence.',
       'recon_analyst':'Interpret observed assets and services; distinguish historical identities and incomplete coverage.',
       'researcher':'Evaluate the supplied advisory evidence and its applicability. Do not invent sources or retrieve external data.',
       'verifier':'Challenge the claim, identify contradictory evidence and propose discriminating positive/baseline observations. Your prose is not independent verification.',
       'reporter':'Draft a report from retained evidence. Separate observations, hypotheses, human review and independently evaluated outcomes.'}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def retain(manager, engagement, value, kind, source):
    data=canonical(value)
    if len(data)>4*1024*1024:raise ValueError('Evidence exceeds 4 MB')
    sha=hashlib.sha256(data).hexdigest()
    # Exclusive create and digest verification protect retained evidence identity.
    root=manager.store.directory/'engagement-evidence'/engagement['id']
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=safe_path(root,sha+'.json',True)
    try:
        with path.open('xb') as f:f.write(data)
        path.chmod(0o600)
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Retained evidence identity mismatch')
    row=dict(id=identity(),projectId=engagement['projectId'],engagementId=engagement['id'],kind=kind,source=source,sha256=sha,bytes=len(data),created=now())
    manager.store.data['securityEvidence'].append(row)
    return row


def read(manager, engagement, evidence_id):
    row=manager.record('securityEvidence',evidence_id,engagement)
    path=safe_path(manager.store.directory/'engagement-evidence'/engagement['id'],row['sha256']+'.json')
    if not path.is_file() or path.stat().st_size>4*1024*1024:raise ValueError('Retained evidence is unavailable')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Retained evidence changed; verification is invalid')
    return row,json.loads(data)


def value_at(value,pointer):
    if not isinstance(pointer,str) or len(pointer)>1000 or pointer and not pointer.startswith('/'):raise ValueError('Use a JSON pointer')
    if not pointer:return value
    for key in pointer[1:].split('/'):
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) and key.isdigit() else value[key]
    return value


def discriminate(manager,engagement,params):
    positive_id=params.get('positiveId');baseline_id=params.get('baselineId')
    if positive_id==baseline_id:raise ValueError('Positive and baseline observations must be independent records')
    positive,p=read(manager,engagement,positive_id);baseline,b=read(manager,engagement,baseline_id)
    if positive['kind']!='run' or baseline['kind']!='run' or positive['source']==baseline['source']:
        raise ValueError('Verification requires two independently collected Wixal run records')
    pr=manager.record('securityRuns',positive['source'],engagement);br=manager.record('securityRuns',baseline['source'],engagement)
    if pr.get('status')!='completed' or br.get('status')!='completed':raise ValueError('Verification requires completed observation runs')
    if pr.get('scopeRevision')!=br.get('scopeRevision') or pr.get('environment')!=br.get('environment') or pr.get('arguments',{}).get('profile')!=br.get('arguments',{}).get('profile'):
        raise ValueError('Verification requires comparable scope, environment and profile')
    if pr['targetId']!=br['targetId'] or pr['capability']!=br['capability'] or pr['capability'] not in ('website_assess','network_scan','network_discover','linux_network_scan'):
        raise ValueError('Positive and baseline need comparable target and capability identities')
    pointer=params.get('pointer','');expected=params.get('expected')
    if not pointer or not isinstance(expected,(str,int,float,bool)) or len(str(expected))>2000:
        raise ValueError('Use a bounded scalar expected signal and explicit JSON pointer')
    try:pv=value_at(p['result'],pointer);bv=value_at(b['result'],pointer)
    except (KeyError,IndexError,TypeError,ValueError):raise ValueError('Verification pointer is absent from retained observations')
    # Type-sensitive equality prevents True == 1 and similar accidental signals.
    positive_hit=type(pv)==type(expected) and pv==expected
    baseline_hit=type(bv)==type(expected) and bv==expected
    return dict(positiveId=positive_id,baselineId=baseline_id,positiveSha256=positive['sha256'],baselineSha256=baseline['sha256'],pointer=pointer,expected=expected,positiveValue=pv,baselineValue=bv,
                status='discriminated' if positive_hit and not baseline_hit else 'inconclusive',
                limitation='Observed scalar discrimination only; this does not establish exploit truth or automatically confirm a finding.')


def paths(manager,engagement,start,end):
    manager.entity(engagement,start);manager.entity(engagement,end)
    edges=[e for e in manager.rows('securityRelations',engagement) if e['state']!='disproved']
    adjacency={}
    for edge in edges:adjacency.setdefault(edge['fromId'],[]).append(edge)
    queue=deque([(start,[],{start})]);result=[];visited=0
    while queue and len(result)<20 and visited<500:
        node,chain,seen=queue.popleft();visited+=1
        if node==end:
            result.append(dict(edgeIds=[e['id'] for e in chain],hops=len(chain),state='candidate',evidenceIds=list(dict.fromkeys(i for e in chain for i in e['evidenceIds'])),limitation='Candidate relationship path; no action or confirmation is implied.'));continue
        if len(chain)>=6:continue
        for edge in adjacency.get(node,[]):
            if edge['toId'] not in seen:queue.append((edge['toId'],chain+[edge],seen|{edge['toId']}))
    return dict(paths=result,truncated=bool(queue),searchLimit=500)


def report(manager,engagement):
    result=dict(schema=1,engagement=copy.deepcopy(engagement),exported=now())
    for collection in COLLECTIONS[1:]:result[collection]=copy.deepcopy(manager.rows(collection,engagement))
    result['targets']=[copy.deepcopy(manager.workspace.target(t)) for t in engagement['targetIds']]
    result['runs']=[copy.deepcopy(r) for r in manager.workspace.runs if r.get('engagementId')==engagement['id']]
    result['findings']=[copy.deepcopy(f) for f in manager.store.data['securityFindings'] if f['targetId'] in engagement['targetIds'] and f['projectId']==engagement['projectId']]
    result['limitations']=['Execution, scalar discrimination, finding review and cleanup are distinct.','Imported claims are untrusted external evidence.','Reports can contain sensitive engagement data; review before sharing.']
    return result
