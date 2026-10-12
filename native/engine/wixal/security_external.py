"""Operator-reviewed controller proposals and inert vendor sensor imports."""
import ipaddress
import json
from datetime import datetime
from urllib.parse import urlsplit
from . import engagement_evidence as evidence
from . import engagement_policy as policy
from .tools import safe_path


def project_artifact(manager,path):
    source=safe_path(manager.store.project()['root'],path)
    if not source.is_file() or source.stat().st_size>4*1024*1024:raise ValueError('Choose a project artifact below 4 MB')
    return source.read_text()


def vendor_events(text,vendor,run,starts,ends):
    if vendor not in ('suricata_eve','zeek_json'):raise ValueError('Choose Suricata EVE or Zeek JSON lines')
    if type(starts) is not int or type(ends) is not int or starts>=ends:raise ValueError('Declare sensor coverage start and end')
    parsed=urlsplit(run['address'] if '://' in run['address'] else '//'+run['address'])
    try:host=str(ipaddress.ip_address(parsed.hostname))
    except ValueError:raise ValueError('Vendor correlation currently requires an exact IP target; hostname/IP attribution is not inferred')
    port=parsed.port or (443 if parsed.scheme=='https' else 80)
    lines=[line for line in text.splitlines() if line.strip() and not line.startswith('#')]
    if len(lines)>10000:raise ValueError('Sensor import exceeds 10,000 records')
    events=[]
    for line in lines:
        row=json.loads(line)
        if not isinstance(row,dict):raise ValueError('Each sensor record must be a JSON object')
        if vendor=='suricata_eve':
            stamp=row.get('timestamp');address=row.get('dest_ip');destination=row.get('dest_port');kind=row.get('event_type')
            if not isinstance(stamp,str):raise ValueError('Suricata timestamp is required')
            instant=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if instant.tzinfo is None:raise ValueError('Suricata timestamp requires a timezone')
            time=int(instant.timestamp()*1000)
            kind={'http':'http_request','alert':'alert','flow':'network_connection'}.get(kind)
        else:
            stamp=row.get('ts');address=row.get('id.resp_h');destination=row.get('id.resp_p')
            if type(stamp) not in (int,float):raise ValueError('Zeek numeric ts is required')
            time=int(stamp*1000);kind='network_connection'
        if kind and address==host and destination==port and starts<=time<=ends and run.get('started',0)<=time<=run.get('finished',0):
            events.append(dict(time=time,runId=run['id'],type=kind,source=vendor,destination=address,port=destination))
    if len(events)>1000:raise ValueError('Matched sensor events exceed 1,000 records')
    return events


async def dispatch(assurance,method,params):
    if method not in ('security-controller-plan-import','security-controller-plan-run','security-vendor-telemetry-import'):return NotImplemented
    manager=assurance.manager;engagement=manager.get(params.get('engagementId'))
    if engagement['status'] in ('completed','closed_incomplete','cancelled'):raise ValueError('Closed engagements are immutable')
    if method=='security-controller-plan-import':
        text=project_artifact(manager,params.get('path'));value=json.loads(text)
        if not isinstance(value,dict) or set(value)!={'name','targetId','nodes'}:raise ValueError('Controller proposal requires name, targetId and typed nodes only')
        target=manager.record('securityTargets',value['targetId'],engagement)
        nodes=manager.workspace.validate_plan(target,value['nodes'])
        if any(n['capability'] not in manager.scope(engagement)['capabilities'] for n in nodes):raise ValueError('Controller proposal exceeds current scope')
        retained=evidence.retain(manager,engagement,value,'external-controller-proposal',params['path'])
        plan=await manager.workspace.dispatch('security-plan-save',value)
        plan.update(controllerEvidenceId=retained['id'],controllerScopeRevision=engagement['scopeRevision'],controllerEngagementId=engagement['id'])
        manager.workspace.publish();return plan
    if method=='security-controller-plan-run':
        plan=manager.workspace.record('securityPlans',params.get('planId'))
        if plan.get('controllerEngagementId')!=engagement['id'] or plan.get('controllerScopeRevision')!=engagement['scopeRevision']:raise ValueError('Controller proposal belongs to another engagement or older scope')
        _,original=evidence.read(manager,engagement,plan['controllerEvidenceId'])
        if plan['targetId']!=original['targetId']:raise ValueError('Controller proposal target changed; import and review it again')
        manager.record('securityTargets',plan['targetId'],engagement)
        if plan['nodes']!=manager.workspace.validate_plan(manager.workspace.target(plan['targetId']),original['nodes']):raise ValueError('Controller proposal changed; import and review it again')
        revision=engagement['scopeRevision'];digest=evidence.digest(plan)
        if not await manager.workspace.service.ask('review',dict(name='security_controller_plan',nameOfPlan=plan['name'],scopeRevision=revision,nodes=plan['nodes'],authority='Typed operations through the existing queue only')):raise ValueError('Controller proposal was not approved')
        if revision!=engagement['scopeRevision'] or digest!=evidence.digest(plan):raise ValueError('Controller proposal or scope changed during review')
        return await manager.workspace.dispatch('security-plan-run',dict(id=plan['id'],model=params.get('model','')))
    run=manager.record('securityRuns',params.get('runId'),engagement)
    if run['status']!='completed' or run.get('scopeRevision')!=engagement['scopeRevision']:raise ValueError('Select a completed current-scope operation')
    text=project_artifact(manager,params.get('path'));vendor=params.get('vendor');starts=params.get('starts');ends=params.get('ends')
    events=vendor_events(text,vendor,run,starts,ends)
    raw=evidence.retain(manager,engagement,dict(vendor=vendor,content=text),'external-vendor-log',params['path'])
    value=dict(sensor=vendor,starts=starts,ends=ends,events=events,rawEvidenceId=raw['id'],attribution='Operator-selected run with exact IP/port and event-time match; external assertions remain unverified')
    retained=evidence.retain(manager,engagement,value,'external-telemetry',params['path'])
    row=manager.add('securityTelemetry',engagement,evidenceId=retained['id'],rawEvidenceId=raw['id'],sensor=vendor,starts=starts,ends=ends,scopeRevision=engagement['scopeRevision'])
    manager.workspace.publish();return row
