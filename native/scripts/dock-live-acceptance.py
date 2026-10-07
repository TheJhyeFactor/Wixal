"""Exercise installed inference and tool evidence; no inserted model/tool results.

--finish restores the selected workspace and archives the validation conversation.
"""
import argparse,asyncio,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'artifacts/native/dock-live-acceptance.json'
async def main():
 args=argparse.ArgumentParser();args.add_argument('--finish',action='store_true');options=args.parse_args()
 reader,writer=await asyncio.open_unix_connection(Path.home()/'Library/Application Support/Wixal Native/engine.sock',limit=16*1024*1024)
 counter=0
 async def call(method,params=None):
  nonlocal counter
  counter+=1;identifier=f'dock-live-{counter}'
  writer.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await writer.drain()
  while line:=await asyncio.wait_for(reader.readline(),660):
   item=json.loads(line)
   if item['event']=='response' and item['data']['id']==identifier:
    if item['data'].get('error'):raise RuntimeError(item['data']['error'])
    return item['data']['result']
  raise RuntimeError('Helper disconnected')
 async def finish(report):
  await call('stop');await call('project-select',dict(id=report['originalProject']))
  if report.get('accountRestored'):
   account=await call('account-restore');assert account.get('signedIn'),'Saved account did not restore'
  if report['originalSession']:await call('session-select',dict(id=report['originalSession']))
  if report.get('validationSession'):await call('session-archive',dict(id=report['validationSession']))
  report['workspaceRestored']=True;ART.write_text(json.dumps(report,indent=2))
 try:
  if options.finish:await finish(json.loads(ART.read_text()));print('Original workspace restored');return
  account=await call('account-restore');assert account.get('signedIn'),'Existing account did not restore'
  state=(await call('hello'))['state']
  report=dict(status='running',originalProject=state['activeProject'],originalSession=state['activeSession'],accountRestored=True)
  ART.write_text(json.dumps(report,indent=2))
  directory=tempfile.mkdtemp(prefix='wixal-dock-live-');Path(directory,'proof.txt').write_text('WIXAL_DOCK_REAL_FILE_EVIDENCE\n')
  await call('project-add',dict(root=directory,memoryMode='off',memorySize=8000))
  state=(await call('hello'))['state'];report['validationSession']=state['activeSession'];report['validationProject']=state['activeProject'];ART.write_text(json.dumps(report,indent=2))
  try:
   result=await call('chat',dict(text='Use @read_file to read proof.txt, and then use @read_file to read missing.txt exactly once. Do not create files and do not retry the missing file. Report the exact proof text and explain the missing-file result.'))
   state=(await call('hello'))['state'];session=next(s for s in state['sessions'] if s['id']==report['validationSession'])
   tools=[m for m in session['messages'] if m['role']=='tool']
   assert any('WIXAL_DOCK_REAL_FILE_EVIDENCE' in m['content'] for m in tools)
   assert any('error' in m['content'] or 'Error:' in m['content'] for m in tools)
   rows=json.loads(__import__('subprocess').check_output([str(ROOT/'native/.build/debug/ActivityAcceptance')],input=json.dumps({'messages':session['messages'],'tasks':state['tasks']}).encode()))
   assert any(r['status']=='failed' for r in rows) and any(r['status']=='completed' and 'WIXAL_DOCK_REAL_FILE_EVIDENCE' in r['output'] for r in rows)
   report.update(status='ready-for-ui-check',actualToolResults=len(tools),failureAndSuccessProjected=True,reportedUsage=bool(state.get('usage')),model=result.get('status'))
   ART.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('originalProject','originalSession','validationSession','validationProject')}))
  except BaseException:report['status']='failed';await finish(report);raise
 finally:writer.close();await writer.wait_closed()
asyncio.run(main())
