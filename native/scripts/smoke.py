"""Exercise the actual .app, bundled Python, JSON IPC, model stream and command path."""
import json
import hashlib
import asyncio
import os
import subprocess
import sys
import tempfile
import time
import signal
from pathlib import Path

native=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(native/"tests"))
from fixture_server import Fixture
app=native.parent/"release/native/Wixal.app"
artifact=native.parent/"artifacts/native"
artifact.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="wixal-native-smoke-") as temporary, Fixture() as fixture:
    root=Path(temporary)/"project";root.mkdir()
    env={**os.environ,"WIXAL_NATIVE_SMOKE":"1","WIXAL_NATIVE_SMOKE_ROOT":str(root),"WIXAL_NATIVE_DATA":str(Path(temporary)/"data"),"WIXAL_NATIVE_ENDPOINT":fixture.url}
    log=(artifact/"packaged-launch.log").open("w")
    launch=["/usr/bin/open","-n","-W",str(app)]
    for key,value in env.items():
        if key.startswith("WIXAL_NATIVE_"):launch.extend(["--env",key+"="+value])
    process=subprocess.Popen(launch,stdout=log,stderr=log)
    report={}
    try:
        for _ in range(900):
            if (root/"native-smoke-error.txt").exists():raise RuntimeError((root/"native-smoke-error.txt").read_text())
            if (root/"native-smoke.json").exists():break
            if process.poll() is not None:raise RuntimeError("Native app exited before the smoke completed")
            time.sleep(.1)
        else:raise TimeoutError("Native packaged smoke timed out")
        report=json.loads((root/"native-smoke.json").read_text())
        assert (root/"smoke.txt").read_text()=="native-agent-ok\n"
        assert report["command"]["output"]=="native-command-ok" and report["command"]["exitCode"]==0
        assert report["state"]["tasks"][-1]["status"]=="completed"
        assert report["windowCount"]>=1
        terminal=subprocess.run([str(app/"Contents/Resources/engine/wixal-engine"),"--terminal","--data",str(Path(temporary)/"data")],input="/models\n/quit\n",text=True,capture_output=True,timeout=15)
        assert terminal.returncode==0,terminal.stderr
        assert "Connected to the Wixal Native desktop engine" in terminal.stdout and "fixture" in terminal.stdout
        report["sharedPackagedTerminal"]="passed"
        async def browser_check():
            reader,writer=await asyncio.open_unix_connection(str(Path(temporary)/"data/engine.sock"),limit=2*1024*1024)
            counter=0
            async def call(name,arguments):
                nonlocal counter
                counter+=1;request_id="browser-smoke-"+str(counter)
                writer.write((json.dumps(dict(id=request_id,method="tool",params=dict(name=name,arguments=arguments)))+"\n").encode());await writer.drain()
                while line:=await asyncio.wait_for(reader.readline(),40):
                    message=json.loads(line)
                    if message["event"]=="response" and message["data"]["id"]==request_id:
                        if message["data"].get("error"):raise RuntimeError(message["data"]["error"])
                        return message["data"]["result"]
                raise RuntimeError("Browser smoke disconnected")
            try:
                expected="first😀line\nsecond🧪line\n"
                (root/"pagination.txt").write_text(expected)
                command=await call("command_start",dict(command="cat pagination.txt"))
                offset=0;pieces=[]
                while True:
                    chunk=await call("command_read",dict(session_id=command["session_id"],offset=offset,max_chars=8,wait_ms=1000))
                    pieces.append(chunk['output']);offset=chunk['next_offset']
                    if not chunk['more'] and chunk['state']!='running':break
                assert ''.join(pieces)==expected and offset==len(expected.encode('utf-16-le'))//2
                report['packagedCommandUTF16Pagination']='passed'
                page=await call("browser_open",dict(url=fixture.url+"/page",wait_for="delayed-ready",wait_ms=2000))
                assert page["readiness"]["matched"] and page["forms"] and page["scripts"]==[]
                assert any("fixture-console" in line for line in page["console"])
                assert "Rendered fixture page" in page["text"]
                old_ref=page["links"][0]["ref"]
                fresh=await call("browser_read",dict(session_id=page["session_id"]))
                try:await call("browser_action",dict(session_id=page["session_id"],ref=old_ref,action="click"))
                except RuntimeError as error:assert "fresh references" in str(error)
                else:raise AssertionError("Stale browser reference was accepted")
                async def control(snapshot,label,action,value=None):
                    match=next(c for c in snapshot['controls'] if c['label']==label)
                    args=dict(session_id=page['session_id'],ref=match['ref'],action=action,wait_ms=200)
                    if value is not None:args['value']=value
                    return await call('browser_action',args)
                for label,action,value in [('Password','fill','blocked'),('Submit form','click',None)]:
                    try:await control(fresh,label,action,value)
                    except RuntimeError as error:assert any(word in str(error) for word in ('unsupported','submission','Credentials'))
                    else:raise AssertionError('Protected action was accepted')
                fresh=await control(fresh,'Name','fill','native-filled')
                fresh=await control(fresh,'Choice','select','two')
                fresh=await control(fresh,'Show result','click')
                assert 'native-filled two' in fresh['text']
                fresh=await control(fresh,'Try script request','click')
                assert 'request-blocked' in fresh['text']
                linked=await call("browser_action",dict(session_id=page["session_id"],ref=fresh["links"][0]["ref"],action="click"))
                assert "linked-page-ok" in linked["text"]
                await call("browser_close",dict(session_id=page["session_id"]))
                return "render / wait_for / console / forms / fill / select / button / blocked sensitive input / blocked submit / blocked script request / stale ref / link / close passed"
            finally:writer.close();await writer.wait_closed()
        report["nativeWebKit"]=asyncio.run(browser_check())
        report['helperSHA256']=hashlib.sha256((app/'Contents/Resources/engine/wixal-engine').read_bytes()).hexdigest()
        (artifact/"packaged-smoke.json").write_text(json.dumps(report,indent=2))
        print("PACKAGED_NATIVE_SMOKE_OK",flush=True)
        if "--hold" in sys.argv:
            (artifact/"smoke-pid.txt").write_text(str(process.pid))
            print("Holding the native QA window for inspection",flush=True)
            hold_seconds=int(sys.argv[sys.argv.index("--hold-seconds")+1]) if "--hold-seconds" in sys.argv else 55
            time.sleep(hold_seconds)
    finally:
        if report.get("pid"):
            try:os.kill(report["pid"],signal.SIGTERM)
            except ProcessLookupError:pass
        process.terminate()
        try:process.wait(10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
