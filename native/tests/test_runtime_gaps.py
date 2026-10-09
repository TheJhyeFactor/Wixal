"""Real process, queue and evidence regressions from the application gap audit."""
import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import unittest
from unittest.mock import patch

import test_agents_runtime as fixtures
from wixal.outcomes import successful,verify
from wixal.nmap_results import parse
from wixal.security_evidence import capture


class RuntimeGapTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted

    async def test_output_check_uses_finished_process_evidence(self):
        session=self.service.store.session()['id'];tools=self.service.tools
        started=await tools.start_command("printf 'ACTUAL-ASYNC-EVIDENCE'",5,session)
        await tools.jobs[started['session_id']]['collector']
        finished=await tools.read_job(dict(session_id=started['session_id'],wait_ms=0),session)
        task=dict(status='completed',sessionId=session,checkpoints=[dict(id='start',name='command_start',status='finished',result=json.dumps(started)),dict(id='read',name='command_read',status='finished',result=json.dumps(finished))],successCriteria=[dict(kind='tool_contains',tool='command_start',value='ACTUAL-ASYNC-EVIDENCE')])
        result=await verify(self.service.store,tools,task)
        self.assertEqual(result['status'],'passed');self.assertEqual(result['checks'][0]['checkpointId'],'start')

    async def test_failed_and_pending_results_never_count_as_success(self):
        for key in ('state','status'):
            for status in ('failed','cancelled','interrupted','queued','running','waiting_review','needs_attention','paused'):
                with self.subTest(key=key,status=status):self.assertFalse(successful(dict(status='finished',result=json.dumps({key:status}))))
        self.assertTrue(successful(dict(status='finished',result=json.dumps(dict(state='completed',exitCode=0)))))

    async def test_output_check_does_not_accept_command_text_as_output(self):
        session=self.service.store.session()['id'];tools=self.service.tools
        result=await tools.start_command("printf 'ACTUAL'; # EXPECTED-MISSING",5,session)
        await tools.jobs[result['session_id']]['collector']
        result=await tools.read_job(dict(session_id=result['session_id'],wait_ms=0),session)
        task=dict(status='completed',sessionId=session,checkpoints=[dict(id='read',name='command_read',status='finished',result=json.dumps(result))],successCriteria=[dict(kind='tool_contains',tool='command_read',value='EXPECTED-MISSING')])
        self.assertEqual((await verify(self.service.store,tools,task))['status'],'failed')

    async def test_unicode_command_pages_always_advance(self):
        session=self.service.store.session()['id'];tools=self.service.tools
        started=await tools.start_command("printf '😀Z'",5,session)
        await tools.jobs[started['session_id']]['collector']
        first=await tools.read_job(dict(session_id=started['session_id'],wait_ms=0,max_chars=1),session)
        self.assertEqual(first['output'],'😀');self.assertEqual(first['next_offset'],2)
        second=await tools.read_job(dict(session_id=started['session_id'],wait_ms=0,max_chars=1,offset=first['next_offset']),session)
        self.assertEqual(second['output'],'Z');self.assertFalse(second['more'])
        with self.assertRaisesRegex(ValueError,'character boundary'):await tools.read_job(dict(session_id=started['session_id'],wait_ms=0,max_chars=2,offset=1),session)

    async def test_process_is_not_terminal_until_evidence_finalization(self):
        entered=asyncio.Event();release=asyncio.Event();session=self.service.store.session()['id'];tools=self.service.tools
        async def finish(job):entered.set();await release.wait();job['structuredResult']=dict(marker='FINALIZED')
        started=await tools.start_command('true',5,session,on_finished=finish)
        await asyncio.wait_for(entered.wait(),5)
        try:
            pending=await tools.read_job(dict(session_id=started['session_id'],wait_ms=0),session)
            self.assertEqual(pending['state'],'running')
        finally:release.set()
        await tools.jobs[started['session_id']]['collector']
        final=await tools.read_job(dict(session_id=started['session_id'],wait_ms=0),session)
        self.assertEqual(final['state'],'completed');self.assertEqual(final['structuredResult']['marker'],'FINALIZED')

    async def test_finalizer_failure_is_visible(self):
        async def fail(job):raise ValueError('evidence failure')
        session=self.service.store.session()['id'];tools=self.service.tools
        started=await tools.start_command('true',5,session,on_finished=fail)
        await tools.jobs[started['session_id']]['collector']
        result=await tools.read_job(dict(session_id=started['session_id'],wait_ms=0),session)
        self.assertEqual(result['state'],'failed');self.assertIn('evidence failure',result['error'])

    async def test_failed_chat_stops_its_running_process(self):
        calls=0
        async def stream(*args):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='command_start',arguments=dict(command='sleep 30')))])
            raise RuntimeError('Controlled provider disconnect')
        with patch('wixal.agent.stream_chat',stream):
            with self.assertRaisesRegex(RuntimeError,'disconnect'):await self.service.dispatch('chat',dict(text='Run a command and inspect it'))
        job=next(iter(self.service.tools.jobs.values()))
        self.assertEqual(job['state'],'stopped');self.assertIsNotNone(job['child'].returncode)
        self.assertEqual(self.service.store.data['tasks'][-1]['status'],'failed')

    async def test_timeout_stops_descendants_after_command_leader_exits(self):
        session=self.service.store.session()['id'];tools=self.service.tools
        started=await tools.start_command("python3 -c \"import subprocess; p=subprocess.Popen(['sleep','30']); print(p.pid,flush=True)\"",.3,session)
        job=tools.jobs[started['session_id']]
        try:
            await asyncio.wait_for(job['collector'],5)
            pid=int(job['output'].strip())
            for _ in range(20):
                state=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
                if not state or state.startswith('Z'):break
                await asyncio.sleep(.01)
            self.assertTrue(not state or state.startswith('Z'),f'Owned descendant remains active: {state}')
            self.assertEqual(job['state'],'stopped');self.assertEqual(job['reason'],'timeout')
        finally:
            if not job.get('groupTerminated'):
                try:os.killpg(job['child'].pid,signal.SIGKILL)
                except ProcessLookupError:pass

    async def test_completed_command_cleans_up_background_descendants(self):
        session=self.service.store.session()['id'];tools=self.service.tools
        started=await tools.start_command("python3 -c \"import subprocess; p=subprocess.Popen(['sleep','30'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True)\"",5,session)
        job=tools.jobs[started['session_id']]
        try:
            await job['collector'];pid=int(job['output'].strip())
            for _ in range(20):
                state=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
                if not state or state.startswith('Z'):break
                await asyncio.sleep(.01)
            self.assertTrue(not state or state.startswith('Z'),f'Untracked background descendant remains active: {state}')
            self.assertEqual(job['state'],'completed');self.assertEqual(job['exitCode'],0)
        finally:
            if not job.get('groupTerminated'):
                try:os.killpg(job['child'].pid,signal.SIGKILL)
                except ProcessLookupError:pass

    async def test_queue_can_be_added_and_cancelled_during_active_run(self):
        blocker=asyncio.create_task(asyncio.Event().wait());self.service.active=blocker
        try:
            job=await self.service.dispatch('agent-enqueue',dict(agentID='coder',prompt='Read evidence later'))
            await self.service.dispatch('agent-job-cancel',dict(id=job['id']))
            self.assertEqual(job['status'],'cancelled');self.assertFalse(blocker.done())
            self.assertTrue(any(e=='state' and any(j['id']==job['id'] and j['status']=='cancelled' for j in d.get('agentJobs',[])) for e,d in self.events))
        finally:blocker.cancel();await asyncio.gather(blocker,return_exceptions=True)

    async def test_stale_run_stop_cannot_cancel_current_task(self):
        self.service.store.data['tasks'].append(dict(id='old',owner='guest',status='completed'))
        blocker=asyncio.create_task(asyncio.Event().wait());self.service.active=blocker
        try:
            with self.assertRaisesRegex(ValueError,'already stopped'):await self.service.dispatch('stop',dict(taskId='old'))
            self.assertFalse(blocker.done())
        finally:blocker.cancel();await asyncio.gather(blocker,return_exceptions=True)

    async def test_resume_requires_original_conversation(self):
        context,_=self.scripted([])
        with context:task=await self.service.dispatch('agent-run',dict(id='coder',prompt='Explain the project'))
        task['status']='paused';task['sessionId']='missing-conversation'
        before=self.service.store.data['activeSession']
        with patch('wixal.agent.stream_chat') as model:
            with self.assertRaisesRegex(ValueError,'retained run conversation'):await self.service.dispatch('agent-resume',dict(id=task['id']))
            model.assert_not_called()
        self.assertEqual(self.service.store.data['activeSession'],before)

    async def test_command_project_rechecked_after_review(self):
        async def changed(details):self.service.store.project()['root']=str(self.base);return True
        with patch.object(self.service.tools,'approve',changed):
            with self.assertRaisesRegex(ValueError,'changed during review'):await self.service.tools.start_command('touch unexpected',5,self.service.store.session()['id'])
        self.assertFalse((self.base/'unexpected').exists());self.assertFalse(self.service.tools.jobs)

    @unittest.skipUnless(shutil.which('nmap'),'Nmap is required for the actual loopback scanner regression')
    async def test_async_nmap_exposes_open_port_even_when_output_is_paged(self):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
        try:
            await self.service.dispatch('settings',dict(enabledTools=['network_scan','network_read']))
            session=self.service.store.session()['id'];tools=self.service.tools
            started=await tools.execute('network_scan',dict(target='127.0.0.1',ports=str(port),profile='ports',timeout_seconds=15),session)
            await tools.jobs[started['session_id']]['collector']
            result=await tools.execute('network_read',dict(session_id=started['session_id'],wait_ms=0,max_chars=1),session)
            self.assertTrue(result['more']);self.assertEqual(result['summary']['openPorts'],1)
            self.assertEqual(result['services'][0]['port'],str(port));self.assertEqual(result['services'][0]['state'],'open')
            self.assertEqual(result['structuredResult']['coverage'],'complete')
            task={};capture(task,'network_read',{},result)
            self.assertEqual(len(task['securityFindings']),1);self.assertEqual(task['securityEvidence'][0]['target'],'127.0.0.1')
        finally:listener.close()

    def test_nmap_parser_requires_complete_successful_xml(self):
        for raw in (b'<nmaprun/>',b'<nmaprun><runstats><finished exit="error"/></runstats></nmaprun>',b'<!DOCTYPE x [<!ENTITY y "bad">]><nmaprun/>',b'<wrong/>',b'<nmaprun>'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):parse(raw)
