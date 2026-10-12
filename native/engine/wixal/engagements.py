"""Native engagement aggregate over the existing investigation queue and evidence store."""
import copy
import json
from .storage import identity, now
from .tools import safe_path
from . import engagement_evidence as evidence
from . import engagement_policy as policy

ACTIVE_RUNS=('queued','blocked','running','waiting_review','waiting_model')
FINAL=('completed','closed_incomplete','cancelled')


class Engagements:
    def __init__(self,workspace):
        self.workspace=workspace;self.store=workspace.store
        from .security_worker import LinuxWorker
        self.worker=LinuxWorker(self)
        for key in evidence.COLLECTIONS:self.store.data.setdefault(key,[])
        # Historical targets remain unapproved. No fabricated engagement migration.
        for item in self.store.data['securityAssignments']:
            if item['status'] in ACTIVE_RUNS:item.update(status='interrupted',error='Engine restarted; inspect retained evidence before explicit reassignment')
        for engagement in self.store.data['securityEngagements']:
            if engagement['status']=='running':engagement.update(status='paused',pauseReason='Engine restarted; explicit approval of current scope is required',approval=None)
        for run in workspace.runs:
            if run.get('engagementId') and run['status']=='interrupted':run['effectState']='unknown'

    def rows(self,collection,engagement):
        return [r for r in self.store.data[collection] if r.get('engagementId')==engagement['id'] and r.get('projectId')==engagement['projectId']]

    def get(self,identifier):
        return self.workspace.record('securityEngagements',identifier)

    def record(self,collection,identifier,engagement):
        row=self.workspace.record(collection,identifier)
        if collection in ('securityRuns','securityFindings','securityDiscoveries','securityTargets'):
            if (row['id'] if collection=='securityTargets' else row.get('targetId')) not in engagement['targetIds']:
                raise ValueError('Record belongs to another engagement target')
            if collection=='securityRuns' and row.get('engagementId')!=engagement['id']:raise ValueError('Run belongs to another engagement')
        elif row.get('engagementId')!=engagement['id']:raise ValueError('Record belongs to another engagement')
        return row

    def scope(self,engagement):return engagement['scopes'][-1]['policy']

    def event(self,engagement,kind,detail):
        self.store.data['securityEngagementEvents'].append(dict(id=identity(),projectId=engagement['projectId'],engagementId=engagement['id'],kind=kind,detail=copy.deepcopy(detail),created=now()))

    def add(self,collection,engagement,**fields):
        row=dict(id=identity(),projectId=engagement['projectId'],engagementId=engagement['id'],created=now(),**fields)
        self.store.data[collection].append(row);return row

    def for_target(self,target):
        return self.get(target['engagementId']) if target.get('engagementId') else None

    def authorize_run(self,run):
        if not run.get('engagementId'):return
        engagement=self.get(run['engagementId']);scope=self.scope(engagement)
        if engagement['status']!='running' or not engagement.get('approval'):
            raise ValueError('Engagement is not approved and running')
        if run['scopeRevision']!=engagement['scopeRevision'] or engagement['approval']['digest']!=evidence.digest(scope):
            raise ValueError('Engagement scope changed; prepare and review a new run')
        if not scope['starts']<=now()<scope['ends']:raise ValueError('Engagement testing window is not active')
        if run['targetId'] not in scope['targetIds'] or run['capability'] not in scope['capabilities']:
            raise ValueError('Target or capability is outside the engagement scope')
        target=self.workspace.target(run['targetId'])
        if target['address']!=run['address'] or policy.excluded(run['address'],scope['exclusions']):
            raise ValueError('Target is excluded or its identity changed')
        if run.get('deadline') and now()>=run['deadline']:raise ValueError('Engagement run deadline expired')

    def bind_run(self,run,params):
        target=self.workspace.target(run['targetId']);engagement=self.for_target(target)
        requested=params.get('engagementId')
        if requested and (not engagement or requested!=engagement['id']):raise ValueError('Engagement does not own the selected target')
        if not engagement:return
        run.update(engagementId=engagement['id'],scopeRevision=engagement['scopeRevision'],effectState='prepared',environment='local-bounded-adapter')
        self.authorize_run(run)
        if len([r for r in self.workspace.runs if r.get('engagementId')==engagement['id']])>=self.scope(engagement)['maxRuns']:
            raise ValueError('Engagement run budget exhausted')
        objective_id=params.get('objectiveId')
        if objective_id:
            objective=self.record('securityObjectives',objective_id,engagement)
            if objective['targetId']!=run['targetId']:raise ValueError('Objective belongs to another target')
            if any(self.record('securityObjectives',p,engagement)['status']!='completed' for p in objective['dependsOn']):raise ValueError('Objective prerequisites are unfinished')
            run['objectiveId']=objective_id
        if run['capability'] in ('network_scan','network_discover','linux_network_scan'):
            if type(run['arguments'].get('timeout_seconds',180)) is not int:raise ValueError('Run deadline must be an integer')
            run['arguments']['timeout_seconds']=min(run['arguments'].get('timeout_seconds',180),self.scope(engagement)['maxSeconds'])

    def started(self,run):
        if not run.get('engagementId'):return
        self.authorize_run(run)
        run.update(effectState='dispatching',deadline=now()+self.scope(self.get(run['engagementId']))['maxSeconds']*1000)
        self.event(self.get(run['engagementId']),'operation_dispatch',dict(runId=run['id'],scopeRevision=run['scopeRevision'],arguments=run['arguments']))

    def finished(self,run):
        if not run.get('engagementId'):return
        engagement=next(e for e in self.store.data['securityEngagements'] if e['id']==run['engagementId'])
        run['effectState']='succeeded' if run['status']=='completed' else 'unknown' if run['status'] in ('cancelled','interrupted') else 'failed'
        if run['status']=='completed' and not run.get('retainedEvidenceId'):
            row=evidence.retain(self,engagement,dict(runId=run['id'],targetId=run['targetId'],capability=run['capability'],arguments=run['arguments'],result=run.get('result',{}),model=run.get('model'),finished=run.get('finished')), 'run',run['id'])
            run['retainedEvidenceId']=row['id']
        if isinstance(run.get('workerCleanup'),dict) and run['workerCleanup'].get('status')=='unknown' and not any(c.get('runId')==run['id'] for c in self.rows('securityCleanup',engagement)):
            self.add('securityCleanup',engagement,runId=run['id'],title='Reconcile Linux worker environment',description='Inspect and remove the owned container/network; cleanup was not acknowledged.',status='pending',evidenceIds=[],scopeRevision=run['scopeRevision'])
        for assignment in self.rows('securityAssignments',engagement):
            if assignment.get('runId')==run['id']:assignment.update(status=run['status'],evidenceId=run.get('retainedEvidenceId'),finished=now())
        self.event(engagement,'operation_receipt',dict(runId=run['id'],state=run['effectState'],evidenceId=run.get('retainedEvidenceId')))

    def entity(self,engagement,identifier):
        for collection in ('securityTargets','securityDiscoveries','securityFindings','securityObjectives'):
            if any(r['id']==identifier for r in self.store.data[collection]):return self.record(collection,identifier,engagement)
        raise ValueError('Choose an engagement asset, finding, observation or objective')

    async def stop(self,engagement,status):
        # Revoke first, then wait for the owned task/process cancellation path.
        engagement.update(status=status,approval=None)
        self.workspace.publish()
        for run in list(self.workspace.runs):
            if run.get('engagementId')==engagement['id'] and run['status'] in ACTIVE_RUNS:
                await self.workspace.dispatch('security-run-stop',dict(id=run['id']))
        self.event(engagement,'engagement_'+status,dict(scopeRevision=engagement['scopeRevision']))

    async def dispatch(self,method,params):
        if method=='security-engagement-worker-configure':return await self.worker.configure(params.get('socket'))
        if method=='security-engagement-worker-inspect':return await self.worker.inspect()
        if method=='security-specialist-catalog':return dict(roles=evidence.ROLES,capabilities=list(policy.CAPABILITIES))
        if method=='security-engagement-skills':
            from .memory import owner
            from pathlib import Path
            package=json.loads((Path(__file__).parent/'resources/redteam-skills.json').read_text())
            added=[]
            for skill in package['skills']:
                old=next((s for s in self.store.data['skills'] if s.get('owner','guest')==owner(self.store) and s.get('name')==skill['name']),None)
                if old:added.append(old['id']);continue
                row=dict(copy.deepcopy(skill),id=identity(),owner=owner(self.store),created=now(),source='wixal:redteam-skills:v1',packageSha256=evidence.digest(package))
                self.store.data['skills'].append(row);added.append(row['id'])
            self.workspace.publish();return dict(skillIds=added)
        if method=='security-engagement-create':
            project=self.store.project()
            if not project:raise ValueError('Choose a project')
            target_ids=policy.strings(params.get('targetIds',[]),'engagement targets')
            if not target_ids:raise ValueError('Choose at least one existing target')
            targets=[self.workspace.target(t) for t in target_ids]
            if any(t.get('archived') for t in targets):raise ValueError('Restore engagement targets first')
            if any(t.get('engagementId') and self.get(t['engagementId'])['status'] not in FINAL for t in targets):raise ValueError('A target already belongs to an open engagement')
            scope=policy.policy(params.get('scope',{}),target_ids)
            if any(policy.excluded(t['address'],scope['exclusions']) for t in targets):raise ValueError('An engagement target is excluded')
            row=dict(id=identity(),schema=1,projectId=project['id'],name=policy.text(params.get('name'),'Engagement name',160),objective=policy.text(params.get('objective'),'Engagement objective'),targetIds=target_ids,status='draft',scopeRevision=1,revision=1,approval=None,created=now(),scopes=[dict(revision=1,policy=scope,created=now())])
            self.store.data['securityEngagements'].append(row)
            for target in targets:target['engagementId']=row['id']
            self.event(row,'engagement_created',dict(targetIds=target_ids));self.workspace.publish();return row
        if method=='security-engagement-snapshot':
            engagement=self.get(params.get('id'));return evidence.report(self,engagement)
        if not method.startswith(('security-engagement-','security-objective-','security-relation-','security-specialist-','security-evidence-','security-verification-','security-cleanup-')):return NotImplemented
        engagement=self.get(params.get('engagementId') or params.get('id'))
        if engagement['status'] in FINAL and method not in ('security-engagement-export','security-evidence-read','security-relation-paths','security-engagement-worker-cleanup'):
            raise ValueError('Closed engagements are immutable')
        if method=='security-engagement-scope':
            if params.get('baseRevision')!=engagement['scopeRevision']:raise ValueError('Scope revision changed; reload before editing')
            if engagement['status'] in FINAL:raise ValueError('Closed engagements are immutable')
            scope=policy.policy(params.get('scope'),engagement['targetIds'])
            await self.stop(engagement,'paused')
            engagement['scopeRevision']+=1;engagement['revision']+=1
            engagement['scopes'].append(dict(revision=engagement['scopeRevision'],policy=scope,created=now()))
            self.event(engagement,'scope_revised',dict(revision=engagement['scopeRevision']));result=engagement
        elif method=='security-engagement-approve':
            revision=engagement['scopeRevision'];scope=copy.deepcopy(self.scope(engagement));sha=evidence.digest(scope)
            if params.get('baseRevision')!=revision or engagement['status'] in FINAL:raise ValueError('Choose the current open scope revision')
            if not scope['starts']<=now()<scope['ends']:raise ValueError('Engagement testing window is not active')
            if any(policy.excluded(self.workspace.target(t)['address'],scope['exclusions']) for t in engagement['targetIds']):raise ValueError('Target is excluded by scope')
            # This boundary is always reviewed, independently of project bypass.
            approved=await self.workspace.service.ask('review',dict(name='security_engagement_scope',engagement=engagement['name'],scopeRevision=revision,scope=scope,targets=[dict(type=self.workspace.target(t)['type'],address=self.workspace.target(t)['address']) for t in engagement['targetIds']],objective=engagement['objective']))
            if not approved:raise ValueError('Engagement scope was not approved')
            if not scope['starts']<=now()<scope['ends']:raise ValueError('Testing window expired during review')
            if revision!=engagement['scopeRevision'] or sha!=evidence.digest(self.scope(engagement)) or engagement['status'] in FINAL:raise ValueError('Scope changed during review')
            engagement.update(status='running',approval=dict(id=identity(),revision=revision,digest=sha,created=now()))
            self.event(engagement,'scope_approved',engagement['approval']);result=engagement
        elif method in ('security-engagement-pause','security-engagement-stop'):
            await self.stop(engagement,'paused' if method.endswith('pause') else 'cancelled');result=engagement
        elif method=='security-engagement-close':
            if any(r.get('engagementId')==engagement['id'] and r['status'] in ACTIVE_RUNS for r in self.workspace.runs):raise ValueError('Stop active work before closing')
            objectives=[o for o in self.rows('securityObjectives',engagement) if o['status']!='superseded'];cleanup=self.rows('securityCleanup',engagement)
            for check in self.rows('securityVerifications',engagement):
                for key in ('positiveId','baselineId'):evidence.read(self,engagement,check[key])
            unknowns=[r for r in self.workspace.runs if r.get('engagementId')==engagement['id'] and r.get('effectState')=='unknown']
            reconciled=all(any(c.get('runId')==r['id'] and c['status'] in ('verified','accepted') for c in cleanup) for r in unknowns)
            complete=reconciled and bool(objectives) and all(o['status']=='completed' and o['scopeRevision']==engagement['scopeRevision'] for o in objectives) and all(c['status'] in ('verified','accepted') for c in cleanup)
            if not complete and not params.get('incomplete'):raise ValueError('Unfinished or older-scope objectives or cleanup prevent completion; explicitly close incomplete with a reason')
            reason=policy.text(params.get('reason'),'Closure rationale')
            engagement.update(status='completed' if complete else 'closed_incomplete',approval=None,closed=now(),closureReason=reason)
            self.event(engagement,'engagement_closed',dict(status=engagement['status'],reason=reason));result=engagement
        elif method=='security-objective-save':
            if engagement['status'] in FINAL:raise ValueError('Closed engagement objectives are immutable')
            target_id=params.get('targetId');self.record('securityTargets',target_id,engagement)
            parents=policy.strings(params.get('dependsOn',[]),'objective dependencies',16)
            for parent in parents:self.record('securityObjectives',parent,engagement)
            previous=self.record('securityObjectives',params['replacesId'],engagement) if params.get('replacesId') else None
            if previous and previous['id'] in parents:raise ValueError('Replacement objective cannot depend on the superseded objective')
            # Dependencies point to existing objectives; immutable edges prevent cycles.
            row=self.add('securityObjectives',engagement,targetId=target_id,title=policy.text(params.get('title'),'Objective',200),hypothesis=policy.text(params.get('hypothesis'),'Hypothesis'),successSignal=policy.text(params.get('successSignal'),'Observable success signal'),dependsOn=parents,status='pending',verificationIds=[],scopeRevision=engagement['scopeRevision'])
            if previous:
                previous.update(previousStatus=previous['status'],status='superseded',supersededBy=row['id'])
                row['replacesId']=previous['id']
            self.event(engagement,'objective_added',dict(id=row['id'],replacesId=params.get('replacesId')));result=row
        elif method=='security-objective-complete':
            row=self.record('securityObjectives',params.get('objectiveId'),engagement)
            if row['status']=='superseded':raise ValueError('A superseded objective cannot be completed again')
            verification=self.record('securityVerifications',params.get('verificationId'),engagement)
            if row['scopeRevision']!=engagement['scopeRevision'] or verification['scopeRevision']!=engagement['scopeRevision']:raise ValueError('Objective or verification belongs to an older scope; create a current objective')
            if verification['objectiveId']!=row['id'] or verification['status']!='discriminated':raise ValueError('Objective needs its own discriminating observation check')
            if any(self.record('securityObjectives',p,engagement)['status']!='completed' for p in row['dependsOn']):raise ValueError('Objective prerequisites are unfinished')
            # Re-read immutable inputs at completion, do not trust stale validation.
            for key in ('positiveId','baselineId'):evidence.read(self,engagement,verification[key])
            row.update(status='completed',verificationIds=list(dict.fromkeys(row['verificationIds']+[verification['id']])),completed=now());result=row
        elif method=='security-relation-add':
            source=params.get('fromId');destination=params.get('toId')
            self.entity(engagement,source);self.entity(engagement,destination)
            if source==destination:raise ValueError('Relationship must connect distinct entities')
            kind=params.get('kind');state=params.get('state','inferred')
            if kind not in ('runs_on','exposes','may_enable','requires','can_access','supports','contradicts') or state not in ('inferred','observed','disproved'):raise ValueError('Choose a supported relation and evidence state')
            refs=policy.strings(params.get('evidenceIds',[]),'relationship evidence',16)
            for ref in refs:evidence.read(self,engagement,ref)
            if state!='inferred' and not refs:raise ValueError('Observed/disproved relationships need retained evidence')
            result=self.add('securityRelations',engagement,fromId=source,toId=destination,kind=kind,state=state,evidenceIds=refs,rationale=policy.text(params.get('rationale'),'Relationship rationale'),scopeRevision=engagement['scopeRevision'])
        elif method=='security-relation-paths':return evidence.paths(self,engagement,params.get('fromId'),params.get('toId'))
        elif method=='security-specialist-assign':
            if self.workspace.service.active and not self.workspace.service.active.done():raise ValueError('Finish current chat or agent work before assigning a specialist')
            role=params.get('role')
            if role not in evidence.ROLES:raise ValueError('Choose a supported specialist role')
            target=self.record('securityTargets',params.get('targetId'),engagement)
            refs=policy.strings(params.get('evidenceIds',[]),'specialist evidence',16)
            if not refs:raise ValueError('Select retained evidence for the specialist')
            run_ids=[]
            for ref in refs:
                record,_=evidence.read(self,engagement,ref)
                if record['kind']!='run':raise ValueError('Specialists require retained Wixal run evidence')
                source=self.record('securityRuns',record['source'],engagement)
                if source['targetId']!=target['id']:raise ValueError('Specialist evidence belongs to another target')
                run_ids.append(source['id'])
            question=policy.text(params.get('question'),'Specialist question')
            run=await self.workspace.prepare_run(dict(targetId=target['id'],capability='analysis',stage='Research',name=role.replace('_',' ').title(),model=params.get('model',''),prompt=evidence.ROLES[role]+'\nQuestion: '+question,evidenceIds=run_ids))
            self.workspace.commit_run(run)
            assignment=self.add('securityAssignments',engagement,role=role,question=question,evidenceIds=refs,runId=run['id'],status='queued',scopeRevision=engagement['scopeRevision'],authority='Retained target evidence only; no tool execution, network, credentials or parent private context')
            run['assignmentId']=assignment['id'];result=assignment
        elif method=='security-evidence-read':
            row,value=evidence.read(self,engagement,params.get('evidenceId'));encoded=json.dumps(value,ensure_ascii=False,indent=2)
            offset=params.get('offset',0)
            if type(offset) is not int or not 0<=offset<=len(encoded):raise ValueError('Invalid evidence offset')
            return dict(evidence=row,content=encoded[offset:offset+12000],nextOffset=min(len(encoded),offset+12000),more=offset+12000<len(encoded))
        elif method=='security-evidence-import':
            # Import inert JSON only; no external controller calls or archive extraction.
            import_path=policy.text(params.get('path'),'Import path',1000)
            from pathlib import PurePath
            if PurePath(import_path).is_absolute() or '..' in PurePath(import_path).parts:raise ValueError('Import path must remain inside the project')
            source=safe_path(self.store.project()['root'],import_path)
            if not source.is_file() or source.stat().st_size>4*1024*1024:raise ValueError('Select an engagement JSON artifact below 4 MB')
            value=json.loads(source.read_text())
            if not isinstance(value,dict):raise ValueError('Imported artifact must be an object')
            result=evidence.retain(self,engagement,value,'external-untrusted',str(source.relative_to(self.store.project()['root'])))
            self.event(engagement,'external_artifact_imported',dict(evidenceId=result['id'],sha256=result['sha256']))
        elif method=='security-verification-add':
            objective=self.record('securityObjectives',params.get('objectiveId'),engagement)
            check=evidence.discriminate(self,engagement,params)
            positive,_=evidence.read(self,engagement,params['positiveId']);run=self.record('securityRuns',positive['source'],engagement)
            if run['targetId']!=objective['targetId']:raise ValueError('Verification belongs to another objective target')
            if run['scopeRevision']!=engagement['scopeRevision']:raise ValueError('Verification requires current scope evidence')
            result=self.add('securityVerifications',engagement,objectiveId=objective['id'],scopeRevision=engagement['scopeRevision'],**check)
            self.event(engagement,'observation_evaluated',dict(id=result['id'],status=result['status']))
        elif method=='security-engagement-worker-cleanup':
            run=self.record('securityRuns',params.get('runId'),engagement)
            if run['status'] in ACTIVE_RUNS:raise ValueError('Stop owned operation before environment cleanup')
            if not await self.workspace.service.ask('review',dict(name='security_worker_cleanup',runId=run['id'],container=run.get('workerContainer'),network=run.get('workerNetwork'))):raise ValueError('Worker cleanup was not approved')
            result=await self.worker.cleanup(run);run['workerCleanup']=result
            self.event(engagement,'worker_cleanup',dict(runId=run['id'],receipt=result))
        elif method=='security-engagement-score':
            from .security_cvss import score_vector
            return score_vector(params.get('vector'))
        elif method=='security-engagement-finding':
            from .security_cvss import score_vector
            row=self.record('securityFindings',params.get('findingId'),engagement)
            score=score_vector(params.get('vector'))
            rationale=policy.text(params.get('rationale'),'Severity rationale')
            row.update(cvssVector=score['normalized_vector'],cvssScore=score['base_score'],cvssVersion='3.1',severity=score['base_severity'].lower(),severityRationale=rationale,verificationState='unverified',needsReview=True)
            self.event(engagement,'finding_scored',dict(id=row['id'],vector=score['normalized_vector'],score=score['base_score']));result=row
        elif method=='security-cleanup-add':
            run_id=params.get('runId','')
            if run_id:self.record('securityRuns',run_id,engagement)
            result=self.add('securityCleanup',engagement,runId=run_id,title=policy.text(params.get('title'),'Cleanup item',200),description=policy.text(params.get('description'),'Cleanup requirement'),status='pending',evidenceIds=[],scopeRevision=engagement['scopeRevision'])
        elif method=='security-cleanup-update':
            row=self.record('securityCleanup',params.get('cleanupId'),engagement);state=params.get('status')
            if state not in ('pending','accepted','verified'):raise ValueError('Choose a cleanup disposition')
            refs=policy.strings(params.get('evidenceIds',[]),'cleanup evidence',16)
            for ref in refs:
                item,_=evidence.read(self,engagement,ref)
                if state=='verified' and item['kind']!='run':raise ValueError('Cleanup verification requires collected run evidence')
            if state=='verified' and not refs:raise ValueError('Cleanup verification needs retained evidence')
            rationale=policy.text(params.get('rationale'),'Cleanup rationale')
            revision=engagement['scopeRevision']
            approved=await self.workspace.service.ask('review',dict(name='security_cleanup_disposition',engagement=engagement['name'],item=row['title'],status=state,rationale=rationale,evidenceIds=refs))
            if not approved:raise ValueError('Cleanup disposition was not approved')
            if engagement['scopeRevision']!=revision or engagement['status'] in FINAL:raise ValueError('Engagement changed during cleanup review')
            for ref in refs:evidence.read(self,engagement,ref)
            row.update(status=state,evidenceIds=refs,rationale=rationale,reviewed=now(),reviewMethod='operator_evidence_review' if state=='verified' else 'operator_disposition');self.event(engagement,'cleanup_reviewed',dict(id=row['id'],status=state));result=row
        elif method=='security-engagement-export':
            report=evidence.report(self,engagement)
            prefix='engagement-'+engagement['id']+'-'+identity()[:8];root=self.store.project()['root']
            json_path=safe_path(root,prefix+'.json',True);md_path=safe_path(root,prefix+'.md',True)
            lines=['# '+engagement['name'],'',engagement['objective'],'','Status: '+engagement['status'],'','Scope revision: '+str(engagement['scopeRevision']),'','Execution, verification, finding review and cleanup are separate.','', '## Approved scope history','',json.dumps(engagement['scopes'],indent=2),'','## Objectives']
            for row in report['securityObjectives']:lines+=['', '### '+row['title'],'',row['hypothesis'],'','Expected observation: '+row['successSignal'],'','Status: '+row['status']]
            for key in ('findings','securityVerifications','securityCleanup','securityEvidence','securityRelations'):
                lines+=['','## '+key,'',json.dumps(report[key],indent=2)]
            # Exclusive names; exports never overwrite source evidence.
            with json_path.open('x') as f:json.dump(report,f,indent=2)
            with md_path.open('x') as f:f.write('\n'.join(lines)+'\n')
            self.event(engagement,'report_exported',dict(paths=[str(json_path),str(md_path)]));result=dict(paths=[str(json_path),str(md_path)])
        else:raise ValueError('Unknown engagement action')
        self.workspace.publish()
        if method=='security-specialist-assign':self.workspace.pump()
        return result
