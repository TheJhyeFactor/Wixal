"""Real disposable loopback remediation and capability-bound retest through IPC."""
import argparse,asyncio,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
async def main(args):
 output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True);real.ART=output;real.STATE=output/'data';project=output/'project';project.mkdir(exist_ok=True)
 async def connection(reader,writer):writer.close();await writer.wait_closed()
 service=await asyncio.start_server(connection,'127.0.0.1',0);control=await asyncio.start_server(connection,'127.0.0.1',0)
 port=service.sockets[0].getsockname()[1];control_port=control.sockets[0].getsockname()[1]
 helper=Path(args.app)/'Contents/Resources/engine/wixal-engine' if args.app else None;c=real.Client(not bool(args.app),helper=helper,endpoint='http://127.0.0.1:19543');c.allowed={'security_engagement_scope','network_scan','command_start'}
 report=dict(status='running',fixture='Disposable local TCP listener; no exploit or remote remediation',port=port,controlPort=control_port)
 try:
  await c.start();await c.call('project-add',dict(root=str(project)))
  t=await c.call('security-target-add',dict(type='Server',address='127.0.0.1',objective='Verify removed test listener with legitimate control still reachable'))
  e=await c.call('security-engagement-create',dict(name='Real loopback fix and retest',objective='Evaluate declared open-to-closed state only',targetIds=[t['id']],scope=dict(capabilities=['network_scan'],maxRuns=8,maxSeconds=30)))
  async def call(method,**params):return await c.call(method,dict(engagementId=e['id'],**params))
  await call('security-engagement-approve',baseRevision=1)
  objective=await call('security-objective-save',targetId=t['id'],title='Remove test listener',hypothesis='Stopping owned listener closes its port',successSignal='Selected port changes open to closed while control remains open',dependsOn=[])
  async def scan(name):
   row=await c.call('security-run-add',dict(targetId=t['id'],engagementId=e['id'],capability='network_scan',stage='Recon',name=name,arguments=dict(profile='ports',ports=f'{port},{control_port}',timeout_seconds=30)))
   for _ in range(300):
    state=await c.state();row=next(r for r in state['securityRuns'] if r['id']==row['id'])
    if row['status'] not in ('queued','running','waiting_review','blocked'):break
    await asyncio.sleep(.2)
   assert row['status']=='completed',row;return row
  before=await scan('Before stopping owned service');assert next(s for s in before['result']['services'] if s['port']==str(port))['state']=='open'
  fields=('description','impact','assumptions','counterevidence','confidenceRationale','severityChangeConditions','remediation','retestPlan')
  draft=dict(targetId=t['id'],objectiveId=objective['id'],title='Disposable listener observation',resultKind='observation',confidence='high',evidenceIds=[before['retainedEvidenceId']],**{k:'Controlled fixture '+k+'; no vulnerability claim' for k in fields})
  finding=await call('security-cyber-manage',action='finding_save',parameters=draft)
  service.close();await service.wait_closed()
  after=await scan('After stopping owned service')
  assert next(s for s in after['result']['services'] if s['port']==str(port))['state']=='closed'
  for run in (before,after):assert next(s for s in run['result']['services'] if s['port']==str(control_port))['state']=='open'
  contract=await call('security-contract-validator-save',objectiveId=objective['id'],validator='network_port_state',config=dict(host='127.0.0.1',port=port,positiveState='open',baselineState='closed'))
  check=await call('security-contract-validator-run',contractId=contract['id'],evidenceIds=[before['retainedEvidenceId'],after['retainedEvidenceId']]);assert check['status']=='validated'
  retest=await call('security-cyber-manage',action='retest',parameters=dict(findingId=finding['finding']['id'],verificationIds=[check['id']],fixDescription='Stopped the disposable local TCP listener',limitations='Only declared loopback port transition checked; legitimate control port stayed open; no remote remediation or vulnerability qualification'))
  assert retest['status']=='declared_checks_passed'
  report.update(status='passed',before=before,after=after,contract=contract,verification=check,retest=retest,reviews=c.reviews)
  (output/'results.json').write_text(json.dumps(report,indent=2))
 finally:
  service.close();control.close();await service.wait_closed();await control.wait_closed();await c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--app');p.add_argument('--output',required=True);asyncio.run(main(p.parse_args()))
