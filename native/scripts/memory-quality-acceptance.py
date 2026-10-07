"""Real embeddings and actual small-model conversation acceptance in isolated storage."""
import asyncio
import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/memory-quality';ART.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
real.ART=ART;real.STATE=ART/'workspace'

async def main():
    options=argparse.ArgumentParser();options.add_argument('--packaged',action='store_true');opts=options.parse_args()
    client=real.Client(not opts.packaged);report=dict(status='running',cases=[]);path=ART/('packaged.json' if opts.packaged else 'source.json')
    report['implementation']='packaged' if opts.packaged else 'source'
    report['helperSHA256']=hashlib.sha256((ROOT/'release/native/Wixal Native.app/Contents/Resources/engine/wixal-engine').read_bytes()).hexdigest() if opts.packaged else None
    def save():path.write_text(json.dumps(report,indent=2))
    save()
    try:
        await client.start()
        await client.model('gemma3:1b')
        if not any(m['name'].startswith('embeddinggemma:') for m in await client.call('models')):await client.call('model-pull',dict(name='embeddinggemma'))
        while True:
            models=await client.call('models')
            tag=next((m['name'] for m in models if m['name'].startswith('embeddinggemma:')),None)
            if tag:break
            status=await client.call('model-status');row=next(d for d in status['downloads'] if d['name']=='embeddinggemma')
            if row['state']=='failed':raise RuntimeError(row.get('error'))
            print('Embedding model downloading:',row.get('completed',0),flush=True);await asyncio.sleep(3)
        await client.call('project-add',dict(root=str(ROOT),memoryMode='project',memorySize=24000))
        for note in (await client.call('memory-status'))['notes']:await client.call('memory-forget',dict(id=note['id']))
        for session in (await client.state())['sessions']:
            if session.get('projectId')==(await client.state())['activeProject']:await client.call('session-archive',dict(id=session['id']))
        await client.call('session-new')
        await client.call('memory-semantic',dict(model=tag))
        note=await client.call('memory-save',dict(content='The invoice service stores its records in PostgreSQL.'))
        await client.call('memory-save',dict(content='The desktop interface uses SwiftUI.'))
        started=time.monotonic();found=await client.call('memory-recall',dict(query='Which database holds the billing data?'))
        assert any(item['id']==note['id'] for item in found),found
        report['cases'].append(dict(name='paraphrase',sources=found,seconds=time.monotonic()-started));save()
        unrelated=await client.call('memory-recall',dict(query='How are volcanic islands formed?'))
        assert not unrelated,unrelated
        report['cases'].append(dict(name='unrelated',sources=unrelated));save()
        result=await client.chat('Which database holds the billing data?')
        assert 'postgres' in result['answer'].lower(),result
        report['cases'].append(dict(name='actual-small-model-recall',result=result));save()
        await client.call('memory-save',dict(id=note['id'],content='The invoice service stores its records in SQLite now.'))
        await client.call('session-new')
        result=await client.chat('Which database holds the billing data?')
        assert 'sqlite' in result['answer'].lower(),result
        report['cases'].append(dict(name='corrected-small-model-answer',result=result));save()
        await client.call('memory-forget',dict(id=note['id']))
        found=await client.call('memory-recall',dict(query='Which database holds the billing data?'))
        assert not any('sqlite' in item['content'].lower() or 'postgres' in item['content'].lower() for item in found),found
        report['cases'].append(dict(name='forgotten-source-exclusion',sources=found));save()
        report.update(status='passed',retrieval=await client.call('memory-status'));save();print('REAL_MEMORY_QUALITY_PASSED',flush=True)
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:await client.close()
asyncio.run(main())
