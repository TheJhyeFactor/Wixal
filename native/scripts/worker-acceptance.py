"""Actual Linux nftables, typed worker execution and owned cancellation in a dedicated local VM."""
import argparse
import asyncio
import importlib.util
import ipaddress
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

TARGET_SCRIPT='''from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading,time
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=b'WIXAL-OWNED-LINUX-LAB-7284';self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*a):pass
for port in (18080,18081):
 server=ThreadingHTTPServer(('0.0.0.0',port),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
print('WIXAL-LAB-READY',flush=True)
while True:time.sleep(1)
'''

POLICY_SCRIPT='''import importlib.util,json,subprocess,sys
s=importlib.util.spec_from_file_location('w','/opt/wixal/entrypoint.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
config=json.loads(sys.argv[1]);denied_ip=sys.argv[2]
probe="""import socket,json,sys
results=[]
for host,port in json.loads(sys.argv[1]):
 try:
  c=socket.create_connection((host,port),timeout=1);c.close();results.append(True)
 except OSError:results.append(False)
print(json.dumps(results))
"""
checks=[[config['addresses'][0],18080],[config['addresses'][0],18081],[denied_ip,18080]]
def run():
 output=subprocess.check_output(['setpriv','--reuid=65534','--regid=65534','--clear-groups','--bounding-set=-all','--no-new-privs','python3','-I','-c',probe,json.dumps(checks)],timeout=10)
 return json.loads(output)
before=run()
subprocess.run(['nft','-f','-'],input=w.rules(config).encode(),check=True,timeout=5)
rules=json.loads(subprocess.check_output(['nft','-j','list','table','inet','wixal']))
after=run()
assert before==[True,True,True],before
assert after==[True,False,False],after
print(json.dumps(dict(before=before,after=after,checks=checks,rules=rules)))
'''


