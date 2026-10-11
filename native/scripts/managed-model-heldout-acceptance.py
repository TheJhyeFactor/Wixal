"""Frozen new wording and model-led managed installation against owned listeners.

Keep the prompt set immutable once execution begins. A failed candidate retires
its tested wording to regression evidence; do not tune it and call it held out.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
real=module('real',Path(__file__).with_name('real-acceptance.py'))
oracle=module('oracle',Path(__file__).with_name('model-port-oracle.py'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

async def main(options):
    art=options.output.resolve();art.mkdir(parents=True,exist_ok=False)
    prompts=json.loads(options.prompt_set.read_text())
    assert isinstance(prompts,list) and prompts and len({p['id'] for p in prompts})==len(prompts)
    (art/'prompt-set.json').write_bytes(options.prompt_set.read_bytes())
    real.ART=art;real.STATE=art/'workspace';project=art/'project';project.mkdir()
    os.environ['WIXAL_MANAGED_TOOLS_ROOT']=str(art/'registry')
    client=real.Client(False,helper=options.helper,endpoint='http://127.0.0.1:11434')
    expected=[];servers=[];connections=[];install_allowed=False
    async def accept(reader,writer):
        connections.append(dict(port=writer.get_extra_info('sockname')[1],time=time.time()))
        writer.close();await writer.wait_closed()
    def review(details):
        if details.get('name')=='addon_install':
            return install_allowed and details.get('addon')=='rustscan' and details.get('provider')=='managed'
        assessment=details.get('assessment',{})
        return details.get('name')=='command_start' and assessment.get('capability') in ('network_discover','network_scan') and assessment.get('target')=='127.0.0.1' and bool(assessment.get('ports')) and set(assessment['ports'])<=set(expected)
    client.review_policy=review
    report=dict(status='running',started=time.time(),cases=[],helperSha256=digest(options.helper),promptSetSha256=digest(options.prompt_set),acceptanceScriptSha256=digest(Path(__file__)),gradingScriptSha256=digest(Path(__file__).with_name('model-port-oracle.py')),qualification='additional_gates_only')
    def save():(art/'report.json').write_text(json.dumps(report,indent=2))
    save()
    try:
        await client.start();await client.call('project-add',dict(root=str(project)))
        hello=await client.call('hello');await client.call('settings',dict(enabledTools=[t['function']['name'] for t in hello['tools']]))
        await client.call('addon-managed-refresh')
        report['model']=await client.model(options.model);await client.call('settings',dict(contextSize=8192));save()
        for prompt in prompts:
            assert digest(options.prompt_set)==report['promptSetSha256'],'Prompt set changed'
            assert digest(options.helper)==report['helperSha256'],'Installed helper changed'
            for server in servers:server.close();await server.wait_closed()
            servers=[await asyncio.start_server(accept,'127.0.0.1',0) for _ in range(2)]
            expected=sorted(s.sockets[0].getsockname()[1] for s in servers)
            install_allowed=prompt['kind']=='install_discovery'
            await client.call('session-new')
            text=prompt['prompt'].format(host='127.0.0.1',ports=','.join(map(str,expected)))
            row=dict(id=prompt['id'],kind=prompt['kind'],prompt=text,status='running',started=time.time(),oracle=dict(host='127.0.0.1',ports=expected))
            report['cases'].append(row);save();before=len(connections);reviews_before=len(client.reviews)
            try:
                output=await client.chat(text);values=[]
                for message in output['toolResults']:
                    try:value=json.loads(message.get('content','{}'))
                    except (ValueError,TypeError):continue
                    if isinstance(value,dict):values.append((message.get('tool_name'),value))
                discoveries=[v for n,v in values if n=='network_read' and v.get('state')=='completed' and v.get('structuredResult',{}).get('scanner')=='RustScan' and v['structuredResult'].get('handoffEligible')]
                scans=[v for n,v in values if n=='network_scan' and v.get('sourceSessionId') and v.get('state')=='completed' and v.get('exitCode') in (None,0)]
                assert any(v['structuredResult']['hosts'][0]['ports']==expected for v in discoveries),'No completed fresh discovery with the listener facts'
                if prompt['kind']=='inspection':
                    assert any(s['sourceSessionId']==d['session_id'] and sorted(int(p['port']) for p in s.get('services',[]))==expected for s in scans for d in discoveries),'No completed inspection bound to this discovery'
                else:assert not scans,'Inspection was not requested'
                if install_allowed:
                    assert any(n=='addon_job' and v.get('status')=='ready' for n,v in values),'Model did not wait for managed installation readiness'
                    assert any(r['name']=='addon_install' and r['approved'] for r in client.reviews[reviews_before:]),'No model-led scoped installation review'
                errors=oracle.contradictions(output['answer'],expected)+oracle.quoted_xml_errors(output['answer'],[s.get('output','') for s in scans])
                assert not errors,errors
                assert all(str(port) in output['answer'] for port in expected),'An observed port was omitted'
                assert not any(r['approved'] and r['name'] not in ('command_start','addon_install') for r in client.reviews[reviews_before:]),'An unrelated action was approved'
                assert not list(project.iterdir()),'Unexpected project file effect'
                row.update(status='passed',output=output,finished=time.time())
            except Exception as error:
                session=await client.session();state=await client.state()
                task=next((t for t in reversed(state['tasks']) if t.get('sessionId')==session['id']),{})
                row.update(status='failed',error=str(error),session=session,task=task,finished=time.time())
            row.update(ledger=connections[before:],reviews=client.reviews[reviews_before:]);save()
            print(json.dumps(dict(id=row['id'],status=row['status'])),flush=True)
        report.update(status='passed' if all(c['status']=='passed' for c in report['cases']) else 'failed',finished=time.time());save()
    except BaseException as error:
        report.update(status='failed',error=str(error),finished=time.time());save();raise
    finally:
        for server in servers:server.close();await server.wait_closed()
        if hasattr(client,'child'):await client.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prompt-set',type=Path,required=True)
    parser.add_argument('--model',default='gpt-oss:20b')
    asyncio.run(main(parser.parse_args()))
