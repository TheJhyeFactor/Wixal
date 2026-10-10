"""Installed real-model branches, isolated artifacts and interruption recovery.

All effects are confined to the disposable output project. The append-only
effect ledger is an independent oracle; an interrupted effect is never retried
by this harness. Every failed run remains retained at its own output path.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import time
from pathlib import Path

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(o):
    base=o.output.resolve();base.mkdir(parents=True,exist_ok=False);project=base/'project';project.mkdir()
    (project/'a.txt').write_text('BRANCH-A-7319\n')
    real.ART=base;real.STATE=base/'workspace';helper=o.app/'Contents/Resources/engine/wixal-engine'
    c=real.Client(False,helper=helper,endpoint=o.endpoint)
    report=dict(status='running',started=time.time(),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),sourceManifestSha256=hashlib.sha256((o.app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(),cases=[])
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    def passed(name,**details):report['cases'].append(dict(name=name,status='passed',**details));save();print(name+': PASS',flush=True)
    allow_final=False;allow_recovery=False
    def review(details):
        if details.get('name')=='workflow_stage':return allow_final or details.get('stage')!='Artifact'
        if details.get('name')=='workflow_recovery':return allow_recovery
        if details.get('name')=='command_start':return details.get('command','').strip()=='python3 effect.py'
        return details.get('name') in ('write_file','workflow_merge')
    c.review_policy=review
    try:
        await c.start();assert any(m['name']==o.model for m in await c.call('models'))
        report['model']=await c.model(o.model);await c.call('settings',dict(contextSize=8192));await c.call('project-add',dict(root=str(project)))
        for identifier,policy in [('reader','Read only'),('writer','Review actions')]:
            await c.call('agent-save',dict(id=identifier,name=identifier,purpose='Verify actual local artifacts',instructions='Read actual files, preserve exact markers, never invent evidence. Write only the requested project file. Never repeat an interrupted effect; inspect its saved ledger first.',model=o.model,reviewPolicy=policy,memoryScope='Memory off'))
        def readstage(identifier,path,marker,dependencies=()):
            return dict(id=identifier,name=identifier,agentID='reader',goal=f'Read {path} and report its exact marker. Do not create missing files.',output='Verified marker',dependsOn=list(dependencies),condition='dependencies_verified',successCriteria=[dict(kind='tool_contains',tool='read_file',value=marker)])
        stages=[readstage('a','a.txt','BRANCH-A-7319'),readstage('b','b.txt','BRANCH-B-7319'),readstage('c','a.txt','BRANCH-A-7319',['a']),readstage('d','b.txt','BRANCH-B-7319',['b']),dict(id='join',name='Join',agentID='reader',goal='Read a.txt and b.txt. Report both exact markers.',output='Combined source evidence',dependsOn=['c','d'],condition='dependencies_verified',successCriteria=[dict(kind='tool_contains',tool='read_file',value='BRANCH-A-7319'),dict(kind='tool_contains',tool='read_file',value='BRANCH-B-7319')]),dict(id='artifact',name='Artifact',agentID='writer',goal='Write summary.json with exactly {"a":"BRANCH-A-7319","b":"BRANCH-B-7319"}. Read it back and verify both fields.',output='Verified isolated JSON',dependsOn=['join'],condition='dependencies_verified',requiresReview=True,isolation='Isolated changes',successCriteria=[dict(kind='json_equals',path='summary.json',pointer='/a',value='BRANCH-A-7319'),dict(kind='json_equals',path='summary.json',pointer='/b',value='BRANCH-B-7319')])]
        flow=await c.call('workflow-save',dict(name='Six-stage branch qualification',brief='Inspect actual prerequisites, then produce a verified isolated artifact.',execution='Dependency graph',stages=stages))
        first=await c.call('workflow-run',dict(id=flow['id']));report['invalidPrerequisiteRun']=copy.deepcopy(first);save()
        assert first['status']=='failed'
        assert not any(s['id'] in ('join','artifact') for s in first['stages'])
        completed_a=next(s for s in first['stages'] if s['id']=='a');failed_b=next(s for s in first['stages'] if s['id']=='b')
        assert completed_a['status']=='completed' and failed_b['status']!='completed'
        passed('invalid-prerequisite-blocks-dependent-artifact',failedTask=failed_b['taskId'])
        (project/'b.txt').write_text('BRANCH-B-7319\n')
        second=await c.call('workflow-resume',dict(runId=first['id']));report['reviewPausedRun']=copy.deepcopy(second);save()
        assert second['status']=='paused' and not (project/'summary.json').exists()
        assert next(s for s in second['stages'] if s['id']=='a')['taskId']==completed_a['taskId']
        assert next(s for s in second['stages'] if s['id']=='b')['attemptHistory'][-1]['taskId']==failed_b['taskId']
        preserved={s['id']:s['taskId'] for s in second['stages'] if s['status']=='completed'}
        await c.close();await c.start();state=await c.state();assert next(r for r in state['workflowRuns'] if r['id']==first['id'])['status']=='paused'
        passed('review-decline-and-restart-preserve-completed-branches',retainedTasks=preserved)
        allow_final=True
        third=await c.call('workflow-resume',dict(runId=first['id']));report['completedGraph']=copy.deepcopy(third);save()
        assert third['status']=='completed' and third['verification']['status']=='passed' and len(third['stages'])==6
        assert all(next(s for s in third['stages'] if s['id']==key)['taskId']==value for key,value in preserved.items())
        artifact=next(s for s in third['stages'] if s['id']=='artifact');isolated=Path(artifact['isolatedRoot'])/'summary.json'
        expected=dict(a='BRANCH-A-7319',b='BRANCH-B-7319');assert json.loads(isolated.read_text())==expected and not (project/'summary.json').exists()
        merged=await c.call('workflow-merge',dict(runId=first['id'],stageId='artifact'));assert json.loads((project/'summary.json').read_text())==expected
        passed('six-stage-real-model-graph-and-reviewed-isolated-merge',merge=merged,artifactSha256=hashlib.sha256((project/'summary.json').read_bytes()).hexdigest())
        # The script durably records its effect before waiting. Termination is
        # timed from the independent file, not model narration or a sleep guess.
        (project/'effect.py').write_text("import os,time\nwith open('effects.log','a') as f:\n f.write('EFFECT-ONCE-7319\\n');f.flush();os.fsync(f.fileno())\nprint('effect committed; waiting',flush=True)\ntime.sleep(120)\n")
        effectflow=await c.call('workflow-save',dict(name='Interrupted effect qualification',brief='Inspect evidence and apply the requested effect once.',stages=[readstage('before','a.txt','BRANCH-A-7319'),dict(id='effect',name='Effect',agentID='writer',goal='First read effects.log if it exists. If it contains EFFECT-ONCE-7319, the effect already happened: do not run any command; read the ledger and report the retained effect. Otherwise read effect.py, then use command_start with exactly python3 effect.py and timeout_seconds 180, and poll command_read. Never repeat this command if it was interrupted.',output='Verified effect ledger',successCriteria=[dict(kind='file_contains',path='effects.log',value='EFFECT-ONCE-7319')])]))
        pending=asyncio.create_task(c.call('workflow-run',dict(id=effectflow['id'])))
        deadline=time.monotonic()+240
        while not (project/'effects.log').exists() and time.monotonic()<deadline:
            if pending.done():raise AssertionError(dict(endedBeforeEffect=await pending))
            await asyncio.sleep(.05)
        assert (project/'effects.log').read_text()=='EFFECT-ONCE-7319\n'
        c.child.kill();await c.child.wait();await c.reading;c.log.close();await asyncio.gather(pending,return_exceptions=True)
        await c.start();state=await c.state();interrupted=next(r for r in state['workflowRuns'] if r['workflowId']==effectflow['id']);report['interruptedEffectRun']=copy.deepcopy(interrupted);save()
        assert interrupted['status']=='interrupted'
        completed_before=next(s for s in interrupted['stages'] if s['id']=='before')['taskId']
        effectstage=next(s for s in interrupted['stages'] if s['id']=='effect');assert effectstage['taskId']
        declined=await c.call('workflow-resume',dict(runId=interrupted['id']));assert declined['status']=='paused'
        assert (project/'effects.log').read_text()=='EFFECT-ONCE-7319\n'
        assert any(r['name']=='workflow_recovery' and not r['approved'] for r in c.reviews)
        passed('interrupted-effect-is-retained-and-declined-recovery-does-not-execute',taskId=effectstage['taskId'])
        allow_recovery=True
        resumed=await c.call('workflow-resume',dict(runId=interrupted['id']));report['resumedEffectRun']=copy.deepcopy(resumed);save()
        assert resumed['status']=='completed' and resumed['verification']['status']=='passed'
        assert next(s for s in resumed['stages'] if s['id']=='before')['taskId']==completed_before
        final=next(s for s in resumed['stages'] if s['id']=='effect');task=next(t for t in (await c.state())['tasks'] if t['id']==final['taskId'])
        assert not any(p['name'] in ('command_start','run_command','write_file') for p in task['checkpoints'])
        assert any(p['name']=='read_file' and 'EFFECT-ONCE-7319' in p.get('result','') for p in task['checkpoints'])
        assert final['attemptHistory'][-1]['taskId']==effectstage['taskId']
        assert (project/'effects.log').read_text()=='EFFECT-ONCE-7319\n'
        passed('reviewed-recovery-inspects-effect-without-replay',completedPrerequisiteTask=completed_before,recoveredTask=final['taskId'])
        report.update(status='passed',reviews=c.reviews)
    except BaseException as error:report.update(status='failed',error=str(error),reviews=c.reviews);raise
    finally:
        if c.child.returncode is None:await c.close()
        report['finished']=time.time();save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--endpoint',default='http://127.0.0.1:11434');p.add_argument('--model',default='gpt-oss:20b');asyncio.run(main(p.parse_args()))
