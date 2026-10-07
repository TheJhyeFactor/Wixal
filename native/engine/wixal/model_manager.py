"""Native model library, resumable transfer queue and engine-reported benchmarks."""
import asyncio
import copy
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from .runtime import request_json, stream_json
from .storage import identity, now

GIB = 1024**3
METHODS = frozenset(('models','model-status','model-imports','model-import','model-pull','model-download-action',
    'model-delete','model-unload','model-use','model-context','runtime-start','runtime-stop','benchmark-start','benchmark-cancel'))


def validate_name(name):
    if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._/:+\-]{0,199}',name):
        raise ValueError('Enter a valid local model tag, for example qwen3:4b')
    if re.search(r'(?:^|[:.\-])cloud(?:$|[:.\-])',name,re.I):
        raise ValueError('Cloud-only models cannot be downloaded to this Mac')
    return name


def hardware():
    total = os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
    cpu=platform.processor() or platform.machine()
    if platform.system()=='Darwin':
        try: cpu=subprocess.check_output(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],timeout=3,text=True).strip()
        except (OSError,subprocess.SubprocessError): pass
    return dict(cpu=cpu,arch=platform.machine(),cores=os.cpu_count() or 1,totalMemory=total,
                memoryBudget=int(total*.75),id=hashlib.sha256(f'{cpu}:{platform.machine()}:{total}'.encode()).hexdigest()[:16])


def estimate(model,device,context,cache_bytes=1):
    context=min(context,model.get('contextLength') or context)
    per_token=(model.get('kvBytesPerToken') or 0)*cache_bytes or 128*1024
    required=math.ceil((model.get('size') or 0)*1.15+context*per_token+GIB)
    return dict(required=required,context=context,fits=bool(model.get('size')) and required<=device['memoryBudget'],estimated=True)


def safe_context(model,device,requested=8192,cache_bytes=1):
    cap=16384 if device['totalMemory']<24*GIB else 32768
    room=device['memoryBudget']-(model.get('size') or 0)*1.15-GIB
    if model.get('size'):
        cap=min(cap,max(2048,int(room/((model.get('kvBytesPerToken') or 0)*cache_bytes or 128*1024)))) if room>0 else min(cap,4096)
    return max(512,min(requested,model.get('contextLength') or 8192,cap))


