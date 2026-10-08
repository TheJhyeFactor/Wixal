"""Verify the agent's repeated-failure stop using actual small-model tool calls.

The target is the existing native directory, which read_file must reject. No
missing-file marker, fake tool reply, or fabricated model response is supplied.
Runs after real-acceptance.py has downloaded the real qwen3:1.7b model; retains
its actual prompts, outputs, counters and request budgets in a separate report.
"""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('real_acceptance',Path(__file__).with_name('real-acceptance.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

async def main():
    client=module.Client(False)
    report=dict(status='running',helperSHA256=hashlib.sha256((module.ROOT/'release/native/Wixal.app/Contents/Resources/engine/wixal-engine').read_bytes()).hexdigest())
    try:
        await client.start();await client.call('project-add',dict(root=str(module.ROOT)))
        model=await client.model('qwen3:1.7b');await client.call('session-new')
        turn=await client.chat('Use @read_file exactly three times, all with path native. The native path is an actual directory in this project. This bounded diagnostic is specifically to verify the controller stops repeated identical directory-read failures. Perform all three attempts even if the first fails, then explain the actual error and stop. Do not change the path, use other tools or edit anything.')
        failures=[row for row in turn['toolResults'] if row['tool_name']=='read_file' and 'error' in row['content']]
        report.update(model=model,observed=turn,actualFailures=len(failures))
        assert len(failures)==3 and 'three times' in failures[-1]['content'],turn
        assert not turn['requests'][-1]['tools'],'The conclusion must be generated after removing tool schemas'
        assert 'directory' in turn['answer'].lower(),turn
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error));raise
    finally:
        (module.ROOT/'artifacts/native/real-failure-guard.json').write_text(json.dumps(report,indent=2))
        await client.close()
    print(json.dumps(dict(status=report['status'],actualFailures=report['actualFailures'],conclusionWithoutTools=True)))

if __name__=='__main__':asyncio.run(main())
