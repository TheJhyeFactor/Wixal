"""Register a temporary LaunchAgent and prove scoped work with no foreground engine.

Only the supplied scratch workspace is used. The job is unregistered in finally.
Sleep/reboot are deliberately not simulated by interrupting the user's Mac.
"""
import argparse,asyncio,hashlib,json,os,sqlite3,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store,now

async def main(args):
    base=Path(args.output).resolve();base.mkdir(parents=True,exist_ok=True)
    workspace=Path.home()/'Library/Application Support/Wixal Agents Acceptance/background'/str(uuid.uuid4());workspace.mkdir(parents=True)
    project=workspace/'project';project.mkdir();data=workspace/'data'
    (project/'source.txt').write_text('LaunchAgent lifecycle marker: BG-WX-8837\n')
    app=Path(args.app).resolve();helper=app/'Contents/Resources/engine/wixal-engine';runtime=app/'Contents/Resources/ollama'
    command=[str(helper),'--data',str(data),'--runtime',str(runtime),'--endpoint',args.endpoint]
    label='app.wixal.native.scheduler.'+hashlib.sha256(str(data.resolve()).encode()).hexdigest()[:12]
    plist=Path.home()/'Library/LaunchAgents'/(label+'.plist');domain='gui/'+str(os.getuid())
    process=None;events=[];report=dict(status='running',outcomes=[],label=label,workspace=str(workspace),limitations=['Sleep/wake and actual reboot require separate host lifecycle acceptance.'])
    async def start():return await asyncio.create_subprocess_exec(*command,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=32*1024*1024)
    async def call(method,params=None):
        identifier=uuid.uuid4().hex;process.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await process.stdin.drain()
        while raw:=await asyncio.wait_for(process.stdout.readline(),400):
            event=json.loads(raw);events.append(event)
            if event['event']=='response' and event['data']['id']==identifier:
                if 'error' in event['data']:raise RuntimeError(event['data']['error'])
                return event['data']['result']
        raise RuntimeError('Engine ended before responding')
    def snapshot():
        db=sqlite3.connect(f'file:{data / "workspace.sqlite3"}?mode=ro',uri=True)
        try:return json.loads(db.execute('SELECT value FROM state').fetchone()[0])
        finally:db.close()
    try:
        process=await start();await call('hello');await call('project-add',dict(root=str(project)));await call('settings',dict(model=args.model,enabledTools=[]))
        await call('agent-save',dict(id='lifecycle-agent',name='Background report agent',purpose='Read source and write an approved report',instructions='Use project file tools. Preserve exact markers and verify the report.',model=args.model,reviewPolicy='Review actions',memoryScope='Project only'))
        schedule=await call('agent-schedule-save',dict(name='Lifecycle report',agentID='lifecycle-agent',prompt='Read source.txt and write lifecycle-report.md containing its exact lifecycle marker. Read back the report. Use file tools.',timing='Every hour',authority=dict(writePaths=['lifecycle-report.md']),successCriteria=[dict(kind='file_contains',path='lifecycle-report.md',value='BG-WX-8837')]))
        enabled=await call('background-settings',dict(enabled=True));report['outcomes'].append(dict(name='LaunchAgent registered',passed=enabled['enabled'] and plist.exists()))
        process.stdin.close();await asyncio.wait_for(process.wait(),30);process=None
        store=Store(data)
        try:
            row=next(s for s in store.data['schedules'] if s['id']==schedule['id']);row['nextRun']=now()-1000;store.save()
        finally:store.close()
        kicked=await asyncio.to_thread(subprocess.run,['launchctl','kickstart',domain+'/'+label],capture_output=True,text=True)
        if kicked.returncode:raise RuntimeError('Could not start registered LaunchAgent: '+kicked.stderr)
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            state=snapshot();last=next(s for s in state['schedules'] if s['id']==schedule['id']).get('lastRun',{})
            if last.get('status') not in (None,'running'):break
            await asyncio.sleep(2)
        else:raise TimeoutError('Background job did not finish')
        artifact=project/'lifecycle-report.md'
        report['outcomes'].append(dict(name='Scoped report verified without foreground engine',passed=last.get('verification',{}).get('status')=='passed' and artifact.exists() and 'BG-WX-8837' in artifact.read_text(),lastRun=last))
        before=len(state['tasks'])
        # A second launch cannot repeat the already-claimed due interval.
        await asyncio.to_thread(subprocess.run,['launchctl','kickstart',domain+'/'+label],capture_output=True)
        await asyncio.sleep(3)
        after=snapshot();report['outcomes'].append(dict(name='No duplicate scheduled task after relaunch',passed=len(after['tasks'])==before))
        await asyncio.to_thread(subprocess.run,['launchctl','bootout',domain,str(plist)],capture_output=True)
        process=await start();await call('hello');disabled=await call('background-settings',dict(enabled=False));report['outcomes'].append(dict(name='Scheduler unregistered through app API',passed=not disabled['enabled'] and not plist.exists()))
        report['status']='passed' if all(o['passed'] for o in report['outcomes']) else 'failed'
    except Exception as error:report.update(status='failed',error=str(error))
    finally:
        if process:
            process.stdin.close()
            try:await asyncio.wait_for(process.wait(),15)
            except TimeoutError:process.terminate();await process.wait()
        await asyncio.to_thread(subprocess.run,['launchctl','bootout',domain,str(plist)],capture_output=True)
        plist.unlink(missing_ok=True)
        report['cleanup']=not plist.exists();(base/'results.json').write_text(json.dumps(report,indent=2));(base/'events.json').write_text(json.dumps(events,indent=2))
        print(json.dumps(report,indent=2),flush=True)
    return report['status']=='passed' and report['cleanup']
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',required=True);parser.add_argument('--output',required=True);parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--timeout',type=int,default=480)
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
