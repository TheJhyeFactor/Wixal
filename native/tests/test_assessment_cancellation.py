"""Cancellation under real local HTTP work, review waits and a live child process.

No inference replies are injected. The server is disposable integration workload;
these checks don't certify external target coverage or desktop button operation.
"""
import asyncio
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from wixal.service import Service
from wixal.storage import Store

class AssessmentCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'; self.root.mkdir()
        self.reviews = asyncio.Queue(); self.cases = asyncio.Queue()
        self.requests = 0
        async def serve(reader, writer):
            try:
                await reader.readuntil(b'\r\n\r\n'); self.requests += 1
                body = ('<html><a href="/next">next</a></html>').encode()
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                await writer.drain()
            finally:
                writer.close(); await writer.wait_closed()
        self.server = await asyncio.start_server(serve, '127.0.0.1', 0)
        self.url = 'http://127.0.0.1:' + str(self.server.sockets[0].getsockname()[1])
        def emit(event, data):
            if event == 'review': self.reviews.put_nowait(data)
            elif event == 'assessment-case': self.cases.put_nowait(data['case'])
        self.service = Service(Path(self.temp.name)/'state', Path(__file__).resolve().parents[2]/'runtime/ollama', emit)
        await self.service.dispatch('project-add', dict(root=str(self.root)))
    async def asyncTearDown(self):
        await self.service.close(); self.server.close(); await self.server.wait_closed(); self.temp.cleanup()
    async def review(self):
        return await asyncio.wait_for(self.reviews.get(), 5)
    async def approve(self, review):
        await self.service.dispatch('respond', dict(id=review['id'], value=True))
    def start(self):
        return asyncio.create_task(self.service.dispatch('assessment-run', dict(name='website_assess', arguments=dict(url=self.url, max_pages=2, report_prefix='actual'))))
    async def stop(self, running):
        await self.service.dispatch('assessment-cancel', {})
        result = await asyncio.wait_for(running, 5)
        self.assertTrue(result['partial']); self.assertEqual(result['status'], 'cancelled')
        self.assertFalse(self.service.pending)
        self.assertFalse(list(self.root.glob('actual.*')), 'Cancellation must not silently deliver project reports')
        return result
    async def test_stop_at_review_performs_no_http_and_retains_restartable_record(self):
        running = self.start(); await self.review()
        result = await self.stop(running)
        self.assertEqual(self.requests, 0); self.assertEqual(result['cases'], [])
        task = self.service.store.data['tasks'][-1]
        self.assertEqual(task['checkpoints'][-1]['status'], 'cancelled')
        await self.service.close()
        self.service.close = lambda: asyncio.sleep(0)
        store = Store(Path(self.temp.name)/'state')
        try:
            self.assertEqual(store.data['assessmentResults'][-1]['result'], result)
            self.assertEqual(store.data['tasks'][-1]['status'], 'cancelled')
        finally: store.close()
    async def test_stop_during_crawl_preserves_exact_completed_cases(self):
        running = self.start(); await self.approve(await self.review())
        first = await asyncio.wait_for(self.cases.get(), 5)
        result = await self.stop(running)
        self.assertIn(first, result['cases']); self.assertGreater(len(result['cases']), 1)
        requests = self.requests; await asyncio.sleep(.3); self.assertEqual(self.requests, requests)
        self.assertEqual(self.service.store.data['assessmentResults'][-1]['status'], 'cancelled')
    async def test_stop_during_delivery_review_keeps_full_completed_report(self):
        running = self.start(); await self.approve(await self.review())
        save_review = await self.review(); self.assertEqual(save_review['name'], 'save_website_evidence')
        result = await self.stop(running)
        self.assertEqual(result['report']['cases'], result['cases'])
        self.assertEqual(result['report']['summary']['requests'], self.requests)
        self.assertGreater(result['report']['summary']['cases'], 10)
        # A second run really executes after cancellation, writes once, then survives reload.
        running = self.start(); await self.approve(await self.review()); await self.approve(await self.review())
        completed = await asyncio.wait_for(running, 5)
        self.assertTrue(completed['saved']); self.assertEqual(json.loads((self.root/'actual.json').read_text())['cases'], completed['report']['cases'])
    async def test_cancel_endpoint_does_not_cancel_unrelated_active_chat(self):
        active = asyncio.create_task(asyncio.sleep(60)); self.service.active = active
        await self.service.dispatch('assessment-cancel', {})
        self.assertFalse(active.done()); active.cancel(); await asyncio.gather(active, return_exceptions=True)

    @unittest.skipUnless(shutil.which('nmap') or Path('/opt/homebrew/bin/nmap').exists(), 'Actual Nmap required')
    async def test_stop_real_loopback_scanner_reaps_child_and_retains_output(self):
        running = asyncio.create_task(self.service.dispatch('assessment-run', dict(name='network_scan', arguments=dict(target='127.0.0.1', profile='ports', ports='1-65535', timeout_seconds=60))))
        await self.approve(await self.review())
        async with asyncio.timeout(5):
            while not self.service.tools.jobs: await asyncio.sleep(.01)
        job = next(iter(self.service.tools.jobs.values()))
        result = await self.stop(running)
        self.assertIsNotNone(job['child'].returncode)
        self.assertTrue(job['collector'].done())
        self.assertEqual(result['output'], job['output'])
        self.assertEqual(result['scannerState'], 'stopped')

if __name__ == '__main__': unittest.main()
