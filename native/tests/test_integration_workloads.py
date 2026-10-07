"""Persistent importer workload and account failure recovery; no live credentials.

These tests drive production storage/import/account code. Firebase failures are an
explicit controlled service boundary, not live account acceptance.
"""
import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store
from wixal.account import Accounts, AccountError
from test_integrations import Vault, Firebase


class MigrationWorkloads(unittest.TestCase):
    def test_populated_collections_persist_and_repeat_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);store=Store(base/'native');project=base/'project';project.mkdir()
            legacy=dict(projects=[dict(id='project',name='Project',root=str(project))],memories=[],
                sessions=[dict(id=f'chat-{i}',projectId='project',title=f'Conversation {i}',messages=[dict(role='user' if j%2==0 else 'assistant',content=f'Conversation {i} message {j}: '+ 'retained working context '*80) for j in range(12)]) for i in range(250)],
                skills=[dict(id=f'skill-{i}',name=f'Skill {i}',content='# Instructions\n'+('Use the actual project files and report results.\n'*20)) for i in range(100)],
                schedules=[dict(id=f'schedule-{i}',projectId='project',prompt=f'Read project report {i}',intervalSeconds=3600,enabled=True,model='saved-local-model',missedRunPolicy='skip') for i in range(100)],
                mcpServers=[dict(id=f'server-{i}',name=f'Local server {i}',command='python3',args=['server.py'],env={'API_KEY':'EXCLUDED_SECRET'}) for i in range(100)])
            source=base/'workspace.json';source.write_text(json.dumps(legacy));source_before=source.read_bytes()
            started=time.monotonic();result=store.import_legacy(source)
            self.assertLess(time.monotonic()-started,30,'A 3000-message workspace took over 30 seconds to import')
            self.assertEqual(result['counts']['sessions'],250)
            self.assertEqual(result['counts']['skills'],100)
            self.assertEqual(result['counts']['schedules'],100)
            self.assertEqual(result['counts']['mcpServers'],100)
            self.assertEqual(source.read_bytes(),source_before)
            self.assertNotIn('EXCLUDED_SECRET',json.dumps(store.data))
            self.assertTrue(all(not s['enabled'] and s['model']=='saved-local-model' and s['missedRunPolicy']=='skip' for s in store.data['schedules']))
            self.assertTrue(all(s['credentialsExcluded'] for s in store.data['mcpServers']))
            self.assertEqual(len(result['warnings']),200)
            # Existing native edits win when the unchanged Electron workspace is imported again.
            store.data['skills'][0]['content']='Reviewed native instructions';store.save()
            second=store.import_legacy(source)
            self.assertTrue(all(count==0 for count in second['counts'].values()))
            self.assertEqual(second['skippedExisting']['skills'],100)
            self.assertEqual(store.data['skills'][0]['content'],'Reviewed native instructions')
            store.close();restored=Store(base/'native')
            self.assertEqual(len(restored.data['sessions']),250)
            self.assertEqual(restored.data['sessions'][-1]['messages'][-1]['content'],legacy['sessions'][-1]['messages'][-1]['content'])
            self.assertEqual(restored.data['migration']['skippedExisting']['schedules'],100)
            self.assertEqual(restored.data['skills'][0]['content'],'Reviewed native instructions');restored.close()

    def test_invalid_collection_is_atomic_and_invalid_records_are_explained(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'native');source=Path(directory)/'workspace.json'
            original=copy.deepcopy(store.data)
            source.write_text(json.dumps(dict(projects=[],sessions=[],memories=[],skills=[dict(id='valid',name='Skill',content='Use actual files')],schedules='invalid collection')))
            with self.assertRaisesRegex(ValueError,'Invalid schedules'):store.import_legacy(source)
            self.assertEqual(store.data,original)
            source.write_text(json.dumps(dict(projects=[],sessions=[],memories=[],skills=[dict(id='invalid',name='Skill',content=3)],schedules=[dict(id='missing-project',projectId='missing',prompt='Run',intervalSeconds=60)],mcpServers=[dict(id='secret',command='server',args=['--token','PRIVATE'])])))
            result=store.import_legacy(source)
            self.assertEqual(len(result['warnings']),3)
            self.assertTrue(any('unknown project' in w for w in result['warnings']))
            self.assertNotIn('PRIVATE',json.dumps(store.data));store.close()


