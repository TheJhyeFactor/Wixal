"""Workspace configuration and delegation boundaries, using real storage/dispatch."""
import asyncio
import copy
import json
from unittest.mock import patch
import unittest
import test_agents_runtime as fixtures
from wixal.agent_context import profile, available_names
from wixal.storage import Store
from wixal.context_policy import select_tools


class AgentWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def test_skill_task_with_reading_and_named_file_exposes_reader(self):
        selected=select_tools(self.service.tools.catalog(),'Load the audit-proof skill, then follow its procedure by reading evidence.txt.')
        self.assertIn('read_file',[t['function']['name'] for t in selected])
        self.assertIn('load_skill',[t['function']['name'] for t in selected])

    async def test_tool_groups_persist_and_block_direct_dispatch(self):
        value=dict(self.agent,toolGroups=['files','files'])
        saved=await self.service.dispatch('agent-save',value)
        self.assertEqual(saved['toolGroups'],['files'])
        token=profile.set(saved)
        try:
            names=available_names(self.service.tools,self.service.store)
            self.assertIn('read_file',names);self.assertNotIn('run_command',names)
            with self.assertRaisesRegex(ValueError,'boundary'):
                await self.service.tools.execute('run_command',dict(command='echo SHOULD-NOT-RUN'),self.service.store.session()['id'])
        finally:profile.reset(token)
        for groups in ('files',['bad'],[{}]):
            with self.assertRaises(ValueError):await self.service.dispatch('agent-save',dict(saved,toolGroups=groups))
        self.assertEqual(self.service.agents.find('agentProfiles','coder')['toolGroups'],['files'])

    async def test_empty_tool_groups_keep_planning_without_effects(self):
        saved=await self.service.dispatch('agent-save',dict(self.agent,toolGroups=[]))
        token=profile.set(saved)
        try:
            names=set(available_names(self.service.tools,self.service.store))
            self.assertEqual(names,{'workspace_info','load_skill','todo_list','tool_result_read'})
        finally:profile.reset(token)

    async def test_readiness_reports_missing_skills_and_never_qualifies_model(self):
        await self.service.dispatch('agent-save',dict(self.agent,skills=['private']))
        self.service.store.data['skills']=[dict(name='private',owner='account:other',content='private')]
        result=await self.service.dispatch('agent-readiness',dict(id='coder'))
        self.assertFalse(result['ready']);self.assertEqual(result['qualification'],'untested')
        self.assertIn('Missing: private',json.dumps(result))
        with self.assertRaisesRegex(ValueError,'Missing agent skills'):
            await self.service.dispatch('agent-run',dict(id='coder',prompt='inspect'))

    async def test_named_specialist_uses_saved_model_and_instructions_without_private_data(self):
        await self.service.dispatch('agent-save',dict(self.agent,id='reviewer',name='Reviewer',instructions='SPECIALIST-INSTRUCTIONS',privateNotes='PRIVATE-SPECIALIST-NOTE',toolGroups=['files'],reviewPolicy='Review actions'))
        seen=[]
        async def stream(endpoint,body,emit):
            seen.append(copy.deepcopy(body))
            self.assertEqual(body['model'],'fixture')
            self.assertNotIn('write_file',available_names(self.service.tools,self.service.store))
            return dict(role='assistant',content='Inspected assigned evidence')
        self.service.agent.current_task_id='parent-run'
        token=profile.set(dict(instructions='PRIVATE-PARENT',privateNotes='PRIVATE-PARENT-NOTES',reviewPolicy='Review actions',toolGroups=['files']))
        try:
            with patch('wixal.agent.stream_chat',stream):
                result=await self.service.delegate('Read evidence','EXPLICIT-HANDOFF','reviewer')
        finally:profile.reset(token);self.service.agent.current_task_id=None
        rendered=json.dumps(seen)
        self.assertIn('SPECIALIST-INSTRUCTIONS',rendered);self.assertIn('EXPLICIT-HANDOFF',rendered)
        self.assertNotIn('PRIVATE-PARENT',rendered);self.assertNotIn('PRIVATE-SPECIALIST-NOTE',rendered)
        self.assertEqual(result['agentId'],'reviewer');self.assertEqual(result['parentTaskId'],'parent-run')
        entry=self.service.store.data['agentDelegations'][-1]
        self.assertEqual(entry['status'],'completed');self.assertEqual(entry['result'],result['result'])
        self.assertEqual(entry['owner'],'guest')

    async def test_specialist_discovery_excludes_other_owner_archived_and_other_project(self):
        await self.service.dispatch('settings',dict(mode='chat'))
        profiles=self.service.store.data['agentProfiles']
        for identifier,changes in [('private',dict(owner='account:other')),('archived',dict(archived=True)),('elsewhere',dict(projectScope='Current project only',projectId='not-here'))]:
            profiles.append(dict(self.agent,id=identifier,**changes))
        result=await self.service.tools.execute('workspace_info',{},self.service.store.session()['id'])
        self.assertEqual([s['id'] for s in result['specialists']],['coder'])
        for identifier in ['private','archived','elsewhere']:
            with self.assertRaises(ValueError):await self.service.delegate('inspect','',identifier)
        self.assertEqual(self.service.store.data['agentDelegations'],[])

    async def test_cancelled_assignment_is_retained_and_parent_policy_restored(self):
        async def stream(*args):raise asyncio.CancelledError()
        policy=dict(name='Parent',reviewPolicy='Review actions')
        token=profile.set(policy)
        try:
            with patch('wixal.agent.stream_chat',stream):
                with self.assertRaises(asyncio.CancelledError):await self.service.delegate('inspect','','coder')
            self.assertEqual(profile.get(),policy)
        finally:profile.reset(token)
        self.assertEqual(self.service.store.data['agentDelegations'][-1]['status'],'cancelled')

    async def test_restarted_assignment_is_interrupted_without_replay(self):
        self.service.store.data['agentDelegations']=[dict(id='child',status='running')]
        from wixal.agents import Agents
        Agents(self.service)
        self.assertEqual(self.service.store.data['agentDelegations'][0]['status'],'interrupted')
