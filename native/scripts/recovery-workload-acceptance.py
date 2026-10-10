"""Frozen-helper recovery workload with real IPC, real model turns and independent oracles.

Only the output directory is used. No host reboot, shared runtime shutdown,
account operation or desktop acceptance is implied by this suite.
"""
import argparse
import asyncio
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
    real.ART=base;real.STATE=base/'workspace'
    helper=options.helper.resolve();app=helper.parents[3]
    client=real.Client(False,helper=helper,payload=app/'Contents/Resources/ollama',endpoint=options.endpoint)
    report=dict(status='running',started=time.time(),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),cases=[],limitations=['Helper IPC acceptance; native desktop and spoken VoiceOver are not exercised.','No sleep, reboot, remote account or second physical device is simulated.'])
    manifest=app/'Contents/Resources/SOURCE_MANIFEST.json'
    report['sourceManifestSha256']=hashlib.sha256(manifest.read_bytes()).hexdigest()
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    def record(name,**evidence):
        report['cases'].append(dict(name=name,status='passed',**evidence));save();print(name+': PASS',flush=True)
    async def reopen(abrupt=False):
        if abrupt:
            client.child.kill();await client.child.wait();await client.reading;client.log.close()
        else:await client.close()
        await client.start()
    save()
    try:
        await client.start()
        models=await client.call('models')
        if not any(m['name']==options.model for m in models):raise RuntimeError('Requested model must already be installed; this suite never downloads one')
        report['model']=await client.model(options.model);await client.call('settings',dict(contextSize=8192))
        projects=[];notes=[]
        for index in range(2):
            project=base/f'project-{index}';project.mkdir();(project/'source.txt').write_text(f'Actual project marker RECOVERY-{index}-7319\n')
            state=await client.call('project-add',dict(root=str(project)));projects.append(state['activeProject'])
            for number in range(options.notes):
                notes.append(await client.call('memory-save',dict(content=f'Project {index} accepted retention marker NOTE-{number:04d}-7319')))
            corrected=notes[-1]
            corrected=await client.call('memory-save',dict(id=corrected['id'],content=f'Project {index} corrected retention marker CORRECTED-7319'))
            forgotten=notes[-2];await client.call('memory-forget',dict(id=forgotten['id']))
            found=await client.call('memory-recall',dict(query='CORRECTED-7319'))
            assert any(n['id']==corrected['id'] for n in found),found
            assert not any(n['id']==forgotten['id'] for n in found),found
            output=await client.chat('Read source.txt and report its exact project marker. Do not change files or save memory.')
            assert f'RECOVERY-{index}-7319' in output['answer'],output
            assert any(m['tool_name']=='read_file' for m in output['toolResults']),output
            record(f'project-{index}-actual-model-read',output=output)
        await client.call('agent-save',dict(id='recovery-reader',name='Recovery reader',purpose='Read retained evidence',instructions='Use actual file tools and preserve exact markers.',model=options.model,reviewPolicy='Read only',memoryScope='Memory off'))
        cancelled=[]
        for index in range(options.jobs):
            job=await client.call('agent-enqueue',dict(agentID='recovery-reader',prompt=f'Read source.txt for queued case {index}',delaySeconds=86400,projectId=projects[index%2]))
            cancelled.append((await client.call('agent-job-cancel',dict(id=job['id'])))['id'])
        before=await client.state();(base/'before-restart.json').write_text(json.dumps(before,indent=2))
        await reopen()
        graceful=await client.state()
        for key in ('sessions','memories','agentJobs','agentProfiles'):
            assert graceful[key]==before[key],key
        record('graceful-restart-retains-exact-records',sessions=len(before['sessions']),notes=len(before['memories']),cancelledJobs=len(cancelled))
        await reopen(abrupt=True)
        restored=await client.state()
        for key in ('sessions','memories','agentJobs','agentProfiles'):
            assert restored[key]==before[key],key
        assert all(j['status']=='cancelled' for j in restored['agentJobs'] if j['id'] in cancelled)
        record('abrupt-idle-restart-retains-records-and-cancellations',cancelledJobs=cancelled)
        for index,project_id in enumerate(projects):
            await client.call('project-select',dict(id=project_id))
            recalled=await client.call('memory-recall',dict(query='CORRECTED-7319'))
            assert recalled and all(f'Project {index} ' in row['content'] for row in recalled),recalled
            record(f'project-{index}-corrected-memory-isolation-after-restart',sources=recalled)
        # Interrupt an actual inference, then independently inspect durable task
        # identity after reopening. The requested turn has no modifying tools.
        await client.call('session-new')
        pending=client.send('chat',dict(text='Explain in detail how a relational database preserves transactions. Do not use tools or save anything.'))
        await client.child.stdin.drain()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            state=await client.state()
            running=next((t for t in reversed(state['tasks']) if t.get('status')=='running'),None)
            if running:break
            if pending.done():raise RuntimeError('Inference finished before interruption; no active-recovery claim can be made')
            await asyncio.sleep(.1)
        else:raise TimeoutError('No active task was observed')
        await reopen(abrupt=True)
        await asyncio.gather(pending,return_exceptions=True)
        restored=await client.state();task=next(t for t in restored['tasks'] if t['id']==running['id'])
        assert task['status']=='interrupted',task
        session=next(s for s in restored['sessions'] if s['id']==task['sessionId'])
        assert any(m['role']=='user' and 'relational database' in m.get('content','') for m in session['messages']),session
        assert len([t for t in restored['tasks'] if t['id']==task['id']])==1
        record('active-model-task-interruption-no-automatic-replay',taskId=task['id'],sessionId=task['sessionId'],taskStatus=task['status'])
        db=sqlite3.connect(f'file:{real.STATE / "workspace.sqlite3"}?mode=ro',uri=True)
        try:assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        finally:db.close()
        record('independent-sqlite-integrity-check')
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error));raise
    finally:
        report['finished']=time.time();save()
        await client.close()
    return True

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--notes',type=int,default=50);parser.add_argument('--jobs',type=int,default=20)
    args=parser.parse_args()
    if not 2<=args.notes<=500 or not 1<=args.jobs<=100:parser.error('Use 2–500 notes and 1–100 queued jobs')
    asyncio.run(main(args))
