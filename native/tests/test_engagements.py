import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from wixal.service import Service
from wixal.storage import identity, now
from wixal.engagements import Engagements
from wixal.engagement_evidence import retain, read
from wixal.engagement_policy import current, connection, tool_gate
from wixal.security_cvss import score_vector, CVSSError


class EngagementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.service=Service(Path(self.temp.name)/'state',Path('/nonexistent/ollama'),lambda *_:None)
        await self.service.dispatch('project-add',dict(root=str(self.root)))
        self.target=await self.service.dispatch('security-target-add',dict(type='Server',address='127.0.0.1',objective='Local fixture'))
        self.manager=self.service.security_workspace.engagements
        self.service.ask=AsyncMock(return_value=True)
        self.service.runtime.catalog=AsyncMock(return_value=[dict(name='test')])
        self.engagement=await self.create()
        await self.service.dispatch('security-queue-settings',dict(paused=True))

    async def asyncTearDown(self):
        await self.service.close();self.temp.cleanup()

    async def call(self,method,**params):return await self.service.dispatch(method,dict(engagementId=self.engagement['id'],**params))

    async def create(self,**kwargs):
        return await self.service.dispatch('security-engagement-create',dict(name='Local review',objective='Demonstrate independent observations',targetIds=[self.target['id']],**kwargs))

    async def approve(self):return await self.call('security-engagement-approve',baseRevision=self.engagement['scopeRevision'])

    async def objective(self):return await self.call('security-objective-save',targetId=self.target['id'],title='Signal changes',hypothesis='The response changes under the test condition',successSignal='Distinct status relative to baseline',dependsOn=[])

    async def queue(self,**kwargs):
        return await self.service.dispatch('security-run-add',dict(targetId=self.target['id'],stage='Attacks',capability='website_simulate',arguments={},**kwargs))

    def observation(self,value,capability='website_assess',**kwargs):
        run=dict(id=identity(),projectId=self.engagement['projectId'],engagementId=self.engagement['id'],targetId=self.target['id'],scopeRevision=self.engagement['scopeRevision'],capability=capability,environment='local-bounded-adapter',address=self.target['address'],status='completed',arguments=dict(profile='baseline'),result=dict(signal=value),finished=now(),**kwargs)
        self.manager.workspace.runs.append(run);self.manager.finished(run)
        return run,self.manager.record('securityEvidence',run['retainedEvidenceId'],self.engagement)

    async def test_legacy_records_not_fabricated_as_approved_engagements(self):
        self.assertEqual(self.engagement['status'],'draft');self.assertIsNone(self.engagement['approval'])
        with self.assertRaisesRegex(ValueError,'not approved'):await self.queue()
        self.assertEqual(self.manager.workspace.runs,[])

    async def test_explicit_scope_review_ignores_project_bypass(self):
        self.service.store.project()['approvalMode']='bypass';await self.approve()
        self.service.ask.assert_awaited_once();self.assertEqual(self.engagement['status'],'running')
        self.assertEqual(self.service.ask.call_args.args[1]['targets'],[dict(type='Server',address='127.0.0.1')])
        run=await self.queue();self.assertEqual(run['scopeRevision'],1);self.assertEqual(run['effectState'],'prepared')

    async def test_review_race_does_not_approve_changed_scope(self):
        async def changed(*_):self.engagement['scopeRevision']+=1;return True
        self.service.ask=changed
        with self.assertRaisesRegex(ValueError,'changed during review'):await self.approve()
        self.assertIsNone(self.engagement['approval'])

    async def test_denied_approval_and_expired_window(self):
        self.service.ask=AsyncMock(return_value=False)
        with self.assertRaisesRegex(ValueError,'not approved'):await self.approve()
        self.engagement['scopes'][-1]['policy']['ends']=now()-1
        with self.assertRaisesRegex(ValueError,'window'):await self.approve()

    async def test_scope_revision_stops_queue_and_invalidates_approval(self):
        await self.approve();run=await self.queue()
        scope=copy.deepcopy(self.manager.scope(self.engagement));scope['maxRuns']=10
        await self.call('security-engagement-scope',baseRevision=1,scope=scope)
        self.assertEqual(run['status'],'cancelled');self.assertEqual(run['effectState'],'not_dispatched')
        self.assertIsNone(self.engagement['approval']);self.assertEqual(len(self.engagement['scopes']),2)
        with self.assertRaisesRegex(ValueError,'revision changed'):await self.call('security-engagement-scope',baseRevision=1,scope=scope)

    async def test_unsupported_or_excluded_scope_is_rejected(self):
        for scope in ({'capabilities':['run_command']},{'targetIds':[]},{'exclusions':['127.0.0.0/8']},{'maxRuns':True}):
            with self.assertRaises(ValueError):await self.call('security-engagement-scope',baseRevision=1,scope=scope) if 'exclusions' not in scope else await self._exclude(scope)

    async def _exclude(self,scope):
        # Revisions can narrow scope, but approval must reject excluded targets.
        await self.call('security-engagement-scope',baseRevision=1,scope=scope)
        await self.approve()

    async def test_target_cannot_be_bound_to_two_open_engagements(self):
        with self.assertRaisesRegex(ValueError,'already belongs'):await self.create()

    async def test_capability_and_budget_are_enforced(self):
        scope=copy.deepcopy(self.manager.scope(self.engagement));scope['maxRuns']=1
        await self.call('security-engagement-scope',baseRevision=1,scope=scope);await self.approve();await self.queue()
        with self.assertRaisesRegex(ValueError,'budget exhausted'):await self.queue()
        with self.assertRaisesRegex(ValueError,'outside the engagement scope'):
            await self.service.dispatch('security-run-add',dict(targetId=self.target['id'],stage='Research',capability='research',model='test',prompt='Query outside'))

    async def test_whole_plan_budget_is_atomic(self):
        scope=copy.deepcopy(self.manager.scope(self.engagement));scope['maxRuns']=1
        await self.call('security-engagement-scope',baseRevision=1,scope=scope);await self.approve()
        plan=await self.service.dispatch('security-plan-save',dict(targetId=self.target['id'],name='Two steps',nodes=[dict(id=str(i),name='Simulation',stage='Attacks',capability='website_simulate',arguments={},dependencies=[]) for i in range(2)]))
        with self.assertRaisesRegex(ValueError,'nothing queued'):await self.service.dispatch('security-plan-run',dict(id=plan['id']))
        self.assertEqual(self.manager.workspace.runs,[])

    async def test_evidence_is_paged_and_hash_checked(self):
        run,row=self.observation('A'*20000)
        result=await self.call('security-evidence-read',evidenceId=row['id'])
        self.assertTrue(result['more']);self.assertEqual(result['nextOffset'],12000)
        path=self.service.store.directory/'engagement-evidence'/self.engagement['id']/(row['sha256']+'.json');path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'changed'):read(self.manager,self.engagement,row['id'])

    async def test_scalar_difference_never_confirms_finding(self):
        objective=await self.objective();_,positive=self.observation(200);_,baseline=self.observation(404)
        check=await self.call('security-verification-add',objectiveId=objective['id'],positiveId=positive['id'],baselineId=baseline['id'],pointer='/signal',expected=200)
        self.assertEqual(check['status'],'discriminated');self.assertEqual(self.service.store.data['securityFindings'],[])
        await self.call('security-objective-complete',objectiveId=objective['id'],verificationId=check['id'])
        self.assertEqual(objective['status'],'completed')

    async def test_verifier_rejects_same_simulated_external_and_mismatched_observations(self):
        objective=await self.objective();_,a=self.observation(200);_,b=self.observation(200,'website_simulate')
        for positive,baseline in ((a,a),(a,b)):
            with self.assertRaises(ValueError):await self.call('security-verification-add',objectiveId=objective['id'],positiveId=positive['id'],baselineId=baseline['id'],pointer='/signal',expected=200)
        (self.root/'external.json').write_text('{"status":"confirmed"}')
        external=await self.call('security-evidence-import',path='external.json')
        with self.assertRaises(ValueError):await self.call('security-verification-add',objectiveId=objective['id'],positiveId=a['id'],baselineId=external['id'],pointer='/signal',expected=200)
        self.assertEqual(external['kind'],'external-untrusted')

    async def test_nondiscriminating_or_type_coerced_signals_are_inconclusive(self):
        objective=await self.objective();_,a=self.observation(True);_,b=self.observation(False)
        check=await self.call('security-verification-add',objectiveId=objective['id'],positiveId=a['id'],baselineId=b['id'],pointer='/signal',expected=1)
        self.assertEqual(check['status'],'inconclusive')
        with self.assertRaises(ValueError):await self.call('security-objective-complete',objectiveId=objective['id'],verificationId=check['id'])

    async def test_completion_requires_objectives_cleanup_and_reconciliation(self):
        with self.assertRaisesRegex(ValueError,'Unfinished'):await self.call('security-engagement-close',reason='No evidence')
        objective=await self.objective();_,a=self.observation(200);_,b=self.observation(404)
        check=await self.call('security-verification-add',objectiveId=objective['id'],positiveId=a['id'],baselineId=b['id'],pointer='/signal',expected=200)
        await self.call('security-objective-complete',objectiveId=objective['id'],verificationId=check['id'])
        cleanup=await self.call('security-cleanup-add',title='Review fixture',description='Inspect retained state')
        with self.assertRaises(ValueError):await self.call('security-engagement-close',reason='Still pending')
        await self.call('security-cleanup-update',cleanupId=cleanup['id'],status='accepted',rationale='Operator accepts retained local fixture',evidenceIds=[])
        await self.call('security-engagement-close',reason='Observation objective evaluated; cleanup reviewed')
        self.assertEqual(self.engagement['status'],'completed')
        with self.assertRaisesRegex(ValueError,'immutable'):await self.objective()

    async def test_scope_revision_does_not_reuse_completed_old_scope_objectives(self):
        objective=await self.objective();_,a=self.observation(200);_,b=self.observation(404)
        check=await self.call('security-verification-add',objectiveId=objective['id'],positiveId=a['id'],baselineId=b['id'],pointer='/signal',expected=200)
        await self.call('security-objective-complete',objectiveId=objective['id'],verificationId=check['id'])
        await self.call('security-engagement-scope',baseRevision=1,scope=copy.deepcopy(self.manager.scope(self.engagement)))
        with self.assertRaisesRegex(ValueError,'older-scope'):await self.call('security-engagement-close',reason='Must replace and verify current objectives')

    async def test_explicit_incomplete_close_retains_unmet_objective(self):
        objective=await self.objective();await self.call('security-engagement-close',reason='Environment unavailable',incomplete=True)
        self.assertEqual(self.engagement['status'],'closed_incomplete');self.assertEqual(objective['status'],'pending')

    async def test_replacing_objective_preserves_history_and_requires_new_check(self):
        old=await self.objective()
        replacement=await self.call('security-objective-save',targetId=self.target['id'],title='Revised objective',hypothesis='A current hypothesis',successSignal='A fresh current observation',dependsOn=[],replacesId=old['id'])
        self.assertEqual(old['status'],'superseded');self.assertEqual(old['previousStatus'],'pending')
        self.assertEqual(replacement['replacesId'],old['id']);self.assertEqual(replacement['status'],'pending')
        with self.assertRaisesRegex(ValueError,'superseded'):await self.call('security-objective-complete',objectiveId=old['id'],verificationId='unused')
        with self.assertRaisesRegex(ValueError,'Unfinished'):await self.call('security-engagement-close',reason='No observation check yet')

    async def test_graph_paths_are_bounded_candidates_and_need_evidence(self):
        objective=await self.objective()
        with self.assertRaisesRegex(ValueError,'need retained evidence'):await self.call('security-relation-add',fromId=self.target['id'],toId=objective['id'],kind='may_enable',state='observed',rationale='No evidence')
        edge=await self.call('security-relation-add',fromId=self.target['id'],toId=objective['id'],kind='may_enable',state='inferred',rationale='Hypothesis only')
        result=await self.call('security-relation-paths',fromId=self.target['id'],toId=objective['id'])
        self.assertEqual(result['paths'][0]['state'],'candidate');self.assertEqual(result['paths'][0]['edgeIds'],[edge['id']])

    async def test_specialist_is_evidence_only_and_requires_current_authority(self):
        _,row=self.observation(200)
        with self.assertRaisesRegex(ValueError,'not approved'):await self.call('security-specialist-assign',targetId=self.target['id'],role='verifier',question='Challenge this evidence',model='test',evidenceIds=[row['id']])
        await self.approve()
        assignment=await self.call('security-specialist-assign',targetId=self.target['id'],role='verifier',question='Challenge this evidence',model='test',evidenceIds=[row['id']])
        run=self.manager.record('securityRuns',assignment['runId'],self.engagement)
        self.assertEqual(run['capability'],'analysis');self.assertIn('no tool execution',assignment['authority'])
        self.assertEqual(run['evidenceIds'],[row['source']])

    async def test_skill_install_is_idempotent_and_contains_only_text(self):
        await self.call('security-engagement-skills');await self.call('security-engagement-skills')
        skills=[s for s in self.service.store.data['skills'] if s.get('source')=='wixal:redteam-skills:v1']
        self.assertEqual(len(skills),5);self.assertTrue(all(s['resources'] for s in skills))

    async def test_scope_blocks_excluded_dns_and_arbitrary_tools(self):
        await self.approve();run=await self.queue()
        run['capability']='website_assess';run['address']='http://lab.example.test'
        self.target['address']=run['address'];self.manager.scope(self.engagement)['capabilities'].append('website_assess') if 'website_assess' not in self.manager.scope(self.engagement)['capabilities'] else None
        self.manager.scope(self.engagement)['exclusions']=['127.0.0.0/8']
        from wixal.engagement_evidence import digest
        self.engagement['approval']['digest']=digest(self.manager.scope(self.engagement))
        token=current.set(dict(manager=self.manager,engagement=self.engagement,run=run))
        try:
            with self.assertRaisesRegex(ValueError,'outside this engagement'):tool_gate('run_command',{})
            with patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=[(2,1,6,'',('127.0.0.1',80))])):
                with self.assertRaisesRegex(ValueError,'excluded'):await connection(run['address'])
            with self.assertRaisesRegex(ValueError,'outside the engagement origin'):await connection('http://other.example.test')
        finally:current.reset(token)

    async def test_restart_revokes_approval_and_marks_uncertain_work(self):
        await self.approve();run=await self.queue();run['status']='interrupted'
        Engagements(self.manager.workspace)
        self.assertEqual(self.engagement['status'],'paused');self.assertIsNone(self.engagement['approval']);self.assertEqual(run['effectState'],'unknown')

    async def test_exports_are_unique_and_include_scope_and_limits(self):
        first=await self.call('security-engagement-export');second=await self.call('security-engagement-export')
        self.assertNotEqual(first['paths'],second['paths']);report=json.loads(Path(first['paths'][0]).read_text())
        self.assertEqual(report['engagement']['scopeRevision'],1);self.assertTrue(report['limitations'])

    async def test_cross_project_and_external_path_escape_rejected(self):
        with self.assertRaises(ValueError):await self.call('security-evidence-import',path='../outside.json')
        other=Path(self.temp.name)/'other';other.mkdir();await self.service.dispatch('project-add',dict(root=str(other)))
        with self.assertRaisesRegex(ValueError,'active project'):await self.call('security-engagement-snapshot',id=self.engagement['id'])


