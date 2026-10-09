"""Durable diagnostics through production Service/Requests, with privacy bounds."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from wixal.diagnostics import Diagnostics
from wixal.service import Service
from wixal.requests import Requests

PAYLOAD=Path(__file__).resolve().parents[2]/'runtime/ollama'

class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_tool_failure_and_corrected_call_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            service=Service(temp,PAYLOAD,lambda *_:None)
            requests=Requests(service,service.emit)
            try:
                await requests.handle('desktop',dict(id='failed-call',method='tool',params=dict(name='web_search',arguments=dict(query='private query',badField='secret-token'))))
                await requests.handle('desktop',dict(id='corrected-call',method='tool',params=dict(name='workspace_info',arguments={})))
                await service.dispatch('diagnostic-ui-event',dict(event='action-select'))
                await service.dispatch('diagnostic-ui-event',dict(event='action-deselect'))
                events=(await service.dispatch('diagnostic-log',{}))['events']
                self.assertTrue(any(e['event']=='request-start' and e.get('requestId')=='failed-call' for e in events))
                self.assertTrue(any(e['event']=='response' and e.get('requestId')=='failed-call' and e.get('status')=='failed' for e in events))
                self.assertTrue(any(e['event']=='response' and e.get('requestId')=='corrected-call' and e.get('status')=='completed' for e in events))
                self.assertTrue(any(e['event']=='action-deselect' for e in events))
                encoded=json.dumps(events)
                self.assertNotIn('secret-token',encoded);self.assertNotIn('private query',encoded)
            finally:await service.close()
            reopened=Service(temp,PAYLOAD,lambda *_:None)
            try:
                events=(await reopened.dispatch('diagnostic-log',{}))['events']
                self.assertTrue(any(e.get('requestId')=='failed-call' for e in events))
                self.assertGreaterEqual(len({e['bootId'] for e in events}),2)
                self.assertEqual(os.stat(Path(temp)/'logs/engine.jsonl').st_mode&0o777,0o600)
            finally:await reopened.close()

    async def test_rotation_and_payload_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            log=Diagnostics(temp,max_bytes=1024,backups=2)
            try:
                log.event('token',dict(text='private response'))
                log.event('thinking',dict(text='private thinking'))
                log.event('tool-start',dict(id='attempt-one',name='web_search',arguments=dict(query='private query')))
                log.event('tool-result',dict(id='attempt-one',name='web_search',status='error',result=json.dumps(dict(error='Unknown tool argument secret-token'))))
                log.event('tool-start',dict(id='attempt-two',name='web_search',arguments=dict(query='private query')))
                log.event('tool-result',dict(id='attempt-two',name='web_search',status='finished',result=json.dumps(dict(text='private page'))))
                events=log.snapshot()['events']
                outcomes=[e for e in events if e['event']=='tool-result']
                self.assertEqual([e['status'] for e in outcomes],['failed','finished'])
                self.assertEqual(outcomes[0]['errorCategory'],'invalid_input')
                self.assertIn('elapsedMs',outcomes[0])
                for i in range(60):log.write('action-select',sessionId='session',index=i)
                files=list(log.directory.glob('engine.jsonl*'))
                self.assertLessEqual(len(files),3)
                self.assertTrue(all(p.stat().st_size<=1024 for p in files))
                encoded=''.join(p.read_text() for p in files)
                for secret in ('private response','private thinking','private query','private page','secret-token'):self.assertNotIn(secret,encoded)
                self.assertLessEqual(len(log.snapshot(limit=5)['events']),5)
            finally:log.close()

class BugReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_zip_handoff_integrity_privacy_and_opt_in(self):
        import hashlib
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            service=Service(temp,PAYLOAD,lambda *_:None)
            try:
                session=service.store.new_session()
                session['messages']=[dict(role='assistant',content='SENSITIVE_CHAT_MARKER_9482',thinking='private thought',attachments=[dict(base64='private image')])]
                service.store.data['account']=dict(token='private credential')
                service.store.save()
                service.emit('tool-result',dict(id='failed-action',name='web_search',status='error',result=json.dumps(dict(error='Unknown tool argument'))))
                path=Path(temp)/'report.zip'
                result=await service.dispatch('diagnostic-export',dict(path=str(path),title='Search failure',observed='Search failed then worked',expected='Show the failed attempt',steps='Ask a question'))
                self.assertEqual(path.stat().st_mode&0o777,0o600)
                self.assertFalse(result['conversationIncluded'])
                with zipfile.ZipFile(path) as archive:
                    names={Path(name).name:name for name in archive.namelist()}
                    self.assertEqual(set(names),{'report.md','events.jsonl','environment.json','codex-workflow.md','manifest.json'})
                    manifest=json.loads(archive.read(names['manifest.json']))
                    for name,info in manifest['files'].items():
                        raw=archive.read(names[name]);self.assertEqual(hashlib.sha256(raw).hexdigest(),info['sha256']);self.assertEqual(len(raw),info['bytes'])
                    raw=b''.join(archive.read(name) for name in archive.namelist()).decode()
                    for secret in ('SENSITIVE_CHAT_MARKER_9482','private thought','private image','private credential'):self.assertNotIn(secret,raw)
                    self.assertIn('invalid_input',raw);self.assertIn('Search failed then worked',raw)
                await service.dispatch('diagnostic-export',dict(path=str(path),includeConversation=True))
                with zipfile.ZipFile(path) as archive:
                    raw=b''.join(archive.read(name) for name in archive.namelist()).decode()
                    self.assertIn('SENSITIVE_CHAT_MARKER_9482',raw)
                    for secret in ('private thought','private image','private credential'):self.assertNotIn(secret,raw)
                with self.assertRaises(ValueError):await service.dispatch('diagnostic-export',dict(path=str(Path(temp)/'bad.json')))
                with self.assertRaises(ValueError):await service.dispatch('diagnostic-export',dict(path=str(path),observed='x'*12001))
            finally:await service.close()
