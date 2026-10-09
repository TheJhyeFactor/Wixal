import json
import tempfile
import unittest
from pathlib import Path
from wixal.service import Service
from wixal.report_privacy import Scrubber

PAYLOAD=Path(__file__).resolve().parents[2]/'runtime/ollama'
class CommunityReportsTests(unittest.IsolatedAsyncioTestCase):
    async def test_opt_in_required_and_known_values_scrubbed(self):
        with tempfile.TemporaryDirectory() as temp:
            service=Service(temp,PAYLOAD,lambda *_:None)
            try:
                with self.assertRaisesRegex(ValueError,'Opt in'):
                    await service.dispatch('community-report-prepare',dict(observed='No consent'))
                service.store.data['account']=dict(profile=dict(name='Private Person',email='person@example.test',id='private-user-id'))
                scrub=Scrubber(service.store,'salt')
                source='Private Person person@example.test private-user-id /Users/other/private.txt https://example.test/?token=secret authorization: Bearer TOKEN_VALUE ghp_12345678901234567890 192.168.1.1 0412 345 678'
                output=scrub.text(source)
                for value in ('Private Person','person@example.test','private-user-id','/Users/other','https://example.test','TOKEN_VALUE','ghp_12345678901234567890','192.168.1.1','0412 345 678'):
                    self.assertNotIn(value,output)
                self.assertGreater(sum(scrub.result()['redactions'].values()),0)
                rows=scrub.events([dict(event='tool-result',taskId='private-task',sessionId='private-session',tool='web_search',status='failed',content='secret content',arguments=dict(query='secret query'),result='secret result')])
                encoded=json.dumps(rows)
                for value in ('private-task','private-session','secret content','secret query','secret result'):self.assertNotIn(value,encoded)
                self.assertEqual(rows[0]['tool'],'web_search')
                self.assertEqual(scrub.alias('private-task'),rows[0]['taskId'])
                self.assertNotEqual(scrub.alias('private-task'),Scrubber(service.store,'another-salt').alias('private-task'))
            finally:await service.close()
    async def test_incomplete_model_report_uses_labelled_sanitized_fallback(self):
        from unittest.mock import patch,AsyncMock
        with tempfile.TemporaryDirectory() as temp:
            service=Service(temp,PAYLOAD,lambda *_:None,'http://127.0.0.1:11434')
            try:
                service.store.data['model']='test-model';service.store.new_session()
                with patch.object(service.runtime,'catalog',AsyncMock(return_value=[dict(name='test-model',capabilities=['completion'])])), patch.object(service.runtime,'endpoint',AsyncMock(return_value='http://127.0.0.1:11434')), patch('wixal.agent.stream_chat',AsyncMock(side_effect=RuntimeError('Model response ended before completion'))):
                    result=await service.dispatch('community-report-prepare',dict(optIn=True,observed='Report from private@example.test',expected='Keep evidence'))
                self.assertEqual(result['method'],'evidence_template')
                self.assertIn('ended before completion',result['fallbackReason'])
                self.assertNotIn('private@example.test',json.dumps(result))
                self.assertIn('no cause has been established',result['body'])
            finally:await service.close()
