"""Fresh real-model Nmap reads against two owned ephemeral loopback listeners.

Every attempt and review is retained. No transcript, scan result or tool call is
injected. Approval admits only the bounded scanner invocation for these ports.
"""
import argparse
import asyncio
import hashlib
import json
import uuid
from pathlib import Path


async def main(args):
    app=args.app.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    project=output/'project';project.mkdir()
    helper=app/'Contents/Resources/engine/wixal-engine';events=[];outcomes=[];connections=[]
    async def accepted(reader,writer):
        connections.append(dict(port=writer.get_extra_info('sockname')[1]))
        writer.close();await writer.wait_closed()
    listeners=[await asyncio.start_server(accepted,'127.0.0.1',0) for _ in range(2)]
    ports=sorted(server.sockets[0].getsockname()[1] for server in listeners)
    process=await asyncio.create_subprocess_exec(str(helper),'--data',str(output/'data'),'--runtime',str(app/'Contents/Resources/ollama'),'--endpoint',args.endpoint,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=32*1024*1024)
    errors=asyncio.create_task(process.stderr.read())
    async def send(method,params,identifier):
        process.stdin.write((json.dumps(dict(id=identifier,method=method,params=params))+'\n').encode());await process.stdin.drain()
    async def call(method,params=None):
        identifier=uuid.uuid4().hex;await send(method,params or {},identifier)
        async with asyncio.timeout(args.timeout):
            while raw:=await process.stdout.readline():
                event=json.loads(raw);events.append(event)
                if event['event']=='review':
                    details=event['data'].get('details',event['data']);assessment=details.get('assessment',{})
                    approved=details.get('name')=='command_start' and assessment.get('capability')=='network_scan' and assessment.get('target')=='127.0.0.1' and sorted(assessment.get('ports',[]))==ports and assessment.get('profile')=='ports'
                    await send('respond',dict(id=event['data']['id'],value=approved),uuid.uuid4().hex)
                if event['event']=='response' and event['data']['id']==identifier:
                    if 'error' in event['data']:raise RuntimeError(event['data']['error'])
                    return event['data']['result']
            raise RuntimeError('Helper ended before responding')
    try:
        await call('project-add',dict(root=str(project)))
        await call('settings',dict(model=args.model,mode='chat',enabledTools=['network_scan','network_read','network_stop']))
        for index in range(args.attempts):
            await call('session-new',dict(mode='chat'))
            prompt=f'Use @network_scan with profile ports to inspect only TCP ports {ports[0]},{ports[1]} on my two owned listeners at 127.0.0.1, with a 30-second timeout. Poll @network_read until the scan has finished. Read its structured services and summary as well as the actual output. Report each port and its observed state. Do not scan other ports or hosts, run generic commands, write files, or infer closed ports from missing text in a paged output.'
            try:
                task=await call('chat',dict(text=prompt));reads=[]
                for checkpoint in task.get('checkpoints',[]):
                    if checkpoint['name']!='network_read' or checkpoint['status']!='finished':continue
                    try:result=json.loads(checkpoint.get('result',''))
                    except ValueError:continue
                    if result.get('state')=='completed' and result.get('structuredResult',{}).get('kind')=='nmap':reads.append(result)
                observed={int(s['port']) for r in reads for s in r.get('services',[]) if s['host']=='127.0.0.1' and s['state']=='open'}
                answer=task.get('result','')
                passed=task['status']=='completed' and observed==set(ports) and all(str(p) in answer for p in ports) and 'open' in answer.lower() and all(p in {r['port'] for r in connections} for p in ports)
                outcomes.append(dict(attempt=index+1,passed=passed,expectedPorts=ports,observedOpenPorts=sorted(observed),task=task))
            except Exception as error:
                outcomes.append(dict(attempt=index+1,passed=False,error=str(error)));await call('stop')
            print(json.dumps({k:v for k,v in outcomes[-1].items() if k!='task'}),flush=True)
    finally:
        process.stdin.close()
        try:await asyncio.wait_for(process.stdout.read(),30);await asyncio.wait_for(process.wait(),30)
        except TimeoutError:process.kill();await process.wait()
        for listener in listeners:listener.close();await listener.wait_closed()
        (output/'events.json').write_text(json.dumps(events,indent=2))
        (output/'helper-stderr.log').write_bytes(await errors)
        report=dict(status='passed' if len(outcomes)==args.attempts and all(o['passed'] for o in outcomes) else 'failed',model=args.model,app=str(app),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),sourceManifestSha256=hashlib.sha256((app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(),connections=connections,outcomes=outcomes,limits=['Bounded local Nmap chat regression, not broad model qualification','Final prose must also be reviewed for factual contradictions'])
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report['status']=='passed'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--endpoint',default='http://127.0.0.1:11434');parser.add_argument('--model',default='gpt-oss:20b');parser.add_argument('--attempts',type=int,choices=range(1,11),default=3);parser.add_argument('--timeout',type=int,default=360)
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
