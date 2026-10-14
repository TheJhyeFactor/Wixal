"""Inspect configuration against current local facts; never infer model qualification."""
from pathlib import Path
from .agent_context import profile, available_names
from .skill_resources import visible


async def inspect(service, identifier):
    agent=service.agents.find('agentProfiles',identifier)
    model=next((m for m in await service.runtime.catalog() if m['name']==agent['model']),None)
    project_id=agent.get('projectId') if agent.get('projectScope')=='Current project only' else service.store.data.get('activeProject')
    project=next((p for p in service.store.data['projects'] if p['id']==project_id),None)
    missing=[name for name in agent.get('skills',[]) if name not in {s['name'] for s in visible(service.store)}]
    checks=[dict(name='Agent',status='blocked' if agent.get('archived') else 'configured',detail='Archived' if agent.get('archived') else agent['name']),
            dict(name='Model',status='configured' if model and 'tools' in model.get('capabilities',[]) else 'blocked',detail='Installed · tool calling advertised' if model and 'tools' in model.get('capabilities',[]) else 'Select an installed model with tool support'),
            dict(name='Project',status='configured' if project and not project.get('syncRootRequired') and Path(project['root']).is_dir() else 'attention',detail=project['name'] if project and not project.get('syncRootRequired') and Path(project['root']).is_dir() else 'Choose an available project for project tools'),
            dict(name='Skills',status='blocked' if missing else 'configured',detail='Missing: '+', '.join(missing) if missing else f"{len(agent.get('skills',[]))} selected"),
            dict(name='Actions',status='configured',detail=agent['reviewPolicy']),
            dict(name='Verification',status='configured' if agent.get('successCriteria') else 'attention',detail=f"{len(agent.get('successCriteria',[]))} outcome checks" if agent.get('successCriteria') else 'No default checks · finished work remains unverified'),
            dict(name='Model reliability',status='untested',detail='Configuration checks do not qualify this model for arbitrary tasks')]
    token=profile.set(agent)
    try:names=available_names(service.tools,service.store)
    finally:profile.reset(token)
    return dict(agentId=agent['id'],checks=checks,tools=names,toolGroups=agent.get('toolGroups'),model=agent['model'],qualification='untested',ready=not any(c['status']=='blocked' for c in checks))
