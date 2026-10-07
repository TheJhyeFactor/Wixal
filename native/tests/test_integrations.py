"""Account and scoped companion tests use temporary state and fake Firebase."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.account import Accounts, AccountError, profile_memory
from wixal.companion import Companion
from wixal.storage import Store
from wixal.integrations import NativeIntegrations

class Vault:
    def __init__(self):self.value=None
    def get(self):return self.value
    def set(self,value):self.value=value

class Firebase:
    def __init__(self):self.calls=[];self.verified=False;self.documents=[]
    def __call__(self,url,body,method,token):
        self.calls.append((url,body,method,token))
        if 'signUp' in url or 'signInWithPassword' in url:return dict(localId='user',email=body['email'],idToken='PRIVATE_ID',refreshToken='PRIVATE_REFRESH',expiresIn='3600')
        if 'update' in url and body.get('password'):return dict(idToken='CHANGED_ID',refreshToken='CHANGED_REFRESH',expiresIn='3600')
        if 'lookup' in url:return dict(users=[dict(email='user@example.com',displayName='Fixture',emailVerified=self.verified)])
        if 'securetoken' in url:return dict(id_token='REFRESHED_ID',refresh_token='PRIVATE_REFRESH',expires_in='3600')
        if method=='GET' and '/profile/memory' in url:raise AccountError('Missing',404)
        if method=='GET' and '/presets' in url:return dict(documents=self.documents)
        return {}

class AccountTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name);self.firebase=Firebase();self.vault=Vault();self.accounts=Accounts(self.temp.name,dict(apiKey='fixture-public',projectId='fixture'),self.vault,self.firebase)
    async def asyncTearDown(self):self.store.close();self.temp.cleanup()
    async def test_create_verifies_and_excludes_tokens(self):
        await self.accounts.dispatch('account-create',dict(email='user@example.com',password='abcdefghijk',name='Fixture'),self.store)
        self.assertTrue(any(call[1].get('requestType')=='VERIFY_EMAIL' for call in self.firebase.calls if isinstance(call[1],dict)))
        self.assertTrue(self.accounts.snapshot()['signedIn']);self.assertNotIn('PRIVATE',json.dumps(self.accounts.snapshot()));self.assertNotIn('PRIVATE',json.dumps(self.store.data))
        with self.assertRaisesRegex(ValueError,'Verify'):await self.accounts.dispatch('account-preset-save',dict(name='Focus'),self.store)
    async def test_verified_preset_preserves_tools_and_approval(self):
        self.firebase.verified=True
        await self.accounts.dispatch('account-sign-in',dict(email='user@example.com',password='ok'),self.store)
        preset=dict(name='Focus',id='preset',ui=dict(theme='paper',textSize=15,reduceMotion=True,sidebarCollapsed=True),mode='chat',contextSize=32768,autoSummary=False)
        self.accounts.presets=[preset];self.store.data['enabledTools']=['read_file'];self.store.data['personalApprovalMode']='review'
        await self.accounts.dispatch('account-preset-apply',dict(id='preset'),self.store)
        self.assertEqual(self.store.data['ui']['theme'],'paper');self.assertEqual(self.store.data['enabledTools'],['read_file']);self.assertEqual(self.store.data['personalApprovalMode'],'review')
        await self.accounts.dispatch('account-sign-out',{},self.store);self.assertIsNone(self.vault.value);self.assertFalse(self.accounts.snapshot()['signedIn'])
    async def test_password_change_refreshes_keychain_without_persisting_password(self):
        await self.accounts.dispatch('account-sign-in',dict(email='user@example.com',password='ok'),self.store)
        await self.accounts.dispatch('account-password-change',dict(password='old-password',newPassword='replacement-password'),self.store)
        self.assertEqual(self.vault.value['idToken'],'CHANGED_ID')
        self.assertNotIn('replacement-password',json.dumps(self.store.data));self.assertNotIn('replacement-password',json.dumps(self.vault.value))
    async def test_successful_restore_replaces_previous_failure_message(self):
        self.firebase.verified=True
        await self.accounts.dispatch('account-sign-in',dict(email='user@example.com',password='ok'),self.store)
        self.accounts.ready=False;self.accounts.message='Saved sign-in could not be restored; guest preferences are active.'
        await self.accounts.dispatch('account-restore',{},self.store)
        self.assertTrue(self.accounts.ready)
        self.assertEqual(self.accounts.message,'Saved sign-in restored.')
        self.vault.value=None
        await self.accounts.dispatch('account-restore',{},self.store)
        self.assertFalse(self.accounts.ready)
        self.assertIn('No saved sign-in',self.accounts.message)
    async def test_delete_requires_confirmation_and_reauthentication(self):
        await self.accounts.dispatch('account-sign-in',dict(email='user@example.com',password='ok'),self.store)
        with self.assertRaises(ValueError):await self.accounts.dispatch('account-delete',dict(password='ok'),self.store)
        await self.accounts.dispatch('account-delete',dict(password='ok',confirmation='DELETE'),self.store)
        self.assertFalse(self.accounts.ready);self.assertIsNone(self.vault.value)
        self.assertTrue(any('accounts:delete' in call[0] for call in self.firebase.calls))
    async def test_guest_memory_bound_and_no_network(self):
        await self.accounts.dispatch('global-memory-save',dict(content='Use concise answers'),self.store)
        self.assertEqual(self.store.data['globalMemory'],'Use concise answers');self.assertFalse(self.firebase.calls)
        with self.assertRaises(ValueError):profile_memory('x'*1201)

class CompanionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'project';self.root.mkdir();(self.root/'hello.txt').write_text('fixture hello');(self.root/'.env').write_text('SECRET')
        self.outside=Path(self.temp.name)/'outside.txt';self.outside.write_text('outside');(self.root/'link.txt').symlink_to(self.outside)
        self.store=Store(Path(self.temp.name)/'state');self.project=self.store.add_project(self.root);self.store.data['enabledTools']=['list_files','read_file','search_files']
        class Service:pass
        self.service=Service();self.service.store=self.store;self.service.emit=lambda *_:None
        self.companion=Companion(self.service)
        await self.companion.dispatch('companion-settings',dict(sharedProjects=[self.project['id']],shareMemory=False));await self.companion.start()
    async def asyncTearDown(self):await self.companion.stop();self.store.close();self.temp.cleanup()
    async def test_scopes_and_protected_paths(self):
        result=await self.companion.call('get_project_context',dict(projectId=self.project['id']))
        self.assertEqual(result['files'],['hello.txt']);self.assertNotIn('memories',result)
        for path in ('.env','link.txt','../outside.txt'):
            with self.assertRaises(ValueError):await self.companion.call('read_project_file',dict(projectId=self.project['id'],path=path))
        with self.assertRaises(ValueError):await self.companion.call('get_project_context',dict(projectId='unshared'))
        await self.companion.dispatch('companion-settings',dict(sharedProjects=[],shareMemory=False))
        with self.assertRaises(ValueError):await self.companion.call('read_project_file',dict(projectId=self.project['id'],path='hello.txt'))
    async def test_task_only_queues(self):
        result=await self.companion.call('create_task',dict(projectId=self.project['id'],title='Read fixture',prompt='Read hello.txt'))
        self.assertEqual(result['status'],'queued');self.assertEqual(self.store.data['tasks'][0]['source'],'ChatGPT');self.assertEqual((self.root/'hello.txt').read_text(),'fixture hello')
    async def http(self,authorization=None,origin=None):
        port=self.companion.server.sockets[0].getsockname()[1];reader,writer=await asyncio.open_connection('127.0.0.1',port)
        body=json.dumps(dict(name='list_projects',args={})).encode();headers=f'POST /bridge HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Length: {len(body)}\r\n'
        if authorization:headers+='Authorization: '+authorization+'\r\n'
        if origin:headers+='Origin: '+origin+'\r\n'
        writer.write(headers.encode()+b'\r\n'+body);await writer.drain();result=await reader.read();writer.close();await writer.wait_closed();return result
    async def test_http_auth_pairing_file_and_revocation(self):
        self.assertEqual(self.companion.file.stat().st_mode&0o777,0o600)
        self.assertIn(b'401',await self.http());self.assertIn(b'403',await self.http('Bearer '+self.companion.token,'https://other.example'))
        self.assertIn(b'200',await self.http('Bearer '+self.companion.token));await self.companion.stop();self.assertFalse(self.companion.file.exists())
    async def test_setup_acceptance_and_exact_legal(self):
        await self.companion.stop();integration=NativeIntegrations(self.service)
        with self.assertRaises(ValueError):await integration.dispatch('entry-complete',dict(choice='guest',legalAccepted=False))
        await integration.dispatch('entry-complete',dict(choice='guest',legalAccepted=True));await integration.dispatch('setup-complete',{})
        self.assertTrue(self.store.data['setup']['completed'])
        handled,value=await integration.dispatch('legal-document',dict(id='privacy'))
        original=Path(__file__).resolve().parents[2]/'resources/legal/privacy.md'
        self.assertTrue(handled);self.assertEqual(value['markdown'],original.read_text())
        self.assertNotIn('token',json.dumps(self.store.data['companion']));await integration.close()

if __name__=='__main__':unittest.main()
