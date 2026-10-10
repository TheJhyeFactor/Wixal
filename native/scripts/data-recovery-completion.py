"""Bounded installed data qualification, plus explicit source SQLite fault injection.

Uses disposable local workspaces and existing model weights. Process termination
is not a physical power-loss claim. Semantic embeddings remain disabled.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

def records(state):
    return {key:copy.deepcopy(state.get(key,[])) for key in ('projects','sessions','memories','globalMemories','forgottenMemories','forgottenMemorySources','supersededMemorySources')}

def disk(path):
    with sqlite3.connect(path/'workspace.sqlite3') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return json.loads(db.execute('SELECT value FROM state').fetchone()[0])

async def main(o):
    base=o.output.resolve();base.mkdir(parents=True,exist_ok=False);real.ART=base;real.STATE=base/'workspace'
    helper=o.app/'Contents/Resources/engine/wixal-engine'
    client=real.Client(False,helper=helper,endpoint=o.endpoint)
    report=dict(status='running',started=time.time(),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),sourceManifestSha256=hashlib.sha256((o.app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(),cases=[],limitations=['One physical Mac; process termination, not power loss.','Six real model turns across three restart cycles; generated scale evidence is separate.','Lexical recall; no embedding model selected or semantic quality claim.'])
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    def passed(name,**evidence):report['cases'].append(dict(name=name,status='passed',**evidence));save();print(name+': PASS',flush=True)
    async def kill():
        client.child.kill();await client.child.wait();await client.reading;client.log.close()
    try:
        await client.start()
        assert any(m['name']==o.model for m in await client.call('models')),'Existing model required; no download'
        report['model']=await client.model(o.model);await client.call('settings',dict(contextSize=8192))
        ids=[];notes=[]
        for i in range(2):
            root=base/f'project-{i}';root.mkdir();(root/'marker.txt').write_text(f'RETENTION-PROJECT-{i}-7319\n')
            state=await client.call('project-add',dict(root=str(root)));ids.append(state['activeProject'])
            for n in range(12):notes.append(await client.call('memory-save',dict(content=f'Project {i} retention note {n}: original amber marker.')))
        turns=[]
        for cycle in range(3):
            for i,identifier in enumerate(ids):
                await client.call('project-select',dict(id=identifier));await client.call('session-new')
                turn=await client.chat('Read marker.txt and report its exact marker. Do not change files or save memory.');turns.append(turn)
                assert f'RETENTION-PROJECT-{i}-7319' in turn['answer']
                assert any(t['tool_name']=='read_file' for t in turn['toolResults'])
            before=records(await client.state());await client.close();await client.start()
            assert records(await client.state())==before
            assert records(disk(real.STATE))==before
            passed(f'repeated-session-cycle-{cycle}',conversationCount=len(before['sessions']),independentRecordDigest=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest())
        report['turns']=turns
        for i,identifier in enumerate(ids):
            await client.call('project-select',dict(id=identifier));note=notes[i*12]
            await client.call('memory-save',dict(id=note['id'],content=f'Project {i} corrected ultramarine setting.'))
            await client.call('memory-forget',dict(id=notes[i*12+1]['id']))
            recalled=await client.call('memory-recall',dict(query='ultramarine'))
            assert recalled and all(f'Project {i}' in n['content'] for n in recalled)
        await client.call('project-select',dict(id=None))
        global_note=await client.call('memory-save',dict(scope='global',content='The shared local preference is celadon.'))
        expected=records(await client.state());backup=base/'backup.json'
        await client.call('workspace-backup',dict(path=str(backup)));backup_hash=hashlib.sha256(backup.read_bytes()).hexdigest()
        # SQLite lock prevents the requested write reaching its commit boundary.
        lock=sqlite3.connect(real.STATE/'workspace.sqlite3');lock.execute('BEGIN IMMEDIATE')
        pending=client.send('memory-save',dict(scope='global',content='UNCOMMITTED-VIOLET-ONLY'));await client.child.stdin.drain()
        await asyncio.sleep(.25);assert not pending.done()
        await kill();lock.rollback();lock.close();await asyncio.gather(pending,return_exceptions=True)
        assert records(disk(real.STATE))==expected
        await client.start();assert records(await client.state())==expected
        passed('kill-during-blocked-write-preserves-last-commit',databaseIntegrity='ok')
        committed=await client.call('memory-save',dict(scope='global',content='Committed jade restart marker.'));committed_state=records(await client.state())
        await kill();assert records(disk(real.STATE))==committed_state
        await client.start();assert records(await client.state())==committed_state
        passed('kill-after-acknowledged-commit-retains-new-record',noteId=committed['id'])
        await client.close();real.STATE=base/'restored';client=real.Client(False,helper=helper,endpoint=o.endpoint);await client.start()
        preview=await client.call('workspace-import-preview',dict(path=str(backup)));before=records(await client.state())
        with sqlite3.connect(real.STATE/'workspace.sqlite3') as db:
            db.execute("CREATE TRIGGER reject_restore BEFORE UPDATE ON state BEGIN SELECT RAISE(ABORT, 'controlled restore failure'); END")
        try:await client.call('workspace-import',dict(path=str(backup),digest=preview['digest']))
        except RuntimeError as error:assert 'controlled restore failure' in str(error)
        else:raise AssertionError('Restore unexpectedly succeeded')
        assert records(await client.state())==before and records(disk(real.STATE))==before
        with sqlite3.connect(real.STATE/'workspace.sqlite3') as db:db.execute('DROP TRIGGER reject_restore')
        passed('failed-installed-restore-is-atomic')
        await client.call('workspace-import',dict(path=str(backup),digest=preview['digest']))
        state=await client.state()
        for key in ('memories','globalMemories','forgottenMemories','forgottenMemorySources','supersededMemorySources'):
            assert state[key]==expected[key],key
        for original in expected['sessions']:
            restored=next(s for s in state['sessions'] if s['id']==original['id'])
            assert [(m['id'],m['role'],m['content']) for m in restored['messages']]==[(m['id'],m['role'],m['content']) for m in original['messages']]
        await client.call('workspace-import',dict(path=str(backup),digest=preview['digest']))
        for identifier in ids:
            await client.call('project-select',dict(id=identifier));assert not any(n['id'] in expected['forgottenMemories'] for n in await client.call('memory-recall',dict(query='amber')))
            recalled=await client.call('memory-recall',dict(query='ultramarine'));assert recalled and all(n['scope']=='project' for n in recalled)
        await client.call('project-select',dict(id=None));assert any(n['id']==global_note['id'] for n in await client.call('memory-recall',dict(query='celadon')))
        after=records(await client.state());await client.close();await client.start();assert records(await client.state())==after
        assert hashlib.sha256(backup.read_bytes()).hexdigest()==backup_hash
        passed('native-restore-retains-scopes-revisions-tombstones-and-history',backupSha256=backup_hash)
        await client.close()
        # Controlled source faults execute the actual Store/import SQL. Each
        # callback terminates inside SQLite's virtual machine, before commit.
        for operation in ('save','import'):
            for cut in (1,5,10):
                target=base/f'source-{operation}-cut-{cut}';target.mkdir()
                with sqlite3.connect(base/'workspace/workspace.sqlite3') as src,sqlite3.connect(target/'workspace.sqlite3') as dst:src.backup(dst)
                prior=records(disk(target));proof=target/'fault.json'
                code="""import json,os,sys\nfrom pathlib import Path\nfrom wixal.storage import Store\nfrom wixal.migration import import_workspace\ns=Store(sys.argv[1]);count=0\ndef interrupt():\n global count\n count+=1\n if count==int(sys.argv[2]):\n  Path(sys.argv[3]).write_text(json.dumps(dict(sqliteOpcodeCallbacks=count,operation=sys.argv[4])))\n  os._exit(91)\n return 0\ns.db.set_progress_handler(interrupt,1)\nif sys.argv[4]=='import':import_workspace(s,sys.argv[5],preserve_preferences=True)\nelse:s.data['globalMemories']=[];s.save()\nraise SystemExit(2)\n"""
                import os
                env={**os.environ,'PYTHONPATH':str(ROOT/'native/engine')}
                child=subprocess.run([sys.executable,'-c',code,str(target),str(cut),str(proof),operation,str(backup)],env=env,capture_output=True,text=True,timeout=30)
                assert child.returncode==91 and proof.exists(),dict(returncode=child.returncode,error=child.stderr)
                assert records(disk(target))==prior
                passed(f'source-sqlite-{operation}-interruption-{cut}',fault=json.loads(proof.read_text()),evidenceClass='controlled-source-fault')
        report['status']='passed'
    except BaseException as error:report.update(status='failed',error=str(error));raise
    finally:
        if hasattr(client,'child') and client.child.returncode is None:await client.close()
        report['finished']=time.time();save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--endpoint',default='http://127.0.0.1:11434');p.add_argument('--model',default='gpt-oss:20b');asyncio.run(main(p.parse_args()))
