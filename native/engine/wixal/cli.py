"""Terminal client for the same Python engine used by the Swift app."""
import asyncio
import json
import os
from pathlib import Path
from .storage import identity
from .service import Service, parser


async def run(args):
    service = None
    async def answer(event, data):
        if event=="host":
            await service.dispatch("respond", dict(id=data["id"], value=dict(error="Rendered browser actions require Wixal Native desktop")))
            return
        print("\nReview: " + json.dumps({k:v for k,v in data.items() if k!="id"}, indent=2))
        approved = (await asyncio.to_thread(input, "Approve? [y/N] ")).strip().lower()=="y"
        await service.dispatch("respond", dict(id=data["id"], value=approved))
    def emit(event, data):
        if event=="token":
            print(data["text"], end="", flush=True)
        elif event in ("review", "host"):
            asyncio.create_task(answer(event,data))
        elif event=="tool-result":
            print("\n["+data["name"]+"] "+data["result"][:2000])
    service = Service(args.data, args.runtime, emit, args.endpoint)
    try:
        print("Wixal Native terminal. /help for commands; /quit to exit.")
        while True:
            text = await asyncio.to_thread(input, "\nwixal> ")
            try:
                if text=="/quit":
                    break
                if text=="/help":
                    print("/project PATH, /models, /model NAME, /new, /import-workspace, /tasks, /resume ID, /quit")
                elif text.startswith("/project "):
                    await service.dispatch("project-add",dict(root=text[9:].strip()))
                elif text=="/models":
                    print(json.dumps(await service.dispatch("models",{}),indent=2))
                elif text.startswith("/model "):
                    await service.dispatch("settings",dict(model=text[7:].strip()))
                elif text=="/new":
                    await service.dispatch("session-new",{})
                elif text=="/import-workspace":
                    print(await service.dispatch("legacy-import",{}))
                elif text=="/tasks":
                    print(json.dumps(service.store.data["tasks"],indent=2))
                elif text.startswith("/resume "):
                    await service.dispatch("chat",dict(text="",resume=text[8:].strip()))
                elif text.strip():
                    await service.dispatch("chat",dict(text=text))
            except Exception as error:
                print("\nError: "+str(error))
    finally:
        await service.close()


async def connected(args):
    reader, writer = await asyncio.open_unix_connection(str(Path(args.data)/"engine.sock"),limit=64*1024*1024)
    async def send(method,params):
        request_id=identity()
        writer.write((json.dumps(dict(id=request_id,method=method,params=params))+"\n").encode());await writer.drain()
        return request_id
    async def call(method,params=None):
        request_id=await send(method,params or {})
        while line := await reader.readline():
            message=json.loads(line);event=message["event"];data=message["data"]
            if event=="token":print(data["text"],end="",flush=True)
            elif event=="tool-result":print("\n["+data["name"]+"] "+data["result"][:2000])
            elif event=="review":
                print("\nReview: "+json.dumps({k:v for k,v in data.items() if k!="id"},indent=2))
                answer=(await asyncio.to_thread(input,"Approve? [y/N] ")).strip().lower()=="y"
                await send("respond",dict(id=data["id"],value=answer))
            elif event=="response" and data["id"]==request_id:
                if data.get("error"):raise RuntimeError(data["error"])
                return data.get("result")
        raise RuntimeError("Desktop engine disconnected")
    try:
        await call("hello")
        print("Connected to the Wixal Native desktop engine. /help for commands.")
        while True:
            text=await asyncio.to_thread(input,"\nwixal> ")
            try:
                if text=="/quit":break
                if text=="/help":print("/project PATH, /models, /model NAME, /new, /tasks, /stop, /quit")
                elif text.startswith("/project "):await call("project-add",dict(root=text[9:].strip()))
                elif text=="/models":print(json.dumps(await call("models"),indent=2))
                elif text.startswith("/model "):await call("settings",dict(model=text[7:].strip()))
                elif text=="/new":await call("session-new")
                elif text=="/tasks":print(json.dumps((await call("hello"))["state"]["tasks"],indent=2))
                elif text=="/stop":await call("stop")
                elif text.strip():await call("chat",dict(text=text))
            except Exception as error:print("\nError: "+str(error))
    finally:
        writer.close();await writer.wait_closed()

async def choose(args):
    if (Path(args.data)/"engine.sock").exists():
        try: return await connected(args)
        except (FileNotFoundError,ConnectionRefusedError):pass
    await run(args)


def main():
    os.umask(0o077)
    asyncio.run(choose(parser().parse_args()))

if __name__=="__main__":
    main()
