"""Native website parity checks against isolated disposable loopback fixtures."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.website import assess_website,bounded_request,execute_website,website_plan
from wixal.simulation import WebsiteFixture,simulate_website,simulation_markdown

class WebsiteTests(unittest.IsolatedAsyncioTestCase):
    async def test_sixteen_expected_control_observations(self):
        report=await simulate_website()
        self.assertEqual(report['summary'],dict(cases=16,expected=16,unexpected=0))
        for mode in ('vulnerable','hardened'):
            self.assertEqual(len([c for c in report['cases'] if c['fixture']==mode]),8)
        self.assertNotIn('SYNTHETIC_CANARY_ONLY',json.dumps(report))
        self.assertNotIn('lab_session',json.dumps(report))
        self.assertIn('16/16',simulation_markdown(report))
    async def test_assessment_preserves_raw_checks_and_redacts_bodies(self):
        async with WebsiteFixture(False) as fixture:
            report=await assess_website(dict(url=fixture.origin,profile='probes',max_pages=1,protected_paths=['/api/admin']),delay=0)
        ids={f['id'] for f in report['findings']}
        self.assertTrue({'frame-protection','reflection-canary','sensitive-file-exposure','open-redirect','unauthenticated-access'}.issubset(ids))
        self.assertTrue(all('body' not in r for r in report['requests']))
        self.assertTrue(all(r['url'].startswith(fixture.origin) for r in report['requests']))
        self.assertNotIn('SYNTHETIC_CANARY_ONLY',json.dumps(report))
        self.assertTrue(any(f['confidence']=='reflection observed; execution unverified' for f in report['findings']))
    async def test_hardened_control_false_positives_absent(self):
        async with WebsiteFixture(True) as fixture:
            report=await assess_website(dict(url=fixture.origin,profile='probes',max_pages=1,protected_paths=['/api/admin']),delay=0)
        self.assertEqual(report['findings'],[])
        self.assertEqual(report['summary']['errors'],0)
    async def test_optional_browser_probe_owner_and_cleanup(self):
        calls=[]
        async def browser(url):
            calls.append(url)
            # Independent HTTP observation mimics visible markup, not proof of execution.
            r=await bounded_request(url)
            text='WIXAL_XSS_EXECUTED' if '<script>' in r['body'] else '<script>escaped</script>'
            return dict(text=text)
        report=await simulate_website(browser_probe=browser)
        self.assertEqual(report['summary']['cases'],18)
        self.assertEqual(report['summary']['expected'],18)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(url.startswith('http://127.0.0.1:') for url in calls))
    async def test_cancel_closes_fixture_and_rejects_reuse(self):
        created=[];original=WebsiteFixture
        def factory(hardened):
            fixture=original(hardened);created.append(fixture);return fixture
        blocked=asyncio.Event()
        async def browser(url): blocked.set();await asyncio.Event().wait()
        with patch('wixal.simulation.WebsiteFixture',factory):
            task=asyncio.create_task(simulate_website(browser_probe=browser))
            await blocked.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertFalse(created[0].server.is_serving())
        self.assertFalse(created[0].writers)
        self.assertFalse(created[0].tasks)
        self.assertEqual(created[0].token,'')
        with self.assertRaises(OSError): await bounded_request(created[0].origin+'/api/admin')
    async def test_reviewed_save_unique_prefix_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            class Store:
                def project(self): return dict(root=directory)
            class Tools:
                store=Store();host=None
                def emit(self,*args): pass
                async def approve(self,details): return True
            result=await execute_website(Tools(),'website_simulate',{'report_prefix':'checked'},'owner')
            self.assertEqual(result['summary']['expected'],16)
            self.assertTrue(result['saved'])
            report=json.loads(Path(directory,'checked.json').read_text())
            self.assertEqual(report['target'],'disposable loopback fixtures')
            before=Path(directory,'checked.json').read_bytes()
            with self.assertRaises(ValueError): await execute_website(Tools(),'website_simulate',{'report_prefix':'checked'},'owner')
            self.assertEqual(Path(directory,'checked.json').read_bytes(),before)
            with self.assertRaises(ValueError): await execute_website(Tools(),'website_simulate',{'report_prefix':'../outside'},'owner')
    async def test_declined_assessment_makes_no_requests(self):
        class Tools:
            async def approve(self,details): return False
        with patch('wixal.website.bounded_request',side_effect=AssertionError('Must not request')):
            result=await execute_website(Tools(),'website_assess',{'url':'https://example.invalid/'},'owner')
        self.assertIn('declined',result)
    def test_scoped_validation(self):
        for bad in ('file:///tmp/test','https://user:password@example.com','https://example.com/?a=1','https://example.com/#fragment'):
            with self.assertRaises(ValueError): website_plan({'url':bad})
        for path in ('https://elsewhere.invalid/x','//elsewhere.invalid/x','/x?query','/x\\escaped','/x#fragment'):
            with self.assertRaises(ValueError): website_plan({'url':'https://example.com','protected_paths':[path]})
        with self.assertRaises(ValueError): website_plan({'url':'https://example.com','max_pages':True})
        self.assertEqual(website_plan({'url':'https://example.com','max_pages':1})['requestLimit'],36)

if __name__=='__main__': unittest.main()
