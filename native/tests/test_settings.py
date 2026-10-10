"""Regression checks for native Settings data and in-task preferences."""
import asyncio
import base64
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from wixal.service import Service
from wixal.conversation import attachments

PAYLOAD=Path(__file__).resolve().parents[2]/'runtime/ollama'

class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.service=Service(self.path/'source',PAYLOAD,lambda *_:None)
        self.other=None
    async def asyncTearDown(self):
        if self.other:await self.other.close()
        await self.service.close();self.temp.cleanup()
    async def test_appearance_during_task_does_not_unlock_context_or_permissions(self):
        event=asyncio.Event();self.service.active=asyncio.create_task(event.wait())
        await self.service.dispatch('settings',{'ui':{'textSize':17,'theme':'forest'}})
        self.assertEqual(self.service.store.data['ui']['textSize'],17)
        for params in ({'contextSize':4096},{'approvalMode':'bypass'},{'enabledTools':[]}):
            with self.assertRaisesRegex(ValueError,'current agent task'):await self.service.dispatch('settings',params)
        with self.assertRaises(ValueError):await self.service.dispatch('settings',{'ui':{'textSize':True}})
        self.assertFalse(self.service.active.done());event.set();await self.service.active
    async def test_backup_preview_roundtrip_images_and_existing_preferences(self):
        store=self.service.store;root=self.path/'project';root.mkdir()
        await self.service.dispatch('project-add',{'root':str(root)})
        image=base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'saved-image').decode()
        session=store.session();session['memoryOwner']='account:private-id';session['messages']=[{'role':'user','content':'Keep this photo','attachments':attachments([{'type':'image','name':'photo.png','base64':image}],store)}]
        store.data['schedules']=[{'id':'schedule','projectId':store.project()['id'],'prompt':'remember','intervalSeconds':60,'enabled':True}]
        store.data['account']={'signedIn':True,'profile':{'id':'private-id','email':'private@example.test'},'globalMemory':'private instructions'}
        store.save();output=self.path/'backup.json'
        result=await self.service.dispatch('workspace-backup',{'path':str(output)})
        data=json.loads(output.read_text());self.assertNotIn('account',data);self.assertNotIn('enabledTools',data)
        self.assertFalse(data['schedules'][0]['enabled']);self.assertNotIn('private@example.test',output.read_text())
        self.assertEqual(os.stat(output).st_mode&0o777,0o600)
        self.other=Service(self.path/'target',PAYLOAD,lambda *_:None)
        target=self.other.store;target.data['ui']['theme']='midnight';target.data['enabledTools']=[];target.data['personalApprovalMode']='review';target.save()
        before=copy.deepcopy(target.data);preview=await self.other.dispatch('workspace-import-preview',{'path':str(output)})
        self.assertEqual(target.data,before);self.assertFalse((target.directory/'attachments').exists())
        self.assertEqual(preview['counts']['sessions'],1)
        await self.other.dispatch('workspace-import',{'path':str(output),'digest':preview['digest']})
        self.assertEqual(target.data['ui']['theme'],'midnight');self.assertEqual(target.data['enabledTools'],[])
        self.assertEqual(target.data['projects'][0]['approvalMode'],'review');self.assertFalse(target.data['schedules'][0]['enabled'])
        self.assertEqual(target.data['sessions'][0]['memoryOwner'],'account:private-id')
        imported=target.data['sessions'][0]['messages'][0]['attachments'][0]
        self.assertEqual((target.directory/'attachments'/imported['imageId']).read_bytes(),base64.b64decode(image))
        repeat=await self.other.dispatch('workspace-import-preview',{'path':str(output)})
        self.assertEqual(repeat['counts']['sessions'],0);self.assertEqual(repeat['skippedExisting']['sessions'],1)
    async def test_changed_or_malformed_source_does_not_import(self):
        p=self.path/'backup.json';p.write_text(json.dumps({'projects':[],'sessions':[],'memories':[]}))
        preview=await self.service.dispatch('workspace-import-preview',{'path':str(p)})
        before=copy.deepcopy(self.service.store.data);p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'changed after preview'):await self.service.dispatch('workspace-import',{'path':str(p),'digest':preview['digest']})
        self.assertEqual(before,self.service.store.data)
        p.write_text('{"sessions": []}')
        with self.assertRaises(ValueError):await self.service.dispatch('workspace-import-preview',{'path':str(p)})
        self.assertEqual(before,self.service.store.data)
    async def test_backup_preserves_memory_provenance_owner_and_recall_exclusions(self):
        store=self.service.store;root=self.path/'memory-project';root.mkdir()
        await self.service.dispatch('project-add',{'root':str(root)})
        session=store.session();session['messages']=[dict(role='user',content='Use obsolete cerulean settings.'),dict(role='user',content='Forget the vermilion deployment.')];store.save()
        old,forgotten=session['messages']
        note=store.memory.save(old['content'],source_session=session['id'],source_message=old['id'])
        store.memory.save('Use current ultramarine settings.',replace=note['id'])
        erased=store.memory.save(forgotten['content'],source_session=session['id'],source_message=forgotten['id']);store.memory.forget(erased['id'])
        store.select_project(None)
        global_note=store.memory.save('The default locale is en-AU.',scope='global')
        # A different identity's saved note must retain its owner on restore.
        store.data['globalMemories'].append(dict(id='private-global',owner='account:other',scope='global',projectId=None,content='Hidden indigo preference.',created=1));store.save()
        path=self.path/'memory.json';await self.service.dispatch('workspace-backup',dict(path=str(path)))
        exported=json.loads(path.read_text());self.assertEqual(exported['globalMemories'],store.data['globalMemories'])
        self.other=Service(self.path/'memory-target',PAYLOAD,lambda *_:None)
        preview=await self.other.dispatch('workspace-import-preview',dict(path=str(path)))
        await self.other.dispatch('workspace-import',dict(path=str(path),digest=preview['digest']))
        target=self.other.store;target.select_project(root_id:=store.data['projects'][0]['id'])
        restored=next(n for n in target.data['memories'] if n['id']==note['id'])
        for key in ('content','owner','sources','revisions','sourceSession','sourceMessage'):self.assertEqual(restored.get(key),note.get(key))
        self.assertFalse(target.memory.recall('cerulean'))
        self.assertFalse(target.memory.recall('vermilion'))
        self.assertTrue(target.memory.recall('ultramarine'))
        target.select_project(None)
        self.assertTrue(any(n['id']==global_note['id'] for n in target.memory.recall('en-AU')))
        self.assertFalse(target.memory.recall('indigo'))
        expected=copy.deepcopy(target.data)
        await self.other.close();self.other=Service(self.path/'memory-target',PAYLOAD,lambda *_:None)
        for key in ('globalMemories','forgottenMemories','forgottenMemorySources','supersededMemorySources'):self.assertEqual(self.other.store.data[key],expected[key])
        self.other.store.select_project(root_id)
        self.assertFalse(self.other.store.memory.recall('vermilion'))
        self.assertFalse(self.other.store.memory.recall('cerulean'))

    async def test_restore_failure_is_atomic_and_stale_backup_cannot_revive_forgotten_note(self):
        import sqlite3
        store=self.service.store;root=self.path/'restore-project';root.mkdir();store.add_project(root)
        note=store.memory.save('Retain saffron marker.')
        path=self.path/'stale.json';await self.service.dispatch('workspace-backup',dict(path=str(path)))
        self.other=Service(self.path/'failure-target',PAYLOAD,lambda *_:None);target=self.other.store
        preview=await self.other.dispatch('workspace-import-preview',dict(path=str(path)));target.save();before=copy.deepcopy(target.data)
        target.db.execute("CREATE TRIGGER reject_restore BEFORE UPDATE ON state BEGIN SELECT RAISE(ABORT, 'write refused'); END");target.db.commit()
        with self.assertRaisesRegex(sqlite3.IntegrityError,'write refused'):await self.other.dispatch('workspace-import',dict(path=str(path),digest=preview['digest']))
        self.assertEqual(target.data,before)
        self.assertEqual(json.loads(target.db.execute('SELECT value FROM state').fetchone()[0]),before)
        target.db.execute('DROP TRIGGER reject_restore');target.db.commit()
        await self.other.dispatch('workspace-import',dict(path=str(path),digest=preview['digest']))
        target.select_project(store.data['activeProject']);target.memory.forget(note['id'])
        await self.other.dispatch('workspace-import',dict(path=str(path),digest=preview['digest']))
        self.assertFalse(any(n['id']==note['id'] for n in target.data['memories']))
        self.assertFalse(target.memory.recall('saffron'))
    async def test_mcp_edit_validates_before_disconnect_and_preserves_identifier(self):
        await self.service.dispatch('mcp-add',{'name':'Demo','command':'python3','args':['-V']})
        original=copy.deepcopy(self.service.store.data['mcpServers'][0]);server_id=original['id']
        with self.assertRaises(ValueError):await self.service.dispatch('mcp-update',{'id':server_id,'name':'Demo','command':'python3','args':[17]})
        self.assertEqual(self.service.store.data['mcpServers'][0],original)
        await self.service.dispatch('mcp-update',{'id':server_id,'name':'Edited','command':'python3','args':['argument with spaces']})
        self.assertEqual(self.service.store.data['mcpServers'][0]['id'],server_id)
        self.assertEqual(self.service.store.data['mcpServers'][0]['args'],['argument with spaces'])
        self.assertEqual(self.service.mcp.connections,{})
    async def test_diagnostics_exclude_names_paths_and_accounts(self):
        self.service.store.data['account']={'profile':{'email':'private@example.test'},'signedIn':True}
        result=await self.service.dispatch('workspace-diagnostics',{})
        encoded=json.dumps(result)
        self.assertNotIn(str(self.path),encoded);self.assertNotIn('private@example.test',encoded)
        self.assertIn('engineVersion',result);self.assertIn('runtimeStatus',result)
