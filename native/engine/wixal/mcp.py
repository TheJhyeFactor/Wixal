from .mcp_names import tool_name
"""Bounded MCP stdio client. Servers are started only by an explicit UI/CLI action."""
import asyncio
import json
import os
import signal
from .storage import identity


class MCP:
    def __init__(self,directory=None,open_url=None):
        self.connections = {}
        self.directory=directory;self.open_url=open_url

    async def connect(self, config, root):
        await self.disconnect(config["id"])
        if config.get('transport')=='http':
            from .remote_mcp import Remote
            remote=Remote(config,self.directory,self.open_url)
            definitions=await remote.start()
            self.connections[config['id']]=dict(remote=remote,definitions=definitions)
            return self.definitions()
        env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "TMPDIR") if k in os.environ}
        process = await asyncio.create_subprocess_exec(config["command"], *config.get("args", []), cwd=root,
            env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=1024*1024, start_new_session=True)
        connection = dict(process=process, lock=asyncio.Lock(), definitions=[])
        self.connections[config["id"]] = connection
        try:
            await self.call(config["id"], "initialize", dict(protocolVersion="2024-11-05", capabilities={}, clientInfo=dict(name="Wixal Native", version="1")))
            process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            await process.stdin.drain()
            cursor, seen = None, set()
            while True:
                page = await self.call(config["id"], "tools/list", {"cursor": cursor} if cursor else {})
                for tool in page.get("tools", []):
                    name = tool["name"]
                    if name in seen or len(seen) >= 80:
                        raise ValueError("MCP catalog has duplicates or exceeds 80 tools")
                    seen.add(name)
                    connection["definitions"].append(dict(type="function", function=dict(
                        name=tool_name(config["id"],name), description=f"{config['name']}: {tool.get('description', name)}",
                        parameters=tool.get("inputSchema", dict(type="object")), original=name)))
                next_cursor = page.get("nextCursor")
                if not next_cursor:
                    break
                if next_cursor == cursor:
                    raise ValueError("Repeated MCP cursor")
                cursor = next_cursor
            return self.definitions()
        except BaseException:
            await self.disconnect(config["id"])
            raise

    def definitions(self):
        return [t for c in self.connections.values() for t in c["definitions"]]

    async def call(self, server_id, method, params):
        conn = self.connections[server_id]
        if 'remote' in conn:return await conn['remote'].call(method,params)
        async with conn["lock"]:
            process = conn["process"]
            request_id = identity()
            process.stdin.write((json.dumps(dict(jsonrpc="2.0", id=request_id, method=method, params=params)) + "\n").encode())
            await process.stdin.drain()
            async def receive():
                for _ in range(100):
                    line = await process.stdout.readline()
                    if not line:
                        raise RuntimeError("MCP server disconnected")
                    message = json.loads(line)
                    if message.get("id") == request_id:
                        if "error" in message:
                            raise RuntimeError(str(message["error"]))
                        return message.get("result", {})
                raise RuntimeError("MCP response flood")
            try:
                return await asyncio.wait_for(receive(), 60)
            except BaseException:
                # A cancelled call cannot leave a late response attached to a later call.
                await self.disconnect(server_id)
                raise

    async def execute(self, name, args):
        for server_id, conn in list(self.connections.items()):
            tool = next((t for t in conn["definitions"] if t["function"]["name"] == name), None)
            if tool:
                result = await self.call(server_id, "tools/call", dict(name=tool["function"]["original"], arguments=args))
                if result.get("isError"):
                    raise RuntimeError(json.dumps(result))
                return "\n".join(c.get("text", f"[{c.get('type')} result omitted; save as a project artifact]") for c in result.get("content", []))
        raise ValueError("MCP tool is disconnected")

    async def disconnect(self, server_id):
        conn = self.connections.pop(server_id, None)
        if conn and 'remote' in conn:
            await conn['remote'].close();return
        if conn and conn["process"].returncode is None:
            try: os.killpg(conn["process"].pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try:
                await asyncio.wait_for(conn["process"].wait(), 3)
            except asyncio.TimeoutError:
                try: os.killpg(conn["process"].pid, signal.SIGKILL)
                except ProcessLookupError: pass
                await conn["process"].wait()

    async def close(self):
        for server_id in list(self.connections):
            await self.disconnect(server_id)
