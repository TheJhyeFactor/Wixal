"""Packaged model browser IPC, live Hub metadata and isolated real GGUF lifecycle."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path,default=ROOT/'release/native/Wixal.app');parser.add_argument('--output',type=Path,default=ROOT/'artifacts/native/model-browser-2026-10-12/packaged')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    real.ART=args.output;real.STATE=args.output/'data'
    helper=args.app/'Contents/Resources/engine/wixal-engine'
    report=dict(status='running',helperSha256=hashlib.file_digest(helper.open('rb'),'sha256').hexdigest(),checks={})
    def record(name,result):
        report['checks'][name]=result;(args.output/'results.json').write_text(json.dumps(report,indent=2));print(name+': passed',flush=True)
    c=real.Client(False,helper,args.app/'Contents/Resources/ollama')
    try:
        await c.start()
        filters=await c.call('model-hf-filters')
        assert len(filters['popularTypes'])==5 and len(filters['providers'])==5
        tasks={row['id']:row['label'] for row in filters['tasks']}
        assert all(tasks[row['id']]==row['label'] for row in filters['popularTypes'])
        providers=await c.call('model-hf-filters',dict(kind='provider',search='google'))
        assert any(row['id'].lower()=='google' for row in providers['providers'])
        record('liveHubTaskCatalogTopFiveAndProviderSearch',dict(filters=filters,providerSearch=providers))
        typed=await c.call('model-hf-search',dict(search='Qwen3-0.6B',publisher='Qwen',task='text-generation'))
        assert typed['models'] and all(row['pipelineTag']=='text-generation' for row in typed['models'])
        record('officialTaskFilter',dict(tasks=[row['pipelineTag'] for row in typed['models']]))
        result=await c.call('model-hf-search',dict(search='Qwen3-0.6B',publisher='Qwen',parameters='2',type='all'))
        assert result['models'] and all(m['publisher']=='Qwen' and m['parameters']<=2e9 for m in result['models'])
        assert any('embedding' in m['types'] for m in result['models'])
        file=next(m['files'][0] for m in result['models'] if m['repo']=='Qwen/Qwen3-0.6B-GGUF')
        assert file['size']>0 and file['fit']['recommended']*.75>=file['fit']['required']
        record('liveHubProviderParametersFilesAndRAM',dict(models=[{k:m.get(k) for k in ('repo','publisher','parameters','types','size')} for m in result['models']],file=file))
        cache=real.STATE/'local-runtime/huggingface';cache.mkdir(parents=True,exist_ok=True)
        original=ROOT/'artifacts/native/hf-security-completion/packaged-acceptance-final/data/local-runtime/huggingface'/(file['sha256']+'.gguf')
        assert original.is_file(),'Acceptance requires the previously retained real GGUF file'
        cached=cache/original.name;shutil.copyfile(original,cached)
        result=await c.call('model-pull',{k:file[k] for k in ('repo','file','revision')})
        job=next(j for j in result['downloads'] if j['name']==file['name'])
        assert job['state'] in ('queued','downloading') and job['publisher']=='Qwen' and job['fit']['required']>0
        record('downloadRowIdentityAndRAM',job)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            status=await c.call('model-status');job=next(j for j in status['downloads'] if j['id']==job['id'])
            if job['state']=='completed':break
            assert job['state']!='failed',job
            await asyncio.sleep(.1)
        else:raise TimeoutError('Real GGUF import did not complete')
        await c.call('model-use',dict(name=file['name']))
        before=await c.state();sessions=len(before['sessions'])
        assert before['modelSources'][file['name']]['pipelineTag']=='text-generation'
        record('verifiedCachedGGUFImportAndSelection',dict(job=job,selected=before['model'],sourceSha256=file['sha256']))
        await c.call('model-delete',dict(name=file['name']))
        after=await c.state();status=await c.call('model-status')
        assert not any(m['name']==file['name'] for m in status['installed'])
        assert not cached.exists() and after['model']=='' and len(after['sessions'])==sessions
        record('realIsolatedDeletionAndCacheReclamation',dict(modelAbsent=True,cacheAbsent=True,historiesRetained=True))
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error));raise
    finally:
        await c.close();(args.output/'results.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':asyncio.run(main())
