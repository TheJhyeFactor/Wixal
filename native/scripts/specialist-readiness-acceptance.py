"""Installed specialist readiness and rejection; no tools are installed or run."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import time
from pathlib import Path

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(options):
    base=options.output.resolve();base.mkdir(parents=True,exist_ok=False)
    real.ART=base;real.STATE=base/'workspace'
    helper=options.helper.resolve();resources=helper.parents[3]/'Contents/Resources'
    client=real.Client(False,helper=helper)
    report=dict(status='running',started=time.time(),cases=[],
                helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
                sourceManifestSha256=hashlib.sha256((resources/'SOURCE_MANIFEST.json').read_bytes()).hexdigest(),
                acceptanceScriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        await client.start();project=base/'project';project.mkdir()
        await client.call('project-add',dict(root=str(project)))
        report['catalogue']=await client.call('tool',dict(name='addon_catalog',arguments={}))
        for identifier in ('mitmproxy','zap','metasploit'):
            row=next(r for r in report['catalogue']['packages'] if r['id']==identifier)
            assert row['adapter']=='setup_required' and row['capabilityReady'] is False,row
            error=None
            try:
                await client.call('tool',dict(name='addon_run',arguments=dict(id=identifier,target='http://127.0.0.1:1',timeout_seconds=10)))
            except RuntimeError as failure:
                error=str(failure)
            assert error and 'Invalid value for id' in error, 'Unsupported specialist was executable: '+identifier
            report['cases'].append(dict(id=identifier,status='passed',readiness=row['readiness'],error=error))
        assert not client.reviews,client.reviews
        report.update(status='passed',reviews=client.reviews)
    except BaseException as error:
        report.update(status='failed',error=str(error));raise
    finally:
        await client.close();report['finished']=time.time()
        (base/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],cases=[r['id'] for r in report['cases']],reviews=len(report['reviews']))))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
