"""Outcome correctness, real filesystem effects, isolation and transfer boundaries."""
import asyncio
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import test_agents_runtime as fixtures
from wixal.agent_context import profile
from wixal.storage import Store,now
from wixal.agent_jobs import run_next
from wixal.scheduling import run_due
from wixal.agent_authority import target_allowed,permits

class OutcomeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted

    async def test_graph_retry_retains_failed_child_and_completed_branch(self):
        flow=await self.service.dispatch('workflow-save',dict(name='Recover branches',execution='Dependency graph',stages=[dict(id='one',name='One',agentID='coder',goal='Inspect'),dict(id='two',name='Two',agentID='coder',goal='Inspect')]))
        calls=0
        async def first(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==2:raise ValueError('Branch provider failed')
            return dict(role='assistant',content='Retained branch evidence')
        with patch('wixal.agent.stream_chat',first):run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        failed=copy.deepcopy(next(s for s in run['stages'] if s['status']=='failed'))
        completed=copy.deepcopy(next(s for s in run['stages'] if s['status']=='completed'))
        context,seen=self.scripted([],'Recovered branch')
        with context:run=await self.service.dispatch('workflow-resume',dict(runId=run['id']))
        recovered=next(s for s in run['stages'] if s['id']==failed['id'])
        self.assertEqual(run['status'],'completed');self.assertEqual(len(seen),1)
        self.assertEqual(next(s for s in run['stages'] if s['id']==completed['id']),completed)
        self.assertEqual(recovered['attemptHistory'],[failed])
        self.assertTrue((self.service.store.directory/'workflow-children'/failed['childId']/'workspace.sqlite3').exists())

    async def test_promotion_rejects_changed_candidate_or_baseline(self):
        from wixal.skill_learning import procedure_digest
        candidate=await self.service.dispatch('skill-propose',dict(name='Bound procedure',content='Read the current source.'))
        candidate['evaluations']=[dict(id=str(i),status='passed',candidateSha256=procedure_digest(candidate),baselineSha256=procedure_digest(None)) for i in range(2)]
        candidate['content']='Unevaluated replacement'
        with self.assertRaisesRegex(ValueError,'changed'):await self.service.dispatch('skill-promote',dict(id=candidate['id']))
        candidate['content']='Read the current source.'
        self.service.store.data['skills'].append(dict(id='new-baseline',name=candidate['name'],owner='guest',content='New baseline'))
        with self.assertRaisesRegex(ValueError,'changed'):await self.service.dispatch('skill-promote',dict(id=candidate['id']))
        self.assertEqual(self.service.store.data['skills'][-1]['content'],'New baseline')

    async def test_empty_completed_inference_retries_once_without_effects(self):
        calls=0
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',usage=dict(eval_count=1))
            self.assertIn('No new action occurred',body['messages'][-1]['content'])
            return dict(role='assistant',content='The task needs no tool actions.',usage=dict(eval_count=5))
        with patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Explain the project'))
        self.assertEqual(calls,2);self.assertEqual(task['checkpoints'],[]);self.assertEqual(task['status'],'completed')
    async def test_repeated_empty_inference_fails_visibly_and_stays_bounded(self):
        calls=0
        async def stream(*args):
            nonlocal calls
            calls+=1;return dict(role='assistant',content='',usage=dict(eval_count=1))
        with patch('wixal.agent.stream_chat',stream):
            with self.assertRaisesRegex(ValueError,'without a visible answer'):await self.service.dispatch('agent-run',dict(id='coder',prompt='Explain the project'))
        self.assertEqual(calls,2);self.assertEqual(self.service.store.data['tasks'][-1]['checkpoints'],[])
    async def test_invalid_tool_json_recovery_executes_no_failed_response(self):
        from wixal.agent import ToolCallSyntaxError
        calls=0
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:raise ToolCallSyntaxError('Invalid model tool JSON')
            self.assertIn('No action from that response executed',body['messages'][-1]['content'])
            return dict(role='assistant',content='No tools were executed.')
        with patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Explain the project'))
        self.assertEqual(calls,2);self.assertEqual(task['checkpoints'],[])
    async def test_invalid_tool_json_retry_is_bounded(self):
        from wixal.agent import ToolCallSyntaxError
        calls=0
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1;raise ToolCallSyntaxError('Invalid model tool JSON')
        with patch('wixal.agent.stream_chat',stream):
            with self.assertRaises(ToolCallSyntaxError):await self.service.dispatch('agent-run',dict(id='coder',prompt='Explain the project'))
        self.assertEqual(calls,3)
    async def test_false_success_missing_artifact_needs_attention(self):
        context,_=self.scripted([],'I saved the report successfully')
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Save report',successCriteria=[dict(kind='file_exists',path='missing.md')]))
        self.assertEqual(task['status'],'needs_attention');self.assertEqual(task['verification']['status'],'failed')
        self.assertFalse((self.root/'missing.md').exists())
    async def test_verification_feedback_recovers_before_final_answer(self):
        (self.root/'evidence.txt').write_text('RECOVERY-MARKER')
        calls=0
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='Done without inspecting')
            if calls==2:
                self.assertIn('Controller verification found unfinished work',body['messages'][-1]['content'])
                return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='evidence.txt')))])
            return dict(role='assistant',content='Observed RECOVERY-MARKER')
        with patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect files evidence.txt',successCriteria=[dict(kind='tool_contains',tool='read_file',value='RECOVERY-MARKER')]))
        self.assertEqual(calls,3);self.assertEqual(task['status'],'completed');self.assertEqual(task['verification']['status'],'passed')
    async def test_sync_preserves_read_only_policy(self):
        await self.service.dispatch('agent-save',{**self.agent,'reviewPolicy':'Read only'})
        saved=self.service.sync.payload()['collections']['agentProfiles'][0]
        self.service.sync.validate('agentProfiles',saved);self.assertEqual(saved['reviewPolicy'],'Read only')
    async def test_writable_skill_evaluation_keeps_original_files_untouched(self):
        (self.root/'original.txt').write_text('ORIGINAL')
        candidate=await self.service.dispatch('skill-propose',dict(name='Writing procedure',content='Write verified report.md.'))
        async def stream(endpoint,body,emit):
            if body['messages'][-1]['role']=='tool':return dict(role='assistant',content='Saved report')
            return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='write_file',arguments=dict(path='report.md',content='EVALUATED')))])
        with patch('wixal.agent.stream_chat',stream):
            result=await self.service.dispatch('skill-evaluate',dict(id=candidate['id'],agentID='coder',cases=[dict(prompt='Write files report.md',successCriteria=[dict(kind='file_contains',path='report.md',value='EVALUATED')])]))
        self.assertEqual(result['status'],'passed');self.assertFalse((self.root/'report.md').exists());self.assertEqual((self.root/'original.txt').read_text(),'ORIGINAL')
        baseline=result['cases'][0]['baseline']['isolatedRoot'];proposed=result['cases'][0]['candidate']['isolatedRoot'];self.assertNotEqual(baseline,proposed)
        self.assertEqual((Path(proposed)/'report.md').read_text(),'EVALUATED')
    async def test_recheck_recovers_verified_task_status_without_repeating_model(self):
        context,_=self.scripted([],'Report saved')
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Save report',successCriteria=[dict(kind='file_contains',path='report.md',value='FIXED')]))
        self.assertEqual(task['status'],'needs_attention');(self.root/'report.md').write_text('FIXED')
        report=await self.service.dispatch('agent-verify',dict(id=task['id']))
        self.assertEqual(report['status'],'passed');self.assertEqual(task['status'],'completed');self.assertNotIn('error',task)
    async def test_recheck_uses_frozen_scoped_command_authority(self):
        command='echo SCOPE-CHECK'
        await self.service.dispatch('agent-save',{**self.agent,'authority':dict(commands=[command])})
        self.accept=False
        context,_=self.scripted([],'Verified the scoped command')
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect project',successCriteria=[dict(kind='command_exit',command=command)]))
        self.assertEqual(task['verification']['status'],'passed')
        report=await self.service.dispatch('agent-verify',dict(id=task['id']))
        self.assertEqual(report['status'],'passed');self.assertIsNone(profile.get())
    async def test_small_context_progressively_loads_schemas_without_changing_user_input(self):
        from wixal.context_policy import token_estimate
        token=profile.set(self.agent)
        try:
            agent=self.service.agent;agent.model_info=dict(name='fixture',capabilities=['tools','thinking']);agent.effective_context=lambda:4096
            session=self.service.store.session();content='Inspect the authorised website security simulation.';session['messages']=[dict(role='user',content=content)]
            body=agent.request_body(session,supports_tools=True)
            self.assertEqual(body['messages'][-1]['content'],content)
            self.assertIn('workspace_info',{t['function']['name'] for t in body['tools']})
            self.assertLessEqual(token_estimate(body['messages'],body.get('tools',[]))[0]+body['options']['num_predict'],4096)
        finally:profile.reset(token)
    async def test_numeric_json_check_records_hash_and_actual(self):
        context,_=self.scripted([('write_file',dict(path='total.json',content='{"total":21}'))])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Write files total.json',successCriteria=[dict(kind='json_equals',path='total.json',pointer='/total',value=21)]))
        self.assertEqual(task['verification']['status'],'passed');self.assertEqual(task['verification']['checks'][0]['actual'],21)
        self.assertEqual(len(task['verification']['checks'][0]['sha256']),64)
    async def test_context_fallback_keeps_pending_inspection_and_lifecycle(self):
        from wixal.context_policy import fit_request,token_estimate
        agent=self.service.agent;agent.model_info=dict(name='fixture',capabilities=['tools']);agent.effective_context=lambda:8192
        agent.selected_tools={'workspace_info','network_discover','network_scan','network_read','network_stop','addon_catalog'}
        await self.service.dispatch('settings',dict(enabledTools=sorted(agent.selected_tools)))
        session=self.service.store.session();prompt='Discover TCP ports on 127.0.0.1 and then inspect only the discovered ports.'
        session['messages']=[dict(role='user',content=prompt),dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments={'session_id':'owned-source'}))]),dict(role='tool',tool_name='network_read',content='Completed owned discovery')]
        self.service.store.data['tasks'].append(dict(id='current-chain',sessionId=session['id'],status='running',prompt=prompt,checkpoints=[dict(name='network_read',status='finished',result=json.dumps(dict(session_id='owned-source',state='completed',structuredResult=dict(handoffEligible=True))))]))
        def pressured(messages,definitions,limit,reserve):
            if len(definitions)>4:raise ValueError('Controlled schema-pressure regression')
            return fit_request(messages,definitions,limit,reserve)
        with patch('wixal.agent.fit_request',pressured):body=agent.request_body(session,supports_tools=True)
        names={tool['function']['name'] for tool in body['tools']}
        self.assertTrue({'network_scan','network_read','network_stop','workspace_info'}<=names)
        self.assertLessEqual(token_estimate(body['messages'],body['tools'])[0]+body['options']['num_predict'],8192)
        self.assertEqual(self.service.store.data['tasks'][-1]['checkpoints'][0]['name'],'network_read')
    async def test_completed_without_checks_is_explicitly_unverified(self):
        context,_=self.scripted([])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Explain the project'))
        self.assertEqual(task['status'],'completed');self.assertEqual(task['verification']['status'],'unverified')
    async def test_verifier_checks_command_exit_not_final_claim(self):
        context,_=self.scripted([],'Everything passes')
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Test project',successCriteria=[dict(kind='command_exit',command='exit 7')]))
        self.assertEqual(task['status'],'needs_attention');self.assertEqual(task['verification']['checks'][0]['evidence']['exitCode'],7)
    async def test_verifier_independently_runs_project_test(self):
        (self.root/'verify.py').write_text("from pathlib import Path\nassert Path('actual.txt').read_text()=='observed'\nprint('REAL CHECK PASSED')\n")
        context,_=self.scripted([('write_file',dict(path='actual.txt',content='observed'))])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Write files actual.txt',successCriteria=[dict(kind='command_exit',command='python3 verify.py')]))
        self.assertEqual(task['verification']['status'],'passed');self.assertIn('REAL CHECK PASSED',task['verification']['checks'][0]['evidence']['output'])
    async def test_verifier_refuses_escape_and_symlink(self):
        with self.assertRaises(ValueError):await self.service.dispatch('agent-save',{**self.agent,'successCriteria':[dict(kind='file_exists',path='../outside')]})
        outside=self.base/'outside';outside.write_text('private');(self.root/'escape').symlink_to(outside)
        context,_=self.scripted([])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Check files',successCriteria=[dict(kind='file_exists',path='escape')]))
        self.assertEqual(task['verification']['status'],'failed')
    async def test_unresolved_tool_error_cannot_be_claimed_complete(self):
        context,_=self.scripted([('read_file',dict(path='missing.txt'))],'All done')
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Read files missing.txt'))
        self.assertEqual(task['status'],'needs_attention');self.assertTrue(task['verification']['unresolved'])
    async def test_live_agent_chooses_tools_with_empty_legacy_switches(self):
        (self.root/'evidence.txt').write_text('ACTUAL LIVE EVIDENCE')
        context,_=self.scripted([('read_file',dict(path='evidence.txt'))])
        with context:task=await self.service.dispatch('chat',dict(text='Read project files evidence.txt'))
        self.assertEqual(task['checkpoints'][0]['status'],'finished');self.assertIn('ACTUAL LIVE EVIDENCE',task['checkpoints'][0]['result'])
        self.assertEqual(self.service.store.data['enabledTools'],[])
    async def test_scoped_background_write_and_verification(self):
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Approved report',agentID='coder',prompt='Write files report.md',timing='Every hour',authority=dict(writePaths=['report.md']),successCriteria=[dict(kind='file_contains',path='report.md',value='APPROVED')]))
        schedule['nextRun']=now()-1000;self.accept=False
        context,_=self.scripted([('write_file',dict(path='report.md',content='APPROVED'))])
        with context:await run_due(self.service,True)
        self.assertEqual((self.root/'report.md').read_text(),'APPROVED');self.assertEqual(schedule['lastRun']['verification']['status'],'passed')
    async def test_scoped_background_cannot_write_neighbour(self):
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Scoped',agentID='coder',prompt='Write files secret.md',timing='Every hour',authority=dict(writePaths=['report.md'])))
        schedule['nextRun']=now()-1000
        context,_=self.scripted([('write_file',dict(path='secret.md',content='OUTSIDE'))])
        with context:await run_due(self.service,True)
        self.assertFalse((self.root/'secret.md').exists());self.assertEqual(schedule['lastRun']['status'],'paused')
    async def test_scoped_background_exact_test_command(self):
        command='python3 -c "print(12345)"'
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Run approved test',agentID='coder',prompt='Inspect files',timing='Every hour',authority=dict(commands=[command]),successCriteria=[dict(kind='command_exit',command=command)]))
        schedule['nextRun']=now()-1000
        context,_=self.scripted([])
        with context:await run_due(self.service,True)
        self.assertEqual(schedule['lastRun']['verification']['status'],'passed')
    async def test_scope_rejects_outside_target_before_network_call(self):
        saved=await self.service.dispatch('agent-save',{**self.agent,'restrictTargets':True,'authority':dict(targets=['http://127.0.0.1:9001'])})
        token=profile.set(saved)
        try:
            with self.assertRaisesRegex(ValueError,'outside'):await self.service.tools.execute('http_request',dict(url='http://127.0.0.1:9002'),self.service.store.session()['id'])
            with self.assertRaisesRegex(ValueError,'exact approved'):await self.service.tools.execute('run_command',dict(command='curl http://outside.test'),self.service.store.session()['id'])
        finally:profile.reset(token)
    async def test_time_budget_pauses_and_preserves_task(self):
        saved=await self.service.dispatch('agent-save',{**self.agent,'timeoutSeconds':10})
        # Exercise cancellation through the actual timeout mechanism with a shorter frozen profile in this regression.
        saved['timeoutSeconds']=0.03
        async def wait(*args):await asyncio.Event().wait()
        with patch('wixal.agent.stream_chat',wait):task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect files'))
        self.assertEqual(task['status'],'paused');self.assertIn('time budget',task['error']);self.assertIsNone(profile.get())
    async def test_resume_keeps_task_identity_and_prior_evidence(self):
        context,_=self.scripted([('read_file',dict(path='missing.txt'))])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Read files missing.txt'))
        original=task['id'];(self.root/'missing.txt').write_text('RECOVERED')
        context,_=self.scripted([('read_file',dict(path='missing.txt'))])
        with context:result=await self.service.dispatch('agent-resume',dict(id=original))
        self.assertEqual(result['id'],original);self.assertEqual(len(result['checkpoints']),2);self.assertEqual(result['status'],'completed')
    async def test_durable_queue_priority_and_no_blind_retry(self):
        low=await self.service.dispatch('agent-enqueue',dict(agentID='coder',prompt='Explain low priority',priority=-1))
        high=await self.service.dispatch('agent-enqueue',dict(agentID='coder',prompt='Explain high priority',priority=2))
        context,_=self.scripted([])
        with context:self.assertTrue(await run_next(self.service))
        self.assertEqual(high['status'],'completed');self.assertEqual(low['status'],'queued')
        await self.service.dispatch('agent-job-cancel',dict(id=low['id']));self.assertFalse(await run_next(self.service))
    async def test_workflow_blocks_after_failed_outcome(self):
        flow=await self.service.dispatch('workflow-save',dict(name='Verified stages',stages=[dict(id='one',name='Produce',agentID='coder',goal='Return report',successCriteria=[dict(kind='file_exists',path='missing.md')]),dict(id='two',name='Use report',agentID='coder',goal='Use report')]))
        context,_=self.scripted([])
        with context:run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['status'],'needs_attention');self.assertEqual(len(run['stages']),1)
    async def test_graph_cycles_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'cycle'):await self.service.dispatch('workflow-save',dict(name='Cycle',execution='Dependency graph',stages=[dict(id='one',name='One',agentID='coder',goal='Inspect',dependsOn=['two']),dict(id='two',name='Two',agentID='coder',goal='Inspect',dependsOn=['one'])]))
    async def test_parallel_graph_uses_isolated_sessions_and_dependency_evidence(self):
        flow=await self.service.dispatch('workflow-save',dict(name='Parallel inspection',execution='Dependency graph',stages=[dict(id='one',name='One',agentID='coder',goal='Inspect files'),dict(id='two',name='Two',agentID='coder',goal='Inspect files'),dict(id='join',name='Join',agentID='coder',goal='Summarise',dependsOn=['one','two'])]))
        original=self.service.store.data['activeSession'];inflight=0;maximum=0
        async def stream(endpoint,body,emit):
            nonlocal inflight,maximum
            inflight+=1;maximum=max(maximum,inflight);await asyncio.sleep(.03);inflight-=1
            return dict(role='assistant',content='SOURCE-EVIDENCE')
        with patch('wixal.agent.stream_chat',stream):run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['status'],'completed');self.assertEqual(maximum,2);self.assertEqual(len(run['stages']),3)
        self.assertEqual(self.service.store.data['activeSession'],original);self.assertEqual(len({s['childId'] for s in run['stages']}),3)
    async def test_graph_conditional_stage_skips_unverified_dependency(self):
        flow=await self.service.dispatch('workflow-save',dict(name='Conditional',execution='Dependency graph',stages=[dict(id='one',name='One',agentID='coder',goal='Inspect files'),dict(id='two',name='Two',agentID='coder',goal='Inspect files',dependsOn=['one'],condition='dependencies_verified')]))
        context,_=self.scripted([])
        with context:run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['stages'][-1]['status'],'skipped')
    async def test_backup_roundtrip_retains_agents_workflows_and_pauses_authority(self):
        await self.service.dispatch('agent-save',{**self.agent,'authority':dict(writePaths=['report.md']), 'privateNotes':'PRIVATE AGENT NOTES'})
        flow=await self.service.dispatch('workflow-save',dict(name='Saved flow',stages=[dict(name='Inspect',agentID='coder',goal='Inspect files')]))
        routine=await self.service.dispatch('agent-schedule-save',dict(name='Calendar routine',agentID='coder',workflowID=flow['id'],prompt='Inspect files',timing='Every weekday',time='09:00',authority=dict(writePaths=['report.md'])))
        backup=self.base/'backup.json';await self.service.dispatch('workspace-backup',dict(path=str(backup)))
        dest=Store(self.base/'import');
        try:
            from wixal.migration import import_workspace
            preview=import_workspace(dest,backup,preview=True,preserve_preferences=True)
            result=import_workspace(dest,backup,preserve_preferences=True,expected_digest=preview['digest'])
            self.assertEqual(result['counts']['agentProfiles'],1);self.assertEqual(result['counts']['agentWorkflows'],1);self.assertEqual(result['counts']['schedules'],1)
            self.assertEqual(dest.data['agentProfiles'][0]['privateNotes'],'PRIVATE AGENT NOTES');self.assertEqual(dest.data['agentProfiles'][0]['authority'],{})
            self.assertFalse(dest.data['schedules'][0]['enabled']);self.assertEqual(dest.data['schedules'][0]['authority'],{})
            second=import_workspace(dest,backup,preserve_preferences=True);self.assertEqual(second['counts']['agentProfiles'],0)
        finally:dest.close()
    async def test_sync_transfers_definitions_without_action_authority(self):
        await self.service.dispatch('agent-save',{**self.agent,'authority':dict(commands=['echo secret']), 'reviewPolicy':'Pre-approved actions'})
        payload=self.service.sync.payload();saved=payload['collections']['agentProfiles'][0]
        self.assertNotIn('authority',saved);self.assertEqual(saved['reviewPolicy'],'Review actions')
        self.service.sync.validate('agentProfiles',saved);self.assertEqual(saved['reviewPolicy'],'Review actions')
    async def test_skill_candidate_requires_repeated_checked_evaluation(self):
        candidate=await self.service.dispatch('skill-propose',dict(name='Evidence procedure',content='Read evidence.txt and preserve the marker.'))
        with self.assertRaisesRegex(ValueError,'two passing'):await self.service.dispatch('skill-promote',dict(id=candidate['id']))
        readonly=await self.service.dispatch('agent-save',{**self.agent,'id':'reader','reviewPolicy':'Read only'})
        (self.root/'evidence.txt').write_text('SOURCE-MARKER')
        async def stream(endpoint,body,emit):
            if body['messages'][-1]['role']=='tool':return dict(role='assistant',content='Observed SOURCE-MARKER')
            return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='evidence.txt')))])
        params=dict(id=candidate['id'],agentID=readonly['id'],cases=[dict(prompt='Read files evidence.txt',successCriteria=[dict(kind='tool_contains',tool='read_file',value='SOURCE-MARKER')])])
        with patch('wixal.agent.stream_chat',stream):
            first=await self.service.dispatch('skill-evaluate',params);second=await self.service.dispatch('skill-evaluate',params)
        self.assertEqual(first['status'],'passed');self.assertEqual(second['status'],'passed')
        skill=await self.service.dispatch('skill-promote',dict(id=candidate['id']));self.assertEqual(len(skill['evaluationIds']),2)
        token=profile.set(self.agent)
        try:await self.service.agents.tool('skill_manage',dict(action='update',name=skill['name'],content='New reviewed procedure'))
        finally:profile.reset(token)
        restored=await self.service.dispatch('skill-rollback',dict(id=skill['id']));self.assertEqual(restored['content'],candidate['content'])
    async def test_model_can_update_and_delete_its_calendar_routine(self):
        token=profile.set(self.agent)
        try:
            routine=await self.service.agents.tool('schedule_manage',dict(action='create',name='Owned routine',prompt='Read files',timing='daily',time='09:00'))
            updated=await self.service.agents.tool('schedule_manage',dict(action='update',id=routine['id'],time='10:30'))
            self.assertEqual(updated['time'],'10:30')
            result=await self.service.agents.tool('schedule_manage',dict(action='delete',id=routine['id']));self.assertTrue(result['deleted'])
            self.assertFalse(self.service.store.data['schedules'])
        finally:profile.reset(token)

