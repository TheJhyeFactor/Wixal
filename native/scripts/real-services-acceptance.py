"""Real Internet/account/companion protocols through the packaged production helper.

No dummy HTTP endpoints, fabricated model/tool results or imported fake records.
Account reset is optional and requires an explicitly supplied mailbox. The external
ChatGPT tunnel is deliberately deferred; local MCP is tested as its own feature.
"""
import argparse,asyncio,hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from importlib import import_module
from importlib.util import spec_from_file_location,module_from_spec
ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('real_acceptance',Path(__file__).with_name('real-acceptance.py'));module=module_from_spec(spec);spec.loader.exec_module(module)

async def main():
 parser=argparse.ArgumentParser();parser.add_argument('--reset-email');parser.add_argument('--target',help='Explicitly authorised public domain; checks only TCP 443 and public GET baseline');args=parser.parse_args()
 # Independent durable acceptance storage, without competing with the model suite.
 module.STATE=ROOT/'artifacts/native/real-services/workspace';module.ART=module.STATE.parent;module.ART.mkdir(parents=True,exist_ok=True)
 helper=ROOT/'release/native/Wixal.app/Contents/Resources/engine/wixal-engine'
 report=dict(status='running',helperSHA256=hashlib.sha256(helper.read_bytes()).hexdigest(),started=time.time(),cases={},chatGPTTunnel='Deferred by user; no credential created and no external connection claimed')
 destination=module.ART/'packaged.json'
 def record(name,data):
  report['cases'][name]=dict(status='passed',observed=data);destination.write_text(json.dumps(report,indent=2));print(name+': PASSED',flush=True)
 client=module.Client(False);client.allowed.update(('web_search','http_request','network_scan','write_file','website_assess','save_website_evidence'))
 try:
  await client.start();await client.call('project-add',dict(root=str(ROOT)))
  package=await client.call('tool',dict(name='read_file',arguments=dict(path='native/Package.swift')))
  assert package['content']==(ROOT/'native/Package.swift').read_text()
  request=await client.call('tool',dict(name='http_request',arguments=dict(url='https://docs.python.org/3/library/sqlite3.html',method='GET',max_chars=24000)))
  assert request['status']==200 and 'sqlite3' in request['content'].lower(),request
  record('realPublicHTTP',request)
  search=await client.call('tool',dict(name='web_search',arguments=dict(query='Python sqlite3 FTS5 documentation',limit=5)))
  assert search['state']=='results' and search['results'] and all(r['url'].startswith(('https://','http://')) for r in search['results']),search
  record('realWebSearch',search)
  # Read a real process's output, including current source Unicode, in small overlapping pages.
  command=await client.call('tool',dict(name='command_start',arguments=dict(command='cat native/engine/wixal/agent.py native/engine/wixal/service.py',timeout_seconds=30)))
  pieces=[];offset=0
  while True:
   row=await client.call('tool',dict(name='command_read',arguments=dict(session_id=command['session_id'],offset=offset,max_chars=997,wait_ms=1000)))
   pieces.append(row['output']);offset=row['next_offset']
   if not row['more'] and row['state']!='running':break
  expected=(ROOT/'native/engine/wixal/agent.py').read_text()+(ROOT/'native/engine/wixal/service.py').read_text()
  assert ''.join(pieces)==expected and row['exitCode']==0
  record('realCommandUnicodePagination',dict(pages=len(pieces),sourceCharacters=len(expected),sha256=hashlib.sha256(expected.encode()).hexdigest(),exitCode=row['exitCode']))
  if args.target:
   readiness=await client.call('security-readiness');assert readiness['installed'],readiness
   scan=await client.call('assessment-run',dict(name='network_scan',arguments=dict(target=args.target,profile='ports',ports='443',timeout_seconds=60)))
   assert scan['exitCode']==0 and '443' in scan['output'],scan
   record('realAuthorisedTCP443',scan)
   assessment=await client.call('assessment-run',dict(name='website_assess',arguments=dict(url='https://'+args.target+'/',profile='baseline',protected_paths=[],max_pages=3,report_prefix='artifacts/native/real-services/public-baseline-'+str(int(time.time())))))
   assert assessment['saved'] and assessment['report']['requests'] and assessment['report']['cases'],assessment
   record('realAuthorisedWebsiteBaseline',assessment)
  # Exercise the genuine packaged companion executable over stdio, not a stand-in server.
  state=await client.state();project=next(p for p in state['projects'] if p['root']==str(ROOT))
  await client.call('companion-settings',dict(sharedProjects=[project['id']],shareMemory=False))
  companion=await client.call('companion-start')
  child=await asyncio.create_subprocess_exec(str(ROOT/'release/native/Wixal.app/Contents/Resources/engine/wixal-engine'),'--companion',companion['connectionFile'],stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=4*1024*1024)
  counter=0
  async def mcp(method,params):
   nonlocal counter
   counter+=1;child.stdin.write((json.dumps(dict(jsonrpc='2.0',id=counter,method=method,params=params))+'\n').encode());await child.stdin.drain()
   while line:=await asyncio.wait_for(child.stdout.readline(),40):
    row=json.loads(line)
    if row.get('id')==counter:
     if row.get('error'):raise RuntimeError(row['error'])
     return row['result']
   raise RuntimeError('Real companion disconnected')
  try:
   init=await mcp('initialize',dict(protocolVersion='2024-11-05',capabilities={},clientInfo=dict(name='Wixal real acceptance',version='1')))
   catalog=await mcp('tools/list',{})
   assert any(t['name']=='read_project_file' for t in catalog['tools'])
   result=await mcp('tools/call',dict(name='read_project_file',arguments=dict(projectId=project['id'],path='native/Package.swift')))
   assert '1.20.0' in json.dumps(result) and 'SwiftTerm' in json.dumps(result),result
   await client.call('companion-settings',dict(sharedProjects=[],shareMemory=False))
   revoked=await mcp('tools/call',dict(name='read_project_file',arguments=dict(projectId=project['id'],path='native/Package.swift')))
   assert revoked.get('isError') or 'not shared' in json.dumps(revoked).lower(),revoked
   record('realPackagedMCPAndRevocation',dict(protocol=init.get('protocolVersion'),tools=[t['name'] for t in catalog['tools']],readMatchedActualProject=True,revocationEnforced=True))
  finally:
   child.stdin.close();await asyncio.wait_for(child.wait(),15);await client.call('companion-revoke')
  if args.reset_email:
   result=await client.call('account-reset',dict(email=args.reset_email))
   assert 'reset link' in result.get('message','').lower(),result
   record('realPasswordResetRequest',dict(serviceResponded=True,message=result['message'],delivery='Awaiting mailbox verification; request acknowledgement alone is not delivery proof'))
  report['status']='passed'
 except BaseException as error:report.update(status='failed',error=str(error));raise
 finally:
  report['finished']=time.time();destination.write_text(json.dumps(report,indent=2));await client.close()

if __name__=='__main__':asyncio.run(main())
