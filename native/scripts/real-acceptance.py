"""Repeatable real-world native acceptance. No mocks, fabricated responses or inserted history.

Cases use this repository's actual files/decisions, actual Ollama downloads and
model requests through production JSON IPC. Independent expected facts come from
source documents; reports retain inputs, observed outputs, counters and hashes.
Separate storage and cached real weights protect the user's working workspace.
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'artifacts/native/real-acceptance'
STATE=ART/'workspace'

class Client:
    def __init__(self,source,helper=None,payload=None):
        self.helper=helper or ROOT/'release/native/Wixal Native.app/Contents/Resources/engine/wixal-engine'
        self.payload=payload or ROOT/'runtime/ollama'
        self.source=source;self.pending={};self.counter=0;self.events=[];self.reviews=[];self.allowed={'read_file','run_command','command_start','command_read','save_memory','forget_memory'}
    async def start(self):
        command=[sys.executable,str(ROOT/'native/engine/engine_main.py')] if self.source else [str(self.helper)]
        self.log=(ART/('source-helper.log' if self.source else 'packaged-helper.log')).open('a')
        self.child=await asyncio.create_subprocess_exec(*command,'--data',str(STATE),'--runtime',str(self.payload),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=self.log,limit=32*1024*1024)
        self.reading=asyncio.create_task(self.read())
        await self.call('hello')
    async def read(self):
        try:
            while line:=await self.child.stdout.readline():
                item=json.loads(line);event=item['event'];data=item['data']
                if event=='response':
                    future=self.pending.pop(data['id'],None)
                    if future and not future.done():future.set_result(data)
                elif event=='review':
                    approved=data.get('name') in self.allowed
                    self.reviews.append(dict(name=data.get('name'),approved=approved,details={k:v for k,v in data.items() if k not in ('id','before')}))
                    self.send('respond',dict(id=data['id'],value=approved))
                elif event in ('error','activity','token','assistant-start'):self.events.append(item)
        finally:
            for future in self.pending.values():
                if not future.done():future.set_exception(RuntimeError('Production helper disconnected'))
    def send(self,method,params=None):
        self.counter+=1;key=str(self.counter)
        future=asyncio.get_running_loop().create_future();self.pending[key]=future
        self.child.stdin.write((json.dumps(dict(id=key,method=method,params=params or {}))+'\n').encode())
        return future
    async def call(self,method,params=None,timeout=900):
        future=self.send(method,params);await self.child.stdin.drain()
        result=await asyncio.wait_for(asyncio.shield(future),timeout)
        if result.get('error'):raise RuntimeError(result['error'])
        return result['result']
    async def state(self):return (await self.call('hello'))['state']
    async def session(self):
        state=await self.state();return next(s for s in state['sessions'] if s['id']==state['activeSession'])
    async def chat(self,prompt):
        outcome=await self.call('chat',dict(text=prompt))
        session=await self.session()
        assert outcome['status']=='completed',outcome
        answers=[m for m in session['messages'] if m['role']=='assistant' and m.get('content')]
        answer=answers[-1]
        assert answer.get('usage',{}).get('eval_count',0)>0,'Response has no actual runner counters'
        usage=answer['usage']
        assert usage.get('prompt_eval_count',0)+usage['eval_count']<=session['requests'][-1]['context'],dict(usage=usage,request=session['requests'][-1])
        for request in session.get('requests',[]):
            assert request['estimatedInput']+request['outputReserve']<=request['context'],request
        return dict(prompt=prompt,answer=answer['content'],usage=answer['usage'],requests=session.get('requests',[]),memorySources=session.get('memorySources',[]),sessionId=session['id'],toolResults=[m for m in session['messages'] if m['role']=='tool'])
    async def model(self,name):
        models=await self.call('models')
        if not any(m['name']==name for m in models):
            existing=next((d for d in (await self.call('model-status'))['downloads'] if d['name']==name and d['state'] in ('paused','failed','downloading','queued')),None)
            if existing and existing['state'] in ('paused','failed'):await self.call('model-download-action',dict(id=existing['id'],action='resume' if existing['state']=='paused' else 'retry'))
            elif not existing:await self.call('model-pull',dict(name=name))
            last=None;started=time.monotonic()
            while time.monotonic()-started<2400:
                status=await self.call('model-status');row=next(d for d in status['downloads'] if d['name']==name)
                if row['state']=='completed':break
                if row['state'] in ('failed','cancelled','paused'):raise RuntimeError('Real model download did not complete: '+json.dumps(row))
                progress=int(row.get('completed',0)/max(1,row.get('total',0))*100)
                if progress!=last and progress%10==0:print(f'{name}: real registry download {progress}%',flush=True);last=progress
                await asyncio.sleep(2)
            else:raise TimeoutError('Real registry download exceeded 40 minutes')
        await self.call('model-use',dict(name=name))
        await self.call('settings',dict(contextSize=4096,mode='chat',autoSummary=True,approvalMode='review'))
        model=next(m for m in await self.call('models') if m['name']==name)
        if 'thinking' in model.get('capabilities',[]) and False not in (model.get('thinking') or {}).get('values',[False]):await self.call('settings',dict(contextSize=8192))
        return {k:model.get(k) for k in ('name','digest','size','capabilities','contextLength')}
    async def close(self):
        if self.child.returncode is None:
            self.child.stdin.close()
            try:await asyncio.wait_for(self.child.wait(),40)
            except TimeoutError:self.child.terminate();await self.child.wait()
        await self.reading;self.log.close()

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',action='store_true');parser.add_argument('--model',default='qwen3:1.7b');parser.add_argument('--plain-model',default='gemma3:1b');options=parser.parse_args()
    ART.mkdir(parents=True,exist_ok=True)
    report_path=ART/('source.json' if options.source else 'packaged.json')
    helper=ROOT/'release/native/Wixal Native.app/Contents/Resources/engine/wixal-engine'
    report=dict(status='running',helperSHA256=hashlib.sha256(helper.read_bytes()).hexdigest() if not options.source else None,implementation='source' if options.source else 'packaged',started=time.time(),cases={},sources={})
    for relative in ('native/README.md','native/Package.swift','native/engine/wixal/agent.py','native/engine/wixal/service.py','package.json'):
        report['sources'][relative]=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    def record(name,observed):
        report['cases'][name]=dict(status='passed',observed=observed)
        report_path.write_text(json.dumps(report,indent=2));print(name+': PASSED',flush=True)
    client=Client(options.source)
    try:
        await client.start()
        await client.call('project-add',dict(root=str(ROOT),memoryMode='project',memorySize=24000))
        await client.call('memory-settings',dict(mode='project',size=24000))
        # These are real product requirements supplied by the user, with source-backed facts.
        schedule='With background scheduling disabled, native Wixal schedules run only while the desktop engine is open; they do not execute with the app closed.'
        assert 'With background scheduling disabled' in (ROOT/'native/README.md').read_text()
        # Previous runs are cleaned through production forget/dismiss APIs, never edited on disk.
        status=await client.call('memory-status')
        for note in status['notes']:
            if 'native wixal schedules' in note['content'].lower() or 'native scheduled tasks' in note['content'].lower():await client.call('memory-forget',dict(id=note['id']))
        for suggestion in status['suggestions']:
            if 'schedule' in suggestion['content'].lower():await client.call('memory-suggestion',dict(id=suggestion['id'],accept=False))
        # This actual installed tag is thinking-only on the current registry. Its
        # low-context exhaustion must fail visibly rather than complete an empty chat.
        catalog=await client.call('models')
        thinking_only=next((m for m in catalog if (m.get('thinking') or {}).get('values')==[True]),None)
        if thinking_only:
            await client.model(thinking_only['name']);await client.call('session-new')
            try:
                await client.call('chat',dict(text='Briefly describe how you can help with Wixal. Give a visible answer.'))
            except RuntimeError as error:
                assert 'without a visible answer' in str(error),error
                session=await client.session()
                assert any(m.get('usage',{}).get('eval_count',0)>0 for m in session['messages']),session
                record('realThinkingOnlyExhaustionIsVisible',dict(model=thinking_only['name'],error=str(error),requests=session['requests']))
            else:
                session=await client.session()
                assert any(m['role']=='assistant' and m.get('content','').strip() for m in session['messages']),session
                response=next(m for m in reversed(session['messages']) if m['role']=='assistant' and m.get('content','').strip())
                record('realThinkingOnlyModelProducesAnswer',dict(model=thinking_only['name'],sessionId=session['id'],answer=response['content'],usage=response['usage'],requests=session['requests']))
        tool_model=await client.model(options.model)
        assert 'tools' in tool_model['capabilities'],'Chosen small model must support real tool calls'
        await client.call('session-new')
        greeting=await client.chat('Explain briefly how you can help with this Wixal project. Do not inspect files yet.')
        request=greeting['requests'][0]
        assert len(request['tools'])<10 and request['estimatedInput']<2048,request
        record('smallModelRequestBudget',dict(model=tool_model,requests=greeting['requests'],usage=greeting['usage']))
        await client.call('session-new')
        saved=await client.chat('Remember that '+schedule+' This is a durable product limitation documented in native/README.md. Save it as project memory. Do not save it globally or inspect unrelated files.')
        status=await client.call('memory-status')
        notes=[n for n in status['notes'] if 'schedule' in n['content'].lower()]
        if not notes:
            candidates=[s for s in status['suggestions'] if 'schedule' in s['content'].lower() and s.get('sourceSession')==saved['sessionId']]
            assert candidates,'Neither real model save nor a reviewable human-source suggestion was produced'
            await client.call('memory-suggestion',dict(id=candidates[-1]['id'],accept=True))
            notes=[n for n in (await client.call('memory-status'))['notes'] if 'schedule' in n['content'].lower()]
        assert notes and notes[-1].get('sourceSession')==saved['sessionId'],notes
        note=notes[-1]
        record('reviewedProjectSave',dict(turn=saved,note=note,reviews=client.reviews))
        await client.call('session-new')
        recalled=await client.chat('When do the native schedules run, and will a scheduled task run after I quit the application? Answer from project memory, without reading files.')
        assert any(s['id']==note['id'] for s in recalled['memorySources']),recalled
        assert re.search(r'open|running',recalled['answer'],re.I) and re.search(r'not|no|cannot|won.t',recalled['answer'],re.I),recalled
        record('crossConversationMemoryChangesAnswer',recalled)
        await client.close();client=Client(options.source);await client.start()
        assert any(n['id']==note['id'] for n in (await client.call('memory-status'))['notes'])
        await client.call('session-new')
        restarted=await client.chat('Recall the schedule limitation we saved for this project. What happens when Wixal is closed?')
        assert any(s['id']==note['id'] for s in restarted['memorySources']),restarted
        record('restartPersistenceWithRealInference',restarted)
        # Independent real project: the website directory exists and has separate scope.
        await client.call('project-add',dict(root=str(ROOT/'website'),memoryMode='project',memorySize=8000))
        other=await client.call('memory-recall',dict(query='Native Wixal schedules desktop engine closed'))
        assert not any(s['id']==note['id'] or s.get('sourceSession')==saved['sessionId'] for s in other),other
        record('projectIsolation',dict(otherProject=str(ROOT/'website'),results=other))
        await client.call('project-add',dict(root=str(ROOT)))
        await client.call('memory-settings',dict(mode='off',size=24000))
        await client.call('session-new')
        disabled=await client.call('context-info')
        assert disabled['memorySources']==[],disabled
        assert await client.call('memory-recall',dict(query='schedules'))==[]
        await client.call('memory-settings',dict(mode='project',size=24000))
        record('memoryOffExcludesNotesAndHistory',disabled)
        # Correction is to another true source-backed wording, never an invented fact.
        corrected='With background scheduling disabled, native scheduled tasks run only while the desktop engine is open. They do not wake a sleeping Mac.'
        assert 'it does not wake a sleeping Mac' in (ROOT/'native/README.md').read_text()
        await client.call('memory-save',dict(scope='project',id=note['id'],content=corrected))
        correction=await client.call('memory-recall',dict(query='scheduled sleeping Mac missed run'))
        assert any(s['id']==note['id'] and s['content']==corrected for s in correction),correction
        await client.call('memory-forget',dict(id=note['id']))
        forgotten=await client.call('memory-recall',dict(query='schedules desktop engine closed sleeping Mac missed run'))
        assert not any(s['id']==note['id'] or s.get('sourceSession')==saved['sessionId'] for s in forgotten),forgotten
        # A question about a fact can remain searchable; the forgotten fact and
        # assistant answers derived from it must disappear from memory recall.
        questions={recalled['sessionId']:recalled['prompt'],restarted['sessionId']:restarted['prompt']}
        assert all(s['content']==questions[s['sourceSession']] for s in forgotten if s.get('sourceSession') in questions),forgotten
        record('correctionAndForgetExcludeDerivedHistory',dict(corrected=corrected,afterForget=forgotten))
        await client.call('memory-settings',dict(mode='both',size=24000))
        global_text='Wixal should make small lightweight open-source models efficient by using relevant memory only when needed, while retaining complete working features.'
        global_note=await client.call('memory-save',dict(scope='global',content=global_text))
        await client.call('memory-settings',dict(mode='project',size=24000))
        isolated=await client.call('memory-recall',dict(query='small lightweight models efficient memory'))
        assert not any(s['id']==global_note['id'] for s in isolated),isolated
        await client.call('project-select',dict(id=None));await client.call('session-new')
        plain_model=await client.model(options.plain_model)
        assert 'tools' not in plain_model['capabilities'],'Plain-model case must use an actual conversation-only model'
        plain=await client.chat('What is my preference for small lightweight models and memory in Wixal? Use my saved preference, without inventing other preferences.')
        assert any(s['id']==global_note['id'] for s in plain['memorySources']),plain
        assert not any(r['tools'] for r in plain['requests']),plain
        assert 'memory' in plain['answer'].lower() and re.search(r'small|lightweight|efficient',plain['answer'],re.I),plain
        await client.call('settings',dict(globalMemoryEnabled=False));await client.call('session-new')
        global_off=await client.call('context-info');assert global_off['memorySources']==[]
        await client.call('settings',dict(globalMemoryEnabled=True))
        await client.call('memory-forget',dict(id=global_note['id']))
        record('plainSmallModelUsesGlobalMemoryAndHonorsScope',dict(model=plain_model,turn=plain,disabled=global_off))
        await client.call('project-add',dict(root=str(ROOT)))
        await client.model(options.model);await client.call('session-new')
        file_turn=await client.chat('Use @read_file to read native/Package.swift. Report the exact pinned SwiftTerm and swift-markdown versions from the real tool result. Do not guess or edit files.')
        versions=dict(re.findall(r'github.com/([^/]+/[^.]+)\.git", exact: "([^"]+)"',(ROOT/'native/Package.swift').read_text()))
        assert file_turn['toolResults'] and all(value in file_turn['answer'] for value in versions.values()),file_turn
        assert any('SwiftTerm' in m['content'] and '1.20.0' in m['content'] for m in file_turn['toolResults']),file_turn
        record('smallModelExecutesRealFileTool',file_turn)
        continuation=await client.call('session-handoff')
        assert continuation['handoff']['sourceSession']==file_turn['sessionId'] and continuation['summary']['method']=='model',continuation
        continued=await client.chat('From the carried conversation summary alone, report the exact pinned SwiftTerm and swift-markdown versions we just verified. Do not read files or run searches. If the summary omits a version, say it is unknown.')
        assert all(value in continued['answer'] for value in versions.values()),continued
        record('realModelSummaryAndContinuation',dict(summary=continuation['summary'],turn=continued))
        # The actual directory is an invalid read_file target; no fake missing files are made.
        await client.call('session-new')
        error_turn=await client.chat('Test the actual directory/file error path: use @read_file with path native (a directory). Repeat the identical call until the controller tells you to stop, then explain the error. Do not change the path, create files, use commands or try another tool.')
        failures=[m for m in error_turn['toolResults'] if m['tool_name']=='read_file' and 'error' in m['content']]
        assert 1<=len(failures)<=3,error_turn
        if len(failures)==3:assert 'three times' in failures[-1]['content'],error_turn
        record('realDirectoryErrorAndFailureGuard',dict(turn=error_turn,repeatedGuardExercised=len(failures)==3))
        # Real command emits the current production source; saved evidence must retain its tail.
        await client.call('session-new')
        evidence_turn=await client.chat('Use @command_start to run exactly cat native/engine/wixal/agent.py native/engine/wixal/service.py in this project. Then use @command_read with max_chars 100000 and wait_ms 1000; keep polling until completed. The output is over 24000 characters; request the full available output, not the default short chunk. Do not modify files. Finally state whether the command completed and its exit code.')
        large=[m for m in evidence_turn['toolResults'] if len(m['content'])>24000]
        assert large,'The real model did not retrieve full source evidence; acceptance is incomplete'
        expected=(ROOT/'native/engine/wixal/agent.py').read_text()+(ROOT/'native/engine/wixal/service.py').read_text()
        outputs=[json.loads(m['content']) for m in large]
        assert any(o.get('output')==expected for o in outputs),'Saved command evidence differs from actual source bytes'
        record('fullEvidenceSavedWithBoundedInference',dict(turn=evidence_turn,sourceCharacters=len(expected),savedCharacters=max(len(m['content']) for m in large)))
        await client.call('session-new')
        await client.call('draft-save',dict(text='Review the real native/Package.swift dependencies before the next build.',attachments=[dict(type='file',name='Package.swift',path='native/Package.swift',content=(ROOT/'native/Package.swift').read_text())]))
        original=await client.session();await client.call('session-new');await client.call('session-select',dict(id=original['id']))
        restored=await client.session();assert restored['draft']==original['draft']
        record('realFileDraftSurvivesNavigation',dict(sessionId=original['id'],draft=restored['draft']))
        await client.call('session-new')
        start=len(client.events)
        pending=client.send('chat',dict(text='Explain the actual Wixal native architecture and its model-memory policy in detail, including the limits already documented for native schedules, account identity and tools. Give a careful extended explanation; do not call tools or invent capabilities.'))
        await client.child.stdin.drain()
        async with asyncio.timeout(60):
            while not any(e['event']=='token' for e in client.events[start:]):
                assert not pending.done(),'Response ended before the cancellation check could observe actual streamed output'
                await asyncio.sleep(.01)
        await client.call('stop')
        await asyncio.wait_for(pending,15)
        cancelled=await client.state();session=await client.session()
        task=next(t for t in reversed(cancelled['tasks']) if t['sessionId']==session['id'])
        assert task['status']=='paused' and await client.call('ping'),task
        record('realStreamingCancellationLeavesResponsiveEngine',dict(taskStatus=task['status'],streamedCharacters=sum(len(e['data'].get('text','')) for e in client.events[start:] if e['event']=='token'),sessionId=session['id']))
        report['status']='passed'
    except BaseException as error:
        report['status']='failed';report['error']=str(error);raise
    finally:
        report['finished']=time.time();report['reviews']=client.reviews
        report_path.write_text(json.dumps(report,indent=2))
        await client.close()

if __name__=='__main__':asyncio.run(main())
