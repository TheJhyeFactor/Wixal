"""Packaged feature acceptance with real HTTP and actual downloaded model weights."""
import asyncio
import importlib.util
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/feature-acceptance';ART.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
real.ART=ART;real.STATE=Path.home()/'Library/Application Support/Wixal Native Acceptance/background-workspace'
MODEL_SOURCE=ROOT/'artifacts/native/real-acceptance/workspace/local-runtime/models'
async def main():
    app=Path.home()/'Applications/Wixal.app'
    helper=app/'Contents/Resources/engine/wixal-engine'
    digest=hashlib.sha256(helper.read_bytes()).hexdigest()
    assert digest==hashlib.sha256((ROOT/'release/native/Wixal.app/Contents/Resources/engine/wixal-engine').read_bytes()).hexdigest(),'Install the current local package before running launchd acceptance'
    report=dict(status='running',checks=[],workspace=str(real.STATE),helperSHA256=digest);path=ART/'packaged.json'
    def save():path.write_text(json.dumps(report,indent=2))
    save()
    models=real.STATE/'local-runtime/models'
    if not models.exists():
        models.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['cp','-cR',str(MODEL_SOURCE),str(models)],check=True)
    client=real.Client(False,helper=helper,payload=app/'Contents/Resources/ollama');label=None;started=False
    try:
        await client.start();started=True
        await client.model('gemma3:1b')
        for schedule in (await client.state())['schedules']:
            if schedule.get('enabled'):await client.call('schedule-toggle',dict(id=schedule['id'],enabled=False))
        await client.call('mcp-add',dict(name='DeepWiki acceptance',transport='http',url='https://mcp.deepwiki.com/mcp'))
        state=await client.state();server=state['mcpServers'][-1]
        await client.call('mcp-connect',dict(id=server['id']))
        hello=await client.call('hello');tool=next(t for t in hello['tools'] if t['function'].get('original')=='read_wiki_structure')
        # Enable the explicitly selected public read in this disposable acceptance workspace.
        await client.call('settings',dict(enabledTools=state['enabledTools']+[tool['function']['name']],approvalMode='bypass'))
        output=await client.call('tool',dict(name=tool['function']['name'],arguments=dict(repoName='modelcontextprotocol/python-sdk')))
        assert 'client' in str(output).lower()
        await client.call('mcp-disconnect',dict(id=server['id']))
        report['checks'].append(dict(name='packaged-live-remote-MCP',result=output));save()
        await client.call('settings',dict(approvalMode='review'))
        await client.call('schedule-add',dict(prompt='Explain in one sentence what background scheduling does for recurring tasks.',intervalSeconds=60,missedRunPolicy='latest'))
        setting=await client.call('background-settings',dict(enabled=True));label=setting['label']
        report['backgroundLabel']=label;save()
        # Close the foreground helper. Launchd must own the run while the app is closed.
        await client.close();started=False
        deadline=time.monotonic()+150
        import sqlite3
        while time.monotonic()<deadline:
            with sqlite3.connect(real.STATE/'workspace.sqlite3') as db:d=json.loads(db.execute('SELECT value FROM state').fetchone()[0])
            schedule=d['schedules'][-1];last=schedule.get('lastRun',{})
            if last.get('status') in ('completed','failed','paused','interrupted'):
                assert last['status']=='completed',last
                assert last.get('background'),last
                task=next(t for t in d['tasks'] if t['id']==last['taskId']);session=next(s for s in d['sessions'] if s['id']==task['sessionId'])
                answer=next(m for m in reversed(session['messages']) if m['role']=='assistant' and m.get('content'))
                assert answer.get('usage',{}).get('eval_count',0)>0
                assert any(word in answer['content'].lower() for word in ('schedul','task','automatic','recurr')),answer
                report['checks'].append(dict(name='launchd-closed-app-real-inference',schedule=last,answer=answer['content'],usage=answer['usage']));save();break
            await asyncio.sleep(3)
        else:raise TimeoutError('LaunchAgent did not produce a completed model response')
        # LaunchAgent must relinquish state for foreground reopening.
        await client.start();started=True
        await client.call('background-settings',dict(enabled=False));label=None
        await client.call('schedule-toggle',dict(id=schedule['id'],enabled=False))
        report.update(status='passed');save();print('PACKAGED_FEATURE_ACCEPTANCE_PASSED')
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:
        if started:
            if label:
                try:await client.call('background-settings',dict(enabled=False));label=None
                except Exception:pass
            await client.close()
        if label:
            plist=Path.home()/'Library/LaunchAgents'/ (label+'.plist')
            subprocess.run(['launchctl','bootout','gui/'+str(os.getuid()),str(plist)],capture_output=True);plist.unlink(missing_ok=True)
asyncio.run(main())
