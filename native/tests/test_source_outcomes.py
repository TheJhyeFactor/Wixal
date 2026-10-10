"""Independent source oracles and verification claims under production dispatch."""
import json
import unittest
from unittest.mock import patch
import test_agents_runtime as fixtures
from wixal.outcomes import criteria,json_pointer

class SourceOutcomeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted

    def source(self):
        (self.root/'source.json').write_text(json.dumps(dict(name='actual',version='1.2',scripts={'one':'test','two':'check'})))
        return [dict(kind='json_matches_source',path='report.json',pointer='/'+field,sourcePath='source.json',sourcePointer='/'+source,transform=transform) for field,source,transform in [('name','name','identity'),('version','version','identity'),('count','scripts','length')]]

    async def test_incorrect_report_cannot_be_verified_by_readback(self):
        checks=self.source()
        context,_=self.scripted([('write_file',dict(path='report.json',content='{"name":"","version":"","count":2}')),('read_file',dict(path='report.json'))],'The report was verified.')
        with context:task=await self.service.dispatch('chat',dict(text='Save a source-bound report',successCriteria=checks))
        self.assertEqual(task['status'],'needs_attention')
        self.assertEqual(task['verification']['status'],'failed')
        self.assertEqual([r['status'] for r in task['verification']['checks']],['failed','failed','passed'])
        self.assertEqual(task['verification']['checks'][0]['actual'],'')
        self.assertEqual(len(task['verification']['checks'][0]['sourceSha256']),64)

    async def test_correct_report_is_verified_against_actual_source(self):
        checks=self.source()
        context,_=self.scripted([('write_file',dict(path='report.json',content='{"name":"actual","version":"1.2","count":2}'))])
        with context:task=await self.service.dispatch('chat',dict(text='Save a source-bound report',successCriteria=checks))
        self.assertEqual(task['verification']['status'],'passed')
        self.assertEqual(task['status'],'completed')
        (self.root/'source.json').write_text('{"name":"changed","version":"1.2","scripts":{}}')
        from wixal.outcomes import verify
        report=await verify(self.service.store,self.service.tools,task)
        self.assertEqual(report['status'],'failed')

    async def test_model_source_check_is_persisted_and_rechecked_after_write(self):
        self.source()
        context,_=self.scripted([('write_file',dict(path='report.json',content='{"name":"actual"}')),('verify_json',dict(path='report.json',pointer='/name',sourcePath='source.json',sourcePointer='/name')),('write_file',dict(path='report.json',content='{"name":"wrong"}'))],'The report was verified.')
        with context:task=await self.service.dispatch('chat',dict(text='Write files and verify report.json'))
        self.assertEqual(task['verification']['status'],'failed')
        self.assertEqual(task['successCriteria'][0]['kind'],'json_matches_source')
        self.assertEqual(task['verification']['checks'][0]['actual'],'wrong')

    async def test_no_checks_cannot_support_an_artifact_verification_claim(self):
        context,_=self.scripted([('write_file',dict(path='report.json',content='{}'))],'The report was created and verified.')
        with context:task=await self.service.dispatch('chat',dict(text='Write report.json'))
        self.assertEqual(task['status'],'needs_attention')
        self.assertNotIn('created and verified',task['result'])
        self.assertIn('independent source verification did not pass',task['result'])

    async def test_honest_unverified_completion_remains_distinct(self):
        context,_=self.scripted([('write_file',dict(path='report.json',content='{}'))],'Saved the report; it is not verified.')
        with context:task=await self.service.dispatch('chat',dict(text='Write report.json'))
        self.assertEqual(task['status'],'completed')
        self.assertEqual(task['verification']['status'],'unverified')

    async def test_missing_credential_and_self_sources_fail_without_proof(self):
        await self.service.dispatch('settings',dict(mode='chat'))
        self.source();(self.root/'report.json').write_text('{"name":"actual"}')
        for source in ['missing.json','.env','report.json']:
            with self.assertRaises((ValueError,OSError)):
                await self.service.tools.execute('verify_json',dict(path='report.json',pointer='/name',sourcePath=source,sourcePointer='/name'),self.service.store.session()['id'])

class SourceSchemaTests(unittest.TestCase):
    def test_paths_and_transforms_are_bounded(self):
        for extra in [dict(sourcePath='../outside'),dict(sourcePath='/outside'),dict(transform='execute')]:
            with self.assertRaises(ValueError):criteria([{**dict(kind='json_matches_source',path='report.json',sourcePath='source.json'),**extra}])
    def test_json_pointer_preserves_empty_keys_and_rejects_negative_indices(self):
        self.assertEqual(json_pointer({'':{'a/b':5}},'//a~1b'),5)
        with self.assertRaises(ValueError):json_pointer([1,2],'/-1')