class SecurityObservationTests(unittest.TestCase):
    def test_completed_network_xml_observations_are_deduplicated_without_exploit_claims(self):
        from wixal.security_evidence import capture
        task=dict(checkpoints=[dict(name='network_scan',arguments=dict(target='127.0.0.1'),result='{"session_id":"scan1"}')])
        output='<nmaprun><host><address addr="127.0.0.1"/><ports><port protocol="tcp" portid="8021"><state state="open" reason="syn-ack"/><service name="http"/></port></ports></host></nmaprun>'
        result=dict(session_id='scan1',state='completed',exitCode=0,output=output,offset=0,more=False)
        capture(task,'network_read',{},result);capture(task,'network_read',{},result)
        self.assertEqual(len(task['securityFindings']),1);self.assertEqual(task['securityFindings'][0]['observations'],2)
        self.assertFalse(task['securityFindings'][0]['verifiedExploit']);self.assertEqual(task['securityEvidence'][0]['target'],'127.0.0.1')
        self.assertEqual(task['securityEvidence'][0]['summary']['openPorts'],1)
    def test_incomplete_network_scan_is_not_structured_success(self):
        from wixal.security_evidence import capture
        task={};capture(task,'network_read',{},dict(state='running',output='<nmaprun>'))
        self.assertNotIn('securityEvidence',task)

