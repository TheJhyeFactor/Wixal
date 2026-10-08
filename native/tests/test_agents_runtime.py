"""Actual Wixal tools/storage with controlled model decisions; not a model benchmark."""
import asyncio
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from wixal.service import Service
from wixal.storage import Store, now
from wixal.agent_context import profile
from wixal.agents import next_calendar
from wixal.scheduling import run_due, due
from fixture_server import Fixture

PAYLOAD=Path(__file__).resolve().parents[2]/'runtime/ollama'

class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'project';self.root.mkdir()
        self.fixture=Fixture().__enter__();self.events=[];self.accept=True
        def emit(event,data):
            self.events.append((event,copy.deepcopy(data)))
            if event=='review':asyncio.create_task(self.service.dispatch('respond',dict(id=data['id'],value=self.accept)))
        self.service=Service(self.base/'data',PAYLOAD,emit,self.fixture.url)
        await self.service.dispatch('project-add',dict(root=str(self.root)))
        await self.service.dispatch('settings',dict(model='fixture',enabledTools=[]))
        self.agent=await self.service.dispatch('agent-save',dict(id='coder',name='Coder',purpose='Solve project tasks',instructions='Inspect, act and verify. Never invent results.',model='fixture',reviewPolicy='Review actions',memoryScope='Project only',skills=[]))
    async def asyncTearDown(self):
        await self.service.close();self.fixture.__exit__();self.temp.cleanup()
    def scripted(self,calls,final='Verified result'):
        index=0;seen=[]
        async def stream(endpoint,body,emit):
            nonlocal index
            seen.append(copy.deepcopy(body))
            if index<len(calls):
                name,args=calls[index];index+=1
                self.assertIn(name,[t['function']['name'] for t in body.get('tools',[])])
                return dict(role='assistant',content='',tool_calls=[dict(function=dict(name=name,arguments=args))])
            return dict(role='assistant',content=final)
        return patch('wixal.agent.stream_chat',stream),seen
    async def test_automatic_discovery_write_command_verify_and_restore(self):
        project=self.service.store.data['activeProject'];session=self.service.store.data['activeSession']
        context,seen=self.scripted([('workspace_info',dict(category='files')),('write_file',dict(path='report.txt',content='verified-output')),('workspace_info',dict(category='commands')),('run_command',dict(command="python3 -c \"from pathlib import Path; assert Path('report.txt').read_text() == 'verified-output'; print('VERIFIED')\""))])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect files and produce a verified report'))
        self.assertEqual(task['status'],'completed');self.assertEqual((self.root/'report.txt').read_text(),'verified-output')
        self.assertIn('VERIFIED',task['checkpoints'][-1]['result']);self.assertEqual(self.service.store.data['enabledTools'],[])
        self.assertEqual(self.service.store.data['activeProject'],project);self.assertEqual(self.service.store.data['activeSession'],session)
        self.assertIsNone(profile.get());self.assertTrue(any('standing instructions' in b['messages'][0]['content'] for b in seen))
        db=self.service.store.db;persisted=json.loads(db.execute('SELECT value FROM state').fetchone()[0]);self.assertEqual(persisted['tasks'][-1]['agentId'],'coder')
    async def test_read_only_rejects_hallucinated_write(self):
        readonly={**self.agent,'id':'reviewer','name':'Reviewer','reviewPolicy':'Read only'};await self.service.dispatch('agent-save',readonly)
        async def stream(*args):return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='write_file',arguments=dict(path='forbidden.txt',content='no')))])
        with patch('wixal.agent.stream_chat',stream):
            with self.assertRaises(ValueError):await self.service.dispatch('agent-run',dict(id='reviewer',prompt='Inspect project files'))
        task=self.service.store.data['tasks'][-1]
        self.assertFalse((self.root/'forbidden.txt').exists());self.assertNotEqual(task['status'],'completed')
    async def test_workflow_handoff_review_and_persistence(self):
        flow=await self.service.dispatch('workflow-save',dict(id='review-flow',name='Review and report',brief='Read evidence',stages=[dict(id='one',name='Inspect',agentID='coder',goal='Inspect project files',output='Evidence',requiresReview=False),dict(id='two',name='Report',agentID='coder',goal='Return report from previous evidence',output='Report',requiresReview=True)]))
        (self.root/'evidence.txt').write_text('SEED-EVIDENCE-42')
        responses=0;seen=[]
        async def stream(endpoint,body,emit):
            nonlocal responses
            seen.append(copy.deepcopy(body));responses+=1
            if responses==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='evidence.txt')))])
            return dict(role='assistant',content='SEED-EVIDENCE-42 with source evidence.txt')
        with patch('wixal.agent.stream_chat',stream):run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['status'],'completed');self.assertEqual(len(run['stages']),2)
        self.assertIn('SEED-EVIDENCE-42',seen[-1]['messages'][-1]['content']);self.assertTrue(any(e=='review' and d['name']=='workflow_stage' for e,d in self.events))
        persisted=json.loads(self.service.store.db.execute('SELECT value FROM state').fetchone()[0]);self.assertEqual(persisted['workflowRuns'][-1]['status'],'completed')
    async def test_workflow_decline_does_not_start_stage(self):
        self.accept=False
        flow=await self.service.dispatch('workflow-save',dict(name='Gated',stages=[dict(name='Review',agentID='coder',goal='Read files',requiresReview=True)]))
        run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['status'],'paused');self.assertFalse(run['stages']);self.assertFalse(self.service.store.data['tasks'])
    async def test_background_schedule_runs_real_read_and_does_not_replay(self):
        (self.root/'evidence.txt').write_text('SCHEDULE-EVIDENCE')
        reviewer=await self.service.dispatch('agent-save',{**self.agent,'id':'readonly','reviewPolicy':'Read only'})
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Read report',agentID=reviewer['id'],prompt='Read files and report evidence.txt',timing='Every day',time='09:00'))
        schedule['nextRun']=now()-1000
        context,_=self.scripted([('read_file',dict(path='evidence.txt'))],'SCHEDULE-EVIDENCE')
        with context:self.assertTrue(await run_due(self.service,True))
        self.assertEqual(schedule['lastRun']['status'],'completed');self.assertFalse(await run_due(self.service,True))
        task=self.service.store.data['tasks'][-1];self.assertIn('SCHEDULE-EVIDENCE',task['checkpoints'][0]['result'])
        self.assertTrue(self.service.store.data['notifications']);self.assertTrue(next(s for s in self.service.store.data['sessions'] if s['id']==task['sessionId'])['scheduledRun'])
    async def test_background_write_pauses_without_side_effect(self):
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Write report',agentID='coder',prompt='Write files report.txt',timing='Every hour'))
        schedule['nextRun']=now()-1000
        context,_=self.scripted([('write_file',dict(path='report.txt',content='unsafe-background'))])
        with context:await run_due(self.service,True)
        self.assertEqual(schedule['lastRun']['status'],'paused');self.assertFalse((self.root/'report.txt').exists())
    async def test_invalid_model_is_blocked_before_task(self):
        await self.service.dispatch('agent-save',{**self.agent,'model':'missing'})
        with self.assertRaisesRegex(ValueError,'Tools'):await self.service.dispatch('agent-run',dict(id='coder',prompt='Do work'))
        self.assertFalse(self.service.store.data['tasks']);self.assertIsNone(profile.get())
    async def test_cancel_restores_selection_and_preserves_interrupted_work(self):
        original=self.service.store.data['activeSession'];ready=asyncio.Event()
        async def wait(*args):ready.set();await asyncio.Event().wait()
        with patch('wixal.agent.stream_chat',wait):
            task=asyncio.create_task(self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect files')))
            await ready.wait();await self.service.dispatch('agent-guide',dict(id=self.service.store.data['tasks'][-1]['id'],text='Do not edit'))
            await self.service.dispatch('stop',{});await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(self.service.store.data['activeSession'],original);self.assertNotEqual(self.service.store.data['tasks'][-1]['status'],'completed')
    async def test_agent_skill_management_is_reviewed_and_versioned(self):
        token=profile.set(self.agent)
        try:
            await self.service.agents.tool('skill_manage',dict(action='create',name='report',content='# Report\nRead and verify evidence.'))
            await self.service.agents.tool('skill_manage',dict(action='update',name='report',content='# Report\nRead, calculate and verify evidence.'))
            skill=self.service.store.data['skills'][-1];self.assertEqual(len(skill['versions']),1)
            self.accept=False
            self.assertIn('declined',await self.service.agents.tool('skill_manage',dict(action='update',name='report',content='discard')))
            self.assertNotEqual(skill['content'],'discard')
        finally:profile.reset(token)
    async def test_model_routine_management_duration_and_recursion_guard(self):
        token=profile.set(self.agent)
        try:
            result=await self.service.agents.tool('schedule_manage',dict(action='create',name='Monitor',prompt='Read files',interval='2h'))
            self.assertEqual(result['intervalSeconds'],7200)
            self.service.store.session()['scheduledRun']=True
            with self.assertRaisesRegex(ValueError,'scheduled run'):await self.service.agents.tool('schedule_manage',dict(action='create',name='Nested',prompt='More',interval='1h'))
        finally:profile.reset(token)

    async def test_starter_pack_is_owned_and_idempotent(self):
        first=await self.service.dispatch('agent-starter-pack',dict(model='fixture'))
        second=await self.service.dispatch('agent-starter-pack',dict(model='fixture'))
        self.assertEqual((first['agents'],first['workflows']),(4,6));self.assertEqual(second['workflows'],0)
        self.assertEqual(len(self.service.store.data['agentWorkflows']),6)
    async def test_background_workflow_cannot_bypass_action_review(self):
        await self.service.dispatch('agent-save',{**self.agent,'reviewPolicy':'Pre-approved enabled actions'})
        flow=await self.service.dispatch('workflow-save',dict(name='Background gated actions',stages=[dict(name='Write',agentID='coder',goal='Write report.txt')]))
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Workflow routine',agentID='coder',workflowID=flow['id'],prompt='Write report.txt',timing='Every hour'))
        schedule['nextRun']=now()-1000
        context,_=self.scripted([('write_file',dict(path='report.txt',content='forbidden'))])
        with context:await run_due(self.service,True)
        self.assertEqual(schedule['lastRun']['status'],'paused');self.assertFalse((self.root/'report.txt').exists())
        task=self.service.store.data['tasks'][-1]
        self.assertTrue(next(row for row in self.service.store.data['sessions'] if row['id']==task['sessionId'])['scheduledRun'])
    async def test_workflow_failure_retains_task_and_resume_skips_completed_stage(self):
        flow=await self.service.dispatch('workflow-save',dict(name='Recoverable',stages=[dict(id='first',name='Inspect',agentID='coder',goal='Inspect files'),dict(id='second',name='Produce',agentID='coder',goal='Return result')]))
        calls=0
        async def fail_second(*args):
            nonlocal calls
            calls+=1
            if calls==2:raise ValueError('Provider unavailable')
            return dict(role='assistant',content='Retained first stage evidence')
        with patch('wixal.agent.stream_chat',fail_second):run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(run['status'],'failed');self.assertEqual(run['stages'][0]['status'],'completed')
        self.assertEqual(run['stages'][1]['error'],'Provider unavailable');self.assertTrue(run['stages'][1]['taskId'])
        completed=run['stages'][0]['taskId'];context,seen=self.scripted([],'Recovered second stage')
        with context:result=await self.service.dispatch('workflow-resume',dict(runId=run['id']))
        self.assertEqual(result['status'],'completed');self.assertEqual(result['stages'][0]['taskId'],completed);self.assertEqual(len(seen),1)
    async def test_read_only_workflow_retry_is_bounded(self):
        flow=await self.service.dispatch('workflow-save',dict(name='Retry',stages=[dict(name='Read',agentID='coder',goal='Read files',failurePolicy='Retry once, then stop')]))
        attempts=0
        async def unavailable(*args):
            nonlocal attempts
            attempts+=1;raise ValueError('Provider unavailable')
        with patch('wixal.agent.stream_chat',unavailable):run=await self.service.dispatch('workflow-run',dict(id=flow['id']))
        self.assertEqual(attempts,2);self.assertEqual(run['status'],'failed')
    async def test_restart_marks_workflow_interrupted_without_replaying(self):
        from wixal.agents import Agents
        self.service.store.data['workflowRuns'].append(dict(id='interrupted',owner='guest',status='running',stages=[dict(id='a',status='completed',result='Verified evidence')]))
        Agents(self.service)
        run=self.service.store.data['workflowRuns'][-1]
        self.assertEqual(run['status'],'interrupted');self.assertEqual(run['stages'][0]['result'],'Verified evidence');self.assertFalse(self.service.store.data['tasks'])

    async def test_manual_routine_preserves_next_due_time_and_runs_saved_project(self):
        schedule=await self.service.dispatch('agent-schedule-save',dict(name='Manual read',agentID='coder',prompt='Read files',timing='Every hour'))
        due_time=schedule['nextRun'];context,_=self.scripted([],'Real routine result')
        with context:run=await self.service.dispatch('agent-schedule-run',dict(id=schedule['id']))
        self.assertEqual(schedule['nextRun'],due_time);self.assertEqual(run['source'],'Schedule');self.assertEqual(schedule['lastRun']['status'],'completed')
        self.assertTrue(schedule['lastRun']['manual']);self.assertEqual(run['projectId'],schedule['projectId'])
    async def test_project_binding_is_enforced_before_execution(self):
        agent=await self.service.dispatch('agent-save',{**self.agent,'projectScope':'Current project only'})
        with self.assertRaisesRegex(ValueError,'bound to another project'):
            await self.service.dispatch('agent-run',dict(id=agent['id'],prompt='Inspect files',projectId='another'))
        self.assertFalse(self.service.store.data['tasks'])

    async def test_profile_registration_does_not_rebind_saved_project(self):
        saved=await self.service.dispatch('agent-save',{**self.agent,'projectScope':'Current project only'})
        bound=saved['projectId'];other=self.base/'other';other.mkdir()
        await self.service.dispatch('project-add',dict(root=str(other)))
        registered=await self.service.dispatch('agent-save',{**self.agent,'projectScope':'Current project only'})
        self.assertEqual(registered['projectId'],bound)
    async def test_model_creates_calendar_routine_with_timezone(self):
        token=profile.set(self.agent)
        try:
            row=await self.service.agents.tool('schedule_manage',dict(action='create',name='Morning report',prompt='Read files',timing='Every weekday',time='09:15',timezone='Australia/Sydney'))
            self.assertEqual(row['timing'],'Every weekday');self.assertEqual(row['time'],'09:15')
            date=datetime.fromtimestamp(row['nextRun']/1000,ZoneInfo('Australia/Sydney'));self.assertLess(date.weekday(),5);self.assertEqual((date.hour,date.minute),(9,15))
        finally:profile.reset(token)

    async def test_management_schemas_are_available_before_model_routes(self):
        context,seen=self.scripted([],'Ready')
        with context:await self.service.dispatch('agent-run',dict(id='coder',prompt='Create recurring work and retain a reusable procedure'))
        names={tool['function']['name'] for tool in seen[0]['tools']}
        self.assertTrue({'schedule_manage','skill_manage'}.issubset(names))
        self.assertIn('does not create a skill',seen[0]['messages'][0]['content'])

    async def test_calendar_alias_preserves_wall_time_over_interval(self):
        token=profile.set(self.agent)
        try:
            row=await self.service.agents.tool('schedule_manage',dict(action='create',name='Weekday report',prompt='Read files',timing='weekday',time='09:15',interval='1d',timezone='Australia/Sydney'))
            self.assertEqual(row['timing'],'Every weekday');self.assertEqual(row['time'],'09:15');self.assertNotIn('intervalSeconds',row)
        finally:profile.reset(token)
    async def test_environment_reports_actual_python3_and_schema_budget_is_progressive(self):
        import shutil
        self.assertEqual(self.service.tools.environment()['executables'].get('python3'),shutil.which('python3'))
        context,seen=self.scripted([],'Ready')
        with context:await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect authorised website security simulation'))
        names={t['function']['name'] for t in seen[0]['tools']}
        self.assertNotIn('schedule_manage',names);self.assertNotIn('skill_manage',names)

    async def test_wrong_tool_arguments_expose_schema_and_recover(self):
        context,seen=self.scripted([('list_files',dict(path='.')),('list_files',dict(directory='.'))],'Recovered inventory')
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect relevant project files'))
        self.assertEqual(task['status'],'completed');first=json.loads(task['checkpoints'][0]['result'])
        self.assertIn('directory',first['inputs']['properties']);self.assertIn('list_files',{t['function']['name'] for t in seen[1]['tools']})
        self.assertEqual(task['checkpoints'][1]['status'],'finished')
    async def test_tool_heavy_thinking_request_preserves_latest_input(self):
        from wixal.context_policy import token_estimate
        token=profile.set(self.agent)
        try:
            self.service.agent.model_info={'name':'fixture','capabilities':['tools','thinking'],'thinking':{'values':['low']}}
            self.service.agent.effective_context=lambda:8192
            session=self.service.store.session();content='Inspect authorised website security simulation. '+'Evidence '*700
            session['messages']=[dict(role='user',content=content)]
            body=self.service.agent.request_body(session,supports_tools=True)
            self.assertEqual(body['messages'][-1]['content'],content)
            self.assertEqual(body['options']['num_predict'],2048)
            self.assertLessEqual(token_estimate(body['messages'],body.get('tools',[]))[0]+body['options']['num_predict'],8192)
        finally:profile.reset(token)

class CalendarTests(unittest.TestCase):
    def test_weekday_monday_and_dst_use_sydney_wall_time(self):
        zone=ZoneInfo('Australia/Sydney');stamp=int(datetime(2026,10,2,10,tzinfo=zone).timestamp()*1000)
        value=next_calendar(dict(timing='Every weekday',time='09:00',timezone='Australia/Sydney'),stamp)
        local=datetime.fromtimestamp(value/1000,zone);self.assertEqual((local.day,local.hour),(5,9));self.assertEqual(local.utcoffset().total_seconds(),39600)
        self.assertEqual(next_calendar(dict(timing='Every Monday',time='09:00',timezone='Australia/Sydney'),stamp),value)
    def test_dst_gap_is_normalised(self):
        zone=ZoneInfo('Australia/Sydney');stamp=int(datetime(2026,10,4,0,tzinfo=zone).timestamp()*1000)
        value=next_calendar(dict(timing='Every day',time='02:30',timezone='Australia/Sydney'),stamp)
        self.assertEqual(datetime.fromtimestamp(value/1000,zone).hour,3)
    def test_calendar_latest_and_skip(self):
        zone=ZoneInfo('Australia/Sydney');stamp=int(datetime(2026,10,8,10,tzinfo=zone).timestamp()*1000)
        old=int(datetime(2026,10,5,9,tzinfo=zone).timestamp()*1000)
        row=dict(enabled=True,timing='Every weekday',time='09:00',timezone='Australia/Sydney',nextRun=old)
        self.assertFalse(due(row,stamp)['skip']);self.assertTrue(due({**row,'missedRunPolicy':'skip'},stamp)['skip'])
