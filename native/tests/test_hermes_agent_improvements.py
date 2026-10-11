"""Regression coverage of native adaptations; controlled decisions, real Store/tools."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch
import test_agents_runtime as fixtures
from wixal.agent import normalize_calls, ToolCallSyntaxError
from wixal.agent_context import profile, available_names
from wixal.context_policy import fit_request, token_estimate
from wixal.conversation import summarize
from wixal.task_state import execute
from wixal.outcomes import verify


class AgentImprovements(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted

    def running(self):
        task=dict(id='active-test',sessionId=self.service.store.session()['id'],status='running',checkpoints=[])
        self.service.store.data['tasks'].append(task)
        return task

    async def test_plan_persists_and_rejects_stale_or_invalid_updates_atomically(self):
        task=self.running();sid=task['sessionId'];store=self.service.store
        todos=[dict(id='read',content='Read evidence',status='in_progress')]
        plan=execute(store,'todo_list',dict(todos=todos,revision=0),sid)
        self.assertEqual(plan['revision'],1)
        self.assertEqual(execute(store,'todo_list',dict(todos=todos,revision=1),sid)['revision'],1)
        for args in (dict(todos=[],revision=0),dict(todos=todos*2,revision=1),dict(todos=[dict(id='x',content='x',status='bad')])):
            with self.assertRaises(ValueError):execute(store,'todo_list',args,sid)
        self.assertEqual(task['plan']['todos'],todos)
        persisted=json.loads(store.db.execute('SELECT value FROM state').fetchone()[0])
        self.assertEqual(persisted['tasks'][-1]['plan']['revision'],1)
        self.assertIn('Read evidence',self.service.agent.context(store.session())[0]['content'])

    async def test_pending_plan_blocks_final_success(self):
        task=self.running()
        task['plan']=dict(todos=[dict(id='missing',content='Finish requested work',status='pending')],revision=1)
        report=await verify(self.service.store,self.service.tools,task)
        self.assertEqual(report['status'],'failed')
        task['plan']['todos'][0]['status']='completed'
        self.assertEqual((await verify(self.service.store,self.service.tools,task))['status'],'unverified')

    async def test_saved_evidence_pages_exact_bytes_without_reexecution(self):
        task=self.running();content='HEAD😀'+('exact-evidence-'*3000)+'TAIL'
        task['checkpoints']=[dict(id='saved',name='write_file',status='finished',result=content)]
        chunks=[];offset=0
        while True:
            result=execute(self.service.store,'tool_result_read',dict(checkpoint_id='saved',offset=offset,max_chars=607),task['sessionId'])
            chunks.append(result['content']);offset=result['next_offset']
            if not result['more']:break
        self.assertEqual(''.join(chunks),content)
        self.assertEqual(result['sha256'],hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(execute(self.service.store,'tool_result_read',{},task['sessionId'])['checkpoints'][0]['checkpoint_id'],'saved')
        self.assertEqual(len(task['checkpoints']),1)
        with self.assertRaises(ValueError):execute(self.service.store,'tool_result_read',dict(checkpoint_id='other-task'),task['sessionId'])

    async def test_tools_require_active_task_and_cannot_read_other_session(self):
        task=self.running()
        with self.assertRaises(ValueError):execute(self.service.store,'todo_list',{},'unrelated')
        task['status']='completed'
        with self.assertRaises(ValueError):execute(self.service.store,'tool_result_read',{},task['sessionId'])

    async def test_imported_skill_support_files_are_snapshots_and_paginated(self):
        folder=self.root/'procedure';folder.mkdir();(folder/'references').mkdir()
        (folder/'SKILL.md').write_text('# Procedure\nRead references/check.md when needed.')
        support=folder/'references/check.md';support.write_text('RETAINED-SUPPORT😀'*100)
        await self.service.dispatch('skill-add',dict(path=str(folder/'SKILL.md')))
        support.write_text('CHANGED EXTERNALLY')
        sid=self.service.store.session()['id'];tools=self.service.tools
        token=profile.set(dict(reviewPolicy='Read only'))
        try:
            result=await tools.execute('load_skill',dict(name='procedure'),sid)
            self.assertEqual(result['resources'][0]['path'],'references/check.md')
            page=await tools.execute('load_skill',dict(name='procedure',resource='references/check.md',max_chars=17),sid)
            self.assertEqual(page['instructions'],'RETAINED-SUPPORT😀')
            self.assertTrue(page['more'])
            with self.assertRaises(ValueError):await tools.execute('load_skill',dict(name='procedure',resource='../SKILL.md'),sid)
        finally:profile.reset(token)

    async def test_skill_symlinks_and_empty_files_rejected(self):
        empty=self.root/'empty.md';empty.write_text('')
        with self.assertRaisesRegex(ValueError,'empty'):await self.service.dispatch('skill-add',dict(path=str(empty)))
        folder=self.root/'linked';folder.mkdir();(folder/'SKILL.md').write_text('# Linked')
        (folder/'references').symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symbolic'):await self.service.dispatch('skill-add',dict(path=str(folder/'SKILL.md')))
        self.assertEqual(self.service.store.data['skills'],[])

    async def test_skill_visibility_follows_workspace_identity(self):
        self.service.store.data['skills']=[dict(name='hidden',content='PRIVATE-PROCEDURE',owner='account:someone-else')]
        with self.assertRaises(ValueError):
            from wixal.skill_resources import load
            load(self.service.store,dict(name='hidden'))
        self.assertNotIn('PRIVATE-PROCEDURE',self.service.agent.context(self.service.store.session())[0]['content'])

    async def test_delegate_has_explicit_context_and_no_parent_private_notes_or_external_tools(self):
        await self.service.dispatch('settings',dict(mode='chat'))
        parent=self.service.store.data['activeSession'];seen=[]
        async def stream(endpoint,body,emit):
            seen.append(copy.deepcopy(body))
            names=available_names(self.service.tools,self.service.store)
            self.assertNotIn('http_request',names);self.assertNotIn('web_search',names)
            self.assertNotIn('delegate_task',names);self.assertIn('read_file',names)
            return dict(role='assistant',content='Child inspected supplied context')
        token=profile.set(dict(name='Parent',instructions='PRIVATE-PARENT-INSTRUCTIONS',privateNotes='PRIVATE-PARENT-NOTES',reviewPolicy='Review actions',memoryScope='Project only'))
        try:
            with patch('wixal.agent.stream_chat',stream):result=await self.service.delegate('Inspect a file','HANDOFF-MARKER file=evidence.txt')
            self.assertEqual(profile.get()['name'],'Parent')
        finally:profile.reset(token)
        payload=json.dumps(seen)
        self.assertIn('HANDOFF-MARKER',payload)
        self.assertNotIn('PRIVATE-PARENT-INSTRUCTIONS',payload);self.assertNotIn('PRIVATE-PARENT-NOTES',payload)
        self.assertEqual(self.service.store.data['activeSession'],parent)
        self.assertNotIn('http_request',result['tools'])

    async def test_repeated_summary_keeps_prior_decisions_and_tool_evidence(self):
        session=self.service.store.session()
        session['summary']=dict(content='User chose durable decision OLD-DECISION',messageCount=2)
        session['messages']=[dict(role='user',content='old'),dict(role='assistant',content='old'),dict(role='user',content='new'),dict(role='tool',tool_name='read_file',toolCallId='source-checkpoint',content='ACTUAL-NEW-EVIDENCE')]
        summary=await summarize(self.service.store,session,None)
        self.assertIn('OLD-DECISION',summary['content']);self.assertIn('ACTUAL-NEW-EVIDENCE',summary['content'])
        self.assertIn('source-checkpoint',summary['content']);self.assertEqual(summary['messageCount'],4)

    async def test_malformed_batch_recovers_before_any_effect(self):
        count=0
        async def stream(*args):
            nonlocal count
            count+=1
            if count==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='write_file',arguments=dict(path='unexpected',content='no'))),dict(function=dict(name='read_file',arguments='{broken'))])
            return dict(role='assistant',content='No action executed from the malformed batch.')
        with patch('wixal.agent.stream_chat',stream):task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Inspect files'))
        self.assertEqual(task['status'],'completed');self.assertFalse((self.root/'unexpected').exists())
        self.assertEqual(task['checkpoints'],[]);self.assertEqual(count,2)


class ContextCompactionTests(unittest.TestCase):
    def test_long_single_task_compacts_whole_rounds_preserving_latest_chains(self):
        messages=[dict(role='system',content='Policy'),dict(role='user',content='ORIGINAL USER GOAL')]
        for i in range(40):
            messages.extend([dict(role='assistant',content='Inspecting '+('reason '*80),tool_calls=[dict(function=dict(name='read_file',arguments=dict(path='source.py',offset=i)))]),dict(role='tool',tool_name='read_file',toolCallId='checkpoint-'+str(i),content='Result '+str(i)+' '+('data '*500))])
        original=copy.deepcopy(messages)
        fitted,reserve,_=fit_request(messages,[],4096)
        self.assertLessEqual(token_estimate(fitted,[])[0]+reserve,4096)
        self.assertEqual(messages,original)
        self.assertIn('ORIGINAL USER GOAL',json.dumps(fitted))
        self.assertTrue(any('Earlier tool rounds compacted' in m.get('content','') for m in fitted))
        self.assertEqual([m.get('toolCallId') for m in fitted if m['role']=='tool'][-2:],['checkpoint-38','checkpoint-39'])
        for i,m in enumerate(fitted):
            if m.get('tool_calls'):self.assertEqual(fitted[i+1]['role'],'tool')

    def test_malformed_arguments_are_never_accepted(self):
        for calls in (None,[{}],[dict(function=dict(name='x',arguments='[]'))],[dict(function=dict(name='x',arguments='{bad'))]):
            with self.subTest(calls=calls),self.assertRaises(ToolCallSyntaxError):normalize_calls(dict(tool_calls=calls))

class ToolSearchTests(unittest.TestCase):
    def test_keyword_search_selects_relevant_schemas_with_a_bound(self):
        from wixal.context_policy import select_tools
        def tool(name,description):return dict(type='function',function=dict(name=name,description=description,parameters=dict(type='object',properties={})))
        available=[tool('workspace_info','Discover tools')]+[tool('mcp_service_'+str(i),'Read invoices from accounting') for i in range(30)]+[tool('read_file','Read project text files')]
        chosen=select_tools(available,load_query='invoices accounting')
        self.assertEqual(len(chosen),9)
        self.assertNotIn('read_file',[t['function']['name'] for t in chosen])
        self.assertEqual([t['function']['name'] for t in select_tools(available,load_query='no_matching_capability')],['workspace_info'])

    def test_nested_plan_schema_rejects_unknown_fields(self):
        from wixal.tools import validate, DEFINITIONS
        schema=next(t['function']['parameters'] for t in DEFINITIONS if t['function']['name']=='todo_list')
        with self.assertRaisesRegex(ValueError,'Unknown tool argument'):
            validate(dict(todos=[dict(id='a',content='x',status='pending',authority='all')]),schema)

class MixedTaskSelectionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def test_named_file_repair_keeps_requested_edit_and_test_schemas(self):
        session=self.service.store.session();session['messages'].append(dict(role='user',content='Inspect bug.py and test_bug.py. Run the test, correct add, then rerun the test.'))
        token=profile.set(self.agent)
        try:
            body=self.service.agent.request_body(session,supports_tools=True)
            names={t['function']['name'] for t in body['tools']}
            self.assertTrue({'read_file','edit_file','run_command','command_read'}<=names)
            self.assertNotIn('network_scan',names)
        finally:profile.reset(token)

    async def test_pure_named_file_read_keeps_narrow_schemas(self):
        session=self.service.store.session();session['messages'].append(dict(role='user',content='Read bug.py and explain the function.'))
        token=profile.set(self.agent)
        try:
            body=self.service.agent.request_body(session,supports_tools=True)
            names={t['function']['name'] for t in body['tools']}
            self.assertIn('read_file',names);self.assertNotIn('run_command',names);self.assertNotIn('edit_file',names)
        finally:profile.reset(token)

class SourceVerificationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def test_csv_sum_is_independently_checked_and_rechecked(self):
        (self.root/'source.csv').write_text('item,value\na,3\nb,7\nc,11\n')
        (self.root/'result.json').write_text('{"total":21}')
        task=dict(id='verify-test',status='running',sessionId=self.service.store.session()['id'],checkpoints=[])
        self.service.store.data['tasks'].append(task)
        token=profile.set(self.agent)
        try:
            result=await self.service.tools.execute('verify_json',dict(path='result.json',pointer='/total',sourcePath='source.csv',sourcePointer='/value',transform='sum'),task['sessionId'])
            self.assertEqual(result['status'],'passed')
            self.assertEqual(result['checks'][0]['expected'],21)
            (self.root/'source.csv').write_text('item,value\na,22\n')
            self.assertEqual((await verify(self.service.store,self.service.tools,task))['status'],'failed')
        finally:profile.reset(token)

    async def test_invalid_source_does_not_install_impossible_criterion(self):
        (self.root/'source.csv').write_text('value\n3\n');(self.root/'result.json').write_text('{"total":3}')
        task=dict(id='bad-source',status='running',sessionId=self.service.store.session()['id'],checkpoints=[])
        self.service.store.data['tasks'].append(task)
        token=profile.set(self.agent)
        try:
            with self.assertRaisesRegex(ValueError,'CSV verification requires'):
                await self.service.tools.execute('verify_json',dict(path='result.json',pointer='/total',sourcePath='source.csv',sourcePointer='/value',transform='identity'),task['sessionId'])
            self.assertFalse(task.get('successCriteria'))
        finally:profile.reset(token)

    def test_sum_rejects_nonfinite_missing_and_boolean_values(self):
        from wixal.outcomes import source_value
        for raw in (b'[true,1]',b'["NaN"]',b'["Infinity"]',b'[null]'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):source_value(raw,'source.json','','sum')
        self.assertEqual(source_value(b'[0.1,0.2]','source.json','','sum'),0.3)

class DiscoveryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def test_successful_requested_tool_recovers_failed_schema_discovery(self):
        failed=dict(id='discovery-error',name='workspace_info',arguments=dict(tool='load_skill',category='skill'),status='error',result=json.dumps(dict(error='Invalid category',inputs={'type':'object'},toolMatch='workspace_info')))
        completed=dict(id='skill-result',name='load_skill',arguments=dict(name='proof'),status='finished',result=json.dumps(dict(instructions='ACTUAL-SKILL-EVIDENCE')))
        task=dict(sessionId=self.service.store.session()['id'],checkpoints=[failed,completed],successCriteria=[dict(kind='tool_contains',tool='load_skill',value='ACTUAL-SKILL-EVIDENCE')])
        self.assertEqual((await verify(self.service.store,self.service.tools,task))['status'],'passed')
        task['successCriteria']=[dict(kind='tool_succeeded',tool='workspace_info')]
        self.assertEqual((await verify(self.service.store,self.service.tools,task))['status'],'failed')
        task['successCriteria']=[];completed['name']='read_file'
        self.assertEqual((await verify(self.service.store,self.service.tools,task))['status'],'needs_attention')
