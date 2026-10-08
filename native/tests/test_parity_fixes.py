"""Regression tests for the 7 October native review; isolated data only."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from wixal.service import Service
from wixal.storage import Store
from wixal.account import Accounts
from wixal.conversation import estimate
from test_integrations import Vault, Firebase

class ParityFixes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.events=[]
        self.service=Service(Path(self.temp.name)/'data',Path(self.temp.name)/'runtime',lambda event,data:self.events.append((event,json.loads(json.dumps(data)))))
        self.store=self.service.store
        self.store.data['model']='plain'
        self.store.new_session()
    async def asyncTearDown(self):
        await self.service.close();self.temp.cleanup()

    async def test_account_agent_memory_and_guest_restore(self):
        firebase=Firebase();firebase.verified=True
        account=Accounts(self.store.directory,dict(apiKey='test',projectId='test'),Vault(),firebase)
        self.service.integrations.account=account
        await self.service.dispatch('global-memory-save',dict(content='guest profile'))
        await self.service.dispatch('account-sign-in',dict(email='user@example.com',password='test'))
        self.assertNotIn('guest profile',self.service.agent.context(self.store.session())[0]['content'])
        await self.service.dispatch('global-memory-save',dict(content='account profile'))
        self.assertEqual(self.store.data['globalMemory'],'guest profile')
        self.assertIn('account profile',self.service.agent.context(self.store.session())[0]['content'])
        # The legacy settings path must also respect the selected identity.
        await self.service.dispatch('settings',dict(globalMemory='account edited'))
        self.assertEqual(self.store.data['globalMemory'],'guest profile')
        await self.service.dispatch('account-sign-out',{})
        prompt=self.service.agent.context(self.store.session())[0]['content']
        self.assertIn('guest profile',prompt);self.assertNotIn('account edited',prompt)
        await self.service.dispatch('account-restore',{})
        self.assertEqual(self.store.active_memory(),'guest profile')

    async def test_plain_chat_omits_tools_and_converts_old_tool_history(self):
        self.store.session()['messages']=[dict(role='user',content='previous'),dict(role='assistant',content='',tool_calls=[dict(function=dict(name='workspace_info',arguments={}))]),dict(role='tool',tool_name='workspace_info',content='previous result')]
        captured=[]
        async def stream(endpoint,body,emit):captured.append(body);return dict(role='assistant',content='A plain reply')
        with patch.object(self.service.runtime,'catalog',AsyncMock(return_value=[dict(name='plain',capabilities=['completion'])])),patch.object(self.service.runtime,'endpoint',AsyncMock(return_value='http://127.0.0.1:1')),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Hello'))
        self.assertEqual(task['status'],'completed');self.assertNotIn('tools',captured[0])
        self.assertFalse(any(m['role']=='tool' or 'tool_calls' in m for m in captured[0]['messages']))
        info=self.store.session()['contextInfo'];self.assertEqual(info['messageCount'],len(self.store.session()['messages']))

    async def test_plain_model_cannot_execute_unsolicited_tool_calls(self):
        async def stream(*args):return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='workspace_info',arguments={}))])
        with patch.object(self.service.runtime,'catalog',AsyncMock(return_value=[dict(name='plain',capabilities=[])])),patch.object(self.service.runtime,'endpoint',AsyncMock(return_value='http://127.0.0.1:1')),patch('wixal.agent.stream_chat',stream),patch.object(self.service.tools,'execute',AsyncMock()) as execute:
            with self.assertRaisesRegex(ValueError,'No action was executed'):await self.service.dispatch('chat',dict(text='hello'))
            execute.assert_not_awaited()

    async def test_mentions_validate_and_keep_followup_tools(self):
        # Chat discovers tools automatically; model and project prerequisites still apply.
        self.store.data['mode']='chat'
        self.store.data['enabledTools']=['workspace_info','load_skill']
        with patch.object(self.service.runtime,'catalog',AsyncMock(return_value=[dict(name='plain',capabilities=[])])):
            with self.assertRaisesRegex(ValueError,'conversation only'):await self.service.dispatch('chat',dict(text='Use @workspace_info.'))
            with self.assertRaisesRegex(ValueError,'Open a project folder'):await self.service.dispatch('chat',dict(text='Use @read_file'))
        captured=[]
        async def stream(endpoint,body,emit):captured.append(body);return dict(role='assistant',content='Done')
        with patch.object(self.service.runtime,'catalog',AsyncMock(return_value=[dict(name='plain',capabilities=['tools'])])),patch.object(self.service.runtime,'endpoint',AsyncMock(return_value='http://127.0.0.1:1')),patch('wixal.agent.stream_chat',stream):
            await self.service.dispatch('chat',dict(text='Use @workspace_info, please @someone'))
        self.assertEqual({t['function']['name'] for t in captured[0]['tools']},{'workspace_info','load_skill','recall_memory'})
        self.assertIn('explicitly requested',captured[0]['messages'][0]['content'])

    async def test_readiness_does_not_depend_on_discovery_permission(self):
        self.store.data['enabledTools']=[]
        with patch('shutil.which',return_value='/fake/nmap'),patch('os.path.isfile',return_value=True),patch('os.access',return_value=True):
            result=await self.service.dispatch('security-readiness',{})
        self.assertTrue(result['installed']);self.assertFalse(result['discoveryEnabled'])

    async def test_assessment_has_progress_before_first_case_and_cancels(self):
        started=asyncio.Event()
        async def execute(*args):started.set();await asyncio.Event().wait()
        with patch.object(self.service.tools,'execute',execute):
            task=asyncio.create_task(self.service.dispatch('assessment-run',dict(name='website_simulate')))
            await started.wait()
            self.assertTrue(any(event=='assessment-progress' and data['state']=='running' for event,data in self.events))
            await self.service.dispatch('assessment-cancel',{})
            result=await task
            self.assertTrue(result['partial'])
            self.assertEqual(result['status'],'cancelled')
            self.assertEqual(self.store.data['assessmentResults'][-1]['result'],result)
        self.assertEqual(self.store.data['tasks'][-1]['status'],'cancelled')

    async def test_migration_settings_records_idempotency_and_no_secrets(self):
        legacy=dict(projects=[],sessions=[],memories=[],ui=dict(theme='forest',textSize=17,reduceMotion=True),autoSummary=False,skills=[dict(id='skill',name='Example',content='# Skill')],schedules=[dict(id='schedule',prompt='test',intervalSeconds=60,enabled=True)],mcpServers=[dict(id='mcp',name='Example',command='server',args=['--token','SECRET','--flag'],env={'KEY':'SECRET'},oauth={'token':'SECRET'})],account={'token':'SECRET'},companion={'token':'SECRET'})
        path=Path(self.temp.name)/'legacy.json';path.write_text(json.dumps(legacy))
        result=self.store.import_legacy(path)
        self.assertEqual(result['counts']['skills'],1);self.assertEqual(self.store.data['ui']['theme'],'forest');self.assertFalse(self.store.data['autoSummary'])
        self.assertFalse(self.store.data['schedules'][0]['enabled'])
        self.assertEqual(self.store.data['mcpServers'],[])
        self.assertTrue(any('credential-bearing invocation excluded' in warning for warning in result['warnings']))
        self.assertNotIn('SECRET',json.dumps(self.store.data))
        again=self.store.import_legacy(path);self.assertTrue(all(count==0 for count in again['counts'].values()))

    async def test_estimate_includes_tools_images_summary_and_latest_response(self):
        session=self.store.session();before=estimate(session,8192,self.store)
        session['messages'].append(dict(role='assistant',content='x'*400,tool_calls=[{'function':{'name':'read_file','arguments':{'path':'x'*400}}}]))
        session['messages'].append(dict(role='user',content='image',imageIds=['image']))
        session['summary']=dict(content='s'*400,messageCount=0)
        after=estimate(session,8192,self.store)
        self.assertGreater(after['estimatedTokens']-before['estimatedTokens'],1300)
        self.assertEqual(after['messageCount'],2)
