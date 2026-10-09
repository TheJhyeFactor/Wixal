"""Launch the installed UI with isolated storage and a held, controlled model response.

This is controller/UI acceptance infrastructure, not real-model qualification.
Only already-completed setup flags are copied from the named existing workspace;
no legal agreement is accepted and no conversations or credentials are copied.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'native/engine'))
from wixal.service import Service


def main(args):
    base=args.output.resolve();base.mkdir(parents=True,exist_ok=False)
    source=sqlite3.connect(f'file:{args.setup_source.resolve()}?mode=ro',uri=True)
    setup=json.loads(source.execute('SELECT value FROM state').fetchone()[0]).get('setup',{})
    source.close()
    if setup.get('entryCompleted') is not True or setup.get('completed') is not True:
        raise ValueError('Use an existing workspace with completed setup; this fixture does not accept legal terms')
    stop=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps(value).encode())
        def do_GET(self):
            self.reply(dict(models=[dict(name='fixture',size=1)]) if self.path=='/api/tags' else dict(version='controlled-ui-fixture'))
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path=='/api/show':
                self.reply(dict(capabilities=['completion','tools'],model_info={'fixture.context_length':8192}));return
            self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.end_headers()
            with (base/'model-requests.jsonl').open('a') as log:log.write(json.dumps(body)+'\n')
            try:
                # Blank NDJSON lines keep the controlled request alive while UI
                # tests queue, guide and cancel through the actual engine.
                while not stop.is_set() and not (base/'release-model').exists():
                    self.wfile.write(b'\n');self.wfile.flush();stop.wait(.5)
                if not stop.is_set():
                    self.wfile.write((json.dumps(dict(message=dict(role='assistant',content='Controlled response completed.'),done=True))+'\n').encode());self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    endpoint=f'http://127.0.0.1:{server.server_port}'
    async def seed():
        service=Service(base/'data',ROOT/'runtime/ollama',lambda *_:None,endpoint)
        try:
            service.store.data['setup']=setup
            service.store.data['ui'].update(theme='midnight',launchSound=False)
            project=base/'project';project.mkdir()
            await service.dispatch('project-add',dict(root=str(project)))
            await service.dispatch('settings',dict(model='fixture',enabledTools=[]))
            agent=await service.dispatch('agent-save',dict(id='ui-acceptance-agent',name='Editor acceptance agent',purpose='Exercise acknowledgement and recovery',instructions='Read only. Wait for controlled acceptance.',model='fixture',reviewPolicy='Read only',memoryScope='Memory off',skills=[]))
            await service.dispatch('workflow-save',dict(id='ui-acceptance-workflow',name='Saved workflow acceptance',stages=[dict(name='Inspect',agentID=agent['id'],goal='Inspect retained evidence')]))
            await service.dispatch('agent-schedule-save',dict(id='ui-acceptance-routine',name='Saved routine acceptance',agentID=agent['id'],prompt='Inspect retained evidence',timing='Every hour',enabled=False))
            service.store.save()
        finally:await service.close()
    asyncio.run(seed())
    app=args.app.resolve()
    report=dict(app=str(app),endpoint=endpoint,storage=str(base/'data'),sourceSetup='copied completed setup flags only',model='controlled fixture; no real-model claim',helperSha256=hashlib.sha256((app/'Contents/Resources/engine/wixal-engine').read_bytes()).hexdigest())
    (base/'launch.json').write_text(json.dumps(report,indent=2)+'\n')
    env={**os.environ,'WIXAL_NATIVE_DATA':str(base/'data'),'WIXAL_NATIVE_ENDPOINT':endpoint,'WIXAL_AGENTS_DESIGN_DATA':str(base/'drafts')}
    with (base/'app-stdout.log').open('w') as stdout,(base/'app-stderr.log').open('w') as stderr:
        process=subprocess.Popen([str(app/'Contents/MacOS/WixalNative')],env=env,stdout=stdout,stderr=stderr)
        def shutdown(*args):stop.set()
        signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
        print(json.dumps(report),flush=True)
        try:
            while process.poll() is None and not stop.wait(.5):pass
        finally:
            stop.set()
            if process.poll() is None:process.terminate();process.wait(timeout=15)
            server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,default=Path('/Applications/Wixal.app'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--setup-source',type=Path,default=Path.home()/'Library/Application Support/Wixal Native/workspace.sqlite3')
    main(parser.parse_args())
