"""Real multi-gigabyte registry download, pause, restart and resume validation."""
import asyncio
import json
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ARTIFACT=ROOT/"artifacts/native/download-acceptance.json"


class Client:
    async def start(self,directory):
        self.child=await asyncio.create_subprocess_exec(str(ROOT/"release/native/Wixal.app/Contents/Resources/engine/wixal-engine"),"--data",str(directory),"--runtime",str(ROOT/"runtime/ollama"),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=16*1024*1024)
        self.counter=0;self.pending={}
        self.reading=asyncio.create_task(self.read())
        await self.call("hello")
        return self
    async def read(self):
        while line:=await self.child.stdout.readline():
            row=json.loads(line)
            if row["event"]=="response":
                data=row["data"];future=self.pending.pop(data["id"],None)
                if future:future.set_result(data)
    async def call(self,method,params=None):
        self.counter+=1;identifier=str(self.counter)
        future=asyncio.get_running_loop().create_future();self.pending[identifier]=future
        self.child.stdin.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+"\n").encode());await self.child.stdin.drain()
        result=await asyncio.wait_for(future,150)
        if result.get("error"):raise RuntimeError(result["error"])
        return result["result"]
    async def close(self):
        self.child.stdin.close()
        try:await asyncio.wait_for(self.child.wait(),30)
        except asyncio.TimeoutError:self.child.kill();await self.child.wait()
        await self.reading


async def main():
    report=dict(status="running",model="qwen3:4b",stages={},started=time.time())
    def record(name,data):
        report["stages"][name]=data;ARTIFACT.write_text(json.dumps(report,indent=2));print(name+": "+json.dumps(data),flush=True)
    with tempfile.TemporaryDirectory(prefix="wixal-download-acceptance-") as directory:
        client=await Client().start(Path(directory)/"data")
        try:
            status=await client.call("model-pull",dict(name=report["model"]))
            download=status["downloads"][-1]
            for _ in range(180):
                status=await client.call("model-status");download=next(d for d in status["downloads"] if d["id"]==download["id"])
                if download["state"]=="failed":raise RuntimeError(download.get("error","Download failed"))
                if download["total"]>2*1024**3 and download["completed"]>32*1024**2:break
                await asyncio.sleep(1)
            else:raise RuntimeError("Registry transfer did not reach a measurable multi-gigabyte layer")
            await client.call("model-download-action",dict(id=download["id"],action="pause"))
            status=await client.call("model-status");paused=next(d for d in status["downloads"] if d["id"]==download["id"])
            assert paused["state"]=="paused",paused
            record("pause",dict(completed=paused["completed"],total=paused["total"],state=paused["state"]))
            await client.call("model-download-action",dict(id=download["id"],action="resume"))
            await asyncio.sleep(2)
            # Kill the actual helper to reproduce interrupted-launch recovery.
            client.child.kill();await client.child.wait();await client.reading
            client=await Client().start(Path(directory)/"data")
            status=await client.call("model-status");interrupted=next(d for d in status["downloads"] if d["id"]==download["id"])
            assert interrupted["state"]=="paused",interrupted
            record("interruptedRestart",dict(state=interrupted["state"],status=interrupted["status"]))
            await client.call("model-download-action",dict(id=download["id"],action="resume"))
            for _ in range(900):
                status=await client.call("model-status");finished=next(d for d in status["downloads"] if d["id"]==download["id"])
                if finished["state"]=="failed":raise RuntimeError(finished.get("error","Download failed"))
                if finished["state"]=="completed":break
                await asyncio.sleep(1)
            else:raise RuntimeError("Download did not complete in 15 minutes")
            models=await client.call("models")
            model=next(m for m in models if m["name"]==report["model"])
            record("resume",dict(completed=finished["completed"],total=finished["total"],state=finished["state"],digest=model["digest"],size=model["size"]))
            report["status"]="passed"
        except BaseException as error:
            report["status"]="failed";report["error"]=str(error);raise
        finally:
            await client.close();report["finished"]=time.time();ARTIFACT.write_text(json.dumps(report,indent=2))


if __name__=="__main__":asyncio.run(main())