class AccountRecovery(unittest.IsolatedAsyncioTestCase):
    async def test_partial_cloud_delete_keeps_identity_and_retry_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);firebase=Firebase();firebase.verified=True;vault=Vault()
            documents=[dict(name=f'projects/fixture/presets/{i}') for i in range(3)]
            fail=True
            def service(url,body,method,token):
                nonlocal fail
                if '/presets' in url and method=='GET':return dict(documents=list(documents))
                if '/presets/' in url and method=='DELETE':
                    if len(documents)==2 and fail:raise AccountError('Temporary cloud outage',503)
                    documents[:]=[doc for doc in documents if not url.endswith(doc['name'].split('/')[-1])];return {}
                return firebase(url,body,method,token)
            accounts=Accounts(directory,dict(apiKey='fixture-public',projectId='fixture'),vault,service)
            # Sign in before injecting cloud documents, which use the Firestore delete shape.
            initial=documents[:];documents.clear()
            await accounts.dispatch('account-sign-in',dict(email='user@example.com',password='current'),store)
            documents[:]=initial
            with self.assertRaisesRegex(ValueError,'1 cloud preset'):
                await accounts.dispatch('account-delete',dict(password='current',confirmation='DELETE'),store)
            self.assertTrue(accounts.ready);self.assertIsNotNone(vault.value)
            self.assertFalse(any('accounts:delete' in call[0] for call in firebase.calls))
            self.assertEqual(len(documents),2)
            fail=False
            await accounts.dispatch('account-delete',dict(password='current',confirmation='DELETE'),store)
            self.assertEqual(documents,[]);self.assertFalse(accounts.ready);self.assertIsNone(vault.value)
            self.assertEqual(store.data['projects'],[]);store.close()

    async def test_online_password_change_reports_keychain_failure_without_losing_current_session(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);firebase=Firebase()
            class FailingVault(Vault):
                def set(self,value):
                    if value and value.get('idToken')=='CHANGED_ID':raise ValueError('Keychain unavailable')
                    super().set(value)
            vault=FailingVault();accounts=Accounts(directory,dict(apiKey='fixture-public',projectId='fixture'),vault,firebase)
            await accounts.dispatch('account-sign-in',dict(email='user@example.com',password='current'),store)
            with self.assertRaisesRegex(ValueError,'Password changed online'):
                await accounts.dispatch('account-password-change',dict(password='current',newPassword='replacement-password'),store)
            self.assertTrue(accounts.ready)
            self.assertEqual(accounts.user['idToken'],'CHANGED_ID')
            self.assertIn('Sign out and sign in with your new password',accounts.snapshot()['message'])
            self.assertNotIn('replacement-password',json.dumps(store.data));store.close()

    async def test_wrong_current_password_does_not_start_cloud_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);firebase=Firebase();vault=Vault()
            accounts=Accounts(directory,dict(apiKey='fixture-public',projectId='fixture'),vault,firebase)
            await accounts.dispatch('account-sign-in',dict(email='user@example.com',password='current'),store)
            def rejected(url,body,method,token):
                if 'signInWithPassword' in url:raise AccountError('Email or password is incorrect.',400)
                return firebase(url,body,method,token)
            accounts.transport=rejected
            before=len(firebase.calls)
            with self.assertRaises(AccountError):await accounts.dispatch('account-delete',dict(password='wrong',confirmation='DELETE'),store)
            self.assertTrue(accounts.ready);self.assertIsNotNone(vault.value)
            self.assertFalse(any(method=='DELETE' for _,_,method,_ in firebase.calls[before:]));store.close()

if __name__=='__main__':unittest.main()
