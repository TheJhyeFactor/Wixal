"""Recovery boundaries with actual files, IPC dispatch and controller review."""
import unittest
import json
import test_agents_runtime as fixtures

class TaskRecoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted

    async def retained(self,prompt):
        await self.service.dispatch('settings',dict(mode='chat',enabledTools=['workspace_info','read_file','run_command','command_start','write_file']))
        (self.root/'effect-ledger.txt').write_text('ONE-EFFECT\n')
        command='python3 -c "from pathlib import Path; p=Path(\'effect-ledger.txt\'); p.write_text(p.read_text()+\'REPLAY\\n\')"'
        session=self.service.store.session()
        checkpoint=dict(id='unfinished-effect',name='run_command',arguments=dict(command=command,timeout_seconds=60),status='started',created=1)
        task=dict(id='legacy-chat-recovery',sessionId=session['id'],projectId=session['projectId'],prompt=prompt,status='interrupted',created=1,checkpoints=[checkpoint])
        self.service.store.data['tasks'].append(task);self.service.store.save()
        return task,command,session['id']

    async def test_first_chat_retry_blocks_command_alias_and_changed_timeout(self):
        task,command,source=await self.retained('Use @run_command to run the recovery command once.')
        task['checkpoints'][0]['name']='command_start'
        await self.service.dispatch('settings',dict(contextSize=4096))
        context,seen=self.scripted([('run_command',dict(command=command,timeout_seconds=200))],'The earlier command remains uncertain.')
        with context:result=await self.service.dispatch('task-start',dict(id=task['id']))
        self.assertEqual((self.root/'effect-ledger.txt').read_text(),'ONE-EFFECT\n')
        from wixal.context_policy import token_estimate
        self.assertLessEqual(token_estimate(seen[0]['messages'],seen[0].get('tools',[]))[0]+seen[0]['options']['num_predict'],4096)
        self.assertTrue(seen[0]['messages'][-1]['content'].startswith('Inspect retained evidence'))
        self.assertIn('unfinished-effect',seen[0]['messages'][0]['content'])
        self.assertEqual(task['checkpoints'][0]['sessionId'],source)
        self.assertEqual(task['checkpoints'][-1]['sessionId'],task['sessionId'])
        self.assertNotEqual(source,task['sessionId'])
        self.assertIn('Not executed: this repeats unfinished checkpoint',task['checkpoints'][-1]['result'])
        self.assertFalse(any(e=='review' for e,d in self.events))
        self.assertEqual(result['status'],'needs_attention')

    async def test_new_effect_requires_recovery_review_despite_global_bypass(self):
        task,_,_=await self.retained('Use @write_file to save recovered.txt.')
        self.service.store.project()['approvalMode']='bypass';self.service.store.save();self.accept=False
        context,_=self.scripted([('write_file',dict(path='recovered.txt',content='NEW EFFECT'))],'The new action was declined.')
        with context:await self.service.dispatch('task-start',dict(id=task['id']))
        self.assertFalse((self.root/'recovered.txt').exists())
        reviews=[d for e,d in self.events if e=='review']
        self.assertEqual([d['name'] for d in reviews],['recovery_action'])
        self.assertEqual(reviews[0]['uncertainEffects'][0]['id'],'unfinished-effect')

    async def test_read_only_inspection_remains_available(self):
        task,_,_=await self.retained('Read effect-ledger.txt with @read_file and report the retained effect. Do not change files.')
        context,_=self.scripted([('read_file',dict(path='effect-ledger.txt'))],'The ledger contains ONE-EFFECT; command completion remains unknown.')
        with context:await self.service.dispatch('task-start',dict(id=task['id']))
        self.assertIn('ONE-EFFECT',task['checkpoints'][-1]['result'])
        self.assertFalse(any(e=='review' for e,d in self.events))
        self.assertEqual((self.root/'effect-ledger.txt').read_text(),'ONE-EFFECT\n')

    async def test_preapproved_agent_cannot_bypass_uncertain_effect_review(self):
        task,_,_=await self.retained('Use @write_file to save recovered.txt.')
        agent=await self.service.dispatch('agent-save',{**self.agent,'reviewPolicy':'Pre-approved actions'})
        task.update(agentId=agent['id'],agentSnapshot=agent);self.service.store.save();self.accept=False
        context,_=self.scripted([('write_file',dict(path='recovered.txt',content='NEW EFFECT'))],'The recovery action was declined.')
        with context:await self.service.dispatch('agent-resume',dict(id=task['id']))
        self.assertFalse((self.root/'recovered.txt').exists())
        self.assertEqual([d['name'] for e,d in self.events if e=='review'],['recovery_action'])

    async def test_async_handle_without_terminal_evidence_cannot_replay(self):
        task,command,_=await self.retained('Use @run_command to run the recovery command once.')
        task['checkpoints'][0].update(name='command_start',status='finished',result=json.dumps(dict(session_id='prior-job',state='running')))
        context,_=self.scripted([('run_command',dict(command=command,timeout_seconds=200))],'The earlier job completion remains unknown.')
        with context:await self.service.dispatch('task-start',dict(id=task['id']))
        self.assertEqual((self.root/'effect-ledger.txt').read_text(),'ONE-EFFECT\n')
        self.assertIn('repeats unfinished checkpoint',task['checkpoints'][-1]['result'])
        self.assertFalse(any(e=='review' for e,d in self.events))

    async def test_completed_read_settles_only_its_matching_async_handle(self):
        from wixal.recovery import uncertain
        task,_,_=await self.retained('Read retained command evidence.')
        task['checkpoints'][0].update(name='command_start',status='finished',result=json.dumps(dict(session_id='prior-job',state='running')))
        terminal=dict(id='terminal-read',name='command_read',status='finished',result=json.dumps(dict(session_id='another-job',state='completed',exitCode=0)))
        task['checkpoints'].append(terminal)
        self.assertEqual([c['id'] for c in uncertain(task)],['unfinished-effect'])
        terminal['result']=json.dumps(dict(session_id='prior-job',state='completed',exitCode=0))
        self.assertEqual(uncertain(task),[])
