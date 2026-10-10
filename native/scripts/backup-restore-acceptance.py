"""Installed backup/restore acceptance over a copied, populated workspace.

No model inference is started. Existing real conversation contents are compared
independently; preview/changed-source refusal and duplicate import use JSON IPC.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import sqlite3
import time
from pathlib import Path

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(options):
    base=options.output.resolve();base.mkdir(parents=True,exist_ok=False)
    source=base/'source-workspace';source.mkdir()
    with sqlite3.connect(options.source_workspace/'workspace.sqlite3') as old,sqlite3.connect(source/'workspace.sqlite3') as new:old.backup(new)
    helper=options.helper.resolve();real.ART=base;real.STATE=source
    client=real.Client(False,helper=helper,endpoint='http://127.0.0.1:11434')
    report=dict(status='running',started=time.time(),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),cases=[],scope='Copied populated database; no account, credential or image restore claim')
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    def passed(name,**details):report['cases'].append(dict(name=name,status='passed',**details));save()
    def content(state):
        return dict(sessions={s['id']:[(m['role'],m.get('content','')) for m in s['messages']] for s in state['sessions']},memories={m['id']:(m.get('projectId'),m['content']) for m in state['memories']},projects={p['id']:(p['name'],p['root']) for p in state['projects']})
    try:
        await client.start();original=await client.state()
        assert len(original['projects'])>=2 and len(original['memories'])>=90
        assert any(m.get('usage',{}).get('eval_count',0)>0 for s in original['sessions'] for m in s['messages'])
        expected=content(original);backup=base/'saved-work.json'
        exported=await client.call('workspace-backup',dict(path=str(backup)));raw=backup.read_bytes();payload=json.loads(raw)
        assert payload['wixalBackupVersion']==1 and 'account' not in payload and 'enabledTools' not in payload
        assert all(not s.get('enabled') for s in payload['schedules'])
        assert content(payload)==expected
        passed('export-preserves-populated-record-content',counts=exported['counts'],sha256=hashlib.sha256(raw).hexdigest(),unencryptedJSON=True)
        await client.close();real.STATE=base/'restored-workspace';client=real.Client(False,helper=helper,endpoint='http://127.0.0.1:11434');await client.start()
        before=copy.deepcopy(await client.state());preview=await client.call('workspace-import-preview',dict(path=str(backup)))
        assert await client.state()==before
        backup.write_bytes(raw+b'\n')
        try:await client.call('workspace-import',dict(path=str(backup),digest=preview['digest']))
        except RuntimeError as error:assert 'source changed after preview' in str(error)
        else:raise AssertionError('Changed source imported without renewed preview')
        assert await client.state()==before
        passed('preview-is-read-only-and-changed-source-is-refused')
        backup.write_bytes(raw);preview=await client.call('workspace-import-preview',dict(path=str(backup)))
        imported=await client.call('workspace-import',dict(path=str(backup),digest=preview['digest']));state=await client.state();observed=content(state)
        for key,records in expected.items():
            for identifier,value in records.items():assert observed[key][identifier]==value,(key,identifier)
        assert state['enabledTools']==before['enabledTools']
        assert all(not s.get('enabled') for s in state['schedules'])
        passed('saved-work-restores-without-enabling-permissions',counts=imported['counts'],warnings=imported['warnings'])
        duplicate=await client.call('workspace-import',dict(path=str(backup),digest=preview['digest']))
        assert all(count==0 for count in duplicate['counts'].values())
        assert content(await client.state())==observed
        await client.close();client=real.Client(False,helper=helper,endpoint='http://127.0.0.1:11434');await client.start()
        assert content(await client.state())==observed
        passed('duplicate-import-is-idempotent-and-restored-records-survive-restart',skipped=duplicate['skippedExisting'])
        report['status']='passed'
    except BaseException as error:report.update(status='failed',error=str(error));raise
    finally:
        await client.close();report['finished']=time.time();save()
    print(json.dumps(dict(status=report['status'],cases=len(report['cases']))))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source-workspace',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
