import asyncio
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.mcp import MCP
from wixal.remote_mcp import validate_url

class RemoteMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_initialize_discovery_call_and_disconnect(self):
        self.requests=[]
        async def serve(reader,writer):
            headers=await reader.readuntil(b'\r\n\r\n');lines=headers.decode().split('\r\n');h=dict(line.split(': ',1) for line in lines[1:] if ': ' in line)
            raw=await reader.readexactly(int(h.get('Content-Length',h.get('content-length','0'))));request=json.loads(raw) if raw else {}
            self.requests.append((lines[0],h,request))
            method=request.get('method')
            if method=='initialize':result=dict(protocolVersion='2025-11-25',capabilities=dict(tools={}),serverInfo=dict(name='Acceptance server',version='1'))
            elif method=='tools/list':result=dict(tools=[dict(name='hello',description='Return exact request',inputSchema=dict(type='object',properties=dict(text=dict(type='string'))))])
            elif method=='tools/call':result=dict(content=[dict(type='text',text=request['params']['arguments']['text'])])
            else:result={}
            body=json.dumps(dict(jsonrpc='2.0',id=request.get('id'),result=result)).encode() if request.get('id') else b''
            writer.write(b'HTTP/1.1 '+(b'204 No Content' if lines[0].startswith('DELETE ') else b'200 OK' if body else b'202 Accepted')+b'\r\nContent-Type: application/json\r\nMcp-Session-Id: test-session\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);await writer.drain();writer.close();await writer.wait_closed()
        server=await asyncio.start_server(serve,'127.0.0.1',0)
        client=MCP()
        try:
            definitions=await client.connect(dict(id='acceptance',name='HTTP',transport='http',url=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}/mcp'),None)
            self.assertEqual(len(definitions),1)
            self.assertEqual(await client.execute(definitions[0]['function']['name'],dict(text='Actual HTTP round trip')),'Actual HTTP round trip')
            self.assertTrue(any(r[2].get('method')=='tools/call' for r in self.requests))
        finally:await client.close();server.close();await server.wait_closed()
        self.assertEqual(client.connections,{})
    def test_url_requires_tls_and_has_no_embedded_credentials(self):
        for url in ('http://example.com/mcp','https://user:pass@example.com/mcp','https://example.com/mcp?token=abc'):
            with self.assertRaises(ValueError):validate_url(url)