class ModelManager:
    def __init__(self,runtime,store,emit,idle=lambda:None):
        self.runtime,self.store,self.emit,self.idle=runtime,store,emit,idle
        self.device=hardware()
        self.installed=[]
        self.importing=''
        self.library=dict(loaded=[],loadedAvailable=False,diskFree=shutil.disk_usage(runtime.models).free)
        self.catalog=json.loads((Path(__file__).parent/'resources/model-catalog.json').read_text())
        self.download_task,self.benchmark_task=None,None
        self.active_download,self.benchmark_progress=None,None
        self.closed=False
        self.store.data.setdefault('modelDownloads',[])
        self.store.data.setdefault('modelBenchmarks',[])
        for item in self.downloads:
            if item['state'] in ('queued','downloading'):
                item.update(state='paused',status='Interrupted by restart. Resume when ready.',rate=0,eta=None)
        self.store.data['modelDownloads']=self.downloads[-30:]
        self.store.save()

    @staticmethod
    def handles(method): return method in METHODS
    @property
    def downloads(self): return self.store.data['modelDownloads']
    @property
    def benchmarks(self): return self.store.data['modelBenchmarks']
    @property
    def busy(self): return bool(self.importing or self.benchmark_task and not self.benchmark_task.done())
    @property
    def downloading(self): return self.active_download is not None
    def require_idle(self):
        self.idle()
        if self.busy: raise ValueError('Finish importing or stop the benchmark first')

    def snapshot(self):
        context=self.store.data.get('contextSize',8192)
        def enriched(item):
            item=copy.deepcopy(item)
            item['fit']=estimate(item,self.device,context,2 if self.runtime.external else 1)
            item['suggestedContext']=next((c for c in (16384,8192,4096) if c<=item.get('contextLength',8192) and estimate(item,self.device,c)['fits']),None)
            return item
        return dict(installed=[enriched(m) for m in self.installed],catalog=[enriched(m) for m in self.catalog['models']],
            catalogChecked=self.catalog.get('checked'),hardware=self.device,library=self.library,downloads=copy.deepcopy(self.downloads),
            benchmarks=copy.deepcopy(self.benchmarks),benchmark=self.benchmark_progress,importing=self.importing,
            runtime=dict(status=self.runtime.status,error=self.runtime.error,mode='external' if self.runtime.external else 'managed',
                         version=json.loads((Path(__file__).parent/'resources/runtime.json').read_text())['version'],
                         library=str(self.runtime.models),endpoint=self.runtime.url or ''))

    def publish(self,save=False):
        if save: self.store.save()
        self.emit('model-manager',self.snapshot())
    def changed(self):
        self.store.save();self.emit('state',self.store.data);self.publish()

    async def refresh(self):
        try:
            self.installed=await self.runtime.catalog()
            url=await self.runtime.endpoint()
            try:
                self.library['loaded']=(await asyncio.to_thread(request_json,url+'/api/ps',None,5)).get('models',[])
                self.library['loadedAvailable']=True
            except (OSError,ValueError): self.library['loadedAvailable']=False
            self.library['diskFree']=shutil.disk_usage(self.runtime.models).free
        except Exception as error:
            self.runtime.update_status('failed',str(error));self.publish();raise
        self.publish()
        return self.snapshot()['installed']

    async def dispatch(self,method,params=None):
        p=params or {}
        if method=='models': return await self.refresh()
        if method=='model-status':
            if p.get('refresh'): await self.refresh()
            return self.snapshot()
        if method=='model-imports': return await asyncio.to_thread(self.runtime.imports)
        if method=='benchmark-cancel':
            if self.benchmark_task:
                self.benchmark_task.cancel();await asyncio.gather(self.benchmark_task,return_exceptions=True)
            return self.snapshot()
        if method=='model-download-action':
            await self.download_action(p['id'],p['action'])
            return self.snapshot()
        self.require_idle()
        if method=='model-pull':
            name=validate_name(p.get('name','').strip())
            if any(v['name']==name and v['state'] in ('queued','downloading') for v in self.downloads):
                raise ValueError('This model is already in the download queue')
            if len([v for v in self.downloads if v['state'] in ('queued','downloading','paused','failed')])>=12:
                raise ValueError('Finish or remove a download before adding more')
            self.store.data['modelDownloads']=[v for v in self.downloads if v['state'] not in ('completed','cancelled')]+[v for v in self.downloads if v['state'] in ('completed','cancelled')][-17:]
            self.downloads.append(dict(id=identity(),name=name,state='queued',status='Queued',created=now(),completed=0,total=0,rate=0,eta=None))
            self.publish(True);self.pump();return self.snapshot()
        if method=='runtime-start': await self.runtime.endpoint();await self.refresh()
        elif method=='runtime-stop':
            if self.downloading: raise ValueError('Pause the active download first')
            await self.runtime.stop();self.library.update(loaded=[],loadedAvailable=True)
        elif method=='model-import':
            self.importing=p.get('name','model');self.publish()
            import threading
            cancelled=threading.Event()
            worker=asyncio.create_task(asyncio.to_thread(self.runtime.import_model,p,cancelled))
            try:
                name=await asyncio.shield(worker)
                await self.refresh()
                if "completion" in next((m for m in self.installed if m["name"]==name),{}).get("capabilities",[]):self.use(name)
            except asyncio.CancelledError:
                cancelled.set()
                await asyncio.gather(worker,return_exceptions=True)
                raise
            finally: self.importing='';self.publish()
            return self.snapshot()['installed']
        elif method=='model-use':
            name=validate_name(p.get('name',''))
            if not self.installed: await self.refresh()
            self.use(name)
        elif method=='model-context':
            requested=p.get('contextSize')
            if type(requested)!=int or requested not in (4096,8192,16384,32768): raise ValueError('Choose a supported context window')
            model=next((m for m in self.installed if m['name']==self.store.data.get('model')),None)
            if model and requested>model.get('contextLength',8192): raise ValueError('This model does not support that context window')
            self.store.data['contextSize']=requested;self.changed()
        elif method=='model-delete':
            if self.downloading: raise ValueError('Pause the download before deleting a model')
            name=validate_name(p.get('name',''))
            if not self.installed: await self.refresh()
            if not any(m['name']==name for m in self.installed): raise ValueError('Choose an installed model')
            url=await self.runtime.endpoint()
            await asyncio.to_thread(request_json,url+'/api/delete',dict(model=name),15,'DELETE')
            self.runtime.metadata.clear();await self.refresh()
            if self.store.data.get('model')==name: self.store.data['model']='';self.changed()
        elif method=='model-unload':
            url=await self.runtime.endpoint()
            names=[validate_name(p['name'])] if p.get('name') else [m.get('name',m.get('model')) for m in self.library.get('loaded',[])]
            for name in names:
                await asyncio.to_thread(request_json,url+'/api/generate',dict(model=validate_name(name),keep_alive=0,stream=False),15)
            await self.refresh()
        elif method=='benchmark-start':
            if self.downloading: raise ValueError('Pause the download before benchmarking')
            name=validate_name(p.get('name',''))
            if not self.installed: await self.refresh()
            model=next((m for m in self.installed if m['name']==name),None)
            if not model: raise ValueError('Choose an installed model to benchmark')
            if 'completion' not in model.get('capabilities',[]):raise ValueError('Conversation benchmarks require a chat model; embedding work is measured in Memory retrieval.')
            self.benchmark_progress=dict(name=name,phase='Preparing benchmark',sample=0)
            self.benchmark_task=asyncio.create_task(self.benchmark(model));self.publish()
        else:
            if method not in METHODS: raise ValueError('Unknown model operation')
        self.publish()
        return self.snapshot()

    def use(self,name):
        model=next((m for m in self.installed if m['name']==name),None)
        if not model: raise ValueError('Refresh the library before selecting this model')
        if 'completion' not in model.get('capabilities',[]):raise ValueError('This is an embedding model. Select it in Memory retrieval instead of chat.')
        requested=min(16384,self.store.data.get('contextSize',8192))
        context=safe_context(model,self.device,requested,2 if self.runtime.external else 1)
        # Standard controls are discrete. Never round upwards beyond the model limit.
        context=next((c for c in (32768,16384,8192,4096) if c<=context),context)
        self.store.data.update(model=name,contextSize=context)
        self.changed()

    def pump(self):
        if self.closed or self.download_task and not self.download_task.done(): return
        item=next((v for v in self.downloads if v['state']=='queued'),None)
        if item and not self.busy: self.download_task=asyncio.create_task(self.transfer(item))

    async def download_action(self,item_id,action):
        item=next((v for v in self.downloads if v['id']==item_id),None)
        if not item: raise ValueError('Unknown download')
        state=item['state']
        if action in ('resume','retry'):
            self.require_idle()
            if state not in ('paused','failed','cancelled'): raise ValueError('This download cannot be resumed')
            if any(v is not item and v['name']==item['name'] and v['state'] in ('queued','downloading') for v in self.downloads): raise ValueError('This model is already in the queue')
            item.update(state='queued',status='Queued to resume',error='',rate=0,eta=None)
        elif action in ('pause','cancel'):
            if state not in ('queued','downloading','paused','failed'): raise ValueError('This download has already finished')
            item.update(state='paused' if action=='pause' else 'cancelled',status='Paused · resume to continue' if action=='pause' else 'Cancelled',rate=0,eta=None)
            if item is self.active_download and self.download_task:
                self.download_task.cancel();await asyncio.gather(self.download_task,return_exceptions=True)
        elif action=='remove':
            if state in ('queued','downloading'): raise ValueError('Cancel the download first')
            self.store.data['modelDownloads']=[v for v in self.downloads if v is not item]
        else: raise ValueError('Unknown download action')
        self.publish(True);self.pump()

    async def transfer(self,item):
        self.active_download=item
        item.update(state='downloading',status='Starting download',rate=0,eta=None)
        self.publish(True)
        layers,last_bytes,last_rate,last_publish={},None,time.monotonic(),0
        previous_status=''
        try:
            endpoint=await self.runtime.endpoint()
            success=False
            async for progress in stream_json(endpoint,'/api/pull',dict(model=item['name'],stream=True)):
                timestamp=time.monotonic()
                if progress.get('digest') and progress.get('total'):
                    layers[progress['digest']]=dict(total=progress['total'],completed=min(progress['total'],progress.get('completed',0)))
                item['total']=sum(v['total'] for v in layers.values()) if layers else progress.get('total') or item['total']
                item['completed']=sum(v['completed'] for v in layers.values()) if layers else progress.get('completed') or item['completed']
                item['status']=progress.get('status','Downloading')
                if last_bytes is None: last_bytes=item['completed'];last_rate=timestamp
                if timestamp-last_rate>=.5:
                    item['rate']=max(0,(item['completed']-last_bytes)/(timestamp-last_rate));last_bytes=item['completed'];last_rate=timestamp
                item['eta']=math.ceil((item['total']-item['completed'])/item['rate']) if item['rate']>0 and item['total']>item['completed'] else None
                if timestamp-last_publish>=.2 or item['status']!=previous_status:
                    self.publish();last_publish=timestamp;previous_status=item['status']
                if progress.get('status')=='success': success=True
            if not success: raise RuntimeError('Download ended before completion. Retry to resume')
            item['status']='Verifying installation';self.publish()
            self.runtime.metadata.clear();await self.refresh()
            if not any(m['name']==item['name'] or m['name']==item['name']+':latest' for m in self.installed):
                raise RuntimeError('The engine did not report the downloaded model in its library')
            item.update(state='completed',status='Installed',completed=item['total'],finished=now())
        except asyncio.CancelledError:
            if item['state']=='downloading': item.update(state='paused',status='Paused when Wixal closed')
            raise
        except Exception as error: item.update(state='failed',status='Download failed',error=str(error)[:800])
        finally:
            item.update(rate=0,eta=None);self.active_download=None;self.download_task=None
            self.publish(True);self.pump()

    async def benchmark(self,model):
        context=min(self.store.data.get('contextSize',8192),model.get('contextLength',8192))
        samples=[]
        name=model['name']
        try:
            endpoint=await self.runtime.endpoint()
            async with asyncio.timeout(180):
                for sample in (1,2):
                    self.benchmark_progress=dict(name=name,phase='Loading and generating' if sample==1 else 'Warm run · measuring generation speed',sample=sample,chunks=0)
                    self.publish()
                    body=dict(model=name,stream=True,messages=[dict(role='user',content='Count upwards from 1 to 200. Write each number and its English word on a separate line. Continue until you reach 200.')],
                              options=dict(num_ctx=context,num_predict=128,temperature=0,seed=42))
                    if 'thinking' in model.get('capabilities',[]):
                        values=(model.get('thinking') or {}).get('values',[])
                        body['think']=False if False in values else 'low' if 'low' in values or model.get('details',{}).get('family')=='gptoss' else False
                    started=time.monotonic();first=None;final=None;last=0
                    async for row in stream_json(endpoint,'/api/chat',body):
                        if row.get('message',{}).get('content') or row.get('message',{}).get('thinking'):
                            if first is None: first=time.monotonic()-started
                            self.benchmark_progress['chunks']+=1
                            if time.monotonic()-last>.25: self.publish();last=time.monotonic()
                        if row.get('done'): final=row
                    if not final or not final.get('eval_count') or not final.get('eval_duration'):
                        raise RuntimeError('The engine reported no generated tokens; this run cannot be scored')
                    tokens=int(final['eval_count']);duration=float(final['eval_duration'])/1e9
                    samples.append(dict(tokens=tokens,tokensPerSecond=round(tokens/duration,2),timeToFirstToken=first,
                                        duration=float(final.get('total_duration',0))/1e9,inputTokens=final.get('prompt_eval_count')))
                version=(await asyncio.to_thread(request_json,endpoint+'/api/version',None,5)).get('version','unknown')
                loaded=(await asyncio.to_thread(request_json,endpoint+'/api/ps',None,5)).get('models',[])
                loaded=next((m for m in loaded if m.get('name',m.get('model'))==name),{})
                result=dict(id=identity(),name=name,digest=model.get('digest'),hardwareId=self.device['id'],context=context,created=now(),status='completed',
                            engineVersion=version,samples=samples,tokensPerSecond=samples[1]['tokensPerSecond'],timeToFirstToken=samples[0]['timeToFirstToken'],
                            loadedBytes=loaded.get('size'),gpuBytes=loaded.get('size_vram'),totalTokens=sum(v['tokens'] for v in samples),
                            mode='external' if self.runtime.external else 'managed',fixture=version=='fixture')
                self.store.data['modelBenchmarks']=[v for v in self.benchmarks if (v.get('name'),v.get('hardwareId'),v.get('mode'))!=(name,self.device['id'],result['mode'])][-199:]+[result]
                self.changed()
        except asyncio.CancelledError: pass
        except Exception as error: self.emit('error',dict(message='Benchmark failed: '+str(error)[:800]))
        finally:
            self.benchmark_progress=None;self.benchmark_task=None;self.publish(True);self.pump()

    async def close(self):
        self.closed=True
        for item in self.downloads:
            if item['state'] in ('queued','downloading'): item.update(state='paused',status='Paused when Wixal closed',rate=0,eta=None)
        tasks=[t for t in (self.download_task,self.benchmark_task) if t]
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        self.store.save()
