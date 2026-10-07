"""Installed WebKit download acceptance with visible Save/Cancel controls.

Only use a disposable app workspace socket: prompts are bypassed there, restored
in finally. The operator (or CUA) must interact with real NSSavePanel and Cancel.
Reports fail on timeouts, wrong bytes, absent error feedback or incomplete state.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('download_fixture',Path(__file__).with_name('browser-download-fixture.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def emit(**data):print(json.dumps(data),flush=True)

async def main(args):
    server=ThreadingHTTPServer(('127.0.0.1',0),fixture.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        async with asyncio.timeout(15):
            while True:
                try: reader,writer=await asyncio.open_unix_connection(args.socket,limit=16*1024*1024);break
                except (FileNotFoundError,ConnectionRefusedError): await asyncio.sleep(.1)
    except BaseException as error:
        server.shutdown();server.server_close();args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(dict(status='failed',phase='connect',error=repr(error)),indent=2));raise
    counter=0
    async def call(method,params=None):
        nonlocal counter
        counter+=1;identifier=f'download-check-{counter}'
        writer.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await writer.drain()
        while line:=await asyncio.wait_for(reader.readline(),60):
            row=json.loads(line)
            if row['event']=='response' and row['data']['id']==identifier:
                if row['data'].get('error'):raise RuntimeError(row['data']['error'])
                return row['data']['result']
        raise RuntimeError('Engine disconnected')
    async def tool(name,arguments):return await call('tool',dict(name=name,arguments=arguments))
    report=dict(status='running',scope='actual installed WebKit HTTP downloads with visible destination and cancellation controls',checks=[])
    app=Path.home()/'Applications/Wixal Native.app'
    report['appSHA256']=hashlib.sha256((app/'Contents/MacOS/WixalNative').read_bytes()).hexdigest()
    report['helperSHA256']=hashlib.sha256((app/'Contents/Resources/engine/wixal-engine').read_bytes()).hexdigest()
    original=None;page=None
    try:
        hello=await call('hello');state=hello['state'];project=next((p for p in state['projects'] if p['id']==state.get('activeProject')),None);original=(project or {}).get('approvalMode',state.get('personalApprovalMode','review'))
        # Invocation requires explicit disposable workspace socket.
        await call('settings',dict(approvalMode='bypass'))
        page=await tool('browser_open',dict(url=f'http://127.0.0.1:{server.server_port}/',interactive=True,wait_ms=0))
        with tempfile.TemporaryDirectory(prefix='wixdl-',dir='/tmp') as directory:
            for route,label,expected in [('/download','Download 8 MB','Completed'),('/slow','Download 64 MB, then cancel','Cancelled'),('/broken','Download with interrupted connection','Failed'),('/download','Download 8 MB','Cancelled')]:
                fresh=await tool('browser_read',dict(session_id=page['session_id'],wait_ms=0))
                link=next(link for link in fresh['links'] if label in link.get('text',link.get('label','')))
                before=len(fresh.get('downloads',[]));destination=Path(directory)/f'check-{before}.bin'
                emit(event='destination-needed',case=label,destination=str(destination),action='Cancel Save panel' if before==3 else 'Save file'+(' then click browser Cancel while downloading' if expected=='Cancelled' else ''))
                action=await tool('browser_action',dict(session_id=page['session_id'],ref=link['ref'],action='click',wait_ms=0))
                record=None
                for _ in range(600):
                    fresh=await tool('browser_read',dict(session_id=page['session_id'],wait_ms=0))
                    downloads=fresh.get('downloads',[])
                    if len(downloads)>before:
                        record=downloads[-1]
                        if record['status'] in ('Completed','Cancelled','Failed'):break
                    await asyncio.sleep(1)
                assert record and record['status']==expected,dict(expected=expected,record=record)
                check=dict(case=label,expected=expected,result=record)
                if expected=='Completed':
                    assert destination.is_file(),'Save to the exact reported destination'
                    raw=destination.read_bytes();assert raw==fixture.CHUNK*128,'Downloaded bytes differ from served bytes'
                    assert Path(record['destination']).resolve()==destination.resolve()
                    assert record['receivedBytes']==len(raw) and record['totalBytes']==len(raw),record
                    check.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                if route=='/slow':assert 0<record['receivedBytes']<record['totalBytes']==67108864,record
                if expected=='Failed':assert record.get('error'),'Failure needs visible error detail'
                report['checks'].append(check);emit(event='case-passed',**check)
            await tool('browser_close',dict(session_id=page['session_id']));page=None
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error));raise
    finally:
        try:
            if page:await tool('browser_close',dict(session_id=page['session_id']))
            if original is not None:await call('settings',dict(approvalMode=original))
        finally:
            writer.close();await writer.wait_closed();server.shutdown();server.server_close()
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));emit(event='finished',report=report)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket',required=True,type=Path,help='Disposable installed app workspace engine.sock')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/native/browser-download-acceptance.json')
    asyncio.run(main(parser.parse_args()))
