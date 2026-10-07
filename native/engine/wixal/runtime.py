"""Port of Wixal's verified managed Ollama lifecycle and model import."""
import asyncio
import hashlib
import json
import os
import shutil
import signal
import socket
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def request_json(url, body=None, timeout=20, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(8*1024*1024)
        return json.loads(raw) if raw.strip() else {}


async def stream_json(endpoint, path, body):
    """Bounded, cancellable local HTTP NDJSON. Closing the task closes the transfer."""
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Model streams require an explicit loopback endpoint")
    reader, writer = await asyncio.wait_for(asyncio.open_connection(parsed.hostname, parsed.port or 80, limit=2*1024*1024),20)
    encoded = json.dumps(body).encode()
    try:
        writer.write((f"POST {path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nContent-Type: application/json\r\nContent-Length: {len(encoded)}\r\nConnection: close\r\n\r\n").encode()+encoded)
        await writer.drain()
        headers = (await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"),120)).decode().split("\r\n")
        status = int(headers[0].split()[1])
        if status != 200:
            error = await asyncio.wait_for(reader.read(8192),10)
            raise RuntimeError(f"Local model engine returned HTTP {status}: {error.decode(errors='replace')[:800]}")
        chunked = any(line.lower().startswith("transfer-encoding:") and "chunked" in line.lower() for line in headers)
        buffer = b""
        while True:
            if chunked:
                line = await asyncio.wait_for(reader.readline(),120)
                if not line: break
                count = int(line.split(b";",1)[0].strip(),16)
                if not count: break
                if count>2*1024*1024: raise ValueError("Model stream chunk is too large")
                buffer += await asyncio.wait_for(reader.readexactly(count),120)
                if await reader.readexactly(2)!=b"\r\n": raise ValueError("Malformed model stream")
            else:
                line = await asyncio.wait_for(reader.readline(),120)
                if not line: break
                buffer += line
            if len(buffer)>2*1024*1024: raise ValueError("Model stream line is too large")
            while b"\n" in buffer:
                line,buffer = buffer.split(b"\n",1)
                if line.strip():
                    item = json.loads(line)
                    if item.get("error"): raise RuntimeError(str(item["error"])[:800])
                    yield item
        if buffer.strip():
            item = json.loads(buffer)
            if item.get("error"): raise RuntimeError(str(item["error"])[:800])
            yield item
    finally:
        writer.close()
        try: await writer.wait_closed()
        except (OSError, asyncio.CancelledError): pass


class Runtime:
    def __init__(self, directory, payload, emit=lambda *_: None, endpoint=None):
        self.directory, self.payload = Path(directory), Path(payload)
        self.models = self.directory / "models"
        self.models.mkdir(parents=True, exist_ok=True)
        self.emit, self.url = emit, endpoint
        self.external = endpoint is not None
        self.process, self.lock, self.checked = None, asyncio.Lock(), False
        self.status, self.error, self.metadata = "external" if self.external else "stopped", "", {}

    def update_status(self, status, error=""):
        self.status, self.error = status, error
        self.emit("runtime", dict(status=status,error=error))

    def verify(self):
        manifest = json.loads((self.payload / "manifest.json").read_text())
        pin = json.loads((Path(__file__).parent / "resources" / "runtime.json").read_text())
        if manifest.get("version") != pin["version"] or manifest.get("sourceCommit") != pin["sourceCommit"]:
            raise ValueError("Bundled model engine does not match Wixal's pin")
        for entry in manifest["files"]:
            file = self.payload / entry["path"]
            if not file.resolve().is_relative_to(self.payload.resolve()):
                raise ValueError("Engine payload path escapes its directory")
            if "link" in entry:
                if not file.is_symlink() or os.readlink(file) != entry["link"]:
                    raise ValueError("Engine library link failed verification")
            else:
                with file.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
                        raise ValueError(f"Engine integrity failure: {entry['path']}")
        self.checked = True

    async def endpoint(self):
        async with self.lock:
            if self.external:
                return self.url
            if self.process and self.process.returncode is None:
                return self.url
            self.update_status("starting")
            if not self.checked:
                try: await asyncio.to_thread(self.verify)
                except Exception as error:
                    self.update_status("failed",str(error)); raise
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            self.url = f"http://127.0.0.1:{port}"
            env = {k: v for k, v in os.environ.items() if not k.startswith(("OLLAMA_", "DYLD_")) and not any(s in k for s in ("TOKEN", "API_KEY", "PASSWORD"))}
            env.update(OLLAMA_HOST=f"127.0.0.1:{port}", OLLAMA_MODELS=str(self.models), OLLAMA_NO_CLOUD="1",
                       OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_NUM_PARALLEL="1", OLLAMA_KEEP_ALIVE="2m", OLLAMA_KV_CACHE_TYPE="q8_0", OLLAMA_FLASH_ATTENTION="1")
            launcher=[sys.executable] if getattr(sys,"frozen",False) else [sys.executable,str(Path(__file__).parents[1]/"engine_main.py")]
            self.process = await asyncio.create_subprocess_exec(*launcher,"--supervise-runtime",str(self.payload/"ollama"),env=env,
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
            for _ in range(100):
                if self.process.returncode is not None:
                    self.update_status("failed","Local model engine exited during startup")
                    raise RuntimeError(self.error)
                try:
                    await asyncio.to_thread(request_json, self.url + "/api/version", None, 1)
                    self.update_status("ready")
                    return self.url
                except (OSError, ValueError):
                    await asyncio.sleep(.1)
            await self.stop()
            self.update_status("failed","Local model engine did not become ready")
            raise TimeoutError(self.error)

    async def stop(self):
        if self.process and self.process.returncode is None:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
                await asyncio.wait_for(self.process.wait(), 5)
            except (ProcessLookupError, asyncio.TimeoutError):
                if self.process.returncode is None:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    await self.process.wait()
        self.process = None
        self.update_status("stopped")

    async def catalog(self):
        url = await self.endpoint()
        models = (await asyncio.to_thread(request_json, url + "/api/tags"))["models"]
        semaphore=asyncio.Semaphore(4)
        async def enrich(model):
            try:
                key=(model["name"],model.get("digest",model.get("modified_at",model.get("size"))))
                import time
                cached=self.metadata.get(key)
                if cached and time.monotonic()-cached[0]<300: info=cached[1]
                else:
                    async with semaphore: info = await asyncio.to_thread(request_json, url + "/api/show", {"model": model["name"]},8)
                    self.metadata[key]=(time.monotonic(),info)
                values=info.get("model_info",{})
                def number(suffix): return next((float(v) for k,v in values.items() if k.endswith(suffix) and isinstance(v,(int,float))),0)
                layers,embedding,heads,kvheads=[number(k) for k in (".block_count",".embedding_length",".attention.head_count",".attention.head_count_kv")]
                model.update(capabilities=info.get("capabilities", []), details=info.get("details", {}),
                    thinking=info.get("thinking"),kvBytesPerToken=int(2*layers*(embedding/heads)*kvheads) if all((layers,embedding,heads,kvheads)) else None,
                    contextLength=next((v for k, v in values.items() if k.endswith(".context_length")), 8192))
            except (OSError,ValueError):
                model["capabilities"] = []
        await asyncio.gather(*(enrich(model) for model in models))
        if len(self.metadata)>256: self.metadata=dict(list(self.metadata.items())[-256:])
        return models

    def imports(self):
        roots = [Path.home() / ".ollama/models", Path.home() / "Library/Application Support/Wixal/local-runtime/models", Path.home() / "Library/Application Support/Wixal Native/local-runtime/models"]
        result = []
        for root in roots:
            if root.resolve() == self.models.resolve():
                continue
            for file in sorted(root.glob("manifests/*/*/*/*")):
                if file.is_file() and not file.is_symlink():
                    parts = file.relative_to(root / "manifests").parts
                    result.append(dict(name=f"{parts[-2]}:{parts[-1]}", source=str(root), manifest=str(file.relative_to(root))))
        return result

    def import_model(self, manifest, cancelled=None):
        def check_cancelled():
            if cancelled is not None and cancelled.is_set():
                raise InterruptedError("Model import cancelled before installation")
        check_cancelled()
        item = next((v for v in self.imports() if v["manifest"] == manifest.get("manifest") and v["source"] == manifest.get("source")), None)
        if not item:
            raise ValueError("Choose a model from the import inventory")
        root = Path(item["source"]).resolve()
        file = root / item["manifest"]
        data = json.loads(file.read_text())
        for layer in [data.get("config", {}), *data.get("layers", [])]:
            digest = layer.get("digest", "")
            if not __import__("re").fullmatch(r"sha256:[a-f0-9]{64}", digest):
                raise ValueError("Invalid model digest")
            blob = root / "blobs" / digest.replace(":", "-")
            if blob.is_symlink() or not blob.resolve().is_relative_to(root):
                raise ValueError("Model blob escapes its library")
            with blob.open("rb") as stream:
                checksum=hashlib.sha256()
                while chunk:=stream.read(4*1024*1024):
                    check_cancelled()
                    checksum.update(chunk)
                if checksum.hexdigest() != digest[7:]:
                    raise ValueError("Model blob failed verification")
            target = self.models / "blobs" / blob.name
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                # Independent APFS clone, with an ordinary copy fallback.
                import ctypes
                clone=getattr(ctypes.CDLL(None),"clonefile",None)
                if clone is None or clone(os.fsencode(blob), os.fsencode(target), 0) != 0:
                    partial=target.with_name(target.name+".importing")
                    try:
                        with blob.open("rb") as source, partial.open("wb") as destination:
                            while chunk:=source.read(4*1024*1024):
                                check_cancelled();destination.write(chunk)
                        check_cancelled();partial.replace(target)
                    finally: partial.unlink(missing_ok=True)
        check_cancelled()
        target = self.models / item["manifest"]
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(json.dumps(data))
        temp.replace(target)
        return item["name"]
