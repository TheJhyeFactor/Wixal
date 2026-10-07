"""Actual packaged WebKit against disposable HTTP web-app fixtures, no inference claim."""
import asyncio
import http.server
import json
import threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/feature-acceptance';STATE=ART/'workspace'
class Site(http.server.BaseHTTPRequestHandler):
 posts=[]
 def log_message(self,*args):pass
 def do_GET(self):
  if self.path=='/stream':body=b'first\nsecond\n';kind='text/plain'
  else:
   body=b'''<!doctype html><h1>Interactive acceptance</h1><form action="/submit" method="post"><label>Test message<input name="message" value="disposable"></label><button type="submit">Submit test message</button></form><div id="stream"></div><div id="worker"></div><script>fetch('/stream').then(async r=>{const reader=r.body.getReader();let out='';while(true){const part=await reader.read();if(part.done)break;out+=new TextDecoder().decode(part.value)}document.getElementById('stream').textContent='STREAM_OK '+out});const worker=new Worker(URL.createObjectURL(new Blob(["postMessage('WORKER_OK')"],{type:'text/javascript'})));worker.onmessage=e=>document.getElementById('worker').textContent=e.data;</script>''';kind='text/html'
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):
  self.posts.append(self.rfile.read(int(self.headers.get('Content-Length',0))).decode());body=b'<h1>SUBMISSION_OK</h1>'
  self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
async def main():
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Site);threading.Thread(target=server.serve_forever,daemon=True).start()
 reader,writer=await asyncio.open_unix_connection(STATE/'engine.sock',limit=16*1024*1024);counter=0
 async def call(method,params):
  nonlocal counter
  counter+=1;key='interactive-'+str(counter);writer.write((json.dumps(dict(id=key,method=method,params=params))+'\n').encode());await writer.drain()
  while line:=await asyncio.wait_for(reader.readline(),60):
   row=json.loads(line)
   if row['event']=='response' and row['data']['id']==key:
    if row['data'].get('error'):raise RuntimeError(row['data']['error'])
    return row['data']['result']
 async def tool(name,args):return await call('tool',dict(name=name,arguments=args))
 report=dict(status='running',source='actual packaged WebKit with disposable web-app fixture')
 try:
  # Bypass only the disposable fixture workspace's controller prompts for deterministic acceptance.
  await call('settings',dict(approvalMode='bypass'))
  page=await tool('browser_open',dict(url=f'http://127.0.0.1:{server.server_port}/',interactive=True,wait_for='WORKER_OK',wait_ms=2000))
  assert 'WORKER_OK' in page['text'] and 'STREAM_OK' in page['text'],page
  control=next(c for c in page['controls'] if c['label']=='Submit test message')
  result=await tool('browser_action',dict(session_id=page['session_id'],ref=control['ref'],action='click'))
  assert 'SUBMISSION_OK' in result['text'] and Site.posts==['message=disposable'],dict(result=result,posts=Site.posts)
  await tool('browser_close',dict(session_id=page['session_id']))
  report.update(status='passed',streaming=True,worker=True,actualPost=Site.posts,submissionResult=result['text'])
 except BaseException as error:report.update(status='failed',error=str(error));raise
 finally:
  await call('settings',dict(approvalMode='review'));writer.close();await writer.wait_closed();server.shutdown();server.server_close();(ART/'interactive-browser.json').write_text(json.dumps(report,indent=2))
 print('PACKAGED_INTERACTIVE_BROWSER_PASSED')
asyncio.run(main())
