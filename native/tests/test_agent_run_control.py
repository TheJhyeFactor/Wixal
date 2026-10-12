"""Controller regressions use real storage/tools and controlled model responses."""
import copy
import json
import unittest
from unittest.mock import patch
import test_agents_runtime as fixtures
from wixal.run_control import RunControl, budget_notice


class RunControlTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def profile(self, **limits):
        await self.service.dispatch('agent-save',{**self.agent, **limits})

    async def test_last_turn_is_reserved_and_evidence_still_verified(self):
        await self.profile(maxTurns=2)
        (self.root/'evidence.txt').write_text('BUDGET-PROOF')
        seen=[]
        async def stream(endpoint,body,emit):
            seen.append(copy.deepcopy(body))
            if len(seen)==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='evidence.txt')))])
            return dict(role='assistant',content='BUDGET-PROOF from evidence.txt')
        with patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Read evidence.txt',successCriteria=[dict(kind='tool_contains',tool='read_file',value='BUDGET-PROOF')]))
        self.assertEqual(task['status'],'completed');self.assertEqual(task['verification']['status'],'passed')
        self.assertNotIn('tools',seen[-1]);self.assertIn('reserved conclusion turn',seen[-1]['messages'][0]['content'])
        self.assertEqual(task['runBudget']['callsUsed'],1)

    async def test_exhausted_calls_allow_conclusion_on_next_turn(self):
        await self.profile(maxCalls=1)
        (self.root/'evidence.txt').write_text('ONE-CALL')
        seen=[]
        async def stream(endpoint,body,emit):
            seen.append(copy.deepcopy(body))
            if len(seen)==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='evidence.txt')))])
            return dict(role='assistant',content='ONE-CALL')
        with patch('wixal.agent.stream_chat',stream):task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Read evidence.txt'))
        self.assertEqual(task['status'],'completed');self.assertNotIn('tools',seen[-1])
        self.assertEqual(task['runBudget']['callsRemaining'],0)

    async def test_oversized_batch_has_no_partial_effect_and_settles_all_calls(self):
        await self.profile(maxCalls=1)
        async def stream(*args):return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='write_file',arguments=dict(path=p,content='must-not-exist'))) for p in ('a.txt','b.txt')])
        with patch('wixal.agent.stream_chat',stream):task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Write a.txt and b.txt'))
        self.assertEqual(task['status'],'paused');self.assertEqual(task['runBudget']['callsUsed'],0)
        self.assertFalse((self.root/'a.txt').exists());self.assertFalse((self.root/'b.txt').exists())
        self.assertEqual(len(task['checkpoints']),2)
        self.assertTrue(all(c['result'].startswith('Not executed:') for c in task['checkpoints']))
        session=next(s for s in self.service.store.data['sessions'] if s['id']==task['sessionId'])
        calls=next(m['tool_calls'] for m in session['messages'] if m.get('tool_calls'))
        self.assertEqual({c['id'] for c in calls},{m['toolCallId'] for m in session['messages'] if m.get('role')=='tool'})

    async def test_three_identical_reads_pause_after_visible_conclusion(self):
        (self.root/'evidence.txt').write_text('UNCHANGED')
        seen=[]
        async def stream(endpoint,body,emit):
            seen.append(copy.deepcopy(body))
            if len(seen)<=3:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='evidence.txt')))])
            return dict(role='assistant',content='The repeated evidence is UNCHANGED; further work remains.')
        with patch('wixal.agent.stream_chat',stream):task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Read evidence.txt and inspect evidence'))
        self.assertEqual(task['status'],'paused');self.assertEqual(task['stopReason'],'no_progress')
        self.assertEqual(len(task['checkpoints']),3);self.assertNotIn('tools',seen[-1])
        self.assertIn('Three consecutive',seen[-1]['messages'][0]['content']);self.assertIn('UNCHANGED',task['result'])
        persisted=json.loads(self.service.store.db.execute('SELECT value FROM state').fetchone()[0])
        self.assertEqual(persisted['tasks'][-1]['stopReason'],'no_progress')

    async def test_reserved_conclusion_cannot_hide_pending_checklist(self):
        await self.profile(maxTurns=2)
        count=0
        async def stream(*args):
            nonlocal count
            count+=1
            if count==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='todo_list',arguments=dict(todos=[dict(id='work',content='Unfinished work',status='pending')],revision=0)))])
            return dict(role='assistant',content='Everything is complete')
        with patch('wixal.agent.stream_chat',stream):task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Use @todo_list to plan work'))
        self.assertEqual(task['status'],'needs_attention');self.assertEqual(task['verification']['status'],'failed')

    def test_changing_results_arguments_and_errors_reset_detector(self):
        control=RunControl(20,100)
        def row(result='a',path='x',status='finished',name='read_file'):
            return [dict(name=name,arguments=dict(path=path),result=result,status=status)]
        self.assertFalse(control.observe(row()));self.assertFalse(control.observe(row()))
        self.assertFalse(control.observe(row('b')));self.assertFalse(control.observe(row(path='y')))
        self.assertFalse(control.observe(row(status='error')));self.assertFalse(control.observe(row()))
        self.assertFalse(control.observe(row()));self.assertTrue(control.observe(row()))

    def test_polling_never_triggers_unchanged_evidence_guard(self):
        for name in ('network_read','command_read','addon_job'):
            control=RunControl(20,100)
            for _ in range(8):self.assertFalse(control.observe([dict(name=name,arguments={},result='running',status='finished')]))

    def test_warning_threshold_and_one_turn_profile(self):
        control=RunControl(10,10)
        self.assertNotIn('nearly exhausted',budget_notice(dict(runBudget=control.snapshot(7))))
        self.assertIn('nearly exhausted',budget_notice(dict(runBudget=control.snapshot(8))))
        self.assertFalse(RunControl(1,5).closing(1))
        self.assertEqual(control.snapshot(10)['turnsRemaining'],0)
