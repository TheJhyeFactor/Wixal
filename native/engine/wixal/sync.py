"""Opt-in encrypted folder sync. New records merge; divergent records require review."""
import asyncio
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
from .account import Keychain
from .memory import owner,SENSITIVE
from .storage import identity,now

MAX=64*1024*1024
COLLECTIONS=('projects','sessions','memories','globalMemories')

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def encode(payload,password):
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt=os.urandom(16);nonce=os.urandom(12)
    key=Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())
    plain=json.dumps(payload,ensure_ascii=False).encode()
    if len(plain)>MAX:raise ValueError('Sync snapshot exceeds 64 MB; reduce the selected history or attachments')
    return b'WIXALSYNC1'+salt+nonce+AESGCM(key).encrypt(nonce,plain,b'WIXALSYNC1')

def decode(raw,password):
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if len(raw)<54 or not raw.startswith(b'WIXALSYNC1') or len(raw)>MAX+1024:raise ValueError('Invalid or oversized Wixal sync snapshot')
    key=Scrypt(salt=raw[10:26],length=32,n=2**15,r=8,p=1).derive(password.encode())
    try:plain=AESGCM(key).decrypt(raw[26:38],raw[38:],b'WIXALSYNC1');return json.loads(plain)
    except Exception:raise ValueError('Cannot decrypt the sync snapshot. Check the shared passphrase.') from None


