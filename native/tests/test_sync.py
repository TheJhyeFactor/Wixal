import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store
from wixal.sync import Sync,encode,decode
class Vault:
 def __init__(self):self.value=dict(passphrase='shared-passphrase-acceptance')
 def get(self):return self.value
 def set(self,value):self.value=value

class SyncTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.folder=root/'shared';self.folder.mkdir()
  self.a=Store(root/'a');self.b=Store(root/'b');self.sa=Sync(self.a);self.sb=Sync(self.b)
  for sync in (self.sa,self.sb):sync.vault=Vault();sync.store.data['syncState'].update(enabled=True,folder=str(self.folder))
 async def asyncTearDown(self):self.a.close();self.b.close();self.temp.cleanup()
 async def test_merge_conflict_forget_and_local_roots(self):
  p=self.a.add_project(self.temp.name);n=self.a.memory.save('Invoice database is PostgreSQL')
  s=self.a.session();s['messages']=[dict(role='user',content='Which invoice database?'),dict(role='assistant',content='PostgreSQL',memoryReferences=[n['id']])];self.a.save()
  await self.sa.run();await self.sb.run()
  self.assertEqual(len(self.b.data['memories']),1);self.assertEqual(len(self.b.data['sessions']),1)
  self.assertEqual(self.b.data['projects'][0]['root'],'');self.assertTrue(self.b.data['projects'][0]['syncRootRequired'])
  self.b.data['projects'][0].update(root=self.temp.name,syncRootRequired=False);self.b.select_project(p['id'])
  self.b.memory.save('Invoice database is SQLite',replace=n['id']);self.a.memory.save('Invoice database is MySQL',replace=n['id'])
  await self.sb.run();await self.sa.run();conflicts=self.sa.snapshot()['conflicts']
  conflict=next(c for c in conflicts if c['collection']=='memories')
  self.sa.resolve(dict(id=conflict['id'],choice='remote'));self.assertIn('SQLite',self.a.memories()[0]['content'])
  self.a.memory.forget(n['id']);await self.sa.run();await self.sb.run();self.assertFalse(self.b.memories())
  for file in self.folder.glob('*.wixalsync'):self.assertNotIn(b'SQLite',file.read_bytes())
 async def test_image_bytes_survive_sync_and_history_recall(self):
  import base64,hashlib
  from wixal.conversation import attachments,read_image
  self.a.add_project(self.temp.name)
  raw=b'\x89PNG\r\n\x1a\n'+b'fixture-image-content'
  saved=attachments([dict(type='image',name='sync.png',base64=base64.b64encode(raw).decode())],self.a)[0]
  self.a.session()['messages']=[dict(role='user',content='Describe the synced attachment',imageIds=[saved['imageId']])];self.a.save()
  await self.sa.run();await self.sb.run()
  image_id=hashlib.sha256(raw).hexdigest()
  self.assertEqual(base64.b64decode(read_image(self.b,image_id)),raw)
  self.assertEqual(self.b.data['sessions'][0]['messages'][0]['imageIds'],[image_id])

 async def test_identity_excludes_foreign_records(self):
  self.a.data['account']=dict(signedIn=True,profile=dict(id='different'));self.a.add_project(self.temp.name);self.a.memory.save('Private account note');await self.sa.run();await self.sb.run()
  self.assertEqual(self.b.data['memories'],[]);self.assertTrue(self.sb.snapshot()['warnings'])
 def test_tamper_wrong_password_and_size_limit(self):
  raw=encode(dict(example='private'),'valid-test-passphrase')
  self.assertEqual(decode(raw,'valid-test-passphrase')['example'],'private')
  for value,password in ((raw,'wrong-passphrase'),(raw[:-1]+bytes([raw[-1]^1]),'valid-test-passphrase')):
   with self.assertRaises(ValueError):decode(value,password)
