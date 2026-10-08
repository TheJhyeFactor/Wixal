"""Additional real-model workflows: automatic tool choice, branches, scoped jobs and failure honesty."""
import argparse,asyncio,copy,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.service import Service
from wixal.storage import now
from wixal.scheduling import run_due
from wixal.agent_jobs import run_next
from wixal.mcp_names import tool_name

async def main(args):
    base=Path(args.output).resolve();base.mkdir(parents=True,exist_ok=True);root=base/'project';root.mkdir(exist_ok=True)
    source=Path(__file__).resolve().parents[1]/'engine/wixal/outcomes.py'
    (root/'source.py').write_bytes(source.read_bytes());(root/'scope.txt').write_text('Authorised targets: disposable loopback simulation only.\nEvidence marker: REAL-WX-8241\n')
    events=[];outcomes=[]
    def emit(event,data):
        events.append(dict(event=event,data=copy.deepcopy(data)))
        if event=='review':asyncio.create_task(service.dispatch('respond',dict(id=data['id'],value=True)))
    service=Service(base/'engine',Path(__file__).resolve().parents[2]/'runtime/ollama',emit,args.endpoint)
    async def attempt(name,action,check):
        start=time.monotonic()
        try:
            result=await asyncio.wait_for(action(),args.timeout);passed=bool(check(result));row=dict(name=name,passed=passed,seconds=round(time.monotonic()-start,2),result=result)
        except Exception as error:row=dict(name=name,passed=False,seconds=round(time.monotonic()-start,2),error=str(error))
        outcomes.append(row);(base/'results.json').write_text(json.dumps(dict(status='running',model=args.model,outcomes=outcomes),indent=2));print(name,'PASS' if row['passed'] else 'FAIL',row['seconds'],flush=True)
    try:
        await service.dispatch('project-add',dict(root=str(root)));await service.dispatch('settings',dict(model=args.model,enabledTools=[]))
        for identifier,policy in [('reader','Read only'),('writer','Review actions')]:await service.dispatch('agent-save',dict(id=identifier,name=identifier,purpose='Work with actual project evidence',instructions='Use real tools, preserve exact source identifiers, inspect errors and never fabricate an artifact or passing result.',model=args.model,reviewPolicy=policy,memoryScope='Project only'))
        await attempt('one-off-automatic-tools',lambda:service.dispatch('chat',dict(text='Read scope.txt from the project files and report its exact evidence marker.')),
                      lambda task:any(c['name']=='read_file' and 'REAL-WX-8241' in c.get('result','') for c in task['checkpoints']) and 'REAL-WX-8241' in task.get('result',''))
        flow=await service.dispatch('workflow-save',dict(name='Parallel source inspection',brief='Inspect actual source and scope without changes.',execution='Dependency graph',stages=[dict(id='source',name='Source',agentID='reader',goal='Read source.py and identify the verification kinds.',output='Source references',successCriteria=[dict(kind='tool_contains',tool='read_file',value='tool_contains')]),dict(id='scope',name='Scope',agentID='reader',goal='Read scope.txt and preserve its exact marker.',output='Exact scope marker',successCriteria=[dict(kind='tool_contains',tool='read_file',value='REAL-WX-8241')]),dict(id='join',name='Synthesis',agentID='reader',goal='Use the dependency evidence to report the marker and verification capability. Preserve the exact marker.',output='Combined evidence',dependsOn=['source','scope'],condition='dependencies_verified')]))
        await attempt('parallel-dependency-workflow',lambda:service.dispatch('workflow-run',dict(id=flow['id'])),lambda run:run['status']=='completed' and len(run['stages'])==3 and 'REAL-WX-8241' in run['result'])
        schedule=await service.dispatch('agent-schedule-save',dict(name='Scoped report routine',agentID='writer',prompt='Read scope.txt. Write unattended-report.md containing its exact evidence marker and read the report back. Use project file tools.',timing='Every hour',authority=dict(writePaths=['unattended-report.md']),successCriteria=[dict(kind='file_contains',path='unattended-report.md',value='REAL-WX-8241')]))
        schedule['nextRun']=now()-1000
        await attempt('scoped-unattended-write',lambda:run_due(service,True),lambda result:result and schedule.get('lastRun',{}).get('verification',{}).get('status')=='passed' and 'REAL-WX-8241' in (root/'unattended-report.md').read_text())
        job=await service.dispatch('agent-enqueue',dict(agentID='reader',prompt='Read scope.txt and report its exact evidence marker.',successCriteria=[dict(kind='tool_contains',tool='read_file',value='REAL-WX-8241')]))
        await attempt('durable-queued-task',lambda:run_next(service),lambda result:result and job['status']=='completed' and job.get('verification',{}).get('status')=='passed')
        await attempt('missing-input-is-not-success',lambda:service.dispatch('agent-run',dict(id='reader',prompt='Inspect the project and verify an artifact named never-created.json. Report honestly if it is absent.',successCriteria=[dict(kind='file_exists',path='never-created.json')])),lambda task:task['status']=='needs_attention' and task.get('verification',{}).get('status')=='failed' and not (root/'never-created.json').exists())
        # A real stdio MCP service with a real model; the service itself is a controlled integration fixture.
        fixture=Path(__file__).resolve().parents[1]/'tests/mcp_fixture.py';config=dict(id='integrationproof',name='Local evidence echo',command=sys.executable,args=[str(fixture)])
        await service.mcp.connect(config,str(root));name=tool_name(config['id'],'echo')
        await attempt('real-model-stdio-mcp',lambda:service.dispatch('agent-run',dict(id='writer',prompt='Use the connected Local evidence echo tool to echo the exact marker MCP-WX-9931 and report the returned text.',successCriteria=[dict(kind='tool_contains',tool=name,value='MCP-WX-9931')])),lambda task:task.get('verification',{}).get('status')=='passed')
        (base/'events.json').write_text(json.dumps(events,indent=2))
    finally:await service.close()
    passed=all(row['passed'] for row in outcomes)
    (base/'results.json').write_text(json.dumps(dict(status='passed' if passed else 'failed',model=args.model,outcomes=outcomes),indent=2));return passed
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--output',required=True);parser.add_argument('--timeout',type=int,default=480)
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
