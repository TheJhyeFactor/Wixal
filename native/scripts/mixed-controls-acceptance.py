"""Installed-helper mixed controls with real IPC/storage/tools and a controlled server.

The server controls timing and decisions. This suite makes no real-model,
keyboard, VoiceOver, sleep or desktop-UI qualification claim.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

class ControlledServer:
    def __init__(self,base):
        self.base=base;self.plans=deque();self.requests=[];self.stop=threading.Event();self.catalog_gate=None
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,value):
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(value).encode())
            def do_GET(self):
                if self.path=='/api/tags' and owner.catalog_gate:
                    gate=owner.catalog_gate;owner.catalog_gate=None;gate['entered'].set()
                    while not gate['release'].wait(.1) and not owner.stop.is_set():pass
                self.reply(dict(models=[dict(name='fixture',size=1)]) if self.path=='/api/tags' else dict(version='controlled'))
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path=='/api/show':self.reply(dict(capabilities=['completion','tools'],model_info={'fixture.context_length':8192}));return
                if not owner.plans:
                    self.send_error(503,'No planned response');return
                plan=owner.plans.popleft();owner.requests.append(dict(plan=plan['name'],body=body))
                (base/'model-requests.json').write_text(json.dumps(owner.requests,indent=2))
                self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.end_headers();plan['entered'].set()
                try:
                    while not plan['release'].wait(.1) and not owner.stop.is_set():self.wfile.write(b'\n');self.wfile.flush()
                    if not owner.stop.is_set():self.wfile.write((json.dumps(dict(message=plan['message'],done=True))+'\n').encode());self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.endpoint=f'http://127.0.0.1:{self.server.server_port}'
    def plan(self,name,content='Controlled completion',tool=None,args=None,held=False):
        message=dict(role='assistant',content=content)
        if tool:message['tool_calls']=[dict(function=dict(name=tool,arguments=args))]
        plan=dict(name=name,message=message,entered=threading.Event(),release=threading.Event())
        if not held:plan['release'].set()
        self.plans.append(plan);return plan
    def close(self):self.stop.set();self.server.shutdown();self.server.server_close();self.thread.join()

class Client(real.Client):
    async def read(self):
        try:
            while line:=await self.child.stdout.readline():
                item=json.loads(line);event=item['event'];data=item['data']
                if event=='response':
                    future=self.pending.pop(data['id'],None)
                    if future and not future.done():future.set_result(data)
                elif event=='review':self.reviews.append(copy.deepcopy(data))
                elif event in ('error','activity','token','assistant-start','tool-result'):self.events.append(item)
        finally:
            for future in self.pending.values():
                if not future.done():future.set_exception(RuntimeError('Production helper disconnected'))
            self.pending.clear()

async def until(predicate,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        await asyncio.sleep(.05)
    raise TimeoutError('Expected independent boundary not observed')

async def main(o):
    base=o.output.resolve();base.mkdir(parents=True,exist_ok=False)
    real.ART=base;real.STATE=base/'workspace';server=ControlledServer(base)
    helper=o.app/'Contents/Resources/engine/wixal-engine'
    c=Client(False,helper=helper,payload=o.app/'Contents/Resources/ollama',endpoint=server.endpoint)
    report=dict(status='running',started=time.time(),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),sourceManifestSha256=hashlib.sha256((o.app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(),scriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=[],limitations=__doc__)
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    def passed(name,**details):report['cases'].append(dict(name=name,status='passed',**details));save();print(name+': PASS',flush=True)
    async def restart(abrupt=False):
        if abrupt:
            c.child.kill();await c.child.wait();await c.reading;c.log.close()
        else:await c.close()
        await c.start()
    async def rejected(method,params):
        try:await c.call(method,params)
        except RuntimeError as error:return str(error)
        raise AssertionError(f'{method} unexpectedly accepted stale controls')
    save()
    try:
        await c.start();await c.model('fixture')
        projects=[]
        for index in range(2):
            root=base/f'project-{index}';root.mkdir();(root/'source.txt').write_text(f'MIXED-PROJECT-{index}-7319\n')
            projects.append((await c.call('project-add',dict(root=str(root))))['activeProject'])
        profile=dict(id='mixed',name='Mixed reader',purpose='Timing acceptance',instructions='Frozen original instructions',model='fixture',reviewPolicy='Review actions',memoryScope='Memory off')
        await c.call('agent-save',profile)
        original=await c.state();selected={k:original[k] for k in ('activeProject','activeSession','model','mode')}
        first=server.plan('late-guidance',content='Answer before guidance',held=True)
        server.plan('guidance-consumed',content='New GUIDANCE-7319 considered')
        pending=asyncio.create_task(c.call('agent-run',dict(id='mixed',prompt='Controlled final answer',projectId=projects[0])))
        await until(first['entered'].is_set);state=await c.state();task=next(t for t in reversed(state['tasks']) if t['status']=='running')
        await c.call('agent-guide',dict(id=task['id'],text='Use GUIDANCE-7319'))
        cancelled=[]
        for index in range(12):
            job=await c.call('agent-enqueue',dict(agentID='mixed',prompt=f'Cancelled mixed brief {index}',projectId=projects[index%2],delaySeconds=86400))
            cancelled.append((await c.call('agent-job-cancel',dict(id=job['id'])))['id'])
        first['release'].set();result=await pending
        assert result['status']=='completed' and not result.get('pendingGuidance') and result['result']=='New GUIDANCE-7319 considered',result
        request=next(r['body'] for r in server.requests if r['plan']=='guidance-consumed')
        assert any('Use GUIDANCE-7319' in m.get('content','') for m in request['messages'])
        assert {k:(await c.state())[k] for k in selected}==selected
        passed('late-guidance-consumed-before-completion-and-context-restored',taskId=task['id'],cancelledJobs=cancelled)
        # Start a queued job, stop it while streaming, then run another project.
        held=server.plan('queued-stop',held=True)
        job=await c.call('agent-enqueue',dict(agentID='mixed',prompt='Frozen queued brief',projectId=projects[0]))
        await until(held['entered'].is_set)
        state=await c.state();active=next(j for j in state['agentJobs'] if j['id']==job['id']);task_id=active['taskId']
        assert next(t for t in state['tasks'] if t['id']==task_id)['queueJobId']==job['id']
        await c.call('stop',dict(taskId=task_id));held['release'].set()
        async def stopped():
            state=await c.state();return next(j for j in state['agentJobs'] if j['id']==job['id'])
        deadline=time.monotonic()+10
        while (stopped_job:=await stopped())['status']=='running' and time.monotonic()<deadline:await asyncio.sleep(.05)
        assert stopped_job['status']=='interrupted' and stopped_job['history'][-1]['taskId']==task_id,stopped_job
        other=server.plan('other-project-active',held=True)
        current=asyncio.create_task(c.call('agent-run',dict(id='mixed',prompt='Other project',projectId=projects[1])))
        await until(other['entered'].is_set)
        stale_stop=await rejected('stop',dict(taskId=task_id));stale_guide=await rejected('agent-guide',dict(id=task_id,text='STALE-7319'))
        assert not current.done();other['release'].set();await current
        passed('queued-stop-links-task-and-stale-controls-do-not-affect-new-project',job=stopped_job,staleStop=stale_stop,staleGuidance=stale_guide)
        # Edit the profile after the queued run, retain an unrelated selection,
        # restart, then resume the frozen original task and verify its request.
        await c.call('agent-save',{**profile,'instructions':'CHANGED PROFILE AFTER QUEUE'})
        await c.call('project-select',dict(id=projects[1]));await c.call('session-new')
        before=await c.state();selection={k:before[k] for k in selected}
        await restart();await restart(abrupt=True)
        restored=await c.state()
        assert all(j['status']=='cancelled' for j in restored['agentJobs'] if j['id'] in cancelled)
        server.plan('resumed-original-context',content='Resumed frozen task')
        resumed=await c.call('agent-resume',dict(id=task_id))
        assert resumed['id']==task_id and resumed['projectId']==projects[0] and resumed['agentSnapshot']['instructions']==profile['instructions']
        after=await c.state();assert {k:after[k] for k in selection}==selection
        request=next(r['body'] for r in server.requests if r['plan']=='resumed-original-context')
        system=request['messages'][0]['content']
        assert 'Frozen original instructions' in system and 'CHANGED PROFILE AFTER QUEUE' not in system and str(base/'project-0') in system
        passed('restart-retains-cancellations-and-resume-restores-frozen-original-context',taskId=task_id,restoredSelection=selection)
        # Hold provider preparation before a task/model request exists. Stopping
        # preparation must not accidentally attach an earlier same-agent task.
        gate=dict(entered=threading.Event(),release=threading.Event());server.catalog_gate=gate
        preparation=await c.call('agent-enqueue',dict(agentID='mixed',prompt='Stopped during provider preparation',projectId=projects[1]))
        await until(gate['entered'].is_set)
        count=len(server.requests);await c.call('stop');gate['release'].set()
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            state=await c.state();prepared=next(j for j in state['agentJobs'] if j['id']==preparation['id'])
            if prepared['status']!='running':break
            await asyncio.sleep(.05)
        assert prepared['status']=='interrupted' and not prepared.get('taskId'),prepared
        assert not any(t.get('queueJobId')==preparation['id'] for t in state['tasks']) and len(server.requests)==count
        passed('stop-during-provider-preparation-does-not-run-or-link-an-unrelated-task',job=prepared)
        # Cancel at an actual pending action review; an obsolete approval must
        # neither execute the effect nor affect the following task.
        server.plan('review-write',content='',tool='write_file',args=dict(path='must-not-exist.txt',content='UNAPPROVED'))
        before_reviews=len(c.reviews)
        pending=asyncio.create_task(c.call('agent-run',dict(id='mixed',prompt='Controlled write review',projectId=projects[0])))
        await until(lambda:len(c.reviews)>before_reviews)
        review=c.reviews[-1];state=await c.state();waiting=next(t for t in reversed(state['tasks']) if t['status']=='waiting_review')
        await c.call('stop',dict(taskId=waiting['id']));await asyncio.gather(pending,return_exceptions=True)
        assert not (base/'project-0/must-not-exist.txt').exists()
        error=await rejected('respond',dict(id=review['id'],value=True))
        passed('stop-at-action-review-leaves-no-effect-and-rejects-stale-approval',taskId=waiting['id'],staleApproval=error)
        # Observe a real committed command effect before stopping. A retained
        # ledger, rather than model prose, establishes what happened once.
        project=base/'project-0'
        (project/'effect.py').write_text("import os,time\nwith open('effects.log','a') as f:\n f.write('MIXED-EFFECT-ONCE-7319\\n');f.flush();os.fsync(f.fileno())\nprint('effect committed',flush=True)\ntime.sleep(120)\n")
        server.plan('command-start',content='',tool='command_start',args=dict(command='python3 effect.py',timeout_seconds=180))
        held=server.plan('command-active',held=True)
        before_reviews=len(c.reviews)
        pending=asyncio.create_task(c.call('agent-run',dict(id='mixed',prompt='Controlled single command effect',projectId=projects[0])))
        await until(lambda:len(c.reviews)>before_reviews)
        review=c.reviews[-1];assert review['name']=='command_start',review
        await c.call('respond',dict(id=review['id'],value=True))
        await until(lambda:(project/'effects.log').exists())
        await until(held['entered'].is_set)
        state=await c.state();executing=next(t for t in reversed(state['tasks']) if t['status']=='running')
        assert (project/'effects.log').read_text()=='MIXED-EFFECT-ONCE-7319\n'
        await c.call('stop',dict(taskId=executing['id']));held['release'].set();await asyncio.gather(pending,return_exceptions=True)
        await restart(abrupt=True)
        state=await c.state();retained=next(t for t in state['tasks'] if t['id']==executing['id'])
        assert retained['status'] in ('paused','interrupted') and any(p['name']=='command_start' for p in retained['checkpoints'])
        assert (project/'effects.log').read_text()=='MIXED-EFFECT-ONCE-7319\n'
        passed('stop-during-real-command-retains-single-effect-and-checkpoints-after-restart',taskId=executing['id'],checkpoints=retained['checkpoints'])
        (project/'verify.py').write_text("import os,time\nwith open('verification-started.log','a') as f:\n f.write('VERIFY-ONCE-7319\\n');f.flush();os.fsync(f.fileno())\ntime.sleep(120)\n")
        server.plan('final-answer-before-verification',content='Inspect the independent verification outcome')
        before_reviews=len(c.reviews)
        pending=asyncio.create_task(c.call('agent-run',dict(id='mixed',prompt='Finish with independently reviewed verification',projectId=projects[0],successCriteria=[dict(kind='command_exit',command='python3 verify.py')])))
        await until(lambda:len(c.reviews)>before_reviews)
        review=c.reviews[-1];assert review['name']=='command_start' and review['command']=='python3 verify.py',review
        await c.call('respond',dict(id=review['id'],value=True))
        await until(lambda:(project/'verification-started.log').exists())
        state=await c.state();verifying=next(t for t in reversed(state['tasks']) if t['status']=='running')
        assert any(p['name']=='verification_command' and p['status']=='started' for p in verifying['checkpoints'])
        await c.call('stop',dict(taskId=verifying['id']));await asyncio.gather(pending,return_exceptions=True)
        await restart();state=await c.state();retained=next(t for t in state['tasks'] if t['id']==verifying['id'])
        assert retained['status']=='paused' and any(p['name']=='verification_command' and p['status']=='interrupted' for p in retained['checkpoints'])
        assert (project/'verification-started.log').read_text()=='VERIFY-ONCE-7319\n'
        passed('selected-stop-during-evidence-verification-retains-interrupted-checkpoint',taskId=verifying['id'],checkpoints=retained['checkpoints'])
        # Abruptly kill an active queued request. The durable queue/task link
        # must survive without an automatic second attempt after reopening.
        held=server.plan('queued-abrupt-restart',held=True)
        crash_job=await c.call('agent-enqueue',dict(agentID='mixed',prompt='Crash-boundary queued brief',projectId=projects[1]))
        await until(held['entered'].is_set);before=await c.state();active=next(j for j in before['agentJobs'] if j['id']==crash_job['id']);linked=active['taskId']
        count=len(server.requests);await restart(abrupt=True);held['release'].set()
        after=await c.state();recovered=next(j for j in after['agentJobs'] if j['id']==crash_job['id'])
        assert recovered['status']=='interrupted' and recovered['taskId']==linked
        assert next(t for t in after['tasks'] if t['id']==linked)['status']=='interrupted'
        await asyncio.sleep(2);assert len(server.requests)==count
        passed('abrupt-active-queue-restart-retains-linked-task-without-replay',job=recovered,taskId=linked)
        (base/'final-state.json').write_text(json.dumps(await c.state(),indent=2))
        report['status']='passed'
    except BaseException as error:report.update(status='failed',error=repr(error));raise
    finally:
        report['finished']=time.time();save()
        if hasattr(c,'child'):await c.close()
        server.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
