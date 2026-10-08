"""Real local inference check using the packaged helper and managed model engine."""
import asyncio
import json
import os
import time
from pathlib import Path

root=Path(__file__).resolve().parents[2]
app=root/'release/native/Wixal.app'
artifact=root/'artifacts/native';artifact.mkdir(parents=True,exist_ok=True)

async def main():
    # Native storage is separate; the original Electron workspace and models are read-only sources.
    child=await asyncio.create_subprocess_exec(str(app/'Contents/Resources/engine/wixal-engine'),'--runtime',str(app/'Contents/Resources/ollama'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=16*1024*1024)
    next_id=0
    async def call(method,params=None):
        nonlocal next_id
        next_id+=1;request_id=str(next_id)
        child.stdin.write((json.dumps(dict(id=request_id,method=method,params=params or {}))+'\n').encode());await child.stdin.drain()
        while True:
            line=await asyncio.wait_for(child.stdout.readline(),240)
            if not line:raise RuntimeError((await child.stderr.read(5000)).decode())
            message=json.loads(line)
            if message['event']=='review':raise RuntimeError('Unexpected action review during inference QA')
            if message['event']=='response' and message['data']['id']==request_id:
                if message['data'].get('error'):raise RuntimeError(message['data']['error'])
                return message['data']['result']
    try:
        await call('hello')
        await call('legacy-import')
        imports=await call('model-imports')
        item=next(i for i in imports if i['name']=='gpt-oss:20b')
        start=time.monotonic()
        models=await call('model-import',item)
        print('Verified and imported the existing local model',flush=True)
        await call('settings',dict(model='gpt-oss:20b',mode='chat'))
        await call('session-new')
        task=await call('chat',dict(text='Reply with exactly: Wixal native local inference works.'))
        hello=await call('hello')
        session=next(s for s in hello['state']['sessions'] if s['id']==hello['state']['activeSession'])
        reply=next(m['content'] for m in reversed(session['messages']) if m['role']=='assistant')
        assert task['status']=='completed' and reply.strip(),reply
        report=dict(status='passed',model='gpt-oss:20b',response=reply,modelCount=len(models),totalSeconds=round(time.monotonic()-start,2),note='Includes model verification/import and cold inference. This is not a language performance benchmark.')
        (artifact/'live-inference.json').write_text(json.dumps(report,indent=2))
        # Ready for normal native use with reviews on, agent mode and the imported model.
        await call('settings',dict(mode='agent',approvalMode='review'))
        await call('session-new')
        print('PACKAGED_REAL_LOCAL_INFERENCE_OK',flush=True)
    finally:
        child.stdin.close()
        await asyncio.wait_for(child.wait(),30)

asyncio.run(main())