class AuthorityTests(unittest.TestCase):
    def test_cidr_and_origins_do_not_expand_to_other_ports_or_hosts(self):
        self.assertTrue(target_allowed('192.168.10.5',['192.168.10.0/24']))
        self.assertFalse(target_allowed('192.168.11.5',['192.168.10.0/24']))
        self.assertTrue(target_allowed('http://localhost:9010/path',['http://localhost:9010']))
        self.assertFalse(target_allowed('http://localhost:9011/path',['http://localhost:9010']))
        self.assertFalse(target_allowed('https://lab.example.test.evil',['lab.example.test']))

class BranchAndRecoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted
    # Retain the shared fixtures without re-running inherited scenarios in discovery.
    async def test_isolated_branch_changes_require_merge_and_detect_conflicts(self):
        (self.root/'source.txt').write_text('ORIGINAL')
        flow=await self.service.dispatch('workflow-save',dict(name='Isolated change',execution='Dependency graph',stages=[dict(id='change',name='Change',agentID='coder',goal='Write files source.txt',isolation='Isolated changes',successCriteria=[dict(kind='file_contains',path='source.txt',value='BRANCH')])]))
        async def stream(endpoint,body,emit):
            if body['messages'][-1]['role']=='tool':return dict(role='assistant',content='Changed the isolated file')
            return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='write_file',arguments=dict(path='source.txt',content='BRANCH')))])
        with patch('wixal.agent.stream_chat',stream):run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['status'],'completed');self.assertEqual((self.root/'source.txt').read_text(),'ORIGINAL')
        (self.root/'source.txt').write_text('CONCURRENT CHANGE')
        with self.assertRaisesRegex(ValueError,'Merge conflict'):await self.service.dispatch('workflow-merge',dict(runId=run['id'],stageId='change'))
        self.assertEqual((self.root/'source.txt').read_text(),'CONCURRENT CHANGE')
        (self.root/'source.txt').write_text('ORIGINAL')
        result=await self.service.dispatch('workflow-merge',dict(runId=run['id'],stageId='change'))
        self.assertTrue(result['merged']);self.assertEqual((self.root/'source.txt').read_text(),'BRANCH')
    async def test_branch_merge_supports_new_directories_and_preserves_mode(self):
        import hashlib
        isolated=self.service.store.directory/'workflow-children'/'nested'/'project';isolated.mkdir(parents=True)
        (isolated/'reports').mkdir();artifact=isolated/'reports'/'check.sh';artifact.write_text('echo VERIFIED');artifact.chmod(0o755)
        run=dict(id='nested-run',owner='guest',projectId=self.service.store.data['activeProject'],definition=dict(name='Nested artifacts'),stages=[dict(id='change',name='New file',mergeStatus='pending_review',isolatedRoot=str(isolated),changes=[dict(path='reports/check.sh',before=None,after=hashlib.sha256(artifact.read_bytes()).hexdigest())])])
        self.service.store.data['workflowRuns'].append(run)
        result=await self.service.dispatch('workflow-merge',dict(runId=run['id'],stageId='change'))
        target=self.root/'reports'/'check.sh';self.assertTrue(result['merged']);self.assertEqual(target.read_text(),'echo VERIFIED');self.assertEqual(target.stat().st_mode & 0o777,0o755)
    async def test_os_sandbox_blocks_branch_command_writes_outside_copy(self):
        from wixal.tools import Tools
        clone=self.base/'clone';clone.mkdir();outside=self.base/'outside.txt'
        original=self.service.store.project()['root'];self.service.store.project()['root']=str(clone)
        token=profile.set({**self.agent,'_branchRoot':str(clone)})
        try:
            result=await self.service.tools.start_command(f"python3 -c \"from pathlib import Path; Path('{outside}').write_text('ESCAPE')\"",10,self.service.store.session()['id'])
            await self.service.tools.jobs[result['session_id']]['collector']
            outcome=await self.service.tools.read_job(dict(session_id=result['session_id'],wait_ms=0),self.service.store.session()['id'])
            self.assertNotEqual(outcome['exitCode'],0);self.assertFalse(outside.exists())
            good=await self.service.tools.start_command("python3 -c \"from pathlib import Path; Path('inside.txt').write_text('ALLOWED')\"",10,self.service.store.session()['id'])
            await self.service.tools.jobs[good['session_id']]['collector'];self.assertEqual((clone/'inside.txt').read_text(),'ALLOWED')
        finally:profile.reset(token);self.service.store.project()['root']=original
    async def test_invalid_command_array_cannot_crash_outcome_verification(self):
        context,_=self.scripted([('run_command',dict(command=['echo','OBSERVED'])),('run_command',dict(command='echo OBSERVED'))])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Run a project command'))
        self.assertEqual(task['status'],'completed');self.assertEqual(task['checkpoints'][0]['status'],'error')
        self.assertEqual(task['verification']['status'],'unverified')
    async def test_queue_retry_only_before_modifying_tool_with_backoff(self):
        job=await self.service.dispatch('agent-enqueue',dict(agentID='coder',prompt='Read files'))
        async def unavailable(*args):raise ValueError('Provider temporarily unavailable')
        with patch('wixal.agent.stream_chat',unavailable):await run_next(self.service)
        self.assertEqual(job['status'],'queued');self.assertGreater(job['notBefore'],now());self.assertTrue(job['taskId'])
        self.assertFalse(await run_next(self.service))
    async def test_tool_call_budget_pauses_without_executing_next_action(self):
        await self.service.dispatch('agent-save',{**self.agent,'maxCalls':1})
        (self.root/'one.txt').write_text('ONE');(self.root/'two.txt').write_text('TWO')
        context,_=self.scripted([('read_file',dict(path='one.txt')),('read_file',dict(path='two.txt'))])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Read files one.txt and two.txt'))
        self.assertEqual(task['status'],'paused');self.assertEqual(len(task['checkpoints']),1)
