"""Streamable HTTP and OAuth via the official MCP SDK; credentials stay in Keychain."""
import asyncio
import urllib.parse
from pathlib import Path
from .account import Keychain
from .mcp_names import tool_name


def validate_url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','::1','localhost')):
        raise ValueError('Remote MCP requires HTTPS; HTTP is allowed only on loopback')
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError('Use a server endpoint without credentials, query parameters or fragments')
    return url


class Vault:
    def __init__(self,directory,server_id):
        self.keychain=Keychain(Path(directory)/'mcp'/server_id);self.keychain.account=b'mcp-oauth'
    async def read(self):return await asyncio.to_thread(self.keychain.get) or {}
    async def write(self,key,value):
        record=await self.read();record[key]=value.model_dump(mode='json');await asyncio.to_thread(self.keychain.set,record)
    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken
        value=(await self.read()).get('tokens');return OAuthToken.model_validate(value) if value else None
    async def set_tokens(self,value):await self.write('tokens',value)
    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        value=(await self.read()).get('client');return OAuthClientInformationFull.model_validate(value) if value else None
    async def set_client_info(self,value):await self.write('client',value)
    async def clear(self):await asyncio.to_thread(self.keychain.set,None)


class Remote:
    def __init__(self,config,directory,open_url):
        self.config=config;self.directory=directory;self.open_url=open_url;self.queue=asyncio.Queue();self.worker=None;self.listener=None
    async def start(self):
        self.ready=asyncio.get_running_loop().create_future();self.worker=asyncio.create_task(self.run())
        try:return await asyncio.wait_for(asyncio.shield(self.ready),300 if self.config.get('oauth') else 30)
        except BaseException:
            await self.close();raise
    async def oauth(self):
        from mcp.client.auth import OAuthClientProvider
        from mcp.shared.auth import OAuthClientMetadata, AuthorizationCodeResult
        vault=Vault(self.directory,self.config['id']);client=await vault.get_client_info()
        old_redirect=str(client.redirect_uris[0]) if client and client.redirect_uris else None
        port=urllib.parse.urlsplit(old_redirect).port if old_redirect else 0
        callback=asyncio.get_running_loop().create_future()
        async def receive(reader,writer):
            try:
                line=await asyncio.wait_for(reader.readline(),5)
                request=line.decode().split()
                target=urllib.parse.urlsplit(request[1]) if len(request)>1 else None
                values=urllib.parse.parse_qs(target.query) if target else {}
                accepted=bool(target and target.path=='/callback' and values.get('code') and not callback.done())
                if accepted:callback.set_result(AuthorizationCodeResult(code=values['code'][0],state=values.get('state',[None])[0],iss=values.get('iss',[None])[0]))
                body=b'You can return to Wixal.' if accepted else b'Invalid or expired callback.'
                writer.write(b'HTTP/1.1 '+(b'200 OK' if accepted else b'400 Bad Request')+b'\r\nContent-Type: text/plain\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);await writer.drain()
            except (OSError,ValueError,TimeoutError):pass
            finally:writer.close();await writer.wait_closed()
        self.listener=await asyncio.start_server(receive,'127.0.0.1',port,limit=8192)
        redirect=f'http://127.0.0.1:{self.listener.sockets[0].getsockname()[1]}/callback'
        metadata=OAuthClientMetadata(client_name='Wixal Native',redirect_uris=[redirect],token_endpoint_auth_method='none',grant_types=['authorization_code','refresh_token'],scope=self.config.get('scope') or None)
        async def browse(url):await self.open_url(url)
        async def get_callback():return await asyncio.wait_for(asyncio.shield(callback),240)
        provider=OAuthClientProvider(self.config['url'],metadata,vault,browse,get_callback)
        if self.config.get('clientId') and not client:
            from mcp.shared.auth import OAuthClientInformationFull
            await vault.set_client_info(OAuthClientInformationFull(**metadata.model_dump(),client_id=self.config['clientId']))
        return provider
    async def run(self):
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        active=None
        try:
            auth=await self.oauth() if self.config.get('oauth') else None
            async with httpx2.AsyncClient(auth=auth,timeout=httpx2.Timeout(30,read=60),follow_redirects=False) as http:
                async with Client(streamable_http_client(validate_url(self.config['url']),http_client=http),read_timeout_seconds=60) as client:
                    definitions=[];cursor=None;seen=set()
                    while True:
                        page=await client.list_tools(cursor=cursor,cache_mode='bypass')
                        for tool in page.tools:
                            if tool.name in seen or len(seen)>=80:raise ValueError('MCP catalog has duplicates or exceeds 80 tools')
                            seen.add(tool.name)
                            definitions.append(dict(type='function',function=dict(name=tool_name(self.config["id"],tool.name),description=f"{self.config['name']}: {tool.description or tool.name}",parameters=tool.input_schema,original=tool.name)))
                        next_cursor=page.next_cursor
                        if not next_cursor:break
                        if next_cursor==cursor:raise ValueError('Repeated MCP cursor')
                        cursor=next_cursor
                    self.ready.set_result(definitions)
                    while True:
                        active=await self.queue.get()
                        if active is None:break
                        method,params,future=active
                        try:
                            if method!='tools/call':raise ValueError('Unsupported remote operation')
                            result=await client.call_tool(params['name'],params.get('arguments',{}))
                            import json
                            value=result.model_dump(mode='json',by_alias=True)
                            if len(json.dumps(value))>8*1024*1024:raise ValueError('Remote MCP result exceeds 8 MB; request a smaller result')
                            if not future.done():future.set_result(value)
                        except Exception as error:
                            if not future.done():future.set_exception(RuntimeError(str(error)[:300]))
                        active=None
        except BaseException as error:
            # Do not expose OAuth responses/tokens through exception text.
            message=RuntimeError('Remote MCP connection failed. Check the endpoint and authorisation, then reconnect.')
            if not self.ready.done():self.ready.set_exception(message)
            if active and not active[2].done():active[2].set_exception(message)
            while not self.queue.empty():
                item=self.queue.get_nowait()
                if item and not item[2].done():item[2].set_exception(message)
            if isinstance(error,asyncio.CancelledError):raise
        finally:
            if self.listener:self.listener.close();await self.listener.wait_closed()
    async def call(self,method,params):
        if not self.worker or self.worker.done():raise RuntimeError('Remote MCP disconnected; reconnect before retrying')
        future=asyncio.get_running_loop().create_future();await self.queue.put((method,params,future))
        try:return await asyncio.wait_for(future,65)
        except BaseException:
            await self.close();raise
    async def close(self):
        if self.worker and not self.worker.done():
            self.worker.cancel();await asyncio.gather(self.worker,return_exceptions=True)
