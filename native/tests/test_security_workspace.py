import asyncio
import tempfile
import unittest
from pathlib import Path
from fixture_server import Fixture
from wixal.service import Service
from wixal.storage import Store


class SecurityWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'; self.root.mkdir()
        self.fixture = Fixture().__enter__()
        self.events = []
        self.service = Service(Path(self.temp.name)/'state', Path(__file__).resolve().parents[2]/'runtime/ollama',
                               lambda kind, data:self.events.append((kind, data)), self.fixture.url)
        await self.service.dispatch('project-add', dict(root=str(self.root)))
        self.target = await self.service.dispatch('security-target-add', dict(type='Server', address='127.0.0.1', objective='Loopback validation'))

    async def asyncTearDown(self):
        await self.service.close(); self.fixture.__exit__(); self.temp.cleanup()

    async def wait_for(self, predicate):
        for _ in range(200):
            if predicate(): return
            await asyncio.sleep(.02)
        self.fail('Timed out waiting for security queue state')

    async def queue(self, **kwargs):
        args = dict(targetId=self.target['id'], stage='Attacks', capability='website_simulate', name='Fixture simulation', arguments={})
        args.update(kwargs)
        return await self.service.dispatch('security-run-add', args)

    async def test_parallel_ownership_review_and_cancellation(self):
        first = await self.queue()
        second = await self.queue(name='Second simulation')
        await self.wait_for(lambda: len([e for e in self.events if e[0]=='review']) == 2)
        self.assertEqual(len(self.service.security_workspace.tasks), 2)
        self.assertNotEqual(first['sessionId'], second['sessionId'])
        self.assertEqual(first['status'], 'waiting_review')
        await self.service.dispatch('security-run-stop', dict(id=first['id']))
        self.assertEqual(first['status'], 'cancelled')
        self.assertEqual(second['status'], 'waiting_review')
        self.assertEqual(len(self.service.security_workspace.tasks), 1)
        # Disabled tools are enforced at execution, regardless of the plan.
        await self.service.dispatch('security-run-stop', dict(id=second['id']))
        self.service.store.data['enabledTools'].remove('website_simulate')
        disabled = await self.queue()
        await self.wait_for(lambda:disabled['status']=='failed')
        self.assertIn('switched off', disabled['error'])

    async def test_real_simulation_dependency_and_result_provenance(self):
        first = await self.queue()
        second = await self.queue(name='Chained simulation', dependency=first['id'])
        self.assertEqual(second['status'], 'blocked')
        responded = set()
        for _ in range(1000):
            for kind, data in list(self.events):
                if kind == 'review' and data['id'] not in responded:
                    responded.add(data['id'])
                    await self.service.dispatch('respond', dict(id=data['id'], value=True))
            if second['status'] in ('completed','failed'): break
            await asyncio.sleep(.01)
        self.assertEqual(first['status'], 'completed', first)
        self.assertEqual(second['status'], 'completed', second)
        self.assertGreaterEqual(second['started'], first['finished'])
        self.assertNotEqual(first['arguments']['report_prefix'], second['arguments']['report_prefix'])
        self.assertTrue((self.root/(first['arguments']['report_prefix']+'.json')).is_file())
        self.assertEqual(second['targetId'], self.target['id'])
        self.assertTrue(first['cases'])

    async def test_queue_pause_restart_and_failed_prerequisite(self):
        await self.service.dispatch('security-queue-settings', dict(paused=True, limit=1))
        first = await self.queue()
        second = await self.queue(dependency=first['id'])
        self.assertEqual(first['status'], 'queued')
        await self.service.dispatch('security-run-stop', dict(id=first['id']))
        self.assertEqual(second['status'], 'blocked')
        directory = self.service.store.directory
        await self.service.close()
        from wixal.security_workspace import SecurityWorkspace
        store = Store(directory)
        try:
            class Owner: pass
            owner=Owner(); owner.store=store
            manager=SecurityWorkspace(owner)
            self.assertEqual(next(r for r in manager.runs if r['id']==second['id'])['status'], 'interrupted')
            self.assertFalse(manager.tasks)
        finally: store.close()
        self.service.close=lambda:asyncio.sleep(0)

    async def test_target_validation_and_cross_project_dependency(self):
        for kind, address in [('Server','-oX /tmp/escape'), ('Network','8.8.8.0/24'), ('Software','../escape'), ('Website / API','https://user:secret@example.org')]:
            with self.assertRaises(ValueError):
                await self.service.dispatch('security-target-add', dict(type=kind,address=address))
        await self.service.dispatch('security-queue-settings', dict(paused=True))
        run=await self.queue()
        other=self.root.parent/'other';other.mkdir()
        # Queue owns its project: destructive/settings changes are blocked while pending.
        with self.assertRaises(ValueError):await self.service.dispatch('project-add', dict(root=str(other)))
        await self.service.dispatch('security-run-stop', dict(id=run['id']))
        await self.service.dispatch('project-add', dict(root=str(other)))
        with self.assertRaises(ValueError):await self.queue()
        fresh=await self.service.dispatch('security-target-add', dict(type='Server',address='127.0.0.1'))
        with self.assertRaises(ValueError):await self.queue(targetId=fresh['id'],dependency=run['id'])

    async def test_model_analysis_records_response_in_own_conversation(self):
        run=await self.queue(capability='analysis',stage='Research',model='fixture',prompt='Explain the evidence and its limitations')
        responded=set()
        for _ in range(300):
            for kind,data in list(self.events):
                if kind=='review' and data['id'] not in responded:
                    responded.add(data['id']);await self.service.dispatch('respond',dict(id=data['id'],value=True))
            if run['status'] in ('completed','failed'):break
            await asyncio.sleep(.01)
        self.assertEqual(run['status'],'completed',run)
        self.assertTrue(run['result']['analysis'])
        session=next(s for s in self.service.store.data['sessions'] if s['id']==run['sessionId'])
        self.assertEqual(session['messages'][-1]['role'],'assistant')
