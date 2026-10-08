"""Chat tool discovery with actual files, subprocesses and controller review."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_agents_runtime as fixtures
from wixal.agent_context import automatic


class ChatToolsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown = fixtures.AgentRuntimeTests.asyncTearDown
    scripted = fixtures.AgentRuntimeTests.scripted

    async def chat(self, text, calls, final='Observed the actual result'):
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        context, seen = self.scripted(calls, final)
        with context:
            task = await self.service.dispatch('chat', dict(text=text))
        self.assertEqual(self.service.store.data['enabledTools'], [])
        self.assertEqual(self.service.store.data['mode'], 'chat')
        self.assertFalse(automatic.get())
        return task, seen

    async def test_chat_reads_with_empty_legacy_switches_and_optional_mention(self):
        (self.root/'evidence.txt').write_text('ACTUAL CHAT EVIDENCE')
        task, seen = await self.chat('Read evidence.txt with @read_file', [('read_file', dict(path='evidence.txt'))])
        self.assertEqual(task['status'], 'completed')
        self.assertIn('ACTUAL CHAT EVIDENCE', task['checkpoints'][0]['result'])
        self.assertIn('read_file', [t['function']['name'] for t in seen[0]['tools']])

    async def test_chat_discovers_another_category_and_reviews_real_effects(self):
        task, seen = await self.chat('Inspect files and verify a report', [
            ('write_file', dict(path='report.txt', content='CHAT-VERIFIED')),
            ('workspace_info', dict(category='commands')),
            ('run_command', dict(command="python3 -c \"from pathlib import Path; assert Path('report.txt').read_text() == 'CHAT-VERIFIED'; print('CHAT CHECK PASSED')\"")),
        ])
        self.assertEqual((self.root/'report.txt').read_text(), 'CHAT-VERIFIED')
        self.assertEqual(task['status'], 'completed')
        self.assertIn('CHAT CHECK PASSED', task['checkpoints'][-1]['result'])
        self.assertEqual([d['name'] for e,d in self.events if e=='review'], ['write_file', 'command_start'])

    async def test_declined_chat_action_stops_tools_without_bypass(self):
        self.accept = False
        # A model may ignore the decline. The controller must block its next call.
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        calls = 0
        async def stream(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                return dict(role='assistant', content='', tool_calls=[dict(function=dict(name='write_file', arguments=dict(path=path, content='NO'))) for path in ('report.txt', 'alternate.txt')])
            return dict(role='assistant', content='The action was declined.')
        with patch('wixal.agent.stream_chat', stream):
            task = await self.service.dispatch('chat', dict(text='Write files report.txt'))
        self.assertFalse((self.root/'report.txt').exists())
        self.assertFalse((self.root/'alternate.txt').exists())
        self.assertEqual(sum(e=='review' for e,d in self.events), 1)
        self.assertEqual(task['status'], 'needs_attention')

    async def test_chat_attachment_read_and_context_inventory_ignore_switches(self):
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        (self.root/'excerpt.txt').write_text('SELECTED EXCERPT')
        result = await self.service.dispatch('tool', dict(name='read_file', arguments=dict(path='excerpt.txt')))
        self.assertEqual(result['content'], 'SELECTED EXCERPT')
        info = await self.service.dispatch('context-info', {})
        self.assertIn('workspace_info', info['selectedTools'])

    async def test_chat_missing_project_and_conversation_only_model_are_clear(self):
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        await self.service.dispatch('project-select', dict(id=None))
        with self.assertRaisesRegex(ValueError, 'Open a project folder'):
            await self.service.dispatch('chat', dict(text='Use @read_file on evidence.txt'))
        from unittest.mock import AsyncMock
        with patch.object(self.service.runtime, 'catalog', AsyncMock(return_value=[dict(name='fixture', capabilities=['completion'])])):
            with self.assertRaisesRegex(ValueError, 'conversation only'):
                await self.service.dispatch('chat', dict(text='Use @web_search'))
            context, seen = self.scripted([], 'A conversational answer')
            with context:
                task = await self.service.dispatch('chat', dict(text='Explain a concept'))
            self.assertEqual(task['status'], 'completed')
            self.assertNotIn('tools', seen[0])

    async def test_connected_mcp_is_discoverable_without_a_switch(self):
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        await self.service.dispatch('mcp-add', dict(name='Chat fixture', command=sys.executable, args=[str(Path(__file__).with_name('mcp_fixture.py'))]))
        server = self.service.store.data['mcpServers'][0]
        await self.service.dispatch('mcp-connect', dict(id=server['id']))
        name = self.service.mcp.definitions()[0]['function']['name']
        task, seen = await self.chat('Use the connected tool to echo evidence', [(name, dict(text='CONNECTED CHAT EVIDENCE'))])
        self.assertEqual(task['checkpoints'][0]['result'], 'CONNECTED CHAT EVIDENCE')
        self.assertTrue(any(e=='review' and d['name']==name for e,d in self.events))

    async def test_chat_recovers_missing_file_before_concluding(self):
        (self.root/'evidence.txt').write_text('RECOVERED CHAT EVIDENCE')
        task, seen = await self.chat('Read project files', [('read_file', dict(path='missing.txt')), ('read_file', dict(path='evidence.txt'))])
        self.assertEqual(task['status'], 'completed')
        self.assertIn('inputs', task['checkpoints'][0]['result'])

    async def test_chat_controller_feedback_recovers_before_final_answer(self):
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        (self.root/'evidence.txt').write_text('RECOVERED CHAT EVIDENCE')
        count = 0
        async def stream(endpoint, body, emit):
            nonlocal count
            count += 1
            if count in (1, 3):
                if count == 3:
                    self.assertIn('Controller verification found unfinished work', body['messages'][-1]['content'])
                return dict(role='assistant', content='', tool_calls=[dict(function=dict(name='read_file', arguments=dict(path='missing.txt' if count==1 else 'evidence.txt')))])
            return dict(role='assistant', content='Finished inspecting the evidence.')
        with patch('wixal.agent.stream_chat', stream):
            task = await self.service.dispatch('chat', dict(text='Read project files'))
        self.assertEqual(count, 4)
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['verification']['unresolved'], [])

    async def test_chat_small_context_loads_schemas_without_truncating_input(self):
        from wixal.context_policy import token_estimate
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        agent = self.service.agent
        agent.model_info = dict(name='fixture', capabilities=['tools', 'thinking'])
        agent.effective_context = lambda: 4096
        session = self.service.store.session()
        prompt = 'Inspect the authorised website security simulation.'
        session['messages'] = [dict(role='user', content=prompt)]
        body = agent.request_body(session, supports_tools=True)
        self.assertEqual(body['messages'][-1]['content'], prompt)
        self.assertIn('workspace_info', [t['function']['name'] for t in body['tools']])
        self.assertLessEqual(token_estimate(body['messages'], body['tools'])[0]+body['options']['num_predict'], 4096)

    async def test_chat_stop_during_review_keeps_files_untouched(self):
        await self.service.dispatch('settings', dict(mode='chat', enabledTools=[]))
        reviewing = asyncio.Event()
        async def wait(details):
            reviewing.set()
            await asyncio.Event().wait()
        self.service.tools.approve = wait
        context, seen = self.scripted([('write_file', dict(path='stopped.txt', content='NO'))])
        with context:
            pending = asyncio.create_task(self.service.dispatch('chat', dict(text='Write files stopped.txt')))
            await asyncio.wait_for(reviewing.wait(), 3)
            await self.service.dispatch('stop', {})
            await asyncio.gather(pending, return_exceptions=True)
        self.assertFalse((self.root/'stopped.txt').exists())
        self.assertEqual(self.service.store.data['tasks'][-1]['status'], 'paused')
        self.assertFalse(automatic.get())

    async def test_chat_command_timeout_schema_matches_execution(self):
        task, seen = await self.chat('Run a Python command', [('run_command', dict(command="python3 -c \"print('BOUNDED CHAT COMMAND')\"", timeout_seconds=10))])
        self.assertEqual(task['status'], 'completed')
        self.assertIn('BOUNDED CHAT COMMAND', task['checkpoints'][0]['result'])
        with self.assertRaisesRegex(ValueError, 'outside its bounds'):
            await self.service.dispatch('tool', dict(name='run_command', arguments=dict(command='echo no', timeout_seconds=0)))
        self.assertIn('command_start', seen[0]['messages'][0]['content'])
