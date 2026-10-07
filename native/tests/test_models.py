"""Exercise native model IPC operations against an actual local HTTP fixture."""
import asyncio
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.model_manager import ModelManager,estimate,safe_context,validate_name
from wixal.runtime import Runtime,stream_json
from wixal.storage import Store

class ModelFixture:
    def __init__(self):
        self.models={'small:latest':dict(name='small:latest',size=1000,digest='abc')}
        self.loaded=[dict(name='small:latest',size=1234,size_vram=1000)]
        self.requests=[]
        self.slow=threading.Event()
    def __enter__(self):
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args): pass
            def send(self,body):
                raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if self.path=='/api/tags': self.send(dict(models=list(owner.models.values())))
                elif self.path=='/api/ps': self.send(dict(models=owner.loaded))
                else: self.send(dict(version='fixture'))
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.path,body))
                if self.path=='/api/show':
                    self.send(dict(capabilities=['completion','tools'],details={'parameter_size':'1B'},model_info={'a.context_length':32768,'a.block_count':12,'a.embedding_length':512,'a.attention.head_count':8,'a.attention.head_count_kv':2}));return
                if self.path=='/api/generate': owner.loaded=[];self.send({});return
                if self.path in ('/api/pull','/api/chat'):
                    self.send_response(200);self.send_header('Transfer-Encoding','chunked');self.send_header('Content-Type','application/x-ndjson');self.end_headers()
                    if self.path=='/api/chat':
                        rows=[dict(message=dict(content='one two '),done=False),dict(message=dict(content='three'),done=True,eval_count=30,eval_duration=1000000000,total_duration=2000000000,prompt_eval_count=10)]
                    else:
                        name=body['model']
                        rows=[dict(status='pulling layer',digest='sha256:a',total=100,completed=10),dict(status='pulling layer',digest='sha256:a',total=100,completed=100),dict(status='success')]
                    try:
                        for idx,row in enumerate(rows):
                            raw=(json.dumps(row)+'\n').encode()
                            # Split JSON across HTTP chunks to cover framing and line reassembly.
                            for part in (raw[:9],raw[9:]):
                                self.wfile.write(f'{len(part):x}\r\n'.encode()+part+b'\r\n');self.wfile.flush()
                            if self.path=='/api/pull' and body['model']=='slow:latest' and idx==0: owner.slow.wait(3)
                        if self.path=='/api/pull': owner.models[body['model']]=dict(name=body['model'],size=100,digest='downloaded')
                        self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
                    except (BrokenPipeError,ConnectionResetError): pass
                    return
                self.send({})
            def do_DELETE(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.models.pop(body['model'],None);self.send({})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        return self
    def __exit__(self,*args):
        self.slow.set();self.server.shutdown();self.server.server_close();self.thread.join()

class ModelsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        self.fixture=ModelFixture().__enter__()
        self.events=[]
        self.runtime=Runtime(Path(self.tmp.name)/'models','unused',lambda k,v:self.events.append((k,v)),self.fixture.url)
        self.manager=ModelManager(self.runtime,self.store,lambda k,v:self.events.append((k,v)))
    async def asyncTearDown(self):
        await self.manager.close();self.store.close();await asyncio.to_thread(self.fixture.__exit__);self.tmp.cleanup()
    async def until(self,test):
        for _ in range(100):
            if test(): return
            await asyncio.sleep(.02)
        self.fail('Operation did not complete')
    async def test_capabilities_fit_use_delete_unload(self):
        models=await self.manager.dispatch('models')
        self.assertEqual(models[0]['kvBytesPerToken'],3072)
        self.assertTrue(models[0]['fit']['estimated'])
        self.assertGreater(len(self.manager.snapshot()['catalog']),10)
        await self.manager.dispatch('model-use',{'name':'small:latest'})
        self.assertEqual(self.store.data['model'],'small:latest')
        await self.manager.dispatch('model-unload',{'name':'small:latest'})
        self.assertEqual(self.manager.library['loaded'],[])
        await self.manager.dispatch('model-delete',{'name':'small:latest'})
        self.assertEqual(self.store.data['model'],'')
        self.assertEqual(self.manager.installed,[])
    async def test_embedding_model_cannot_replace_chat_selection(self):
        await self.manager.refresh();previous=self.store.data['model']
        self.manager.installed.append(dict(name='embedding:latest',capabilities=['embedding']))
        with self.assertRaisesRegex(ValueError,'Memory retrieval'):self.manager.use('embedding:latest')
        self.assertEqual(self.store.data['model'],previous)

    async def test_download_queue_completed_and_real_disk_state(self):
        await self.manager.dispatch('model-pull',{'name':'download:latest'})
        await self.until(lambda:self.manager.downloads[0]['state']=='completed')
        self.assertIn('download:latest',[m['name'] for m in self.manager.installed])
        self.assertEqual(self.manager.downloads[0]['completed'],100)
        self.assertTrue(any(k=='model-manager' for k,v in self.events))
    async def test_pause_cancel_persist_resume(self):
        await self.manager.dispatch('model-pull',{'name':'slow:latest'})
        await self.until(lambda:self.manager.downloads[0]['completed']>0)
        job=self.manager.downloads[0]
        await asyncio.wait_for(self.manager.dispatch('model-download-action',{'id':job['id'],'action':'pause'}),1)
        self.assertEqual(job['state'],'paused')
        self.assertIsNone(self.manager.active_download)
        self.assertEqual(self.store.db.execute('SELECT value FROM state WHERE id=1').fetchone()[0].find('paused')>=0,True)
        self.fixture.slow.set()
        await self.manager.dispatch('model-download-action',{'id':job['id'],'action':'resume'})
        await self.until(lambda:job['state']=='completed')
        await self.manager.dispatch('model-download-action',{'id':job['id'],'action':'remove'})
        self.assertEqual(self.manager.downloads,[])
    async def test_duplicate_tag_cloud_validation(self):
        for name in ('','qwen;rm','gpt-cloud','../bad','x'*201):
            with self.assertRaises(ValueError): validate_name(name)
        self.assertEqual(validate_name('qwen3:4b'),'qwen3:4b')
        await self.manager.dispatch('model-pull',{'name':'slow:latest'})
        with self.assertRaises(ValueError): await self.manager.dispatch('model-pull',{'name':'slow:latest'})
    async def test_two_run_benchmark_uses_reported_counters(self):
        await self.manager.dispatch('models')
        await self.manager.dispatch('benchmark-start',{'name':'small:latest'})
        await self.until(lambda:not self.manager.busy)
        self.assertEqual(self.manager.benchmarks[-1]['tokensPerSecond'],30)
        self.assertEqual(len(self.manager.benchmarks[-1]['samples']),2)
        self.assertTrue(self.manager.benchmarks[-1]['fixture'])
        requests=[b for p,b in self.fixture.requests if p=='/api/chat']
        self.assertEqual(len(requests),2)
        self.assertNotIn('tools',requests[0])
        self.assertEqual(requests[0]['options']['num_predict'],128)
    async def test_restart_pauses_unfinished_downloads(self):
        await self.manager.dispatch('model-pull',{'name':'slow:latest'})
        await self.until(lambda:self.manager.active_download is not None)
        await self.manager.close()
        self.manager=ModelManager(self.runtime,self.store,lambda *_:None)
        self.assertEqual(self.manager.downloads[0]['state'],'paused')
        self.assertIsNone(self.manager.download_task)
    async def test_unscorable_benchmark_is_not_saved(self):
        from unittest.mock import patch
        async def no_metrics(*args): yield dict(done=True,message={'content':'hello'})
        await self.manager.dispatch('models')
        with patch('wixal.model_manager.stream_json',no_metrics):
            await self.manager.dispatch('benchmark-start',{'name':'small:latest'})
            await self.until(lambda:not self.manager.busy)
        self.assertEqual(self.manager.benchmarks,[])
        self.assertTrue(any(k=='error' and 'cannot be scored' in v['message'] for k,v in self.events))
    def test_memory_budget_and_context(self):
        device=dict(totalMemory=16*1024**3,memoryBudget=12*1024**3)
        self.assertFalse(estimate(dict(size=15*1024**3,contextLength=32768),device,8192)['fits'])
        self.assertLessEqual(safe_context(dict(size=1*1024**3,contextLength=8192),device,32768),8192)

if __name__=='__main__': unittest.main()
