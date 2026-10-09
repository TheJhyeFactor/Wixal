"""Observe the real native app's first paint, engine handshake and workspace mount.

Uses isolated native storage and the actual supplied app/helper. The slow case
holds a real SQLite exclusive lock for three seconds, then releases it. No
model server, engine response or legally accepted setup state is fabricated.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'native/engine'))
from wixal.storage import Store

def case(app,output,name):
    folder=output/name;folder.mkdir(parents=True,exist_ok=False)
    data=folder/'data';data.mkdir()
    ui=dict(theme='sakura',launchAnimation=True,launchSound=False,reduceMotion=False)
    if name=='animation-off':ui.update(theme='paper',launchAnimation=False)
    if name=='reduced-motion':ui.update(theme='forest',reduceMotion=True)
    if name=='failed-database':
        (data/'workspace.sqlite3').mkdir()
    else:
        store=Store(data);store.data['ui'].update(ui);store.save();store.close()
    key='startup.appearance.'+hashlib.sha256(str(data).encode()).hexdigest()
    arguments=['defaults','write','app.wixal.native.preview',key,'-dict','theme',ui['theme']]
    for setting in ('launchAnimation','launchSound','reduceMotion'):
        arguments += [setting,'-bool','YES' if ui[setting] else 'NO']
    subprocess.run(arguments,check=True)
    lock=None
    if name=='slow-database':
        lock=sqlite3.connect(data/'workspace.sqlite3')
        lock.execute('PRAGMA journal_mode=DELETE');lock.execute('BEGIN EXCLUSIVE')
    trace=folder/'trace.jsonl'
    env={**os.environ,'WIXAL_NATIVE_DATA':str(data),'WIXAL_NATIVE_ACCEPTANCE':'1',
         'WIXAL_NATIVE_STARTUP_TRACE':str(trace)}
    stdout=(folder/'stdout.log').open('w');stderr=(folder/'stderr.log').open('w')
    child=subprocess.Popen([str(app/'Contents/MacOS/WixalNative')],env=env,stdout=stdout,stderr=stderr)
    try:
        started=time.monotonic();release_at=None;events=[]
        while time.monotonic()-started<40:
            if child.poll() is not None:raise RuntimeError('App exited before startup observation completed')
            if trace.exists():
                events=[json.loads(line) for line in trace.read_text().splitlines()]
                phases={event['phase']:event['uptime'] for event in events}
                if lock is not None and 'engine-launched' in phases and release_at is None:
                    release_at=time.monotonic()+3.0
                if lock is not None and release_at is not None and time.monotonic()>=release_at:
                    lock.rollback();lock.close();lock=None
                if 'workspace-mounted' in phases:break
            time.sleep(.02)
        else:raise TimeoutError('Native startup did not reach the workspace or recovery screen')
        phases={event['phase']:event['uptime'] for event in events}
        assert phases['splash-presented']<=phases['engine-start']<=phases['engine-launched']
        assert phases['reveal-finished']>=phases['splash-presented']
        assert phases['workspace-mounted']>=phases['workspace-released']>=phases['reveal-finished']
        if name=='failed-database':assert 'engine-ready' not in phases
        else:assert phases['workspace-released']>=phases['engine-ready']
        if name=='slow-database':assert phases['engine-ready']-phases['splash-presented']>=3
        if name in ('animation-off','reduced-motion'):
            assert .2<=phases['reveal-finished']-phases['splash-presented']<1.5
        else:assert phases['reveal-finished']-phases['splash-presented']>=1.8
        result=dict(case=name,status='passed',events=events,ui=ui,
                    splashToWorkspaceSeconds=round(phases['workspace-mounted']-phases['splash-presented'],3),
                    engine='actual bundled helper',database='isolated actual native SQLite storage')
        (folder/'report.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({key:result[key] for key in ('case','status','splashToWorkspaceSeconds')}),flush=True)
        return result
    finally:
        if lock is not None:lock.rollback();lock.close()
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        stdout.close();stderr.close()
        subprocess.run(['defaults','delete','app.wixal.native.preview',key],capture_output=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,default=Path('/Applications/Wixal.app'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['animated','animation-off','reduced-motion','slow-database','failed-database'])
    options=parser.parse_args();options.output=options.output.resolve()
    names=[options.case] if options.case else ['animated','animation-off','reduced-motion','slow-database','failed-database']
    results=[case(options.app,options.output,name) for name in names]
    binary=options.app/'Contents/MacOS/WixalNative';helper=options.app/'Contents/Resources/engine/wixal-engine'
    report=dict(status='passed',app=str(options.app),cases=results,
                appBinarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest())
    (options.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
