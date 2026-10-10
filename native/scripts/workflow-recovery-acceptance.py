"""Installed real-model dependency recovery with independent stage/task oracles.

The missing prerequisite is deliberate. Its repair is an explicit harness write
inside a disposable project; the failed attempt remains retained.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import time
from pathlib import Path

spec=importlib.util.spec_from_file_location('real',Path(__file__).with_name('real-acceptance.py'))
real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)

async def main(options):
    base=options.output.resolve();base.mkdir(parents=True,exist_ok=False);project=base/'project';project.mkdir()
    (project/'source.txt').write_text('WORKFLOW-SOURCE-7319\n')
    real.ART=base;real.STATE=base/'workspace';helper=options.helper.resolve()
    client=real.Client(False,helper=helper,endpoint='http://127.0.0.1:11434')
    report=dict(status='running',started=time.time(),helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),cases=[])
    def save():(base/'results.json').write_text(json.dumps(report,indent=2))
    try:
        await client.start();report['model']=await client.model(options.model)
        await client.call('settings',dict(contextSize=8192));await client.call('project-add',dict(root=str(project)))
        await client.call('agent-save',dict(id='reader',name='Workflow reader',purpose='Inspect actual source files',instructions='Use read_file to inspect the actual requested file. Preserve exact markers. Report missing files honestly.',model=options.model,reviewPolicy='Read only',memoryScope='Memory off'))
        flow=await client.call('workflow-save',dict(name='Verified dependency recovery',brief='Inspect actual local prerequisites, then produce an evidence summary.',execution='Dependency graph',stages=[
            dict(id='source',name='Source',agentID='reader',goal='Read source.txt and report its exact marker.',output='Source marker',successCriteria=[dict(kind='tool_contains',tool='read_file',value='WORKFLOW-SOURCE-7319')]),
            dict(id='prerequisite',name='Prerequisite',agentID='reader',goal='Read prerequisite.txt and report its exact marker. If absent, report it as missing without creating it.',output='Prerequisite marker',successCriteria=[dict(kind='tool_contains',tool='read_file',value='WORKFLOW-PREREQUISITE-7319')]),
            dict(id='join',name='Join',agentID='reader',goal='Read source.txt and prerequisite.txt. Report both exact markers and cite each filename.',output='Combined verified evidence',dependsOn=['source','prerequisite'],condition='dependencies_verified',successCriteria=[dict(kind='tool_contains',tool='read_file',value='WORKFLOW-SOURCE-7319'),dict(kind='tool_contains',tool='read_file',value='WORKFLOW-PREREQUISITE-7319')])]))
        first=await client.call('workflow-run',dict(id=flow['id']))
        report['firstRun']=copy.deepcopy(first);save()
        assert first['status']!='completed',first
        source=next(s for s in first['stages'] if s['id']=='source');failed=next(s for s in first['stages'] if s['id']=='prerequisite')
        assert source['status']=='completed' and source['verification']['status']=='passed',source
        assert failed['status']!='completed' and failed.get('childId') and failed.get('taskId'),failed
        assert not any(s['id']=='join' for s in first['stages']),first
        report['cases'].append(dict(name='invalid-prerequisite-blocks-dependent-stage',status='passed',taskId=failed['taskId']));save()
        (project/'prerequisite.txt').write_text('WORKFLOW-PREREQUISITE-7319\n')
        second=await client.call('workflow-resume',dict(runId=first['id']));report['resumedRun']=copy.deepcopy(second);save()
        assert second['status']=='completed' and second['verification']['status']=='passed',second
        retained=next(s for s in second['stages'] if s['id']=='source');recovered=next(s for s in second['stages'] if s['id']=='prerequisite')
        assert retained['taskId']==source['taskId'],retained
        assert recovered['childId']!=failed['childId'] and recovered['attemptHistory'][-1]['taskId']==failed['taskId'],recovered
        assert all(marker in second['result'] for marker in ('WORKFLOW-SOURCE-7319','WORKFLOW-PREREQUISITE-7319'))
        state=await client.state();task=next(t for t in state['tasks'] if t['id']==failed['taskId'])
        assert task['status']!='completed',task
        report['cases'].append(dict(name='resume-retains-failed-attempt-and-skips-completed-source',status='passed',retainedSourceTask=source['taskId'],failedTask=failed['taskId'],recoveredTask=recovered['taskId']))
        report['status']='passed'
    except BaseException as error:report.update(status='failed',error=str(error));raise
    finally:
        await client.close();report['finished']=time.time();save()
    print(json.dumps(dict(status=report['status'],cases=len(report['cases']))))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--model',default='gpt-oss:20b')
    asyncio.run(main(parser.parse_args()))
