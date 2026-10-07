"""Real helper, bundled model runner and local Nmap acceptance; no mocked services.

Writes each completed stage immediately. --source exercises current development code.
The default exercises the packaged helper. User storage and models are read only inputs.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",action="store_true")
    args=parser.parse_args()
    artifact=ROOT/"artifacts/native"/("acceptance-source.json" if args.source else "acceptance-packaged.json")
    artifact.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status="running",implementation="source" if args.source else "packaged",stages={},started=time.time())
    def checkpoint(name,result):
        report["stages"][name]=result
        artifact.write_text(json.dumps(report,indent=2))
        print(name+": "+json.dumps(result),flush=True)
    with tempfile.TemporaryDirectory(prefix="wixal-acceptance-") as directory:
        project=Path(directory)/"project";project.mkdir()
        runtime=ROOT/"runtime/ollama"
        command=[sys.executable,str(ROOT/"native/engine/engine_main.py")] if args.source else [str(ROOT/"release/native/Wixal Native.app/Contents/Resources/engine/wixal-engine")]
        stderr=(ROOT/"artifacts/native/acceptance-stderr.log").open("w")
        child=await asyncio.create_subprocess_exec(*command,"--data",str(Path(directory)/"data"),"--runtime",str(runtime),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=stderr,limit=16*1024*1024)
        pending={};counter=0;events=[]
        async def reader():
            while line:=await child.stdout.readline():
                message=json.loads(line);event,data=message["event"],message["data"]
                if event=="response":
                    future=pending.pop(data["id"],None)
                    if future and not future.done():future.set_result(data)
                elif event in ("activity","error","assessment-progress","operation"):
                    events.append(message)
            for future in pending.values():
                if not future.done():future.set_exception(RuntimeError("Helper disconnected"))
        reading=asyncio.create_task(reader())
        def send(method,params=None):
            nonlocal counter
            counter+=1;identifier=str(counter)
            future=asyncio.get_running_loop().create_future();pending[identifier]=future
            child.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+"\n").encode())
            return identifier,future
        async def call(method,params=None,timeout=660):
            _,future=send(method,params);await child.stdin.drain()
            data=await asyncio.wait_for(asyncio.shield(future),timeout)
            if data.get("error"):raise RuntimeError(data["error"])
            return data["result"]
        async def session():
            hello=await call("hello")
            return next(s for s in hello["state"]["sessions"] if s["id"]==hello["state"]["activeSession"])
        try:
            await call("hello")
            legacy=Path.home()/"Library/Application Support/Wixal/workspace.json"
            if legacy.exists():
                before=hashlib.sha256(legacy.read_bytes()).hexdigest()
                imported=await call("legacy-import",dict(path=str(legacy)))
                repeated=await call("legacy-import",dict(path=str(legacy)))
                assert not any(repeated["counts"].values()),repeated
                assert hashlib.sha256(legacy.read_bytes()).hexdigest()==before
                checkpoint("legacyImport",dict(counts=imported["counts"],warnings=imported["warnings"],idempotent=True,sourceUnchanged=True))
            await call("project-add",dict(root=str(project)))
            inventory=await call("model-imports")
            choice=next(i for i in inventory if i["name"]=="gemma3:12b")
            models=await call("model-import",choice,1900)
            model=next(m for m in models if m["name"]==choice["name"])
            assert "vision" in model["capabilities"] and "tools" not in model["capabilities"]
            checkpoint("realImport",dict(name=model["name"],capabilities=model["capabilities"]))
            await call("settings",dict(model=model["name"],mode="chat",contextSize=4096,approvalMode="review"))
            image=ROOT/"assets/icon-variants/sakura.png"
            if not image.exists():image=next((ROOT/"assets").rglob("*.png"))
            task=await call("chat",dict(text="Describe this app icon in one brief sentence. Do not use tools.",attachments=[dict(type="image",name=image.name,base64=base64.b64encode(image.read_bytes()).decode())]))
            saved=await session();reply=next(m for m in reversed(saved["messages"]) if m["role"]=="assistant")
            assert task["status"]=="completed" and reply["content"] and reply["usage"]["eval_count"]>0
            checkpoint("realImage",dict(content=reply["content"],usage=reply["usage"]))
            await call("benchmark-start",dict(name=model["name"]))
            for _ in range(200):
                status=await call("model-status")
                if status.get("benchmarks"):break
                await asyncio.sleep(1)
            else:raise RuntimeError("Benchmark did not complete")
            benchmark=status["benchmarks"][-1]
            assert not benchmark["fixture"] and benchmark["totalTokens"]>0
            checkpoint("realBenchmark",benchmark)
            await call("settings",dict(approvalMode="bypass"))
            listener=await asyncio.start_server(lambda r,w:w.close(),"127.0.0.1",0)
            port=listener.sockets[0].getsockname()[1]
            try:
                scan=await call("assessment-run",dict(name="network_scan",arguments=dict(target="127.0.0.1",profile="ports",ports=str(port),timeout_seconds=30)))
                assert str(port) in scan.get("output","") and scan.get("exitCode")==0,scan
                checkpoint("realNmap",dict(target="127.0.0.1",port=port,exitCode=scan["exitCode"]))
            finally:listener.close();await listener.wait_closed()
            await call("settings",dict(approvalMode="review",autoSummary=True))
            # Actual project source, real responses and successive turns exercise context pressure.
            for path in (ROOT/"native/engine/wixal/agent.py",ROOT/"native/engine/wixal/service.py"):
                task=await call("chat",dict(text="Review this source. Give three concise observations about cancellation and context management, using only the supplied text.\n"+path.read_text()[:20000]))
                assert task["status"]=="completed",task
            before=await session();info=await call("context-info")
            assert info["messageCount"]==len(before["messages"]) and info["imageTokens"]>=0
            handoff=await call("session-handoff")
            assert handoff["summary"]["content"] and handoff["handoff"]["sourceSession"]==before["id"]
            checkpoint("realContinuation",dict(summaryMethod=handoff["summary"]["method"],fallbackReason=handoff["summary"].get("fallbackReason"),summaryCharacters=len(handoff["summary"]["content"]),context=info))
            identifier,future=send("chat",dict(text="Write a detailed, 2000 word explanation of Python asynchronous cancellation."))
            await child.stdin.drain();await asyncio.sleep(2)
            ack=await call("cancel-request",dict(id=identifier))
            result=await asyncio.wait_for(future,20)
            assert ack["cancelled"] and result.get("cancelled"),result
            assert await call("ping") is True
            checkpoint("realCancellation",dict(acknowledged=True,helperResponsive=True))
            tools_choice=next(i for i in inventory if i["name"]=="gpt-oss:20b")
            models=await call("model-import",tools_choice,1900)
            assert "tools" in next(m for m in models if m["name"]==tools_choice["name"])["capabilities"]
            await call("settings",dict(model=tools_choice["name"],mode="agent",approvalMode="bypass",contextSize=8192))
            (project/"proof.txt").write_text("native-acceptance-real-file-20261007\n")
            task=await call("chat",dict(text="Use @read_file to read proof.txt in this project, and report its exact content."))
            current=await session();outputs=[m["content"] for m in current["messages"] if m["role"]=="tool"]
            assert task["status"]=="completed" and any("native-acceptance-real-file-20261007" in output for output in outputs),task
            checkpoint("realModelTool",dict(model=tools_choice["name"],toolResults=outputs[-3:]))
            report["status"]="passed"
        except BaseException as error:
            report["status"]="failed";report["error"]=str(error);raise
        finally:
            report["finished"]=time.time();report["events"]=events[-20:]
            artifact.write_text(json.dumps(report,indent=2))
            child.stdin.close()
            try:await asyncio.wait_for(child.wait(),30)
            except asyncio.TimeoutError:child.kill();await child.wait()
            await reading;stderr.close()


if __name__=="__main__":asyncio.run(main())
