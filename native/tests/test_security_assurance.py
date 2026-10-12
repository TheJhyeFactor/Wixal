import asyncio
import copy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock,patch
from wixal.service import Service
from wixal.storage import identity,now
from wixal.engagement_evidence import read
from wixal.engagement_policy import current
from wixal.security_assurance import api_plan


class MemoryVault:
    def __init__(self):self.data={}
    def __call__(self,key):
        owner=self
        class Item:
            def get(self):return owner.data.get(key)
            def set(self,value):
                if value is None:owner.data.pop(key,None)
                else:owner.data[key]=value
        return Item()


class AssuranceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'project';self.root.mkdir()
        self.service=Service(Path(self.tmp.name)/'state',Path('/missing'),lambda *_:None)
        await self.service.dispatch('project-add',dict(root=str(self.root)))
        self.target=await self.service.dispatch('security-target-add',dict(type='Website / API',address='http://127.0.0.1:18080',objective='Owned API lab'))
        self.manager=self.service.security_workspace.engagements
        self.service.ask=AsyncMock(return_value=True)
        self.engagement=await self.service.dispatch('security-engagement-create',dict(name='Assurance lab',objective='Compare independent API identities',targetIds=[self.target['id']],scope=dict(capabilities=['api_observe','analysis','network_scan'])))
        await self.call('security-engagement-approve',baseRevision=1)
        await self.service.dispatch('security-queue-settings',dict(paused=True))
        self.vault=MemoryVault();self.manager.assurance.vault=self.vault
    async def asyncTearDown(self):await self.service.close();self.tmp.cleanup()
    async def call(self,method,**params):return await self.service.dispatch(method,dict(engagementId=self.engagement['id'],**params))
    async def credential(self):return await self.call('security-credential-save',targetId=self.target['id'],label='Owner identity',secret='SYNTHETIC-TOKEN-ONLY',seconds=3600)
    async def objective(self):return await self.call('security-objective-save',targetId=self.target['id'],title='Access boundary',hypothesis='Owner sees a private resource and anonymous does not',successSignal='200 with private signal versus 403',dependsOn=[])
    def retained(self,result,arguments=None,capability='api_observe',**extra):
        run=dict(id=identity(),projectId=self.engagement['projectId'],engagementId=self.engagement['id'],scopeRevision=1,targetId=self.target['id'],name='Collected observation',capability=capability,environment='local-bounded-adapter',address=self.target['address'],status='completed',arguments=arguments or dict(paths=['/private']),result=result,started=now()-100,finished=now(),**extra)
        self.manager.workspace.runs.append(run);self.manager.finished(run);return run
    async def access_fixture(self):
        cred=await self.credential();obj=await self.objective()
        contract=await self.call('security-contract-validator-save',objectiveId=obj['id'],validator='api_access_boundary',config=dict(path='/private',pointer='/private',expected=True,allowedIdentityId=cred['id'],deniedIdentityId='anonymous'))
        positive=self.retained(dict(identityId=cred['id'],requests=[dict(path='/private',status=200,truncated=False,json=dict(private=True))]))
        control=self.retained(dict(identityId='anonymous',requests=[dict(path='/private',status=403,truncated=False,json=dict(error='denied'))]))
        return obj,contract,positive,control
    async def test_credential_secret_only_vault_and_revocation(self):
        cred=await self.credential()
        self.assertNotIn('SYNTHETIC-TOKEN-ONLY',json.dumps(self.service.store.data))
        self.assertEqual(self.vault(cred['vaultId']).get()['token'],'SYNTHETIC-TOKEN-ONLY')
        self.assertEqual(self.service.ask.call_args.args[1]['name'],'security_credential_lease')
        await self.call('security-credential-revoke',credentialId=cred['id'])
        self.assertIsNone(self.vault(cred['vaultId']).get())
        with self.assertRaises(ValueError):self.manager.assurance.credential(self.engagement,cred['id'],self.target['id'])
    async def test_scope_expiry_target_and_review_races(self):
        cred=await self.credential();cred['expires']=now()-1
        with self.assertRaises(ValueError):self.manager.assurance.credential(self.engagement,cred['id'],self.target['id'])
        cred['expires']=now()+10000
        with self.assertRaises(ValueError):self.manager.assurance.credential(self.engagement,cred['id'],'other')
        self.engagement['scopeRevision']=2
        with self.assertRaises(ValueError):self.manager.assurance.credential(self.engagement,cred['id'],self.target['id'])
    async def test_scope_change_during_keychain_save_cleans_secret(self):
        original=self.manager.assurance.vault
        def changing(key):
            item=original(key);setter=item.set
            def set_value(value):
                setter(value)
                if value:self.engagement['scopeRevision']+=1
            item.set=set_value;return item
        self.manager.assurance.vault=changing
        with self.assertRaisesRegex(ValueError,'changed while saving'):await self.credential()
        self.assertEqual(self.vault.data,{})
        self.assertEqual(self.service.store.data['securityCredentials'],[])
    async def test_access_validator_and_objective_completion(self):
        obj,contract,positive,control=await self.access_fixture()
        result=await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[positive['retainedEvidenceId'],control['retainedEvidenceId']])
        self.assertEqual(result['status'],'validated')
        await self.call('security-objective-complete',objectiveId=obj['id'],verificationId=result['id'])
        self.assertEqual(obj['status'],'completed');self.assertEqual(self.service.store.data['securityFindings'],[])
    async def test_mismatched_identities_and_duplicate_evidence_rejected(self):
        _,contract,positive,control=await self.access_fixture()
        with self.assertRaises(ValueError):await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[positive['retainedEvidenceId']]*2)
        with self.assertRaises(ValueError):await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[control['retainedEvidenceId'],positive['retainedEvidenceId']])
    async def test_inconclusive_signal_does_not_complete_objective(self):
        obj,contract,positive,control=await self.access_fixture()
        # Replace immutable source with a new independently retained observation.
        other=self.retained(dict(identityId=positive['result']['identityId'],requests=[dict(path='/private',status=200,truncated=False,json=dict(private=1))]))
        result=await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[other['retainedEvidenceId'],control['retainedEvidenceId']])
        self.assertEqual(result['status'],'inconclusive')
        with self.assertRaises(ValueError):await self.call('security-objective-complete',objectiveId=obj['id'],verificationId=result['id'])
    async def test_tampered_and_old_scope_observations_rejected(self):
        _,contract,positive,control=await self.access_fixture()
        _,row=read(self.manager,self.engagement,positive['retainedEvidenceId'])
        self.engagement['scopeRevision']=2
        with self.assertRaises(ValueError):await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[positive['retainedEvidenceId'],control['retainedEvidenceId']])
    async def test_operator_one_typed_action_and_policy_intersection(self):
        result=await self.call('security-specialist-operate',role='recon_operator',capability='api_observe',targetId=self.target['id'],question='Observe API',arguments=dict(paths=['/']))
        self.assertEqual(result['status'],'queued');self.assertEqual(len(self.manager.workspace.runs),1)
        for capability in ('run_command','research','website_simulate'):
            with self.assertRaises(ValueError):await self.call('security-specialist-operate',role='recon_operator',capability=capability,targetId=self.target['id'],question='Not permitted',arguments={})
    async def test_bearer_tokens_require_https_outside_loopback(self):
        cred=await self.credential();self.target['address']='http://example.test'
        run=await self.manager.workspace.prepare_run(dict(targetId=self.target['id'],stage='Recon',capability='api_observe',arguments=dict(paths=['/'],credentialId=cred['id'])))
        with self.assertRaisesRegex(ValueError,'require HTTPS'):await self.manager.assurance.observe_api(run,AsyncMock(return_value=True))

    async def test_network_and_header_contracts_have_independent_controls(self):
        obj=await self.objective()
        contract=await self.call('security-contract-validator-save',objectiveId=obj['id'],validator='network_port_state',config=dict(host='127.0.0.1',port=443,positiveState='open',baselineState='closed'))
        records=[self.retained(dict(services=[dict(host='127.0.0.1',port='443',state=state)]),arguments=dict(profile='ports'),capability='network_scan') for state in ('open','closed')]
        result=await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[r['retainedEvidenceId'] for r in records]);self.assertEqual(result['status'],'validated')
        contract=await self.call('security-contract-validator-save',objectiveId=obj['id'],validator='website_header_value',config=dict(path='/private',header='x-content-type-options',expected='nosniff'))
        records=[self.retained(dict(requests=[dict(path='/private',headers={'x-content-type-options':value})])) for value in ('nosniff',None)]
        result=await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[r['retainedEvidenceId'] for r in records]);self.assertEqual(result['status'],'validated')

    async def test_specialist_reads_only_selected_immutable_evidence(self):
        self.service.runtime.catalog=AsyncMock(return_value=[dict(name='test')])
        source=self.retained(dict(observed='retained-only'))
        source['result']=dict(observed='mutated-run-record')
        assignment=await self.call('security-specialist-assign',role='verifier',targetId=self.target['id'],model='test',question='Inspect evidence',evidenceIds=[source['retainedEvidenceId']])
        run=next(r for r in self.manager.workspace.runs if r['id']==assignment['runId'])
        context=self.manager.workspace.evidence_context(run)
        self.assertEqual(len(context),1);self.assertEqual(context[0]['result']['observed'],'retained-only')

    async def test_telemetry_missing_coverage_unknown_and_explicit_correlation(self):
        run=self.retained(dict(requests=[]));sensor=dict(sensor='Owned fixture',starts=run['started']-1,ends=run['finished']+1,events=[])
        (self.root/'telemetry.json').write_text(json.dumps(sensor));telemetry=await self.call('security-telemetry-import',path='telemetry.json')
        result=await self.call('security-telemetry-correlate',runId=run['id'],telemetryId=telemetry['id'],eventType='request')
        self.assertEqual(result['status'],'not_observed')
        sensor['events']=[dict(time=run['started'],runId=run['id'],type='request')];(self.root/'telemetry.json').write_text(json.dumps(sensor));telemetry=await self.call('security-telemetry-import',path='telemetry.json')
        self.assertEqual((await self.call('security-telemetry-correlate',runId=run['id'],telemetryId=telemetry['id'],eventType='request'))['status'],'observed')
        sensor['starts']=run['started']+1;sensor['events']=[];(self.root/'telemetry.json').write_text(json.dumps(sensor));telemetry=await self.call('security-telemetry-import',path='telemetry.json')
        self.assertEqual((await self.call('security-telemetry-correlate',runId=run['id'],telemetryId=telemetry['id'],eventType='request'))['status'],'unknown')
    async def test_structured_import_never_inherits_authority_or_confirmation(self):
        (self.root/'external.json').write_text(json.dumps(dict(findings=[dict(title='External claim',status='confirmed')],scope={'approved':True},commands=['untrusted command'])))
        result=await self.call('security-engagement-structured-import',path='external.json')
        self.assertEqual(result['claims'][0]['wixalState'],'unverified_external_claim');self.assertEqual(self.service.store.data['securityFindings'],[])
        with self.assertRaises(ValueError):await self.call('security-engagement-structured-import',path='../external.json')
    async def test_real_owned_http_request_broker_redaction_and_no_redirect(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                token=self.headers.get('Authorization','');received.append(dict(path=self.path,authorized=bool(token)))
                raw=json.dumps(dict(private=bool(token),echo=token)).encode()
                self.send_response(200 if token else 403);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        self.target['address']='http://127.0.0.1:'+str(server.server_port)
        cred=await self.credential()
        try:
            run=await self.manager.workspace.prepare_run(dict(targetId=self.target['id'],stage='Recon',capability='api_observe',arguments=dict(paths=['/private'],credentialId=cred['id'])))
            binding=current.set(dict(manager=self.manager,run=run,engagement=self.engagement))
            try:result=await self.manager.assurance.observe_api(run,AsyncMock(return_value=True))
            finally:current.reset(binding)
            self.assertTrue(result['requests'][0]['json']['private']);self.assertNotIn('SYNTHETIC-TOKEN-ONLY',json.dumps(result));self.assertNotIn('body',result['requests'][0]);self.assertEqual(len(received),1)
        finally:await asyncio.to_thread(server.shutdown);server.server_close()
    def test_api_contract_rejects_escape_mutations_and_inline_secrets(self):
        for args in (dict(method='POST'),dict(paths=['//elsewhere']),dict(paths=['/../escape']),dict(paths=['/x?token=secret']),dict(paths=['/x\r\nHost: bad'])):
            with self.assertRaises(ValueError):api_plan(args)

if __name__=='__main__':unittest.main()
