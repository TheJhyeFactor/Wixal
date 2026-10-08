"""Actual loopback scanner and real-model skill evaluations in disposable projects."""
import argparse,asyncio,copy,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.service import Service

async def main(args):
    base=Path(args.output).resolve();base.mkdir(parents=True,exist_ok=True);root=base/'project';root.mkdir(exist_ok=True)
    (root/'skill-source.txt').write_text('Reusable procedure evidence marker: SKILL-WX-6688\n')
    events=[];outcomes=[];service=None
    async def client(reader,writer):
        try:
            await asyncio.wait_for(reader.read(8192),5)
            content=b'Wixal authorised loopback acceptance server'
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\nContent-Length: '+str(len(content)).encode()+b'\r\n\r\n'+content);await writer.drain()
        except (TimeoutError,ConnectionError):pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except ConnectionError:pass
    server=await asyncio.start_server(client,'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
    def emit(event,data):
        events.append(dict(event=event,data=copy.deepcopy(data)))
        if event=='review':asyncio.create_task(service.dispatch('respond',dict(id=data['id'],value=True)))
    service=Service(base/'engine',Path(__file__).resolve().parents[2]/'runtime/ollama',emit,args.endpoint)
    async def attempt(name,action,check):
        start=time.monotonic()
        try:
            result=await asyncio.wait_for(action(),args.timeout);row=dict(name=name,passed=bool(check(result)),seconds=round(time.monotonic()-start,2),result=result)
        except Exception as error:row=dict(name=name,passed=False,error=str(error),seconds=round(time.monotonic()-start,2))
        outcomes.append(row);(base/'results.json').write_text(json.dumps(dict(status='running',model=args.model,port=port,outcomes=outcomes),indent=2));print(name,'PASS' if row['passed'] else 'FAIL',row['seconds'],flush=True)
    try:
        await service.dispatch('project-add',dict(root=str(root)));await service.dispatch('settings',dict(model=args.model,enabledTools=[]))
        await service.dispatch('agent-save',dict(id='scanner',name='Scoped scanner',purpose='Observe the explicitly authorised loopback service',instructions='Use actual network tools and retain the completed scanner output. Open ports are observations, not proof of vulnerabilities or exploitation.',model=args.model,reviewPolicy='Review actions',memoryScope='Memory off',authority=dict(targets=['127.0.0.1']),restrictTargets=True))
        await attempt('real-loopback-nmap-evidence',lambda:service.dispatch('agent-run',dict(id='scanner',prompt=f'Use network_scan to inspect only 127.0.0.1 TCP port {port}, profile ports. Wait for the completed result with network_read. Report the observed port state. Do not scan other targets or ports.',successCriteria=[dict(kind='tool_succeeded',tool='network_read')])),lambda task:task.get('verification',{}).get('status')=='passed' and any(f.get('id')==f'open-port-tcp-{port}' and f.get('url')=='127.0.0.1' and not f['verifiedExploit'] for f in task.get('securityFindings',[])))
        await service.dispatch('agent-save',dict(id='writer',name='Procedure evaluator',purpose='Produce evidence-based reports',instructions='Use project file tools to inspect the actual source, preserve exact identifiers, write the requested report and read it back. Correct tool errors before concluding.',model=args.model,reviewPolicy='Review actions',memoryScope='Memory off'))
        candidate=await service.dispatch('skill-propose',dict(name='Verified source report',description='Inspect, preserve and verify exact markers.',content='Read the source file first. Copy its marker exactly into the requested report. Read the saved report to verify it. Do not claim that an unexecuted operation succeeded.'))
        params=dict(id=candidate['id'],agentID='writer',cases=[dict(prompt='Read skill-source.txt and write procedure-report.md containing its exact evidence marker. Read the saved report to verify it.',successCriteria=[dict(kind='file_contains',path='procedure-report.md',value='SKILL-WX-6688'),dict(kind='tool_contains',tool='read_file',value='SKILL-WX-6688')])])
        for number in (1,2):await attempt(f'isolated-baseline-and-candidate-evaluation-{number}',lambda:service.dispatch('skill-evaluate',params),lambda report:report['status']=='passed' and not (root/'procedure-report.md').exists() and report['cases'][0]['baseline']['isolatedRoot']!=report['cases'][0]['candidate']['isolatedRoot'])
        await attempt('evaluated-skill-promotion',lambda:service.dispatch('skill-promote',dict(id=candidate['id'])),lambda skill:len(skill.get('evaluationIds',[]))==2 and skill['content']==candidate['content'])
        (base/'events.json').write_text(json.dumps(events,indent=2))
    finally:
        server.close();await server.wait_closed();await service.close()
    passed=all(row['passed'] for row in outcomes);(base/'results.json').write_text(json.dumps(dict(status='passed' if passed else 'failed',model=args.model,port=port,outcomes=outcomes),indent=2));return passed
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--output',required=True);parser.add_argument('--timeout',type=int,default=600)
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
