import asyncio
import hashlib
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
from unittest.mock import AsyncMock
from wixal.storage import now
from wixal import engagement_policy as policy
from wixal.security_assurance import mutation_plan
from wixal.security_external import vendor_events
import test_security_assurance as fixtures


class SecurityExtensions(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AssuranceTests.asyncSetUp
    asyncTearDown=fixtures.AssuranceTests.asyncTearDown
    call=fixtures.AssuranceTests.call
    objective=fixtures.AssuranceTests.objective

    async def enable_mutations(self):
        await self.call('security-engagement-scope',baseRevision=1,scope=dict(capabilities=['api_observe','api_mutate','analysis']))
        await self.call('security-engagement-approve',baseRevision=2)

    async def collect(self,capability,arguments):
        run=await self.manager.workspace.prepare_run(dict(targetId=self.target['id'],stage='Recon',capability=capability,arguments=arguments))
        run.update(status='running',started=now());self.manager.started(run)
        token=policy.current.set(dict(manager=self.manager,engagement=self.engagement,run=run))
        try:run['result']=await self.manager.assurance.observe_api(run,AsyncMock(return_value=True))
        finally:policy.current.reset(token)
        run.update(status='completed',finished=now());self.manager.workspace.runs.append(run);self.manager.finished(run)
        return run

    async def test_mutation_inputs_reject_inline_secrets_and_invalid_paths(self):
        for args in (dict(path='//other',method='POST'),dict(path='/',method='GET'),dict(path='/',method='POST',body={'password':'no'}),dict(path='/',method='POST',body={'x':float('nan')})):
            with self.assertRaises(ValueError):mutation_plan(args)
        self.assertEqual(mutation_plan(dict(path='/state',method='PATCH',body={'flag':True}))['body'],{'flag':True})

    async def test_cookie_mutation_independent_state_and_cleanup(self):
        await self.enable_mutations();events=[];state={'flag':False}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def reply(self,status,value):
                raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):events.append(('GET',self.path));self.reply(200,state)
            def do_PATCH(self):
                events.append(('PATCH',self.path))
                if self.headers.get('Cookie')!='session=SYNTHETIC-COOKIE':self.reply(403,{'denied':True});return
                state.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))));self.reply(200,dict(flag=state['flag'],echo='SYNTHETIC-COOKIE'))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        self.target['address']='http://127.0.0.1:'+str(server.server_port)
        try:
            credential=await self.call('security-credential-save',targetId=self.target['id'],kind='cookie',label='Cookie lab',secret='session=SYNTHETIC-COOKIE',seconds=600)
            baseline=await self.collect('api_observe',dict(paths=['/state']))
            mutation=await self.collect('api_mutate',dict(path='/state',method='PATCH',body={'flag':True},credentialId=credential['id']))
            positive=await self.collect('api_observe',dict(paths=['/state']))
            self.assertEqual(events,[('GET','/state'),('PATCH','/state'),('GET','/state')]);self.assertTrue(state['flag'])
            self.assertNotIn('SYNTHETIC-COOKIE',json.dumps(mutation['result']))
            self.assertEqual(self.manager.rows('securityCleanup',self.engagement)[0]['status'],'pending')
            objective=await self.objective()
            contract=await self.call('security-contract-validator-save',objectiveId=objective['id'],validator='api_mutation_state',config=dict(path='/state',pointer='/flag',before=False,after=True,mutationRunId=mutation['id']))
            result=await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[positive['retainedEvidenceId'],baseline['retainedEvidenceId']])
            self.assertEqual(result['status'],'validated')
            with self.assertRaises(ValueError):await self.call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[baseline['retainedEvidenceId'],positive['retainedEvidenceId']])
        finally:server.shutdown();server.server_close()

    async def test_declined_mutation_does_not_connect(self):
        await self.enable_mutations();self.service.ask=AsyncMock(return_value=False)
        run=await self.manager.workspace.prepare_run(dict(targetId=self.target['id'],stage='Recon',capability='api_mutate',arguments=dict(path='/',method='DELETE')))
        with self.assertRaisesRegex(ValueError,'not approved'):await self.manager.assurance.observe_api(run,AsyncMock(return_value=True))

    async def test_failed_mutation_retains_unknown_effect_and_cleanup_requirement(self):
        await self.enable_mutations()
        run=await self.manager.workspace.prepare_run(dict(targetId=self.target['id'],stage='Recon',capability='api_mutate',arguments=dict(path='/',method='POST')))
        run.update(status='failed');self.manager.workspace.runs.append(run);self.manager.finished(run)
        self.assertEqual(run['effectState'],'unknown');self.assertTrue(self.manager.rows('securityCleanup',self.engagement))

    async def test_controller_bridge_import_is_inert_and_decline_keeps_queue_empty(self):
        value=dict(name='External proposal',targetId=self.target['id'],nodes=[dict(id='observe',name='Observe',stage='Recon',capability='api_observe',arguments=dict(paths=['/']),dependencies=[])])
        (self.root/'proposal.json').write_text(json.dumps(value))
        plan=await self.call('security-controller-plan-import',path='proposal.json')
        self.assertEqual(plan['status'],'draft');self.assertEqual(self.manager.workspace.runs,[])
        self.service.ask=AsyncMock(return_value=False)
        with self.assertRaisesRegex(ValueError,'not approved'):await self.call('security-controller-plan-run',planId=plan['id'])
        self.assertEqual(self.manager.workspace.runs,[])
        self.service.ask=AsyncMock(return_value=True)
        result=await self.call('security-controller-plan-run',planId=plan['id'])
        self.assertEqual(len(result['runIds']),1);self.assertEqual(len(self.manager.workspace.runs),1)

    async def test_controller_cannot_import_commands_or_bypass_scope(self):
        for capability in ('command_start','api_mutate'):
            (self.root/'proposal.json').write_text(json.dumps(dict(name='Rejected',targetId=self.target['id'],nodes=[dict(id='x',stage='Recon',capability=capability,arguments={})])))
            with self.assertRaises(ValueError):await self.call('security-controller-plan-import',path='proposal.json')
        self.assertEqual(self.manager.workspace.runs,[])

    async def test_real_oauth_pkce_callback_and_secret_isolation(self):
        exchanges=[];authorization={}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                form=parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode());exchanges.append(form)
                challenge=__import__('base64').urlsafe_b64encode(hashlib.sha256(form['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
                good=challenge==authorization['code_challenge'][0] and form['code']==['LAB-CODE'] and form['redirect_uri']==authorization['redirect_uri']
                raw=json.dumps(dict(access_token='SYNTHETIC-OAUTH-TOKEN',token_type='Bearer',expires_in=600)).encode()
                self.send_response(200 if good else 400);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();self.target['address']='http://127.0.0.1:'+str(server.server_port)
        try:
            flow=await self.call('security-oauth-start',targetId=self.target['id'],label='OAuth lab',clientId='public-lab')
            authorization.update(parse_qs(urlsplit(flow['authorizationUrl']).query));self.assertEqual(authorization['code_challenge_method'],['S256'])
            callback=urlsplit(flow['redirectUri'])
            async def request(state):
                reader,writer=await asyncio.open_connection(callback.hostname,callback.port)
                writer.write(('GET /callback?state='+state+'&code=LAB-CODE HTTP/1.1\r\nHost: localhost\r\n\r\n').encode());await writer.drain();result=await reader.read();writer.close();await writer.wait_closed();return result
            self.assertIn(b'400 Bad Request',await request('wrong-state'));self.assertEqual(exchanges,[])
            self.assertIn(b'200 OK',await request(authorization['state'][0]));self.assertEqual(len(exchanges),1)
            self.assertNotIn('SYNTHETIC-OAUTH-TOKEN',json.dumps(self.service.store.data));self.assertNotIn('code_verifier',json.dumps(self.service.store.data))
            self.assertEqual(self.service.store.data['securityOAuthFlows'][-1]['status'],'completed')
            self.assertEqual(self.service.store.data['securityCredentials'][-1]['kind'],'oauth_access_token')
        finally:server.shutdown();server.server_close()

    def test_vendor_adapter_requires_exact_destination_time_and_ip(self):
        run=dict(id='owned',address='http://127.0.0.1:8080',started=1000,finished=3000)
        text='\n'.join(json.dumps(dict(ts=stamp,**{'id.resp_h':host,'id.resp_p':8080})) for stamp,host in [(2,'127.0.0.1'),(2,'127.0.0.2'),(4,'127.0.0.1')])
        events=vendor_events(text,'zeek_json',run,0,5000)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['runId'],'owned')
        with self.assertRaises(ValueError):vendor_events(text,'zeek_json',{**run,'address':'https://example.test'},0,5000)

    async def test_oauth_decline_scope_change_and_shutdown_close_callback(self):
        self.service.ask=AsyncMock(return_value=False)
        with self.assertRaisesRegex(ValueError,'not approved'):await self.call('security-oauth-start',targetId=self.target['id'],label='Declined',clientId='public')
        self.assertEqual(self.manager.assurance.oauth.flows,{})
        self.service.ask=AsyncMock(return_value=True)
        flow=await self.call('security-oauth-start',targetId=self.target['id'],label='Pending',clientId='public')
        url=urlsplit(flow['redirectUri']);await self.manager.assurance.oauth.close()
        with self.assertRaises(OSError):await asyncio.open_connection(url.hostname,url.port)
        self.assertEqual(self.service.store.data['securityOAuthFlows'][-1]['status'],'interrupted')

    async def test_controller_scope_revision_and_target_edits_block_execution(self):
        value=dict(name='Proposal',targetId=self.target['id'],nodes=[dict(id='x',stage='Recon',capability='api_observe',arguments=dict(paths=['/']))])
        (self.root/'p.json').write_text(json.dumps(value));plan=await self.call('security-controller-plan-import',path='p.json')
        plan['targetId']='different'
        with self.assertRaises(ValueError):await self.call('security-controller-plan-run',planId=plan['id'])
        plan['targetId']=self.target['id'];self.engagement['scopeRevision']+=1
        with self.assertRaisesRegex(ValueError,'older scope'):await self.call('security-controller-plan-run',planId=plan['id'])
        self.assertEqual(self.manager.workspace.runs,[])

    async def test_scope_changes_during_mutation_review_block_transport(self):
        await self.enable_mutations()
        async def change(*_):self.engagement['scopeRevision']+=1;return True
        self.service.ask=change
        run=await self.manager.workspace.prepare_run(dict(targetId=self.target['id'],stage='Recon',capability='api_mutate',arguments=dict(path='/',method='POST')))
        with self.assertRaisesRegex(ValueError,'scope changed'):await self.manager.assurance.observe_api(run,AsyncMock(return_value=True))

    def test_suricata_timestamp_and_event_selection(self):
        run=dict(id='owned',address='http://127.0.0.1:8080',started=1000,finished=3000)
        row=dict(timestamp='1970-01-01T00:00:02+00:00',dest_ip='127.0.0.1',dest_port=8080,event_type='http')
        self.assertEqual(vendor_events(json.dumps(row),'suricata_eve',run,0,4000)[0]['type'],'http_request')
        row['timestamp']='1970-01-01T00:00:02'
        with self.assertRaisesRegex(ValueError,'timezone'):vendor_events(json.dumps(row),'suricata_eve',run,0,4000)
