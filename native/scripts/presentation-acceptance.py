"""Generate an actual local-model response for installed Markdown/scroll inspection.

--finish restores the original workspace and archives only the validation chat.
No model responses are fabricated or inserted into storage.
"""
import argparse
import asyncio
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ARTIFACT=ROOT/'artifacts/native/presentation-acceptance.json'


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--finish',action='store_true');options=parser.parse_args()
    reader,writer=await asyncio.open_unix_connection(Path.home()/'Library/Application Support/Wixal Native/engine.sock',limit=16*1024*1024)
    counter=0
    async def call(method,params=None):
        nonlocal counter
        counter+=1;identifier=f'presentation-check-{counter}'
        writer.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await writer.drain()
        while row:=await asyncio.wait_for(reader.readline(),180):
            message=json.loads(row)
            if message['event']=='response' and message['data']['id']==identifier:
                data=message['data']
                if data.get('error'):raise RuntimeError(data['error'])
                return data['result']
        raise RuntimeError('Helper disconnected')
    async def restore(report):
        await call('stop')
        backup=report['workspace']
        await call('settings',dict(mode=backup['mode']))
        await call('project-select',dict(id=backup['projectId']))
        if backup['sessionId']:await call('session-select',dict(id=backup['sessionId']))
        if report.get('validationSession'):await call('session-archive',dict(id=report['validationSession']))
        report['workspaceRestored']=True
        ARTIFACT.write_text(json.dumps(report,indent=2))
    try:
        if options.finish:
            report=json.loads(ARTIFACT.read_text());await restore(report)
            print(json.dumps(dict(status=report['status'],workspaceRestored=True)));return
        state=(await call('hello'))['state']
        report=dict(status='running',implementation='installed real local-model response',workspace=dict(projectId=state.get('activeProject'),sessionId=state.get('activeSession'),mode=state.get('mode','agent')))
        ARTIFACT.write_text(json.dumps(report,indent=2))
        try:
            await call('project-select',dict(id=None));await call('session-new')
            report['validationSession']=(await call('hello'))['state']['activeSession']
            ARTIFACT.write_text(json.dumps(report,indent=2))
            await call('settings',dict(mode='chat'))
            result=await call('chat',dict(text='Create a Markdown rendering reference about organising a reading list. Do not use tools. Include a setext heading, a three-level nested bullet list, two task checkbox items, a quote containing a short paragraph and a fenced Swift code block, an ordinary fenced Python code block, a reference-style link to https://docs.python.org/3/, and a table with 45 numbered rows and 3 columns. Put bold words and inline code in table cells; left-align the first column and right-align the third. End with six substantial paragraphs of practical advice. Return only the requested Markdown.'))
            state=(await call('hello'))['state']
            session=next(s for s in state['sessions'] if s['id']==report['validationSession'])
            response=next(m['content'] for m in reversed(session['messages']) if m['role']=='assistant' and m.get('content'))
            assert result['status']=='completed' and len(response)>2000 and response.count('|')>75 and '```' in response
            report.update(status='ready-for-visual-check',responseCharacters=len(response),tablePipeCount=response.count('|'))
            (ROOT/'artifacts/native/presentation-response.md').write_text(response)
            ARTIFACT.write_text(json.dumps(report,indent=2))
            print(json.dumps(dict(status=report['status'],responseCharacters=len(response))))
        except BaseException:
            report['status']='failed';await restore(report);raise
    finally:
        writer.close();await writer.wait_closed()


if __name__=='__main__':asyncio.run(main())
