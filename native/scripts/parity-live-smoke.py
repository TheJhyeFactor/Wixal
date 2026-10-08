"""Real local model/image/benchmark and loopback Nmap checks in disposable storage."""
import asyncio, base64, json, os, struct, tempfile, time, zlib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
app=root/'release/native/Wixal.app'
artifact=root/'artifacts/native/parity-live.json'

def red_image():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',256,256,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\0\0'*256)*256))+chunk(b'IEND',b'')

async def main():
    with tempfile.TemporaryDirectory(prefix='wixal-real-parity-') as directory:
        project=Path(directory)/'project';project.mkdir()
        child=await asyncio.create_subprocess_exec(str(app/'Contents/Resources/engine/wixal-engine'),'--data',str(Path(directory)/'data'),'--runtime',str(app/'Contents/Resources/ollama'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=16*1024*1024)
        counter=0;events=[];report={'scope':'Packaged Python helper + bundled real Ollama; disposable workspace. No account or external target used.'}
        async def call(method,params=None):
            nonlocal counter
            counter+=1;identifier=str(counter);child.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await child.stdin.drain()
            while line:=await asyncio.wait_for(child.stdout.readline(),300):
                message=json.loads(line)
                if message['event']=='response' and message['data']['id']==identifier:
                    if message['data'].get('error'):raise RuntimeError(message['data']['error'])
                    return message['data']['result']
                if message['event'] in ('error','model-manager'):events.append(message)
            raise RuntimeError('Helper disconnected')
        try:
            await call('hello');await call('project-add',dict(root=str(project)))
            imports=await call('model-imports');choice=next(i for i in imports if i['name']=='gemma3:12b')
            started=time.monotonic();models=await call('model-import',choice)
            model=next(m for m in models if m['name']=='gemma3:12b');report['importSeconds']=round(time.monotonic()-started,2);report['model']=dict(name=model['name'],capabilities=model['capabilities'])
            print('Verified model imported',flush=True)
            await call('settings',dict(model=model['name'],contextSize=4096,mode='chat',approvalMode='review'))
            task=await call('chat',dict(text='What is the single dominant colour in this image? Answer with one word.',attachments=[dict(type='image',name='red-square.png',base64=base64.b64encode(red_image()).decode())]))
            hello=await call('hello');session=next(s for s in hello['state']['sessions'] if s['id']==hello['state']['activeSession']);reply=next(m for m in reversed(session['messages']) if m['role']=='assistant')
            assert task['status']=='completed' and 'red' in reply['content'].lower(),reply
            report['realImageResponse']=dict(content=reply['content'],usage=reply.get('usage'));print('Real image inference passed',flush=True)
            await call('benchmark-start',dict(name=model['name']))
            for _ in range(180):
                status=await call('model-status')
                if status.get('benchmarks'):break
                await asyncio.sleep(1)
            else:raise RuntimeError('Real benchmark did not complete: '+json.dumps(events[-2:]))
            report['benchmark']=status['benchmarks'][-1];assert not report['benchmark']['fixture'];print('Real model benchmark passed',flush=True)
            # Explicitly confined to a disposable loopback listener.
            server=await asyncio.start_server(lambda r,w:w.close(),'127.0.0.1',0)
            port=server.sockets[0].getsockname()[1]
            await call('settings',dict(approvalMode='bypass'))
            try:
                result=await call('assessment-run',dict(name='network_scan',arguments=dict(target='127.0.0.1',profile='ports',ports=str(port),timeout_seconds=30)))
                assert str(port) in result.get('output',''),result
                report['nmap']=dict(status='passed',target='127.0.0.1',port=port,exitCode=result.get('exitCode'));print('Real loopback Nmap passed',flush=True)
            finally:server.close();await server.wait_closed()
            # A long real conversation with deterministic supplied history, followed by model summary and handoff.
            await call('settings',dict(approvalMode='review'))
            task=await call('chat',dict(text='Summarise this synthetic project note in one sentence: '+('The project uses a blue theme and local files. Tests must preserve the original source. '*180)))
            assert task['status']=='completed'
            handoff=await call('session-handoff')
            assert handoff['summary']['content'] and handoff['handoff']['sourceSession']==session['id']
            report['longConversation']=dict(status='passed',summaryMethod=handoff['summary']['method'],summaryCharacters=len(handoff['summary']['content']))
            report['status']='passed'
        except Exception as error:
            report['status']='failed';report['error']=str(error);raise
        finally:
            artifact.write_text(json.dumps(report,indent=2));child.stdin.close()
            try:await asyncio.wait_for(child.wait(),30)
            except asyncio.TimeoutError:child.kill();await child.wait()
        print('PACKAGED_REAL_PARITY_OK',flush=True)
asyncio.run(main())
