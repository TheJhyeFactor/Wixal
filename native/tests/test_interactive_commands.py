import asyncio
import unittest
import test_agents_runtime as fixtures


class InteractiveCommands(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def test_real_pty_keeps_process_state_between_reviewed_inputs(self):
        tools=self.service.tools;sid=self.service.store.session()['id']
        await self.service.dispatch('settings',dict(mode='chat'))
        result=await tools.execute('command_start',dict(command="python3 -u -c 'import sys; print(sys.stdin.isatty()); x=input(); print(\"FIRST:\"+x); y=input(); print(\"SECOND:\"+x+y)'",interactive=True,timeout_seconds=10),sid)
        args=dict(session_id=result['session_id'],wait_ms=50)
        try:
            for _ in range(30):
                result=await tools.execute('command_read',args,sid)
                if 'True' in result['output']:break
            self.assertIn('True',result['output'])
            await tools.execute('command_write',dict(session_id=args['session_id'],input='one\n'),sid)
            await tools.execute('command_write',dict(session_id=args['session_id'],input='two\n'),sid)
            for _ in range(30):
                result=await tools.execute('command_read',args,sid)
                if result['state']!='running':break
            self.assertEqual(result['state'],'completed');self.assertEqual(result['exitCode'],0);self.assertIn('SECOND:onetwo',result['output'])
            self.assertNotIn('pty',tools.jobs[args['session_id']])
            with self.assertRaises(ValueError):await tools.execute('command_read',args,'another-session')
        finally:await tools.close(sid)

    async def test_declined_pty_never_creates_process(self):
        self.accept=False;await self.service.dispatch('settings',dict(mode='chat'))
        result=await self.service.tools.execute('command_start',dict(command='python3',interactive=True),self.service.store.session()['id'])
        self.assertIn('User declined',result);self.assertEqual(self.service.tools.jobs,{})

    async def test_passive_reads_report_quiet_process_without_killing_it(self):
        tools=self.service.tools;sid=self.service.store.session()['id']
        await self.service.dispatch('settings',dict(mode='chat'))
        result=await tools.execute('command_start',dict(command="python3 -u -c 'import time; print(\"ready\",flush=True); time.sleep(10)'",timeout_seconds=12),sid)
        args=dict(session_id=result['session_id'],wait_ms=50)
        try:
            for _ in range(30):
                result=await tools.execute('command_read',args,sid)
                if 'ready' in result['output']:break
            for _ in range(4):result=await tools.execute('command_read',dict(args,wait_ms=0),sid)
            self.assertEqual(result['progressState'],'no_new_output')
            self.assertEqual(result['state'],'running');self.assertFalse(tools.jobs[args['session_id']].get('groupTerminated'))
        finally:await tools.close(sid)