async def main(args):
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    real.ART=output;real.STATE=output/'data';project=output/'project';project.mkdir(exist_ok=True)
    suffix=uuid.uuid4().hex[:12];target_name='wixal-lab-'+suffix;network='wixal-policy-'+suffix
    command=['docker','--host','unix://'+str(Path(args.socket).resolve())]
    async def docker(*argv):
        child=await asyncio.create_subprocess_exec(*command,*argv,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        async with asyncio.timeout(120):out,err=await child.communicate()
        if child.returncode:raise RuntimeError(err.decode()[:3000])
        return out.decode()
    report=dict(status='running',implementation='source' if args.source else 'packaged',cases={},socket=args.socket)
    def save():(output/'results.json').write_text(json.dumps(report,indent=2))
    app=Path(args.app).resolve() if args.app else None
    c=real.Client(args.source,helper=app/'Contents/Resources/engine/wixal-engine' if app else None,payload=ROOT/'runtime/ollama',endpoint='http://127.0.0.1:11434')
    c.allowed={'security_worker_runtime','security_engagement_scope','security_linux_worker','security_worker_cleanup','security_cleanup_disposition'}
    started=False
    try:
        await docker('run','--detach','--name',target_name,'--label','wixal.validation='+suffix,'--network','host','--entrypoint','python3','wixal-security-worker:v1','-I','-u','-c',TARGET_SCRIPT)
        for _ in range(50):
            if 'WIXAL-LAB-READY' in await docker('logs',target_name):break
            await asyncio.sleep(.1)
        else:raise AssertionError('Owned target did not start')
        bridge=json.loads(await docker('network','inspect','bridge'))[0]['IPAM']['Config'][0]['Gateway'];ipaddress.ip_address(bridge)
        await docker('network','create','--label','wixal.validation='+suffix,'--subnet','172.28.91.0/24',network)
        config=dict(addresses=[bridge],ports=[18080],profile='ports',seconds=30,engagementId=suffix,runId=suffix,scopeRevision=1)
        policy_result=json.loads(await docker('run','--rm','--network',network,'--cap-drop','ALL','--cap-add','NET_ADMIN','--cap-add','SETUID','--cap-add','SETGID','--cap-add','SETPCAP','--security-opt','no-new-privileges','--entrypoint','python3','wixal-security-worker:v1','-I','-c',POLICY_SCRIPT,json.dumps(config),'172.28.91.1'))
        report['cases']['actualEgressPolicy']=policy_result;save()
        await c.start();started=True
        await c.call('project-add',dict(root=str(project)))
        await c.call('security-engagement-worker-configure',dict(socket=args.socket))
        ready=await c.call('security-engagement-worker-inspect');assert ready['available'],ready;report['imageId']=ready['imageId']
        target=await c.call('security-target-add',dict(type='Server',address=bridge,objective='Owned Linux lab service'))
        silent=await c.call('security-target-add',dict(type='Server',address='172.28.91.99',objective='Owned unused lab address for cancellation'))
        engagement=await c.call('security-engagement-create',dict(name='Actual Linux worker validation',objective='Observe owned lab service and prove bounded egress/cancellation',targetIds=[target['id'],silent['id']],scope=dict(capabilities=['linux_network_scan'],maxSeconds=30,maxRuns=8)))
        await c.call('security-engagement-approve',dict(engagementId=engagement['id'],baseRevision=1))
        scan=await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='linux_network_scan',arguments=dict(profile='ports',ports='18080',timeout_seconds=30),name='Actual isolated port observation'))
        async def get(run_id):return next(r for r in (await c.state())['securityRuns'] if r['id']==run_id)
        for _ in range(600):
            scan=await get(scan['id'])
            if scan['status'] in ('completed','failed','interrupted'):break
            await asyncio.sleep(.1)
        assert scan['status']=='completed',scan
        assert any(s['host']==bridge and s['port']=='18080' and s['state']=='open' for s in scan['result']['services']),scan
        assert scan['result']['enforcementReceipt']['configSha256']==scan['workerApproval']['configSha256']
        assert scan['workerCleanup'] and all(r.get('removed') or r.get('absent') for r in scan['workerCleanup'])
        report['cases']['productionWorker']=scan;save()
        pending=await c.call('security-run-add',dict(targetId=silent['id'],stage='Recon',capability='linux_network_scan',arguments=dict(profile='ports',ports='18080',timeout_seconds=30),name='Owned cancellation probe'))
        observed_container=False
        for _ in range(100):
            pending=await get(pending['id'])
            if pending.get('workerContainer'):
                names=(await docker('container','ls','--filter','name='+pending['workerContainer'],'--format','{{.Names}}')).splitlines()
                if pending['workerContainer'] in names:observed_container=True;break
            if pending['status'] in ('completed','failed','interrupted'):break
            await asyncio.sleep(.05)
        assert observed_container,pending
        await c.call('security-run-stop',dict(id=pending['id']));pending=await get(pending['id'])
        assert pending['status']=='cancelled' and pending['effectState']=='unknown',pending
        assert all(r.get('removed') or r.get('absent') for r in pending['workerCleanup']),pending
        assert not (await docker('container','ls','--all','--filter','label=wixal.run='+pending['id'],'--format','{{.Names}}')).strip()
        assert not (await docker('network','ls','--filter','label=wixal.run='+pending['id'],'--format','{{.Name}}')).strip()
        report['cases']['actualCancellation']=pending
        report.update(status='passed',reviews=c.reviews);save()
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    finally:
        if started:await c.close()
        for kind,name in (('container',target_name),('network',network)):
            try:
                info=json.loads(await docker(kind,'inspect',name))[0]
                labels=info.get('Config',{}).get('Labels',{}) if kind=='container' else info.get('Labels',{})
                assert labels.get('wixal.validation')==suffix
                await docker(kind,'rm',*(['--force'] if kind=='container' else []),name)
            except RuntimeError:pass
    print(json.dumps(dict(status=report['status'],cases=list(report['cases']),report=str(output/'results.json')),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',action='store_true');parser.add_argument('--app');parser.add_argument('--socket',required=True);parser.add_argument('--output',required=True)
    asyncio.run(main(parser.parse_args()))
