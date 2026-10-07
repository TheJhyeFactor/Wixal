"""Real bundled crypto and Keychain with two local workspaces.
Uses persisted actual model conversation/image evidence, not fabricated replies.
This does not certify cloud-folder delivery or another Mac.
"""
import asyncio,base64,hashlib,importlib.util,json,secrets,shutil,sqlite3,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/folder-sync';ART.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real);real.ART=ART
async def main():
 root=Path(tempfile.mkdtemp(prefix='run-',dir=ART));a=root/'a';b=root/'b';folder=root/'encrypted';folder.mkdir();a.mkdir()
 source=ROOT/'artifacts/native/feature-acceptance/workspace'
 with sqlite3.connect(source/'workspace.sqlite3') as original,sqlite3.connect(a/'workspace.sqlite3') as copied:original.backup(copied)
 shutil.copytree(source/'attachments',a/'attachments')
 ca=real.Client(False);cb=real.Client(False);opened=[];report=dict(status='running',scope='actual packaged helpers, macOS Keychain and local encrypted folder',workspace=str(root))
 path=ART/'packaged.json';password=secrets.token_urlsafe(32)
 try:
  real.STATE=a;await ca.start();opened.append(ca);real.STATE=b;await cb.start();opened.append(cb)
  original=await ca.state();evidence=next(s for s in original['sessions'] if any(m.get('imageIds') for m in s['messages']) and any(m.get('usage',{}).get('eval_count',0)>0 for m in s['messages']))
  for client in opened:await client.call('sync-settings',dict(enabled=True,folder=str(folder),passphrase=password))
  await ca.call('sync-run');await cb.call('sync-run');incoming=await cb.state()
  received=next(s for s in incoming['sessions'] if s['id']==evidence['id']);assert received['messages']==evidence['messages']
  for p in incoming['projects']:assert p['root']=='' and p['syncRootRequired']
  image_id=next(i for m in received['messages'] for i in m.get('imageIds',[]));image=await cb.call('image-read',dict(id=image_id));assert hashlib.sha256(base64.b64decode(image['base64'])).hexdigest()==image_id
  before={f.name:f.read_bytes() for f in folder.glob('*.wixalsync')};await cb.call('sync-run');assert before=={f.name:f.read_bytes() for f in folder.glob('*.wixalsync')},'Unchanged sync rewrote ciphertext'
  for client in opened:await client.call('project-select',dict(id=None))
  note=await ca.call('memory-save',dict(scope='global',content='The native Package.swift pins SwiftTerm 1.20.0.'));assert 'exact: "1.20.0"' in (ROOT/'native/Package.swift').read_text()
  await ca.call('sync-run');await cb.call('sync-run')
  await ca.call('memory-save',dict(scope='global',id=note['id'],content='The native terminal dependency is SwiftTerm 1.20.0.'))
  await cb.call('memory-save',dict(scope='global',id=note['id'],content='The native Package.swift also pins swift-markdown 0.9.0.'));assert 'exact: "0.9.0"' in (ROOT/'native/Package.swift').read_text()
  await cb.call('sync-run');result=await ca.call('sync-run');conflict=next(c for c in result['conflicts'] if c['record']['id']==note['id'])
  await ca.call('sync-resolve',dict(id=conflict['id'],choice='remote'))
  state=await ca.state();assert next(n for n in state['globalMemories'] if n['id']==note['id'])['content'].endswith('0.9.0.')
  await ca.call('memory-forget',dict(id=note['id']));await ca.call('sync-run');await cb.call('sync-run');assert not any(n['id']==note['id'] for n in (await cb.state())['globalMemories'])
  report.update(status='passed',checks=['actual model messages and counters preserved','image bytes verified','project roots require local remapping','unchanged ciphertext not rewritten','divergent notes produce review','explicit incoming resolution','forget tombstone reaches second workspace'],files=len(list(folder.glob('*.wixalsync'))),externalTwoDeviceDelivery='not exercised')
 except BaseException as error:report.update(status='failed',error=str(error));raise
 finally:
  for client in reversed(opened):
   try:await client.call('sync-settings',dict(enabled=False))
   finally:await client.close()
  path.write_text(json.dumps(report,indent=2))
 print('PACKAGED_ENCRYPTED_SYNC_PASSED')
asyncio.run(main())
