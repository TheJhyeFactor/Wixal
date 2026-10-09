"""Real IPC, registry installation, ffuf, packet capture and model tool discovery."""
import asyncio
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'artifacts/native/addon-library';ART.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
real.ART=ART;real.STATE=ART/'workspace'

async def main():
    source='--source' in sys.argv
    c=real.Client(source);c.allowed.update({'addon_install','addon_workflow'})
    report=dict(status='running',execution='source' if source else 'packaged',cases={})
    output=ART/('source.json' if source else 'packaged.json')
    def save():output.write_text(json.dumps(report,indent=2))
    async def read(job):
        async with asyncio.timeout(90):
            while True:
                row=await c.call('tool',dict(name='command_read',arguments=dict(session_id=job['session_id'],offset=0,wait_ms=500,max_chars=100000)))
                if row['state']!='running':return row
    async def serve(reader,writer):
        try:
            request=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),3)
            route=request.split(b' ')[1];known=route==b'/known';body=b'known test endpoint' if known else b'not found'
            writer.write((b'HTTP/1.1 200 OK' if known else b'HTTP/1.1 404 Not Found')+b'\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);await writer.drain()
        except (TimeoutError,ConnectionError,asyncio.IncompleteReadError):pass
        finally:writer.close();await writer.wait_closed()
    server=await asyncio.start_server(serve,'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
    models=real.STATE/'local-runtime/models'
    if not (models/'manifests').exists():
        models.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['cp','-cR',str(ROOT/'artifacts/native/real-acceptance/workspace/local-runtime/models'),str(models)],check=True)
    save()
    try:
        await c.start();await c.call('project-add',dict(root=str(ART)))
        await c.call('settings',dict(enabledTools=[d['function']['name'] for d in (await c.call('hello'))['tools']]))
        catalog=await c.call('addon-catalog');assert len(catalog['packages'])>=10
        report['cases']['catalog']=dict(packages=[dict(id=r['id'],installed=r['installed'],path=r['path']) for r in catalog['packages']]);save()
        candidate=await c.call('addon-discover',dict(query='nmap'));assert candidate['id']=='nmap'
        report['cases']['realRegistry']=candidate;save()
        pack=await c.call('addon-workflow',dict(id='web-assessment'))
        loaded=await c.call('tool',dict(name='load_skill',arguments=dict(name=pack['name'])))
        assert loaded['instructions']==pack['content'];report['cases']['workflow']=dict(id=pack['id'],name=pack['name']);save()
        (ART/'words.txt').write_text('known\nmissing\n')
        job=await c.call('tool',dict(name='addon_run',arguments=dict(id='ffuf',target=f'http://127.0.0.1:{port}',path='words.txt',timeout_seconds=30)))
        row=await read(job);assert row['exitCode']==0,row
        assert '/known' in row['output'] and '200' in row['output'],row
        report['cases']['actualFfuf']=row;save()
        target=await c.call('security-target-add',dict(type='Website / API',address=f'http://127.0.0.1:{port}'))
        queued=await c.call('security-run-add',dict(targetId=target['id'],stage='Recon',capability='addon:ffuf',arguments=dict(path='words.txt',timeout_seconds=30)))
        async with asyncio.timeout(60):
            while True:
                queued=next(r for r in (await c.state())['securityRuns'] if r['id']==queued['id'])
                if queued['status'] not in ('queued','running','waiting_review'):break
                await asyncio.sleep(.2)
        assert queued['status']=='completed' and '/known' in queued['output'],queued
        assert queued['result']['evidenceText'] and queued['result']['requests'],queued
        report['cases']['investigationAdapter']=queued;save()
        # Real pcap container with one synthetic, explicitly labelled Ethernet/IPv4/UDP packet.
        ethernet=bytes.fromhex('ffffffffffff0011223344550800');ip=bytes.fromhex('4500001c00000000401100007f0000017f000001');udp=struct.pack('!HHHH',1234,5678,8,0);packet=ethernet+ip+udp
        capture=struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)+struct.pack('<IIII',int(time.time()),0,len(packet),len(packet))+packet
        (ART/'labelled-fixture.pcap').write_bytes(capture)
        job=await c.call('tool',dict(name='addon_run',arguments=dict(id='wireshark',path='labelled-fixture.pcap')))
        row=await read(job);assert row['exitCode']==0 and 'udp' in row['output'],row
        report['cases']['actualTshark']=dict(result=row,capture='Synthetic packet fixture; actual TShark executable');save()
        # Install a missing supported scanner through the actual registry. Do not install the whole catalogue.
        install=await c.call('addon-install',dict(id='osv-scanner',reason='Verify one supported registry installation for the native capability library'))
        if install.get('status')!='ready':
            async with asyncio.timeout(1200):
                while True:
                    install=await c.call('addon-job',dict(id=install['id']))
                    if install['status'] not in ('queued','running','waiting_review'):break
                    await asyncio.sleep(1)
        assert install['status']=='ready',install
        report['cases']['actualInstallation']=install;save()
        software=ART/'actual-software';software.mkdir(exist_ok=True)
        for name in ('package.json','package-lock.json'):
            if (ROOT/name).exists():(software/name).write_bytes((ROOT/name).read_bytes())
        job=await c.call('tool',dict(name='addon_run',arguments=dict(id='osv-scanner',path='actual-software',timeout_seconds=180)))
        scanned=await read(job)
        assert scanned['exitCode'] in (0,1) and 'results' in scanned['output'],scanned
        report['cases']['actualOsvScan']=scanned;save()
        # Real tool-capable local model discovery; no additional program installation is authorised here.
        c.allowed.discard('addon_install')
        models=real.STATE/'local-runtime/models'
        if not models.exists():
            models.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run(['cp','-cR',str(ROOT/'artifacts/native/real-acceptance/workspace/local-runtime/models'),str(models)],check=True)
        await c.model('qwen3:1.7b')
        await c.call('settings',dict(contextSize=8192))
        result=await c.chat('Use @addon_catalog with query ffuf to inspect whether ffuf is installed and which adapter is available. Report only that readiness evidence. Do not install or execute any programs.')
        assert any(m.get('tool_name')=='addon_catalog' for m in result['toolResults']),result
        report['cases']['realModelDiscovery']=result;save()
        report.update(status='passed',helperSHA256=None if source else hashlib.sha256(c.helper.read_bytes()).hexdigest(),finished=time.time());save()
        print(json.dumps(dict(status=report['status'],execution=report['execution'],cases=list(report['cases'])),indent=2))
    except BaseException as error:
        report.update(status='failed',error=str(error));save();raise
    finally:
        server.close();await server.wait_closed()
        if hasattr(c,'child'):await c.close()
asyncio.run(main())
