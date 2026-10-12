"""Scoped identity leases, read-only API observations and deterministic contracts."""
import asyncio
import copy
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit
from .account import Keychain
from .storage import identity, now
from . import engagement_evidence as evidence
from . import engagement_policy as policy

COLLECTIONS=('securityCredentials','securityValidationContracts','securityTelemetry')
VALIDATORS=('api_access_boundary','network_port_state','website_header_value')


def api_plan(args):
    if not isinstance(args,dict) or set(args)-{'paths','credentialId'}:raise ValueError('API observations accept paths and a credential reference only')
    paths=args.get('paths',['/'])
    if not isinstance(paths,list) or not 1<=len(paths)<=6 or any(not isinstance(p,str) or len(p)>300 or not p.startswith('/') or p.startswith('//') or re.search(r'[\\?#\r\n ]',p) or '..' in p.split('/') for p in paths):raise ValueError('Choose 1–6 same-origin paths without queries, credentials or traversal')
    ref=args.get('credentialId','')
    if not isinstance(ref,str) or len(ref)>100:raise ValueError('Invalid credential reference')
    return dict(paths=list(dict.fromkeys(paths)),credentialId=ref)


class Assurance:
    def __init__(self,manager):
        self.manager=manager;self.store=manager.store
        for key in COLLECTIONS:self.store.data.setdefault(key,[])

    def vault(self,identifier):
        value=Keychain(self.store.directory/'security-credentials'/identifier);value.account=b'engagement-token';return value

    def credential(self,engagement,identifier,target_id):
        row=self.manager.record('securityCredentials',identifier,engagement)
        if row.get('revoked') or row['expires']<=now() or row['scopeRevision']!=engagement['scopeRevision'] or row['targetId']!=target_id:raise ValueError('Identity lease is revoked, expired or outside the current target/scope')
        return row

    async def observe_api(self,run,approve):
        manager=self.manager;engagement=manager.get(run['engagementId']);plan=api_plan(run['arguments'])
        row=self.credential(engagement,plan['credentialId'],run['targetId']) if plan['credentialId'] else None
        if row and urlsplit(run['address']).scheme!='https':
            import ipaddress
            try:loopback=ipaddress.ip_address(urlsplit(run['address']).hostname).is_loopback
            except ValueError:loopback=False
            if not loopback:raise ValueError('Bearer-token observations require HTTPS, except for an explicit loopback lab')
        intent=dict(name='security_api_observe',target=run['address'],paths=plan['paths'],method='GET',identity=dict(id=row['id'],label=row['label'],expires=row['expires']) if row else 'anonymous',scopeRevision=run['scopeRevision'])
        # Credential use is always reviewed, including in project bypass mode.
        allowed=await manager.workspace.service.ask('review',intent) if row else await approve(intent)
        if not allowed:raise ValueError('API observations were not approved')
        manager.authorize_run(run)
        secret=''
        if row:
            self.credential(engagement,row['id'],run['targetId'])
            value=await asyncio.to_thread(self.vault(row.get('vaultId',row['id'])).get)
            if not isinstance(value,dict) or not isinstance(value.get('token'),str):raise ValueError('Identity token is unavailable in Keychain')
            secret=value['token']
        from .website import bounded_request,origin
        results=[]
        try:
            for path in plan['paths']:
                manager.authorize_run(run)
                if row:self.credential(engagement,row['id'],run['targetId'])
                url=urljoin(run['address'],path)
                if origin(url)!=origin(run['address']):raise ValueError('API path is outside the approved origin')
                response=await bounded_request(url,headers={'Authorization':'Bearer '+secret} if secret else {},limit=64*1024)
                manager.authorize_run(run)
                if row:self.credential(engagement,row['id'],run['targetId'])
                # Keep the transport digest. Retain structured values, not a raw
                # body that could contain alternate JSON encodings of the token.
                try:body=json.loads(response.pop('body'))
                except (ValueError,TypeError):body=None
                def scrub(value):
                    if isinstance(value,str):
                        from urllib.parse import quote
                        return value.replace(secret,'[REDACTED]').replace(quote(secret,safe=''),'[REDACTED]') if secret else value
                    if isinstance(value,dict):return {scrub(k):scrub(v) for k,v in value.items()}
                    if isinstance(value,list):return [scrub(v) for v in value]
                    return value
                response=scrub(response);response['json']=scrub(body)
                response['path']=path;results.append(response)
                await asyncio.sleep(.1)
        finally:secret=''
        return dict(profile='readonly_get',requests=results,identityId=row['id'] if row else 'anonymous',identityLabel=row['label'] if row else 'Anonymous',credentialLeaseRevision=row['scopeRevision'] if row else None,limitations=['GET observations only; no redirects, cookie sessions or mutations. HTTP success alone does not establish authorization correctness.'])

    def validate(self,engagement,params):
        contract=self.manager.record('securityValidationContracts',params.get('contractId'),engagement)
        if contract['scopeRevision']!=engagement['scopeRevision']:raise ValueError('Validation contract belongs to an older scope')
        refs=policy.strings(params.get('evidenceIds',[]),'validator evidence',2)
        if len(refs)!=2 or refs[0]==refs[1]:raise ValueError('Select two distinct positive/control evidence records')
        rows=[];values=[];runs=[]
        for ref in refs:
            row,value=evidence.read(self.manager,engagement,ref)
            if row['kind']!='run':raise ValueError('Validators require collected run evidence')
            run=self.manager.record('securityRuns',row['source'],engagement)
            if run['status']!='completed' or run['targetId']!=contract['targetId'] or run.get('scopeRevision')!=engagement['scopeRevision']:raise ValueError('Validator inputs require completed current-scope target runs')
            rows.append(row);values.append(value['result']);runs.append(run)
        if runs[0]['id']==runs[1]['id'] or runs[0]['capability']!=runs[1]['capability'] or runs[0].get('environment')!=runs[1].get('environment'):raise ValueError('Validator inputs have incompatible collection identities')
        validator=contract['validator'];config=contract['config'];details={};passed=False
        if validator=='api_access_boundary':
            if runs[0]['capability']!='api_observe' or runs[0]['arguments'].get('paths')!=runs[1]['arguments'].get('paths'):raise ValueError('Access validation requires identical read-only request paths')
            if values[0]['identityId']==values[1]['identityId'] or values[0]['identityId']!=config['allowedIdentityId'] or values[1]['identityId']!=config['deniedIdentityId']:raise ValueError('Access validation requires the declared distinct identities')
            observations=[next((r for r in v['requests'] if r['path']==config['path']),None) for v in values]
            if not all(observations) or any(o['truncated'] for o in observations):raise ValueError('Access validation requires complete bounded response bodies')
            try:signal=evidence.value_at(observations[0]['json'],config['pointer'])
            except (KeyError,TypeError,IndexError,ValueError):signal=None
            try:control=evidence.value_at(observations[1]['json'],config['pointer'])
            except (KeyError,TypeError,IndexError,ValueError):control=None
            passed=observations[0]['status']==200 and observations[1]['status'] in (401,403) and type(signal)==type(config['expected']) and signal==config['expected'] and not (type(control)==type(signal) and control==signal)
            details=dict(allowedStatus=observations[0]['status'],deniedStatus=observations[1]['status'],signal=signal,control=control)
        elif validator=='network_port_state':
            if runs[0]['capability'] not in ('network_scan','linux_network_scan') or runs[0]['arguments'].get('profile')!=runs[1]['arguments'].get('profile'):raise ValueError('Port validation requires comparable network profiles')
            observations=[[s for s in v.get('services',[]) if str(s.get('port'))==str(config['port']) and s.get('host')==config['host']] for v in values]
            passed=all(len(o)==1 for o in observations) and observations[0][0]['state']==config['positiveState'] and observations[1][0]['state']==config['baselineState']
            details=dict(observations=observations)
        else:
            if runs[0]['capability']!='api_observe' or runs[0]['arguments']!=runs[1]['arguments']:raise ValueError('Header validation requires identical API observations')
            observations=[next((r for r in v['requests'] if r['path']==config['path']),None) for v in values]
            if not all(observations):raise ValueError('Header observation is unavailable')
            positive=observations[0]['headers'].get(config['header']);baseline=observations[1]['headers'].get(config['header'])
            passed=positive==config['expected'] and baseline!=positive;details=dict(positive=positive,baseline=baseline)
        return self.manager.add('securityVerifications',engagement,objectiveId=contract['objectiveId'],contractId=contract['id'],validator=validator,status='validated' if passed else 'inconclusive',scopeRevision=engagement['scopeRevision'],positiveId=refs[0],baselineId=refs[1],positiveSha256=rows[0]['sha256'],baselineSha256=rows[1]['sha256'],details=details,limitation='Validates only the declared access boundary, port state or response-header observation; no broader compromise claim.')

    async def dispatch(self,method,params):
        if method not in ('security-credential-save','security-credential-revoke','security-contract-validator-save','security-contract-validator-run','security-engagement-worker-reconcile','security-telemetry-import','security-telemetry-correlate','security-specialist-operate','security-engagement-structured-import'):return NotImplemented
        manager=self.manager;engagement=manager.get(params.get('engagementId'))
        if engagement['status'] in ('completed','closed_incomplete','cancelled'):raise ValueError('Closed engagements are immutable')
        revision=engagement['scopeRevision']
        if method=='security-credential-save':
            manager.record('securityTargets',params.get('targetId'),engagement)
            label=policy.text(params.get('label'),'Identity label',100);secret=params.get('secret');duration=params.get('seconds',3600)
            if not isinstance(secret,str) or not 8<=len(secret)<=4096 or not re.fullmatch(r'[A-Za-z0-9._~+/-]+=*',secret) or type(duration) is not int or not 60<=duration<=86400:raise ValueError('Provide a bounded bearer token and a 60–86,400 second lease')
            identifier=identity();intent=dict(name='security_credential_lease',label=label,targetId=params['targetId'],scopeRevision=revision,seconds=duration,storage='macOS Keychain; reference only in engagement records')
            if not await manager.workspace.service.ask('review',intent):raise ValueError('Identity lease was not approved')
            if revision!=engagement['scopeRevision'] or engagement['status'] in ('completed','closed_incomplete','cancelled'):raise ValueError('Scope changed during identity review')
            await asyncio.to_thread(self.vault(identifier).set,dict(token=secret));secret=''
            if revision!=engagement['scopeRevision'] or engagement['status'] in ('completed','closed_incomplete','cancelled') or self.store.data.get('activeProject')!=engagement['projectId']:
                await asyncio.to_thread(self.vault(identifier).set,None)
                raise ValueError('Scope or project changed while saving the identity lease')
            result=manager.add('securityCredentials',engagement,targetId=params['targetId'],label=label,expires=min(now()+duration*1000,manager.scope(engagement)['ends']),scopeRevision=revision,revoked=False)
            # The vault key is the record identity, never the label or user input.
            result['vaultId']=identifier
        elif method=='security-credential-revoke':
            result=manager.record('securityCredentials',params.get('credentialId'),engagement)
            result['revoked']=True
            await asyncio.to_thread(self.vault(result.get('vaultId',result['id'])).set,None)
        elif method=='security-contract-validator-save':
            objective=manager.record('securityObjectives',params.get('objectiveId'),engagement)
            if objective['scopeRevision']!=revision:raise ValueError('Choose a current objective')
            validator=params.get('validator');config=copy.deepcopy(params.get('config'))
            if validator not in VALIDATORS or not isinstance(config,dict):raise ValueError('Choose a supported validation contract')
            if validator=='api_access_boundary':
                if set(config)!={'path','pointer','expected','allowedIdentityId','deniedIdentityId'}:raise ValueError('Access contract requires path, signal and allowed/denied identities')
                api_plan(dict(paths=[config['path']]))
                if config['allowedIdentityId']==config['deniedIdentityId']:raise ValueError('Choose distinct test identities')
                for key in ('allowedIdentityId','deniedIdentityId'):
                    if config[key]!='anonymous':self.credential(engagement,config[key],objective['targetId'])
                if not isinstance(config['pointer'],str) or not config['pointer'].startswith('/') or len(config['pointer'])>1000 or type(config['expected']) not in (str,int,bool) or len(str(config['expected']))>1000:raise ValueError('Choose a bounded explicit JSON signal')
            elif validator=='network_port_state':
                if set(config)!={'host','port','positiveState','baselineState'} or type(config['port']) is not int or not 1<=config['port']<=65535 or config['positiveState'] not in ('open','closed','filtered') or config['baselineState'] not in ('open','closed','filtered') or config['positiveState']==config['baselineState']:raise ValueError('Choose a host, port and distinct observed states')
                policy.text(config['host'],'Observed host',250)
            else:
                from .website import HEADER_NAMES
                if set(config)!={'path','header','expected'} or config['header'] not in HEADER_NAMES:raise ValueError('Choose an allowed response header')
                api_plan(dict(paths=[config['path']]));policy.text(config['expected'],'Expected header value',1000)
            result=manager.add('securityValidationContracts',engagement,targetId=objective['targetId'],objectiveId=objective['id'],validator=validator,config=config,scopeRevision=revision)
        elif method=='security-contract-validator-run':result=self.validate(engagement,params)
        elif method=='security-engagement-worker-reconcile':
            run=manager.record('securityRuns',params.get('runId'),engagement)
            if run['status'] in ('queued','running','waiting_review','waiting_model','blocked'):raise ValueError('Stop active work before reconciliation')
            result=await manager.worker.reconcile(run)
            run['workerReconciliation']=result
        elif method=='security-specialist-operate':
            role=params.get('role');capability=params.get('capability')
            allowed={'recon_operator':('api_observe','website_assess','network_scan','linux_network_scan'),'inventory_operator':('software_inventory',)}
            if capability not in allowed.get(role,()):raise ValueError('Choose an operator role and its bounded supported capability')
            target=manager.record('securityTargets',params.get('targetId'),engagement)
            question=policy.text(params.get('question'),'Operation purpose',1000)
            run=await manager.workspace.prepare_run(dict(targetId=target['id'],capability=capability,arguments=params.get('arguments',{}),stage='Recon',name=role.replace('_',' ').title(),prompt=question,objectiveId=params.get('objectiveId')))
            if run.get('engagementId')!=engagement['id']:raise ValueError('Operator target is outside the engagement')
            manager.workspace.commit_run(run)
            result=manager.add('securityAssignments',engagement,role=role,question=question,evidenceIds=[],runId=run['id'],status='queued',scopeRevision=revision,authority='One exact reviewed typed operation; no arbitrary tools, commands or credential values')
            run['assignmentId']=result['id']
        elif method in ('security-telemetry-import','security-engagement-structured-import'):
            from pathlib import PurePath
            path=params.get('path','')
            if not isinstance(path,str) or PurePath(path).is_absolute() or '..' in PurePath(path).parts:raise ValueError('Choose a JSON file inside the project')
            from .tools import safe_path
            source=safe_path(self.store.project()['root'],path)
            if not source.is_file() or source.stat().st_size>4*1024*1024:raise ValueError('Choose a JSON artifact below 4 MB')
            value=json.loads(source.read_text())
            if method=='security-telemetry-import':
                if not isinstance(value,dict) or set(value)-{'sensor','starts','ends','events'} or not isinstance(value.get('events'),list) or len(value['events'])>1000 or type(value.get('starts')) is not int or type(value.get('ends')) is not int or value['starts']>=value['ends']:raise ValueError('Telemetry requires sensor, bounded time coverage and events')
                policy.text(value.get('sensor'),'Sensor',200)
                for event in value['events']:
                    if not isinstance(event,dict) or type(event.get('time')) is not int or not value['starts']<=event['time']<=value['ends'] or not isinstance(event.get('runId'),str):raise ValueError('Each sensor event needs a covered time and exact runId')
                retained=evidence.retain(manager,engagement,value,'external-telemetry',path)
                result=manager.add('securityTelemetry',engagement,evidenceId=retained['id'],sensor=value['sensor'],starts=value['starts'],ends=value['ends'],scopeRevision=revision)
            else:
                # Explicit structural import; external conclusions never become native findings.
                if not isinstance(value,dict) or not isinstance(value.get('findings'),list) or len(value['findings'])>200:raise ValueError('Structured export requires at most 200 findings')
                for finding in value['findings']:
                    if not isinstance(finding,dict) or not isinstance(finding.get('title'),str) or not isinstance(finding.get('status'),str):raise ValueError('Each external finding needs title and status')
                retained=evidence.retain(manager,engagement,value,'external-untrusted',path)
                result=dict(evidenceId=retained['id'],claims=[dict(title=f['title'][:500],externalStatus=f['status'][:100],wixalState='unverified_external_claim') for f in value['findings']],authority='None; no commands, approval, objectives or native confirmed findings imported')
        else:
            run=manager.record('securityRuns',params.get('runId'),engagement)
            expected=policy.text(params.get('eventType'),'Expected defensive event',100)
            telemetry=manager.record('securityTelemetry',params.get('telemetryId'),engagement)
            _,data=evidence.read(manager,engagement,telemetry['evidenceId'])
            if run.get('scopeRevision')!=revision or telemetry['scopeRevision']!=revision:raise ValueError('Correlation requires current scope observations')
            starts=run.get('started');ends=run.get('finished')
            complete=type(starts) is int and type(ends) is int and data['starts']<=starts<=ends<=data['ends']
            hits=[e for e in data['events'] if e['runId']==run['id'] and e.get('type')==expected and starts is not None and ends is not None and starts<=e['time']<=ends]
            result=dict(runId=run['id'],telemetryId=telemetry['id'],expected=expected,status='observed' if hits else 'not_observed' if complete else 'unknown',coverageComplete=complete,matches=len(hits),limitation='Imported sensor assertions are external evidence; absence is meaningful only within declared sensor coverage')
            manager.event(engagement,'defensive_correlation',result)
        manager.event(engagement,method,dict(scopeRevision=revision))
        manager.workspace.publish()
        if method=='security-specialist-operate':manager.workspace.pump()
        return result
