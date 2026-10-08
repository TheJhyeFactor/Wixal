"""Run real packaged assessments against an explicitly authorised domain.

Uses disposable project/state storage. Saves actual evidence under artifacts/native.
TCP scope is port 443 only; website scope is the baseline public-read profile.
"""
import argparse
import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',required=True,help='Domain explicitly authorised by its owner')
    options=parser.parse_args()
    target=options.target.strip()
    if not target or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in target):
        parser.error('Supply a domain without URL path or scheme')
    destination=ROOT/'artifacts/native'
    destination.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',implementation='current packaged helper',target=target,stages={},started=time.time())
    def checkpoint(name,value):
        report['stages'][name]=value
        (destination/'external-acceptance.json').write_text(json.dumps(report,indent=2))
        print(name+': '+json.dumps(value),flush=True)
    with tempfile.TemporaryDirectory(prefix='wixal-external-acceptance-') as directory:
        project=Path(directory)/'project';project.mkdir()
        child=await asyncio.create_subprocess_exec(str(ROOT/'release/native/Wixal.app/Contents/Resources/engine/wixal-engine'),'--data',str(Path(directory)/'data'),'--runtime',str(ROOT/'runtime/ollama'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=16*1024*1024)
        counter=0;events=[]
        async def call(method,params=None):
            nonlocal counter
            counter+=1;identifier=str(counter)
            child.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+'\n').encode());await child.stdin.drain()
            while row:=await asyncio.wait_for(child.stdout.readline(),200):
                message=json.loads(row)
                if message['event'] in ('assessment-case','assessment-progress'):events.append(message)
                if message['event']=='response' and message['data']['id']==identifier:
                    data=message['data']
                    if data.get('error'):raise RuntimeError(data['error'])
                    return data['result']
            raise RuntimeError('Helper disconnected before completion')
        try:
            await call('hello')
            await call('project-add',dict(root=str(project)))
            await call('settings',dict(approvalMode='bypass'))
            readiness=await call('security-readiness')
            assert readiness['installed'],readiness
            scan=await call('assessment-run',dict(name='network_scan',arguments=dict(target=target,profile='ports',ports='443',timeout_seconds=60)))
            assert scan.get('exitCode')==0 and '443' in scan.get('output',''),scan
            (destination/'external-nmap.json').write_text(json.dumps(scan,indent=2))
            checkpoint('realNmap',dict(target=target,ports='443',exitCode=scan['exitCode'],evidence='external-nmap.json'))
            website=await call('assessment-run',dict(name='website_assess',arguments=dict(url='https://'+target+'/',profile='baseline',protected_paths=[],report_prefix='authorised-website-baseline',max_pages=3)))
            assert website['saved'] and website['report']['target']=='https://'+target+'/'
            assert website['report']['requests'] and website['report']['cases']
            for filename in website['paths']:
                source=Path(filename)
                shutil.copy2(source,destination/('external-website'+source.suffix))
            checkpoint('realWebsite',dict(target=website['report']['target'],requestCount=len(website['report']['requests']),summary=website['summary'],progressEvents=len(events),evidence=['external-website.json','external-website.md']))
            try:
                searched=await call('tool',dict(name='web_search',arguments=dict(query='site:'+target,limit=5)))
                assert searched['state'] in ('results','no_results')
                assert all(item['url'].startswith(('https://','http://')) for item in searched['results'])
                (destination/'external-search.json').write_text(json.dumps(searched,indent=2))
                checkpoint('realSearch',dict(state=searched['state'],resultCount=len(searched['results']),evidence='external-search.json'))
            except RuntimeError as error:
                if 'challenge' not in str(error).lower():raise
                checkpoint('realSearch',dict(state='provider-challenge',error=str(error),resultsPathVerified=False))
            report['status']='passed'
        except BaseException as error:
            report.update(status='failed',error=str(error));raise
        finally:
            if child.returncode is None:
                child.stdin.close()
                try:await asyncio.wait_for(child.wait(),10)
                except asyncio.TimeoutError:child.kill();await child.wait()
            report['finished']=time.time()
            (destination/'external-acceptance.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(status=report['status'],target=target)),flush=True)


if __name__=='__main__':asyncio.run(main())
