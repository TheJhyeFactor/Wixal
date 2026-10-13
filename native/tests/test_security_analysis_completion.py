import unittest
from unittest.mock import AsyncMock,patch
import test_security_workspace as fixtures


class AnalysisCompletionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.SecurityWorkspaceTests.asyncSetUp
    asyncTearDown=fixtures.SecurityWorkspaceTests.asyncTearDown
    wait_for=fixtures.SecurityWorkspaceTests.wait_for

    async def run_analysis(self,responses):
        self.service.ask=AsyncMock(return_value=True)
        self.service.runtime.catalog=AsyncMock(return_value=[dict(name='test',capabilities=['tools','thinking'],contextLength=16384)])
        with patch('wixal.security_workspace.stream_chat',new=AsyncMock(side_effect=responses)) as stream:
            run=await self.service.dispatch('security-run-add',dict(targetId=self.target['id'],stage='Research',capability='analysis',model='test',prompt='Describe supplied evidence and limits'))
            await self.wait_for(lambda:run['status'] in ('completed','failed'))
            return run,stream

    async def test_reasoning_only_result_gets_one_bounded_conclusion(self):
        first=dict(role='assistant',content='',thinking='Reasoning only',usage={'eval_count':2400})
        final=dict(role='assistant',content='No independent target evidence was supplied.',usage={'eval_count':12})
        run,stream=await self.run_analysis([first,final])
        self.assertEqual(run['status'],'completed');self.assertEqual(len(run['inferenceAttempts']),2)
        self.assertEqual(run['result']['analysis'],final['content'])
        self.assertFalse(stream.call_args_list[1].args[1]['think'])

    async def test_two_empty_results_fail_instead_of_claiming_completion(self):
        empty=dict(role='assistant',content='',thinking='No final answer',usage={'eval_count':2400})
        run,stream=await self.run_analysis([empty,empty])
        self.assertEqual(run['status'],'failed');self.assertEqual(stream.await_count,2)
        self.assertIn('no final analysis',run['error']);self.assertEqual(run['result']['analysis'],'')

    async def test_analysis_tool_calls_never_execute_or_complete(self):
        response=dict(role='assistant',content='Attempting a command',tool_calls=[dict(function=dict(name='run_command',arguments={}))],usage={})
        run,stream=await self.run_analysis([response])
        self.assertEqual(run['status'],'failed');self.assertEqual(stream.await_count,1)
        self.assertFalse(self.service.tools.jobs)
