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
