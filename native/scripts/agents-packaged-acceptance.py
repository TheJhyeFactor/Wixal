"""Exercise the frozen helper through the same JSON IPC used by Swift.

Uses an isolated database, actual repository documentation and scratch output.
Does not register a LaunchAgent or modify the running user's Wixal workspace.
"""
import argparse
import hashlib
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from wixal.storage import Store, now


async def main(args):
    app = Path(args.app).resolve()
    base = Path(args.output).resolve()
    base.mkdir(parents=True, exist_ok=True)
    data = base / 'data'
    scratch = base / 'project'
    scratch.mkdir(exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    helper = app / 'Contents/Resources/engine/wixal-engine'
    runtime = app / 'Contents/Resources/ollama'
    command = [str(helper), '--data', str(data), '--runtime', str(runtime), '--endpoint', args.endpoint]
    events, outcomes = [], []
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=32*1024*1024)
    errors = asyncio.create_task(process.stderr.read())

    async def call(method, params=None):
        identifier = uuid.uuid4().hex
        process.stdin.write((json.dumps(dict(id=identifier, method=method, params=params or {}))+'\n').encode())
        await process.stdin.drain()
        while True:
            raw = await asyncio.wait_for(process.stdout.readline(), 360)
            if not raw:
                raise RuntimeError('Frozen helper ended before responding')
            event = json.loads(raw)
            events.append(event)
            if event['event'] == 'review':
                # Only scratch writes are requested by this acceptance suite.
                process.stdin.write((json.dumps(dict(id=uuid.uuid4().hex, method='respond',
                    params=dict(id=event['data']['id'], value=True)))+'\n').encode())
                await process.stdin.drain()
            if event['event'] == 'response' and event['data']['id'] == identifier:
                if 'error' in event['data']:
                    raise RuntimeError(event['data']['error'])
                return event['data']['result']

    try:
        project = await call('project-add', dict(root=str(repo)))
        await call('settings', dict(model=args.model, enabledTools=[]))
        await call('agent-save', dict(id='packaged-reviewer', name='Packaged source reviewer',
            purpose='Inspect actual source documentation', instructions='Inspect actual files, preserve exact identifiers and cite evidence.',
            model=args.model, reviewPolicy='Read only', memoryScope='Project only', skills=[]))
        prompt = 'Read native/third_party/hermes/NOTICE.md. Report the exact copied function and the pinned upstream revision. Do not change files.'
        result = await call('agent-run', dict(id='packaged-reviewer', prompt=prompt))
        outcomes.append(dict(name='frozen-real-source-review', passed=result['status']=='completed'
            and 'parse_duration' in result.get('result','') and '0e21933114c911075782d5744cee5403996d38ae' in result.get('result','')
            and any(c['name']=='read_file' for c in result['checkpoints']), result=result))
        await call('project-add', dict(root=str(scratch)))
        await call('agent-save', dict(id='packaged-coder', name='Packaged artifact agent', purpose='Produce verified artifacts',
            instructions='Use tools to produce the requested output and read it back to verify.', model=args.model,
            reviewPolicy='Review actions', memoryScope='Project only', skills=[]))
        result = await call('agent-run', dict(id='packaged-coder', prompt='Write packaged-proof.json with exactly {"engine":"wixal","verified":true}. Read it back and verify the exact fields.'))
        outcomes.append(dict(name='frozen-reviewed-artifact', passed=result['status']=='completed'
            and json.loads((scratch/'packaged-proof.json').read_text())==dict(engine='wixal',verified=True), result=result))
        if args.management:
            result = await call('agent-run', dict(id='packaged-coder', prompt='At my request, create a routine named Weekday proof review for this same agent every weekday at 09:15 in Australia/Sydney. Its task is to read packaged-proof.json and report its actual fields. Do not run it now. Verify the saved calendar timing by listing the routines.'))
            state = (await call('hello'))['state']
            routine = next((s for s in state['schedules'] if s.get('name')=='Weekday proof review'), {})
            outcomes.append(dict(name='model-calendar-routine-creation', passed=result['status']=='completed'
                and routine.get('timing')=='Every weekday' and routine.get('time')=='09:15'
                and routine.get('timezone')=='Australia/Sydney'
                and any(c['name']=='schedule_manage' for c in result['checkpoints']), result=result, routine=routine))
            result = await call('agent-run', dict(id='packaged-coder', prompt='Inspect packaged-proof.json. If its engine field is wixal and verified is true, save a reusable skill named packaged-proof-check describing how to read and verify this artifact on future tasks. Preserve the exact field names and values. Verify that the skill was saved.'))
            state = (await call('hello'))['state']
            skill = next((s for s in state['skills'] if s.get('name')=='packaged-proof-check'), {})
            outcomes.append(dict(name='model-verified-skill-creation', passed=result['status']=='completed'
                and 'wixal' in skill.get('content','') and 'verified' in skill.get('content','')
                and any(c['name']=='read_file' for c in result['checkpoints'])
                and any(c['name']=='skill_manage' for c in result['checkpoints']), result=result, skill=skill))
        await call('agent-schedule-save', dict(id='packaged-routine', name='Frozen background source review',
            agentID='packaged-reviewer', prompt=prompt, projectId=project['activeProject'], intervalSeconds=60))
    finally:
        process.stdin.close()
        # Drain all remaining messages while the helper closes owned requests.
        await asyncio.wait_for(process.stdout.read(), 30)
        await asyncio.wait_for(process.wait(), 30)
        (base/'helper-stderr.log').write_bytes(await errors)
        (base/'events.json').write_text(json.dumps(events, indent=2))
        (base/'results.json').write_text(json.dumps(dict(model=args.model, app=str(app), outcomes=outcomes), indent=2))
    store = Store(data)
    row = next(s for s in store.data['schedules'] if s['id']=='packaged-routine')
    row['nextRun'] = now()-1000
    store.save()
    store.close()
    background = await asyncio.create_subprocess_exec(str(helper), '--background', *command[1:],
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, error = await asyncio.wait_for(background.communicate(), 360)
    (base/'background.log').write_bytes(out+error)
    store = Store(data)
    try:
        row = next(s for s in store.data['schedules'] if s['id']=='packaged-routine')
        task = next((t for t in store.data['tasks'] if t['id']==row.get('lastRun',{}).get('taskId')), {})
        outcomes.append(dict(name='frozen-background-tool-run', passed=background.returncode==0
            and row.get('lastRun',{}).get('status')=='completed' and task.get('source')=='Background schedule'
            and 'parse_duration' in task.get('result',''), lastRun=row.get('lastRun'), result=task))
    finally:
        store.close()
    (base/'results.json').write_text(json.dumps(dict(status='passed' if all(r['passed'] for r in outcomes) else 'failed',model=args.model,app=str(app),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),sourceManifestSha256=hashlib.sha256((app/'Contents/Resources/SOURCE_MANIFEST.json').read_bytes()).hexdigest(),outcomes=outcomes),indent=2))
    print(json.dumps([dict(name=r['name'], passed=r['passed']) for r in outcomes]))
    return all(r['passed'] for r in outcomes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--model', default='gpt-oss:20b')
    parser.add_argument('--management', action='store_true', help='Also verify real model calendar and skill creation')
    raise SystemExit(0 if asyncio.run(main(parser.parse_args())) else 1)
