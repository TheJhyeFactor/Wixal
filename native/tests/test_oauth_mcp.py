"""Actual loopback OAuth/PKCE HTTP exchanges using the production MCP SDK.
This fixture does not represent acceptance with an external account provider.
"""
import asyncio,base64,hashlib,json,sys,tempfile,unittest,urllib.parse,urllib.request
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.remote_mcp import Remote
class Vault:
    tokens=None;client=None
    def __init__(self,*args):pass
    async def get_tokens(self):return self.tokens
    async def set_tokens(self,value):Vault.tokens=value
    async def get_client_info(self):return self.client
    async def set_client_info(self,value):Vault.client=value
class OAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_registration_pkce_bearer_and_reconnect(self):
        Vault.tokens=Vault.client=None;self.authorizations=[];self.token_requests=[];base=''
        async def serve(reader,writer):
            head=(await reader.readuntil(b'\r\n\r\n')).decode();lines=head.split('\r\n');method,path,_=lines[0].split();headers=dict((k.lower(),v.strip()) for k,v in (line.split(':',1) for line in lines[1:] if ':' in line))
            raw=await reader.readexactly(int(headers.get('content-length','0')));status='200 OK';extra='';body={}
            if path.startswith('/.well-known/oauth-protected-resource'):
                body=dict(resource=base+'/mcp',authorization_servers=[base],scopes_supported=['read'])
            elif path=='/.well-known/oauth-authorization-server':
                body=dict(issuer=base,authorization_endpoint=base+'/authorize',token_endpoint=base+'/token',registration_endpoint=base+'/register',response_types_supported=['code'],code_challenge_methods_supported=['S256'],grant_types_supported=['authorization_code','refresh_token'])
            elif path=='/register':body=json.loads(raw)|dict(client_id='fixture-client')
            elif path=='/token':
                value=urllib.parse.parse_qs(raw.decode());self.token_requests.append(value)
                verifier=value['code_verifier'][0];challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
                self.assertEqual(challenge,self.authorizations[-1]['code_challenge'][0]);self.assertEqual(value['code'][0],'disposable-code')
                body=dict(access_token='disposable-fixture-access',token_type='Bearer',expires_in=3600,refresh_token='disposable-fixture-refresh',scope='read')
            elif path=='/mcp':
                if headers.get('authorization')!='Bearer disposable-fixture-access':
                    status='401 Unauthorized';extra=f'WWW-Authenticate: Bearer resource_metadata="{base}/.well-known/oauth-protected-resource"\r\n';body=dict(error='unauthorized')
                elif method=='DELETE':status='204 No Content';body=None
                elif method=='GET':status='405 Method Not Allowed';body=None
                else:
                    request=json.loads(raw)
                    if request.get('method')=='initialize':result=dict(protocolVersion='2025-11-25',capabilities=dict(tools={}),serverInfo=dict(name='OAuth fixture',version='1'))
                    elif request.get('method')=='tools/list':result=dict(tools=[])
                    else:result={}
                    if 'id' in request:body=dict(jsonrpc='2.0',id=request['id'],result=result)
                    else:status='202 Accepted';body=None
            else:status='404 Not Found';body={}
            encoded=json.dumps(body).encode() if body is not None else b''
            writer.write(f'HTTP/1.1 {status}\r\n{extra}Content-Type: application/json\r\nContent-Length: {len(encoded)}\r\nConnection: close\r\n\r\n'.encode()+encoded);await writer.drain();writer.close();await writer.wait_closed()
        server=await asyncio.start_server(serve,'127.0.0.1',0);base=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
        async def open_url(url):
            values=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query);self.authorizations.append(values)
            self.assertEqual(values['code_challenge_method'],['S256']);self.assertTrue(values['state'][0]);self.assertEqual(values['resource'],[base+'/mcp'])
            callback=values['redirect_uri'][0]+'?'+urllib.parse.urlencode(dict(code='disposable-code',state=values['state'][0]))
            def visit():
                with urllib.request.urlopen(callback,timeout=5) as response:self.assertEqual(response.status,200)
            await asyncio.to_thread(visit)
        config=dict(id='oauth-fixture',name='Fixture',transport='http',url=base+'/mcp',oauth=True)
        try:
            with tempfile.TemporaryDirectory() as directory,patch('wixal.remote_mcp.Vault',Vault):
                for _ in range(2):
                    remote=Remote(config,directory,open_url)
                    try:self.assertEqual(await remote.start(),[])
                    finally:await remote.close()
            self.assertEqual(len(self.authorizations),1);self.assertEqual(len(self.token_requests),1)
            self.assertIsNotNone(Vault.tokens);self.assertIsNotNone(Vault.client)
        finally:server.close();await server.wait_closed()
