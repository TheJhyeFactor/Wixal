"""Kill the real packaged helper and verify its managed runner is reaped."""
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


async def main():
    with tempfile.TemporaryDirectory(prefix="wixal-recovery-acceptance-") as directory:
        child=await asyncio.create_subprocess_exec(str(ROOT/"release/native/Wixal.app/Contents/Resources/engine/wixal-engine"),"--data",directory,"--runtime",str(ROOT/"runtime/ollama"),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        async def call(method):
            child.stdin.write((json.dumps(dict(id=method,method=method,params={}))+"\n").encode());await child.stdin.drain()
            while line:=await asyncio.wait_for(child.stdout.readline(),140):
                row=json.loads(line)
                if row["event"]=="response" and row["data"]["id"]==method:
                    if row["data"].get("error"):raise RuntimeError(row["data"]["error"])
                    return row["data"]["result"]
            raise RuntimeError("Disconnected before response")
        def children(pid):
            result=subprocess.run(["pgrep","-P",str(pid)],text=True,capture_output=True)
            return [int(value) for value in result.stdout.split()]
        def alive(pid):
            try:os.kill(pid,0);return True
            except ProcessLookupError:return False
        report=dict(status="running",implementation="packaged")
        try:
            await call("hello");await call("runtime-start")
            supervisors=children(child.pid)
            runners=[pid for supervisor in supervisors for pid in children(supervisor)]
            assert supervisors and runners,(supervisors,runners)
            child.kill();await child.wait()
            for _ in range(60):
                if not any(alive(pid) for pid in supervisors+runners):break
                await asyncio.sleep(.1)
            else:raise RuntimeError("Managed processes survived helper termination")
            report.update(status="passed",supervisorCount=len(supervisors),runnerCount=len(runners),cleanupAfterAbruptTermination=True)
        except BaseException as error:
            report.update(status="failed",error=str(error));raise
        finally:
            if child.returncode is None:child.stdin.close();await asyncio.wait_for(child.wait(),30)
            (ROOT/"artifacts/native/recovery-acceptance.json").write_text(json.dumps(report,indent=2))
        print(json.dumps(report))


if __name__=="__main__":asyncio.run(main())
