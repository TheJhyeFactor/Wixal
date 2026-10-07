"""Production IPC cancellation workload against real disposable HTTP requests.

Exercises source or packaged helper, never changes the user's workspace. No model
replies or assessment results are injected. Loopback HTTP is integration workload,
not external website acceptance. Each failure is retained in the JSON report.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
import time
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'artifacts/native/workflow-assessment'; ART.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('real', ROOT/'native/scripts/real-acceptance.py')
real = importlib.util.module_from_spec(spec); spec.loader.exec_module(real)
real.ART = ART

class Client(real.Client):
    async def read(self):
        try:
            while line := await self.child.stdout.readline():
                item = json.loads(line); event, data = item['event'], item['data']
                if event == 'response':
                    future = self.pending.pop(data['id'], None)
                    if future and not future.done(): future.set_result(data)
                else: self.events.append(item)
        finally:
            for future in self.pending.values():
                if not future.done(): future.set_exception(RuntimeError('Helper disconnected'))
    async def event(self, kind, start):
        async with asyncio.timeout(10):
            while True:
                item = next((e for e in self.events[start:] if e['event'] == kind), None)
                if item: return item['data']
                await asyncio.sleep(.01)
    async def approve(self, review):
        await self.call('respond', dict(id=review['id'], value=True))

async def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--source', action='store_true'); args = parser.parse_args()
    run = ART/str(time.time_ns()); run.mkdir(); real.STATE = Path(tempfile.mkdtemp(prefix='wix-assess-', dir='/tmp'))
    helper = ROOT/'release/native/Wixal Native.app/Contents/Resources/engine/wixal-engine'
    report = dict(status='running', started=time.time(), implementation='source' if args.source else 'packaged', helperSHA256=None if args.source else hashlib.sha256(helper.read_bytes()).hexdigest(), workloads=[], scope='real loopback HTTP and production IPC; desktop Stop button excluded')
    report_path = ART/('source.json' if args.source else 'packaged.json')
    def save(): report_path.write_text(json.dumps(report, indent=2))
    requests = []
    async def serve(reader, writer):
        try:
            request = await reader.readuntil(b'\r\n\r\n'); path=request.split(b' ')[1].decode(); requests.append(path)
            page = int(path.strip('/') or '0')
            body = ('<html><a href="/'+str(page+1)+'">Continue</a>'+('Actual transfer body. '*2500)+'</html>').encode()
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body); await writer.drain()
        finally: writer.close(); await writer.wait_closed()
    server = await asyncio.start_server(serve, '127.0.0.1', 0)
    url='http://127.0.0.1:'+str(server.sockets[0].getsockname()[1])
    c=Client(args.source); save()
    try:
        await c.start(); await c.call('project-add', dict(root=str(run)))
        for index, phase in enumerate(('review', 'crawl', 'save', 'crawl', 'save')):
            start=len(c.events); before=len(requests); began=time.monotonic()
            future=c.send('assessment-run', dict(name='website_assess', arguments=dict(url=url, max_pages=12, report_prefix='cancel-'+str(index))))
            review=await c.event('review',start)
            if phase != 'review':
                start=len(c.events); await c.approve(review)
                await c.event('assessment-case',start)
                if phase=='save': await c.event('review',start)
            await c.call('assessment-cancel'); response=await asyncio.wait_for(future,10)
            assert not response.get('error'),response
            result=response['result']; assert result['partial'] and result['status']=='cancelled',result
            assert not list(run.glob('cancel-'+str(index)+'.*'))
            if phase=='review': assert len(requests)==before and not result['cases']
            else: assert result['cases'] and all('evidence' in row for row in result['cases'])
            if phase=='save': assert result['report']['cases']==result['cases'] and result['report']['summary']['requests']==12
            state=await c.state(); saved=state['assessmentResults'][-1]
            assert saved['result']==result and saved['status']=='cancelled'
            task=state['tasks'][-1]; assert task['checkpoints'][-1]['result']==result
            report['workloads'].append(dict(phase=phase,requests=len(requests)-before,completedCases=len(result['cases']),seconds=time.monotonic()-began,taskId=task['id'],status='passed')); save()
        await c.close(); c=Client(args.source); await c.start(); state=await c.state()
        assert len(state['assessmentResults'])==5 and all(r['status']=='cancelled' for r in state['assessmentResults'])
        assert len(state['tasks'])==5 and all(t['status']=='cancelled' for t in state['tasks'])
        report.update(status='passed', restartRecords=5, totalRequests=len(requests))
    except BaseException as error: report.update(status='failed', error=repr(error)); raise
    finally:
        await c.close(); server.close(); await server.wait_closed(); report['finished']=time.time(); save()
    print(json.dumps(report,indent=2))
asyncio.run(main())
