"""Controller regressions for completing agent controls and recovery.

Models are controlled here; storage, IPC dispatch and cancellation are real.
"""
import asyncio
import copy
import json
import unittest
from unittest.mock import patch
import test_agents_runtime as fixtures
from wixal.agent_jobs import run_next


class AgentControlsCompletionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown = fixtures.AgentRuntimeTests.asyncTearDown
    scripted = fixtures.AgentRuntimeTests.scripted

    async def completed(self):
        context, _ = self.scripted([])
        with context:
            task = await self.service.dispatch('agent-run', dict(id='coder', prompt='Inspect the project'))
        task['status'] = 'paused'
        return task

    async def test_resume_does_not_retag_another_conversation(self):
        task = await self.completed()
        unrelated = self.service.store.new_session()
        before = copy.deepcopy(unrelated)
        context, _ = self.scripted([])
        with context:
            result = await self.service.dispatch('agent-resume', dict(id=task['id']))
        self.assertEqual(unrelated, before)
        self.assertEqual(result['sessionId'], task['sessionId'])
        self.assertEqual(self.service.store.data['activeSession'], unrelated['id'])

    async def test_personal_resume_restores_both_project_and_session(self):
        await self.service.dispatch('project-select', dict(id=None))
        task = await self.completed()
        session = task['sessionId']
        await self.service.dispatch('project-select', dict(id=self.service.store.data['projects'][0]['id']))
        selected = self.service.store.data['activeProject']
        context, seen = self.scripted([])
        with context:
            result = await self.service.dispatch('agent-resume', dict(id=task['id']))
        self.assertIsNone(result['projectId'])
        self.assertEqual(result['sessionId'], session)
        self.assertEqual(self.service.store.data['activeProject'], selected)
        self.assertNotIn(str(self.root), seen[0]['messages'][0]['content'])

    async def test_resume_missing_project_fails_before_context_mutation(self):
        task = await self.completed()
        self.service.store.data['projects'].clear()
        before = copy.deepcopy(self.service.store.data)
        with patch('wixal.agent.stream_chat') as model:
            with self.assertRaisesRegex(ValueError, 'project'):
                await self.service.dispatch('agent-resume', dict(id=task['id']))
            model.assert_not_called()
        self.assertEqual(self.service.store.data, before)

    async def test_personal_queue_does_not_inherit_later_project(self):
        await self.service.dispatch('project-select', dict(id=None))
        job = await self.service.dispatch('agent-enqueue', dict(agentID='coder', prompt='Explain your task'))
        await self.service.dispatch('project-select', dict(id=self.service.store.data['projects'][0]['id']))
        selected = self.service.store.data['activeProject']
        context, _ = self.scripted([])
        with context:
            self.assertTrue(await run_next(self.service))
        task = self.service.agents.find('tasks', job['taskId'])
        self.assertIsNone(task['projectId'])
        self.assertEqual(self.service.store.data['activeProject'], selected)

    async def test_stale_running_identity_cannot_stop_or_guide_current_run(self):
        entered = asyncio.Event()
        async def wait(*args):
            entered.set()
            await asyncio.Event().wait()
        self.service.store.data['tasks'].append(dict(id='stale-running', owner='guest', agentId='coder', status='running'))
        with patch('wixal.agent.stream_chat', wait):
            current = asyncio.create_task(self.service.dispatch('agent-run', dict(id='coder', prompt='Wait for guidance')))
            await asyncio.wait_for(entered.wait(), 5)
            actual = self.service.store.data['tasks'][-1]
            try:
                with self.assertRaisesRegex(ValueError, 'active'):
                    await self.service.dispatch('stop', dict(taskId='stale-running'))
                with self.assertRaisesRegex(ValueError, 'active'):
                    await self.service.dispatch('agent-guide', dict(id='stale-running', text='Do not send this elsewhere'))
                self.assertFalse(current.done())
                await self.service.dispatch('agent-guide', dict(id=actual['id'], text='Use the retained evidence'))
                self.assertEqual(actual['pendingGuidance'], ['Use the retained evidence'])
                await self.service.dispatch('stop', dict(taskId=actual['id']))
            finally:
                if not current.done():
                    self.service.active.cancel()
                await asyncio.gather(current, return_exceptions=True)
            self.assertEqual(actual['status'], 'paused')

    async def test_queue_cancellation_is_durable_and_does_not_mutate_frozen_profile(self):
        job = await self.service.dispatch('agent-enqueue', dict(agentID='coder', prompt='Read later'))
        frozen = copy.deepcopy(job['profile'])
        await self.service.dispatch('agent-save', {**self.agent, 'instructions':'Changed after queueing'})
        await self.service.dispatch('agent-job-cancel', dict(id=job['id']))
        persisted = json.loads(self.service.store.db.execute('SELECT value FROM state').fetchone()[0])
        saved = next(j for j in persisted['agentJobs'] if j['id']==job['id'])
        self.assertEqual(saved['status'], 'cancelled')
        self.assertEqual(saved['profile'], frozen)
        self.assertFalse(await run_next(self.service))

    async def test_workflow_stop_targets_parent_and_rejects_stale_running_workflow(self):
        flow = await self.service.dispatch('workflow-save', dict(name='Stop acceptance', stages=[dict(name='Wait',agentID='coder',goal='Wait for inspection')]))
        self.service.store.data['workflowRuns'].append(dict(id='stale-workflow',owner='guest',status='running'))
        entered=asyncio.Event()
        async def wait(*args):
            entered.set()
            await asyncio.Event().wait()
        with patch('wixal.agent.stream_chat', wait):
            current=asyncio.create_task(self.service.dispatch('workflow-run', dict(id=flow['id'])))
            await asyncio.wait_for(entered.wait(), 5)
            run=self.service.store.data['workflowRuns'][-1]
            task=self.service.store.data['tasks'][-1]
            try:
                with self.assertRaisesRegex(ValueError,'active'):
                    await self.service.dispatch('stop',dict(runId='stale-workflow'))
                with self.assertRaisesRegex(ValueError,'parent workflow'):
                    await self.service.dispatch('stop',dict(taskId=task['id']))
                self.assertFalse(current.done())
                await self.service.dispatch('stop',dict(runId=run['id']))
            finally:
                if not current.done():self.service.active.cancel()
                await asyncio.gather(current,return_exceptions=True)
        self.assertEqual(run['status'],'interrupted')
        self.assertEqual(run['stages'][0]['taskId'],task['id'])
        self.assertIsNone(self.service.agents.active_workflow_id)
        self.assertIsNone(self.service.agent.current_task_id)

    async def test_edit_schedule_preserves_saved_project_when_selection_changes(self):
        for personal in (False,True):
            with self.subTest(personal=personal):
                await self.service.dispatch('project-select',dict(id=None if personal else self.service.store.data['projects'][0]['id']))
                routine=await self.service.dispatch('agent-schedule-save',dict(name='Original routine',agentID='coder',prompt='Read evidence',timing='Every hour',enabled=False))
                expected=routine['projectId']
                await self.service.dispatch('project-select',dict(id=self.service.store.data['projects'][0]['id'] if personal else None))
                # The native editor sends its fields without projectId.
                saved=await self.service.dispatch('agent-schedule-save',dict(id=routine['id'],name='Edited routine',agentID='coder',prompt='Read new evidence',timing='Every hour',enabled=False))
                self.assertEqual(saved['projectId'],expected)
