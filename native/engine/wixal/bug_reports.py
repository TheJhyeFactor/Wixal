"""User-invoked portable bug evidence. No automatic upload or GitHub mutation."""
import hashlib
import json
import os
import platform
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from . import VERSION


def text(params, key, maximum):
    value=params.get(key,'')
    if not isinstance(value,str) or len(value)>maximum:raise ValueError(f'{key} must be below {maximum} characters')
    return value.strip()


def event_rows(diagnostics):
    rows=[]
    diagnostics.handler.flush()
    for index in reversed(range(diagnostics.handler.backupCount+1)):
        path=diagnostics.directory/('engine.jsonl'+(f'.{index}' if index else ''))
        try:
            with path.open() as source:
                for line in source:
                    try:
                        row=json.loads(line)
                        if isinstance(row,dict):rows.append(row)
                    except ValueError:pass
        except FileNotFoundError:pass
    return rows


def export(service, params, health):
    path=Path(text(params,'path',4096)).expanduser().absolute()
    if path.suffix.lower()!='.zip':raise ValueError('Save the bug report as a ZIP file')
    if path.is_symlink():raise ValueError('Choose a regular ZIP file, not a symbolic link')
    include=params.get('includeConversation',False)
    if not isinstance(include,bool):raise ValueError('Choose whether to include the current conversation')
    title=text(params,'title',200) or 'Wixal bug report'
    observed=text(params,'observed',12000) or 'Not supplied. Describe what went wrong.'
    expected=text(params,'expected',12000) or 'Not supplied. Describe the expected result.'
    steps=text(params,'steps',12000) or 'Not supplied. Add the actions leading to the problem.'
    created=datetime.now(timezone.utc).isoformat()
    identifier='wixal-bug-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+os.urandom(3).hex()
    session=service.store.session()
    rows=event_rows(service.diagnostics)
    environment=dict(reportId=identifier,created=created,engineVersion=VERSION,health=health,
                     activeSessionId=(session or {}).get('id'),logEventCount=len(rows),conversationIncluded=include)
    environment['platform']=dict(system=platform.system(),release=platform.release(),architecture=platform.machine())
    # The packaged engine resides beside the manifest in Contents/Resources.
    source=Path(sys.executable).resolve().parent.parent/'SOURCE_MANIFEST.json'
    if source.is_file():environment['sourceManifestSha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    def encoded(value):return json.dumps(value,ensure_ascii=False,indent=2).encode()
    files={'environment.json':encoded(environment),
           'events.jsonl':''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows).encode(),
           'codex-workflow.md':(Path(__file__).parent/'resources/bug-investigation.md').read_bytes()}
    if include and session:
        # Explicit opt-in captures saved visible text and checkpoints; never credentials,
        # attachment bytes, thinking, account data, memory sources or project paths.
        messages=[{k:m[k] for k in ('role','content','displayContent','created','tool_calls','tool_name','toolCallId','usage') if k in m} for m in session.get('messages',[])]
        tasks=[{k:t[k] for k in ('id','sessionId','status','created','updated','turns','error','verification','checkpoints') if k in t} for t in service.store.data.get('tasks',[]) if t.get('sessionId')==session['id']]
        files['conversation.json']=encoded(dict(sessionId=session['id'],messages=messages,tasks=tasks))
    failures=[r for r in rows if r.get('status') in ('failed','error','needs_attention') or r.get('errorCategory')]
    evidence='\n'.join(f"- event={r.get('event')} status={r.get('status','')} category={r.get('errorCategory','')} request={r.get('requestId','')} task={r.get('taskId','')} action={r.get('actionId','')} tool={r.get('tool','')} timestamp={r.get('timestamp')}" for r in failures[-30:]) or 'No failure event was retained. This does not rule out a UI or application bug.'
    report=f'''# {title}

Report ID: {identifier}
Created (UTC): {created}
Repository: https://github.com/TheJhyeFactor/Wixal
Engine version: {VERSION}

## What happened (user report)

{observed}

## Expected behavior (user report)

{expected}

## Steps leading to the problem (user report)

{steps}

## Recorded evidence

{evidence}

## Investigation status

Not yet investigated. No root cause or reproducibility claim has been established by this export. Logs are a bounded snapshot and may not cover the incident. Match task/action/request IDs and boot/sequence IDs in events.jsonl.

## Handoff to Codex

Attach this ZIP or extract it and point Codex at this folder. Ask it to follow codex-workflow.md. Verify manifest.json first. This Markdown file is also a GitHub issue draft; review and remove any private user-entered details before publishing. GitHub publication is a separate action.

## Contents and privacy

This export includes local metadata logs and environment diagnostics. Current conversation/action evidence included: {str(include).lower()}. Optional conversation evidence may contain private text, paths, URLs or secrets supplied in chats and tool results. No account credentials, image bytes or model thinking are intentionally collected. User-entered report text is included verbatim. Review the files before sharing publicly.
'''
    files['report.md']=report.encode()
    if sum(map(len,files.values()))>32*1024*1024:raise ValueError('Bug report exceeds 32 MB; export without conversation details')
    files['manifest.json']=encoded(dict(formatVersion=1,reportId=identifier,files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in files.items()}))
    fd,temporary=tempfile.mkstemp(prefix='.wixal-bug-',suffix='.zip',dir=path.parent)
    try:
        with os.fdopen(fd,'w+b') as stream:
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,data in files.items():archive.writestr(identifier+'/'+name,data)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return dict(path=str(path),reportId=identifier,bytes=path.stat().st_size,eventCount=len(rows),conversationIncluded=include,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


async def dispatch(service,params):
    from .workspace_data import dispatch as workspace_dispatch
    health=await workspace_dispatch(service,'workspace-diagnostics',{})
    # Snapshot saved work on the engine loop; no concurrent mutations while collecting.
    return export(service,params,health)
