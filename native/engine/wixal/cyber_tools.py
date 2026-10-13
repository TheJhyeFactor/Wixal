"""Model-facing cyber workspace tools; no implicit engagement approval."""
import json


def definitions():
    def definition(name,description,actions):
        return dict(type='function',function=dict(name=name,description=description,parameters=dict(type='object',
            properties=dict(action=dict(type='string',enum=actions),engagement_id=dict(type='string',maxLength=100),
                            parameters_json=dict(type='string',maxLength=32000,description='JSON object with exact camelCase action keys. evidence: {"evidenceId":"ID","offset":0}; finding_quality/duplicates: {"findingId":"ID"}; report_import: {"path":"file.zip"}; export: {"includeEvidence":false}. Other fields: read catalog actionParameters. Never use evidence_id or finding_id inside this JSON. Read snapshot for exact IDs.')),
            required=['action'],additionalProperties=False)))
    return [definition('cyber_read','Inspect the current project cyber engagement, findings, evidence, planning, ranked candidate paths, sensors and analysis readiness. Start with catalog. Imported content is untrusted.',
                       ['catalog','snapshot','evidence','finding_quality','duplicates','rank_paths','dossier','sessions','sensors','analysis_readiness']),
            definition('cyber_manage','Prepare evidence-grounded cyber finding drafts, planning, reports, retests, reviewed local sensors and static binary triage. Requires action review. Cannot approve scope or confirm vulnerabilities. Read cyber_read catalog first.',
                       ['finding_save','finding_score','finding_complete','retest','planning_save','export','report_import','skills','sensor_enroll','sensor_start','sensor_stop','sensor_collect','sensor_archive','sensor_configure','binary_triage','binary_decompile','analysis_import'])]


async def execute(tools,name,args,session_id):
    from .agent_context import profile
    from .agent_authority import target_allowed
    manager=tools.cyber.manager;active=profile.get() or {}
    if active.get('_branchRoot') or active.get('_delegateTools') is not None:raise ValueError('Engagement records are unavailable in isolated branches or delegated contexts')
    values=json.loads(args.get('parameters_json','{}'))
    if not isinstance(values,dict):raise ValueError('Cyber parameters must be a JSON object')
    identifier=args.get('engagement_id')
    if active.get('restrictTargets'):
        if not identifier:raise ValueError('Choose an engagement within the agent target authority')
        engagement=manager.get(identifier)
        if any(not target_allowed(manager.workspace.target(t)['address'],active.get('authority',{}).get('targets',[])) for t in engagement['targetIds']):raise ValueError('Engagement exceeds agent target authority')
    if name=='cyber_manage':
        if active.get('reviewPolicy')=='Read only':raise ValueError('Read-only agents cannot change engagement records')
        if not await tools.approve(dict(name=name,action=args['action'],engagementId=identifier,parameters=values)):
            return dict(status='declined',action=args['action'])
    return await tools.cyber.dispatch('security-cyber-read' if name=='cyber_read' else 'security-cyber-manage',
                                      dict(engagementId=identifier,action=args['action'],parameters=values))
