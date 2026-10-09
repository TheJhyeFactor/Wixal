"""Installed-helper loopback topology, empty-result and cancellation acceptance."""
import asyncio
import argparse
import hashlib
import importlib.util
import json
import sys
import time
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper',type=Path,default=Path('/Applications/Wixal Tools Preview.app/Contents/Resources/engine/wixal-engine'));parser.add_argument('--output',type=Path,default=ROOT/'artifacts/native/managed-tools/lifecycle');options=parser.parse_args()
ART=options.output.resolve();ART.mkdir(parents=True,exist_ok=True);os.environ['WIXAL_MANAGED_TOOLS_ROOT']=str(ART/'registry')
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real);real.ART=ART;real.STATE=ART/'runs'/str(time.time_ns())/'workspace'
helper=options.helper
async def main():
 c=real.Client(False,helper=helper);c.allowed.add('command_start');servers=[];report=dict(status='running',cases={},helper=str(helper),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),workspace=str(real.STATE))
 def save():(ART/'report.json').write_text(json.dumps(report,indent=2))
 async def finished(started):
  async with asyncio.timeout(45):
   while True:
    r=await c.call('tool',dict(name='network_read',arguments=dict(session_id=started['session_id'],wait_ms=100,max_chars=100000)))
    if r['state']!='running' and r.get('structuredResult'):return r
    await asyncio.sleep(.1)
 try:
  await c.start();await c.call('project-add',dict(root=str(ART)));hello=await c.call('hello');await c.call('settings',dict(enabledTools=[r['function']['name'] for r in hello['tools']]))
  job=await c.call('addon-install',dict(id='rustscan',provider='managed',reason='Install an actual trusted package for isolated lifecycle checks'))
  while job['status'] not in ('ready','failed','cancelled'):
   await asyncio.sleep(.1);job=await c.call('addon-job',dict(id=job['id']))
  assert job['status']=='ready',job
  for host in ('127.0.0.1','::1'):servers.append(await asyncio.start_server(lambda r,w:w.close(),host,0))
  ports=[s.sockets[0].getsockname()[1] for s in servers];oracle={'127.0.0.1':[ports[0]],'::1':[ports[1]]}
  started=await c.call('tool',dict(name='network_discover',arguments=dict(target='localhost',ports=','.join(map(str,ports)),timeout_seconds=30)));result=(await finished(started))['structuredResult'];assert {h['host']:h['ports'] for h in result['hosts']}==oracle,result
  inspected=await c.call('tool',dict(name='network_scan',arguments=dict(target='localhost',source_session_id=started['session_id'],profile='ports',timeout_seconds=30)));assert {r['target']:list(map(int,r['ports'].split(','))) for r in inspected['invocations']}==oracle,inspected
  report['cases']['actualIPv4IPv6HostSpecificHandoff']=dict(oracle=oracle,discovery=result,inspection=inspected);save()
  for server in servers:server.close();await server.wait_closed()
  started=await c.call('tool',dict(name='network_discover',arguments=dict(target='127.0.0.1',ports=str(ports[0]),timeout_seconds=20)));result=(await finished(started))['structuredResult'];assert result['hosts'][0]['ports']==[] and result['handoffEligible'],result
  skipped=await c.call('tool',dict(name='network_scan',arguments=dict(target='127.0.0.1',source_session_id=started['session_id'])));assert skipped['skipped'] and skipped['sourceSessionId']==started['session_id'];report['cases']['actualEmptyCoverage']=dict(discovery=result,inspection=skipped);save()
  started=await c.call('tool',dict(name='network_discover',arguments=dict(target='127.0.0.1',coverage='all_tcp',timeout_seconds=30)));stopped=await c.call('tool',dict(name='network_stop',arguments=dict(session_id=started['session_id'])));result=await finished(started);assert result['state']=='stopped' and not result['structuredResult']['handoffEligible'],result
  report['cases']['actualCancellation']=dict(stop=stopped,result=result);report.update(status='passed',finished=time.time());save();print(json.dumps(dict(status='passed',cases=list(report['cases']))))
 except BaseException as error:report.update(status='failed',error=str(error));save();raise
 finally:
  for server in servers:server.close();await server.wait_closed()
  if hasattr(c,'child'):await c.close()
asyncio.run(main())
