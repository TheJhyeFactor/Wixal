"""Real-model Chat acceptance through the packaged helper's production JSON IPC.

Uses actual Wixal source and tool definitions, an isolated workspace, and reviewed
scratch artifacts. It never changes the user's saved workspace or tool preferences.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import uuid
from pathlib import Path


async def main(args):
    app = Path(args.app).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    scratch = output/'project'
    scratch.mkdir(exist_ok=True)
    manifest = repo/'package.json'
    shutil.copy2(manifest, scratch/'package.json')
    project_manifest = json.loads(manifest.read_text())
    expected = dict(name=project_manifest['name'], version=project_manifest['version'], scriptCount=len(project_manifest['scripts']))
    source_checks=[dict(kind='json_matches_source',path='chat-project-report.json',pointer='/'+field,sourcePath='package.json',sourcePointer='/'+source,transform=transform) for field,source,transform in [('name','name','identity'),('version','version','identity'),('scriptCount','scripts','length')]]
    acceptance_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    helper = app/'Contents/Resources/engine/wixal-engine'
    process = await asyncio.create_subprocess_exec(str(helper), '--data', str(output/'data'),
        '--runtime', str(app/'Contents/Resources/ollama'), '--endpoint', args.endpoint,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=32*1024*1024)
    stderr = asyncio.create_task(process.stderr.read())
    events, outcomes = [], []
    allow_writes = False

    async def call(method, params=None):
        identifier = uuid.uuid4().hex
        async def send(method, params, identifier):
            process.stdin.write((json.dumps(dict(id=identifier, method=method, params=params))+'\n').encode())
            await process.stdin.drain()
        await send(method, params or {}, identifier)
        while True:
            raw = await asyncio.wait_for(process.stdout.readline(), 360)
            if not raw:
                raise RuntimeError('Packaged helper ended before responding')
            event = json.loads(raw)
            events.append(event)
            if event['event']=='review':
                details = event['data'].get('details', event['data'])
                approved = allow_writes and details.get('name') in ('write_file', 'command_start')
                await send('respond', dict(id=event['data']['id'], value=approved), uuid.uuid4().hex)
            if event['event']=='response' and event['data']['id']==identifier:
                if 'error' in event['data']:
                    raise RuntimeError(event['data']['error'])
                return event['data']['result']

    try:
        await call('project-add', dict(root=str(repo)))
        await call('settings', dict(model=args.model, mode='chat', enabledTools=[]))
        task = await call('chat', dict(text='Read native/engine/wixal/agent_context.py. Explain how Chat now discovers tools and what still limits a saved Read only agent. Quote the exact chat mode value and READ_TOOLS identifier from the actual file. Do not modify anything.'))
        outcomes.append(dict(name='chat-automatic-source-inspection', passed=task['status']=='completed'
            and 'READ_TOOLS' in task.get('result','') and 'chat' in task.get('result','')
            and any(c['name']=='read_file' and c['status']=='finished' for c in task['checkpoints']), task=task))
        print(json.dumps(dict(name=outcomes[-1]['name'], passed=outcomes[-1]['passed'])), flush=True)

        await call('project-add', dict(root=str(scratch)))
        await call('session-new', dict(mode='chat'))
        allow_writes = True
        task = await call('chat', dict(text='Read package.json, copied from the actual Wixal project manifest. Use an installed python3 command to calculate the number of entries in scripts before writing the report; do not count them mentally. Use write_file to save chat-project-report.json with exactly the keys name (the package name), version (the package version), and scriptCount (the integer number of entries in scripts). Read the saved report back to verify it. Discover other schemas with workspace_info if needed. Do not change package.json or save memory.',successCriteria=source_checks))
        path = scratch/'chat-project-report.json'
        actual = json.loads(path.read_text()) if path.exists() else None
        outcomes.append(dict(name='chat-reviewed-report-and-readback', passed=task['status']=='completed' and task['verification']['status']=='passed' and actual==expected
            and any(c['name'] in ('run_command','command_read') and c['status']=='finished' and json.loads(c['result']).get('exitCode')==0 and str(expected['scriptCount']) in json.loads(c['result']).get('output','') for c in task['checkpoints'] if c.get('result','').startswith('{'))
            and any(c['name']=='write_file' and c['status']=='finished' for c in task['checkpoints'])
            and any(c['name']=='read_file' and c.get('arguments',{}).get('path')=='chat-project-report.json' for c in task['checkpoints']), expected=expected, actual=actual, task=task))
        print(json.dumps(dict(name=outcomes[-1]['name'], passed=outcomes[-1]['passed'])), flush=True)

        task = await call('chat', dict(text='Run an installed python3 command to independently compare chat-project-report.json with package.json: name and version must match, and scriptCount must equal len(scripts). Print CHAT-REPORT-VERIFIED only after the assertions pass. Inspect the actual command exit code and output before concluding.'))
        outcomes.append(dict(name='chat-command-verifies-the-actual-report', passed=task['status']=='completed'
            and any(c['name'] in ('run_command', 'command_read') and 'CHAT-REPORT-VERIFIED' in c.get('result','')
                and json.loads(c['result']).get('exitCode')==0 for c in task['checkpoints'] if c.get('result','').startswith('{')), task=task))
        print(json.dumps(dict(name=outcomes[-1]['name'], passed=outcomes[-1]['passed'])), flush=True)

        await call('session-new', dict(mode='chat'))
        allow_writes = False
        task = await call('chat', dict(text='Use write_file to create declined-chat-report.md explaining the project tool catalog. If the controller declines the action, stop and explain that no report was created. Do not try another tool or path.'))
        outcomes.append(dict(name='chat-declined-write-has-no-effect', passed=not (scratch/'declined-chat-report.md').exists()
            and any(str(c.get('result','')).startswith('User declined') for c in task['checkpoints'])
            and task['status']=='needs_attention', task=task))
        print(json.dumps(dict(name=outcomes[-1]['name'], passed=outcomes[-1]['passed'])), flush=True)
        state = (await call('hello'))['state']
        if state['enabledTools'] or state['mode']!='chat':
            raise AssertionError('Chat changed the legacy tool preferences or mode')
    finally:
        process.stdin.close()
        await asyncio.wait_for(process.stdout.read(), 30)
        await asyncio.wait_for(process.wait(), 30)
        (output/'helper-stderr.log').write_bytes(await stderr)
        (output/'events.json').write_text(json.dumps(events, indent=2))
        report = dict(status='passed' if len(outcomes)==4 and all(r['passed'] for r in outcomes) else 'failed',
            model=args.model, app=str(app), acceptanceScriptSha256=acceptance_sha, helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
            sourceManifestSha256=hashlib.sha256((app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(), outcomes=outcomes)
        (output/'results.json').write_text(json.dumps(report, indent=2))
    return report['status']=='passed'


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--model', default='gpt-oss:20b')
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
