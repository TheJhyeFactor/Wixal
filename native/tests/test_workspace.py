"""Cross-screen state tests against the real service and local model fixture."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from fixture_server import Fixture
from wixal.service import Service
from wixal.storage import Store, identity

class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.fixture=Fixture().__enter__()
        def emit(event,data):
            if event=='review':asyncio.create_task(self.service.dispatch('respond',dict(id=data['id'],value=True)))
        self.service=Service(Path(self.temp.name)/'state',Path(__file__).resolve().parents[2]/'runtime/ollama',emit,self.fixture.url)
        await self.service.dispatch('project-add',dict(root=str(self.root)))
        await self.service.dispatch('settings',dict(model='fixture'))
    async def asyncTearDown(self):
        await self.service.close();self.fixture.__exit__();self.temp.cleanup()
    async def test_inbox_start_reuses_identity_and_keeps_completed_response(self):
        task=dict(id=identity(),projectId=self.service.store.project()['id'],prompt='Write smoke.txt',source='ChatGPT',status='failed',error='old failure',result='old result',checkpoints=[])
        self.service.store.data['tasks'].append(task)
        result=await self.service.dispatch('task-start',dict(id=task['id']))
        self.assertEqual(result['id'],task['id']);self.assertEqual(result['source'],'ChatGPT')
        self.assertEqual(result['status'],'completed');self.assertNotIn('error',result)
        self.assertTrue(result['result']);self.assertEqual(len(self.service.store.data['tasks']),1)
        self.assertEqual((self.root/'smoke.txt').read_text(),'native-agent-ok\n')
        self.assertEqual(self.service.store.session()['id'],result['sessionId'])
    async def test_memory_edit_cannot_cross_projects_or_disabled_scope(self):
        await self.service.dispatch('memory-add',dict(content='first note'))
        note=self.service.store.memories()[0]
        await self.service.dispatch('memory-settings',dict(mode='both',size=8000))
        await self.service.dispatch('memory-update',dict(id=note['id'],content='edited note'))
        other=Path(self.temp.name)/'other';other.mkdir()
        await self.service.dispatch('project-add',dict(root=str(other)))
        with self.assertRaises(ValueError):await self.service.dispatch('memory-update',dict(id=note['id'],content='wrong scope'))
        self.assertEqual(note['content'],'edited note')
        await self.service.dispatch('memory-settings',dict(mode='off'))
        with self.assertRaises(ValueError):await self.service.dispatch('memory-add',dict(content='disabled'))
    async def test_delete_conversation_preserves_files_and_selects_valid_session(self):
        (self.root/'keep.txt').write_text('retain')
        session=self.service.store.session();session['messages']=[dict(role='assistant',content='saved response')]
        await self.service.dispatch('session-rename',dict(id=session['id'],title='Renamed'))
        self.assertIn('saved response',await self.service.dispatch('session-copy',dict(id=session['id'])))
        await self.service.dispatch('session-delete',dict(id=session['id']))
        self.assertEqual((self.root/'keep.txt').read_text(),'retain')
        self.assertNotEqual(self.service.store.session()['id'],session['id'])
    async def test_interrupted_first_setup_does_not_become_completed_on_reopen(self):
        self.assertFalse(self.service.store.data['setup']['completed'])
        with self.assertRaises(ValueError):await self.service.dispatch('setup-complete',{})
        directory=self.service.store.directory
        await self.service.close()
        reopened=Store(directory)
        try:self.assertFalse(reopened.data['setup']['completed'])
        finally:reopened.close()
        # Avoid closing the same engine again in teardown.
        self.service.close=lambda:asyncio.sleep(0)