class Sync:
    def __init__(self,store):
        self.store=store;self.lock=asyncio.Lock()
        store.data.setdefault('syncState',dict(device=identity(),enabled=False,conflicts=[],bases={},warnings=[]))
        self.vault=Keychain(store.directory/'sync');self.vault.account=b'folder-sync'
    def snapshot(self):
        state=self.store.data['syncState']
        return {k:state.get(k) for k in ('enabled','folder','lastSync','conflicts','warnings','lastResult')}
    def payload(self):
        d=self.store.data;who=owner(self.store);selected={k:[] for k in COLLECTIONS}
        # Project notes belong to a local project; project sessions must match the active identity.
        selected['projects']=[self.comparable('projects',p) for p in d['projects']]
        allowed={p['id'] for p in selected['projects']}
        selected['sessions']=[copy.deepcopy(s) for s in d['sessions'] if s.get('memoryOwner','guest')==who and (s.get('projectId') is None or s['projectId'] in allowed)]
        for session in selected['sessions']:
            session.pop('draft',None);session.pop('contextInfo',None);session.pop('requests',None)
            session['messages']=[m for m in session.get('messages',[]) if not SENSITIVE.search(m.get('content',''))]
        selected['memories']=[copy.deepcopy(n) for n in d['memories'] if n.get('projectId') in allowed and not SENSITIVE.search(n['content'])]
        selected['globalMemories']=[copy.deepcopy(n) for n in d['globalMemories'] if n.get('owner')==who and not SENSITIVE.search(n['content'])]
        images={}
        for session in selected['sessions']:
            for m in session['messages']:
                for image_id in m.get('imageIds',[]):
                    from .conversation import read_image
                    images[image_id]=read_image(self.store,image_id)
        return dict(version=1,device=d['syncState']['device'],owner=who,collections=selected,images=images,
                    forgottenMemories=d['forgottenMemories'],forgottenMemorySources=d['forgottenMemorySources'],supersededMemorySources=d['supersededMemorySources'])
    async def configure(self,params):
        state=self.store.data['syncState']
        if params.get('enabled') is False:
            state['enabled']=False;await asyncio.to_thread(self.vault.set,None);self.store.save();return self.snapshot()
        folder=Path(params.get('folder','')).expanduser().resolve(strict=True)
        if not folder.is_dir():raise ValueError('Choose a shared folder available on both devices')
        password=params.get('passphrase','')
        if not isinstance(password,str) or not 12<=len(password)<=512:raise ValueError('Use a shared sync passphrase of at least 12 characters')
        # Validate existing snapshots before enabling so a wrong passphrase cannot fork the workspace.
        snapshots=list(folder.glob('*.wixalsync'))
        if len(snapshots)>20:raise ValueError('This sync folder has too many device snapshots')
        for file in snapshots:
            if file.is_symlink() or file.stat().st_size>MAX+1024:raise ValueError('Invalid sync snapshot')
            await asyncio.to_thread(decode,file.read_bytes(),password)
        await asyncio.to_thread(self.vault.set,dict(passphrase=password))
        state.update(enabled=True,folder=str(folder),warnings=[]);self.store.save();return self.snapshot()
    async def run(self):
        if self.lock.locked():raise ValueError('Sync is already running')
        backup=copy.deepcopy(self.store.data)
        try:return await self._run()
        except BaseException:
            self.store.data.clear();self.store.data.update(backup);self.store.save();raise

    async def _run(self):
        if self.lock.locked():raise ValueError('Sync is already running')
        async with self.lock:
            state=self.store.data['syncState']
            if not state['enabled']:raise ValueError('Enable encrypted folder sync first')
            secret=await asyncio.to_thread(self.vault.get)
            if not secret:raise ValueError('Enter the shared sync passphrase again')
            folder=Path(state['folder'])
            if not folder.is_dir():raise ValueError('The shared folder is unavailable')
            warnings=[];merged=0
            files=list(folder.glob('*.wixalsync'))
            if len(files)>20:raise ValueError('This sync folder has too many device snapshots')
            for file in files:
                if file.name==state['device']+'.wixalsync':continue
                if file.is_symlink() or file.stat().st_size>MAX+1024:raise ValueError('Invalid sync snapshot')
                remote=await asyncio.to_thread(decode,file.read_bytes(),secret['passphrase'])
                if remote.get('version')!=1:raise ValueError('Unsupported sync snapshot version')
                if remote.get('owner')!=owner(self.store):warnings.append('A snapshot belongs to another identity and was excluded.');continue
                # Tombstones stop a forgotten fact being restored by a device that was offline.
                for key in ('forgottenMemories','forgottenMemorySources','supersededMemorySources'):
                    values=remote.get(key,[])
                    if not isinstance(values,list) or not all(isinstance(v,str) and len(v)<=200 for v in values):raise ValueError('Invalid sync exclusions')
                    self.store.data[key]=list(dict.fromkeys(self.store.data[key]+values))
                for collection in COLLECTIONS:
                    records=remote.get('collections',{}).get(collection,[])
                    if not isinstance(records,list) or len(records)>50000:raise ValueError('Invalid sync collection')
                    local={n['id']:n for n in self.store.data[collection]}
                    for record in records:
                        if not isinstance(record,dict) or not isinstance(record.get('id'),str):raise ValueError('Invalid sync record')
                        if collection in ('memories','globalMemories') and record['id'] in self.store.data['forgottenMemories']:continue
                        self.validate(collection,record)
                        if collection=='globalMemories' and record.get('owner')!=remote['owner']:raise ValueError('A synced global note belongs to another identity')
                        if collection=='sessions' and record.get('memoryOwner','guest')!=remote['owner']:raise ValueError('A synced conversation belongs to another identity')
                        current=local.get(record['id']);key=collection+':'+record['id'];hash_remote=fingerprint(record)
                        previous=state['bases'].get(key)
                        if current is None:
                            if collection=='projects':record=record|dict(root='',syncRootRequired=True)
                            self.store.data[collection].append(copy.deepcopy(record));local[record['id']]=record;merged+=1;state['bases'][key]=fingerprint(self.comparable(collection,record))
                        else:
                            comparison=self.comparable(collection,current);incoming=self.comparable(collection,record)
                            if fingerprint(comparison)==fingerprint(incoming):
                                state['bases'][key]=fingerprint(incoming);state['conflicts']=[c for c in state['conflicts'] if c['key']!=key];continue
                            if previous and fingerprint(comparison)==previous:
                                replacement=copy.deepcopy(record)
                                if collection=='projects':replacement.update(root=current.get('root',''),syncRootRequired=current.get('syncRootRequired',False),approvalMode=current.get('approvalMode','review'))
                                self.store.data[collection][self.store.data[collection].index(current)]=replacement;state['bases'][key]=fingerprint(incoming);merged+=1
                            elif not any(c['key']==key and c['digest']==hash_remote and c['localDigest']==fingerprint(current) for c in state['conflicts']):
                                state['conflicts']=[c for c in state['conflicts'] if c['key']!=key or c.get('device')!=remote.get('device')]
                                state['conflicts'].append(dict(id=identity(),key=key,collection=collection,record=record,digest=hash_remote,localDigest=fingerprint(current),title=record.get('title') or record.get('name') or record.get('content','')[:100],device=remote.get('device')))
                for image_id,encoded in remote.get('images',{}).items():
                    import re
                    if not re.fullmatch('[a-f0-9]{64}',image_id) or not isinstance(encoded,str) or len(encoded)>8*1024*1024:raise ValueError('Invalid synced image')
                    raw=base64.b64decode(encoded,validate=True)
                    if hashlib.sha256(raw).hexdigest()!=image_id:raise ValueError('Synced image failed integrity validation')
                    images=self.store.directory/'attachments';images.mkdir(exist_ok=True)
                    target=images/image_id
                    if not target.exists():target.write_bytes(raw);target.chmod(0o600)
            for collection in ('memories','globalMemories'):
                self.store.data[collection]=[n for n in self.store.data[collection] if n['id'] not in self.store.data['forgottenMemories']]
            payload=self.payload();fingerprint_payload=fingerprint(payload)
            target=folder/(state['device']+'.wixalsync')
            if state.get('published')!=fingerprint_payload or not target.exists():
                raw=await asyncio.to_thread(encode,payload,secret['passphrase'])
                temporary=target.with_suffix('.tmp');temporary.write_bytes(raw);temporary.chmod(0o600);temporary.replace(target)
                state['published']=fingerprint_payload
            state.update(lastSync=now(),warnings=list(dict.fromkeys(warnings)),lastResult=dict(merged=merged,conflicts=len(state['conflicts'])))
            self.store.save();return self.snapshot()
    @staticmethod
    def comparable(collection,record):
        value=copy.deepcopy(record)
        if collection=='projects':
            for key in ('root','syncRootRequired','approvalMode'):value.pop(key,None)
        if collection=='sessions':
            for key in ('draft','contextInfo','requests'):value.pop(key,None)
        return value
    @staticmethod
    def validate(collection,record):
        if collection=='projects':
            if not isinstance(record.get('name'),str):raise ValueError('Invalid synced project')
            # Local command/approval settings and root paths never travel through sync.
            for key in ('approvalMode','root'):record.pop(key,None)
        elif collection=='sessions':
            if not isinstance(record.get('messages'),list) or not isinstance(record.get('title'),str):raise ValueError('Invalid synced conversation')
            for message in record['messages']:
                if not isinstance(message,dict) or message.get('role') not in ('user','assistant','tool') or not isinstance(message.get('content',''),str):raise ValueError('Invalid synced message')
        elif not isinstance(record.get('content'),str) or not 1<=len(record['content'])<=4000:raise ValueError('Invalid synced note')
    def resolve(self,params):
        state=self.store.data['syncState'];conflict=next((c for c in state['conflicts'] if c['id']==params.get('id')),None)
        if not conflict:raise ValueError('This conflict was already resolved')
        collection=conflict['collection'];current=next((n for n in self.store.data[collection] if n['id']==conflict['record']['id']),None)
        if not current or fingerprint(current)!=conflict['localDigest']:raise ValueError('Local record changed. Sync again before reviewing this conflict.')
        if params.get('choice')=='remote':
            replacement=copy.deepcopy(conflict['record'])
            if collection=='projects':replacement.update(root=current.get('root',''),syncRootRequired=current.get('syncRootRequired',False),approvalMode=current.get('approvalMode','review'))
            self.store.data[collection][self.store.data[collection].index(current)]=replacement
        elif params.get('choice')!='local':raise ValueError('Choose local or incoming')
        state['bases'][conflict['key']]=fingerprint(self.comparable(collection,conflict['record']))
        state['conflicts']=[c for c in state['conflicts'] if c['key']!=conflict['key']];self.store.save();return self.snapshot()