class CVSSTests(unittest.TestCase):
    def test_known_base_vectors(self):
        for vector,score in [('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',9.8),('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H',10.0),('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N',0.0),('CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N',5.4)]:
            self.assertEqual(score_vector(vector)['base_score'],score)
    def test_malformed_and_duplicate_metrics_rejected(self):
        base='CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'
        for vector in (base.replace('3.1','3.0'),base+'/AV:A',base+'/',base.replace('AV:N','AV:Q')):
            with self.assertRaises(CVSSError):score_vector(vector)

class EngagementLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_loopback_assessment_simulation_and_restart(self):
        from fixture_server import Fixture
        from wixal.security_workspace import SecurityWorkspace
        with tempfile.TemporaryDirectory() as temp, Fixture() as fixture:
            root=Path(temp)/'project';root.mkdir()
            service=Service(Path(temp)/'state',Path('/nonexistent'),lambda *_:None,fixture.url)
            service.ask=AsyncMock(return_value=True)
            try:
                await service.dispatch('project-add',dict(root=str(root)))
                target=await service.dispatch('security-target-add',dict(type='Website / API',address=fixture.url,objective='Actual loopback observation'))
                engagement=await service.dispatch('security-engagement-create',dict(name='Loopback run',objective='Collect actual response evidence',targetIds=[target['id']]))
                await service.dispatch('security-engagement-approve',dict(engagementId=engagement['id'],baseRevision=1))
                assessment=await service.dispatch('security-run-add',dict(targetId=target['id'],stage='Recon',capability='website_assess',arguments=dict(profile='baseline',max_pages=1)))
                simulation=await service.dispatch('security-run-add',dict(targetId=target['id'],stage='Attacks',capability='website_simulate',arguments={}))
                for _ in range(1000):
                    if assessment['status'] in ('completed','failed') and simulation['status'] in ('completed','failed'):break
                    await asyncio.sleep(.02)
                self.assertEqual(assessment['status'],'completed',assessment)
                self.assertEqual(simulation['status'],'completed',simulation)
                self.assertEqual(simulation['result']['report']['summary']['unexpected'],0)
                self.assertTrue(assessment.get('retainedEvidenceId'))
                manager=service.security_workspace.engagements
                row,data=read(manager,engagement,assessment['retainedEvidenceId'])
                self.assertEqual(data['result']['report']['requests'][0]['status'],200)
                self.assertEqual(assessment['effectState'],'succeeded')
                scope_count=len(engagement['scopes']);evidence_count=len(manager.rows('securityEvidence',engagement))
                await service.security_workspace.close();service.security_workspace=SecurityWorkspace(service)
                self.assertEqual(engagement['status'],'paused');self.assertEqual(len(engagement['scopes']),scope_count)
                self.assertEqual(len(manager.rows('securityEvidence',engagement)),evidence_count)
            finally:await service.close()

    async def test_engagement_network_parameters_are_bound_before_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'project';root.mkdir();service=Service(Path(temp)/'state',Path('/nonexistent'),lambda *_:None)
            service.ask=AsyncMock(return_value=True)
            try:
                await service.dispatch('project-add',dict(root=str(root)))
                target=await service.dispatch('security-target-add',dict(type='Server',address='127.0.0.1'))
                engagement=await service.dispatch('security-engagement-create',dict(name='Network bound',objective='Inspect loopback',targetIds=[target['id']],scope=dict(capabilities=['network_scan'],maxSeconds=30)))
                await service.dispatch('security-engagement-approve',dict(engagementId=engagement['id'],baseRevision=1))
                await service.dispatch('security-queue-settings',dict(paused=True))
                run=await service.dispatch('security-run-add',dict(targetId=target['id'],stage='Recon',capability='network_scan',arguments=dict(profile='ports',ports='443',timeout_seconds=180)))
                self.assertEqual(run['arguments']['timeout_seconds'],30);self.assertEqual(run['arguments']['target'],'127.0.0.1')
                self.assertEqual(run['engagementId'],engagement['id'])
            finally:await service.close()
