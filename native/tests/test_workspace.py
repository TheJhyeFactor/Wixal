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
    async def test_new_conversation_reuses_empty_chat_and_preserves_drafts(self):
        await self.service.dispatch('session-new',dict(mode='chat'))
        first=self.service.store.session()['id']
        count=len(self.service.store.data['sessions'])
        for _ in range(20):await self.service.dispatch('session-new',dict(mode='chat'))
        self.assertEqual(self.service.store.session()['id'],first)
        self.assertEqual(len(self.service.store.data['sessions']),count)
        self.service.store.session()['draft']=dict(text='Keep my draft',attachments=[])
        await self.service.dispatch('session-new',dict(mode='chat'))
        self.assertNotEqual(self.service.store.session()['id'],first)
        old=next(s for s in self.service.store.data['sessions'] if s['id']==first)
        self.assertEqual(old['draft']['text'],'Keep my draft')
        self.service.store.session()['draft']=dict(text='',attachments=[dict(name='image.png')])
        attached=self.service.store.session()['id']
        await self.service.dispatch('session-new',dict(mode='chat'))
        self.assertNotEqual(self.service.store.session()['id'],attached)

    async def test_create_project_uses_managed_folder_and_rejects_duplicates_and_traversal(self):
        await self.service.dispatch('project-create',dict(name='My project'))
        expected=self.service.store.directory/'Projects'/'My project'
        self.assertTrue(expected.is_dir())
        self.assertEqual(self.service.store.project()['root'],str(expected.resolve()))
        self.assertEqual(self.service.store.project()['name'],'My project')
        for name in ['My project','../escape','bad/name','', '.hidden']:
            with self.assertRaises(ValueError):await self.service.dispatch('project-create',dict(name=name))

    async def test_inbox_start_reuses_identity_and_keeps_completed_response(self):
        await self.service.dispatch("settings",dict(mode="chat"))
        task=dict(id=identity(),projectId=self.service.store.project()['id'],prompt='Write smoke.txt',source='ChatGPT',status='failed',error='old failure',result='old result',checkpoints=[])
        self.service.store.data['tasks'].append(task)
        result=await self.service.dispatch('task-start',dict(id=task['id']))
        self.assertEqual(result['id'],task['id']);self.assertEqual(result['source'],'ChatGPT')
        self.assertEqual(result['status'],'completed');self.assertNotIn('error',result)
        self.assertTrue(result['result']);self.assertEqual(len(self.service.store.data['tasks']),1)
        self.assertEqual((self.root/'smoke.txt').read_text(),'native-agent-ok\n')
        self.assertEqual(self.service.store.session()['id'],result['sessionId'])
        self.assertEqual(self.service.store.session()['mode'],'agent')
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
    async def test_conversation_modes_restore_when_selected(self):
        await self.service.dispatch('session-new',dict(mode='chat'))
        chat=self.service.store.session()['id']
        await self.service.dispatch('session-new',dict(mode='agent'))
        agent=self.service.store.session()['id']
        await self.service.dispatch('session-select',dict(id=chat))
        self.assertEqual(self.service.store.data['mode'],'chat')
        await self.service.dispatch('session-select',dict(id=agent))
        self.assertEqual(self.service.store.data['mode'],'agent')
        with self.assertRaises(ValueError):await self.service.dispatch('session-new',dict(mode='invalid'))

    async def test_project_delete_cascades_and_preserves_other_scope_and_files(self):
        store=self.service.store;pid=store.project()['id'];sid=store.session()['id']
        (self.root/'keep.txt').write_text('retain')
        store.session()['messages']=[dict(id=identity(),role='user',content='deletionunique history evidence')]
        await self.service.dispatch('memory-add',dict(content='deletionunique project note'))
        note_id=store.memories()[0]['id']
        store.data['globalMemories'].append(dict(id=identity(),owner='guest',content='retain explicit global note'))
        for name in ('tasks','schedules','assessmentResults','memorySuggestionsPending'):
            store.data[name].append(dict(id=identity(),projectId=pid,sessionId=sid))
        store.data['usage'].append(dict(sessionId=sid,model='fixture'))
        store.save();store.memory.sync()
        self.assertTrue(store.db.execute('SELECT count(*) FROM memory_search WHERE session=?',(sid,)).fetchone()[0])
        await self.service.dispatch('session-archive',dict(id=sid))
        other=Path(self.temp.name)/'other';other.mkdir()
        await self.service.dispatch('project-add',dict(root=str(other)))
        other_id=store.project()['id'];other_sid=store.session()['id']
        with self.assertRaises(ValueError):await self.service.dispatch('project-delete',dict(id=pid))
        await self.service.dispatch('project-delete',dict(id=pid,confirmed=True))
        self.assertEqual(store.project()['id'],other_id)
        self.assertEqual(store.session()['id'],other_sid)
        self.assertEqual((self.root/'keep.txt').read_text(),'retain')
        for name in ('sessions','memories','tasks','schedules','assessmentResults','memorySuggestionsPending'):
            self.assertFalse(any(x.get('projectId')==pid for x in store.data[name]),name)
        self.assertFalse(any(x.get('sessionId')==sid for x in store.data['usage']))
        self.assertEqual(len(store.data['globalMemories']),1)
        self.assertEqual(store.db.execute('SELECT count(*) FROM memory_search WHERE session=?',(sid,)).fetchone()[0],0)
        self.assertEqual(store.db.execute('SELECT count(*) FROM memory_vectors WHERE key=?',('note:'+note_id,)).fetchone()[0],0)
        directory=store.directory
        await self.service.close()
        self.service.close=lambda:asyncio.sleep(0)
        reopened=Store(directory)
        try:
            self.assertFalse(any(p['id']==pid for p in reopened.data['projects']))
            self.assertFalse(any(s.get('projectId')==pid for s in reopened.data['sessions']))
        finally:reopened.close()
    async def test_delete_active_project_returns_to_valid_personal_conversation(self):
        store=self.service.store;pid=store.project()['id']
        (self.root/'keep.txt').write_text('retain')
        await self.service.dispatch('session-new',dict(mode='chat'))
        await self.service.dispatch('project-delete',dict(id=pid,confirmed=True))
        self.assertIsNone(store.project())
        self.assertIsNone(store.data['activeProject'])
        self.assertIsNotNone(store.session())
        self.assertIsNone(store.session()['projectId'])
        self.assertEqual(store.session()['mode'],'chat')
        self.assertEqual((self.root/'keep.txt').read_text(),'retain')
        self.assertFalse(any(s.get('projectId')==pid for s in store.data['sessions']))

    async def test_deleted_project_is_not_restored_from_older_encrypted_snapshot(self):
        from wixal.sync import encode
        store=self.service.store;pid=store.project()['id']
        await self.service.dispatch('memory-add',dict(content='deleted project context'))
        snapshot=self.service.sync.payload();snapshot['device']='offline-fixture'
        folder=Path(self.temp.name)/'shared';folder.mkdir()
        secret=dict(passphrase='disposable-sync-passphrase')
        class Vault:
            def get(self):return secret
        self.service.sync.vault=Vault()
        store.data['syncState'].update(enabled=True,folder=str(folder))
        (folder/'offline-fixture.wixalsync').write_bytes(encode(snapshot,secret['passphrase']))
        await self.service.dispatch('project-delete',dict(id=pid,confirmed=True))
        await self.service.sync.run()
        self.assertFalse(any(p['id']==pid for p in store.data['projects']))
        self.assertFalse(any(s.get('projectId')==pid for s in store.data['sessions']))
        self.assertFalse(any(n.get('projectId')==pid for n in store.data['memories']))
        self.assertFalse(store.data['syncState']['conflicts'])
