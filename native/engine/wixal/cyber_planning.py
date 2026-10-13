"""Native engagement planning and evidence-aware candidate prioritisation."""
import copy
from . import engagement_evidence as evidence
from .engagement_policy import text
from .storage import now

PLAN_FIELDS = ('threatProfile','acceptanceCriteria','deconfliction','contacts','dataHandling',
               'abortConditions','deliverables','retention','retestCriteria')


def save(manager,engagement,params):
    if set(params)-{'baseRevision',*PLAN_FIELDS}:raise ValueError('Unknown planning fields')
    old = engagement.get('planning',dict(revision=0))
    if params.get('baseRevision') != old['revision']:raise ValueError('Planning revision changed; reload before editing')
    plan = {key:text(params.get(key),key) for key in PLAN_FIELDS}
    plan.update(revision=old['revision']+1,scopeRevision=engagement['scopeRevision'],updated=now(),
                authority='Planning content cannot approve scope, grant tools or schedule execution.')
    engagement.setdefault('planningHistory',[]).append(copy.deepcopy(old))
    engagement['planning'] = plan
    manager.event(engagement,'planning_saved',dict(revision=plan['revision']))
    return plan


def dossier(manager,engagement):
    scope = manager.scope(engagement);plan = engagement.get('planning',{})
    missing = [key for key in PLAN_FIELDS if not plan.get(key)]
    objectives = manager.rows('securityObjectives',engagement)
    consistency=[]
    for key in ('contacts','dataHandling','abortConditions','threatProfile'):
        if plan.get(key) and scope.get(key) and plan[key].strip()!=scope[key].strip():
            consistency.append(dict(field=key,status='differs_from_approved_scope',message='Planning differs from scope; update and review scope before relying on the new value.'))
    for objective in objectives:
        if objective.get('scopeRevision')!=engagement['scopeRevision']:
            consistency.append(dict(objectiveId=objective['id'],status='stale_objective'))
        elif not objective.get('successSignal'):
            consistency.append(dict(objectiveId=objective['id'],status='missing_observable_success_signal'))
    return dict(engagementId=engagement['id'],scopeRevision=engagement['scopeRevision'],
                objective=engagement['objective'],scope=copy.deepcopy(scope),planning=copy.deepcopy(plan),
                objectives=copy.deepcopy(objectives),missingFields=missing,consistencyChecks=consistency,
                executionReady=engagement['status']=='running' and bool(engagement.get('approval')) and not consistency and not missing,
                stale=bool(plan) and plan.get('scopeRevision')!=engagement['scopeRevision'],
                questions=[dict(field=key,question={
                    'acceptanceCriteria':'What exact observation would establish each objective?',
                    'deconfliction':'Who must be notified and how will test activity be distinguished from an incident?',
                    'retention':'Which evidence may be retained, for how long and by whom?',
                    'retestCriteria':'Which original checks and legitimate functions must be retested?'
                }.get(key,'Describe '+key)) for key in missing],
                limitation='A complete dossier is not scope approval or evidence that an objective was achieved.')


def ranked_paths(manager,engagement,params):
    result = evidence.paths(manager,engagement,params.get('fromId'),params.get('toId'))
    for path in result['paths']:
        edges = [manager.record('securityRelations',ref,engagement) for ref in path['edgeIds']]
        assumptions = sum(e['state']=='inferred' for e in edges)
        stale=sum(e.get('scopeRevision')!=engagement['scopeRevision'] for e in edges)
        contradicted=sum(e['state']=='disproved' for e in edges)
        # Transparent ranking favors fewer unobserved assumptions, then shorter paths.
        # It never uses model-provided probability or grants execution authority.
        path.update(priorityScore=max(0,100-20*assumptions-5*len(edges)-40*stale-100*contradicted),unresolvedAssumptions=assumptions,
                    staleRelationships=stale,contradictedRelationships=contradicted,
                    readiness='blocked' if stale or contradicted else 'needs_evidence' if assumptions else 'observed_relationships_only',
                    informationGainChecks=assumptions,estimatedEffort='unknown; operator must estimate capability-specific effort',
                    rationale=f'{assumptions} inferred relationships; {len(edges)} prerequisite steps',
                    nextChecks=[dict(relationId=e['id'],question='Independently test: '+e['rationale'],
                                     evidenceIds=e['evidenceIds'],requires='Current approved scope and a supported typed capability',
                                     stopCondition='Missing authority, unavailable capability or contradictory evidence') for e in edges if e['state']=='inferred'])
    result['paths'].sort(key=lambda p:(-p['priorityScore'],p['hops']))
    result['rankingPolicy'] = 'Fewer inferred relationships and shorter paths first; candidate ordering, not exploit probability.'
    return result


def sessions(manager,engagement):
    rows = []
    for run in manager.workspace.runs:
        if run.get('engagementId')!=engagement['id'] or run.get('projectId')!=engagement['projectId']:continue
        rows.append(dict(runId=run['id'],name=run.get('name',''),status=run['status'],effectState=run.get('effectState','unknown'),
                         environment=run.get('environment'),started=run.get('started'),finished=run.get('finished'),
                         evidenceId=run.get('retainedEvidenceId'),cleanup=run.get('workerCleanup'),
                         recovery='Inspect retained evidence and reconcile unknown effects before preparing a new run' if run.get('effectState')=='unknown' else 'Use the existing operation controller'))
    return dict(sessions=rows[-100:],limitation='Operation sessions use the existing controller. No shell replay or automatic resume is performed.')
