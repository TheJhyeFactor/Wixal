"""Same-origin OAuth authorization-code + S256 PKCE, with a short-lived loopback callback."""
import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode, urlsplit, parse_qs, urljoin
from .storage import identity, now
from .security_assurance import api_plan
from . import engagement_policy as policy


class OAuth:
    def __init__(self,assurance):
        self.assurance=assurance;self.flows={};self.callbacks=set()

    async def close(self):
        flows=list(self.flows.values());self.flows.clear()
        for flow in flows:
            flow['server'].close();flow['expiry'].cancel()
            flow['record'].update(status='interrupted')
        await asyncio.gather(*(f['server'].wait_closed() for f in flows))
        callbacks=list(self.callbacks)
        for task in callbacks:task.cancel()
        await asyncio.gather(*callbacks,return_exceptions=True)

    async def start(self,params):
        manager=self.assurance.manager;engagement=manager.get(params.get('engagementId'))
        target=manager.record('securityTargets',params.get('targetId'),engagement)
        run=dict(targetId=target['id'],address=target['address'],capability='api_observe',scopeRevision=engagement['scopeRevision'])
        manager.authorize_run(run)
        paths=api_plan(dict(paths=[params.get('authorizationPath','/authorize'),params.get('tokenPath','/token')]))['paths']
        if len(paths)!=2:raise ValueError('Authorization and token endpoints must be distinct')
        client=params.get('clientId');label=policy.text(params.get('label'),'OAuth identity label',100)
        if not isinstance(client,str) or not client or len(client)>200 or any(c.isspace() or ord(c)<32 for c in client):raise ValueError('Choose a public OAuth client identifier')
        scope=params.get('scope','')
        if not isinstance(scope,str) or len(scope)>500 or any(ord(c)<32 for c in scope):raise ValueError('Invalid OAuth scope')
        parsed=urlsplit(target['address'])
        if parsed.scheme!='https' and parsed.hostname!='127.0.0.1':raise ValueError('OAuth requires HTTPS except for an owned 127.0.0.1 lab')
        if len(self.flows)>=4:raise ValueError('Four OAuth flows are already pending')
        if not await manager.workspace.service.ask('review',dict(name='security_oauth_authorize',target=target['address'],clientId=client,scope=scope,authorizationPath=paths[0],tokenPath=paths[1],scopeRevision=engagement['scopeRevision'])):raise ValueError('OAuth flow was not approved')
        manager.authorize_run(run)
        if len(self.flows)>=4:raise ValueError('OAuth flow capacity changed during review')
        verifier=secrets.token_urlsafe(48);state=secrets.token_urlsafe(32);identifier=identity()
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        record=manager.add('securityOAuthFlows',engagement,targetId=target['id'],scopeRevision=engagement['scopeRevision'],status='waiting_callback',expires=now()+300000,label=label)
        async def callback(reader,writer):
            accepted=False;status='400 Bad Request';message='OAuth callback rejected'
            task=asyncio.current_task();self.callbacks.add(task)
            try:
                raw=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),5)
                if len(raw)>8192:raise ValueError('Oversized callback')
                line=raw.split(b'\r\n',1)[0].decode('ascii');method,path,_=line.split(' ')
                url=urlsplit(path);values=parse_qs(url.query,strict_parsing=True)
                flow=self.flows.get(identifier)
                if method!='GET' or url.path!='/callback' or not flow or now()>=record['expires'] or set(values)!={'state','code'} or any(len(v)!=1 for v in values.values()) or not hmac.compare_digest(values['state'][0],state) or not 1<=len(values['code'][0])<=4096:raise ValueError('Invalid OAuth callback')
                self.flows.pop(identifier);flow['server'].close();flow['expiry'].cancel();accepted=True
                record.update(status='exchanging')
                manager.authorize_run(run)
                from .website import bounded_request
                token=policy.current.set(dict(manager=manager,engagement=engagement,run=run))
                try:
                    response=await bounded_request(urljoin(target['address'],paths[1]),method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'},body=urlencode(dict(grant_type='authorization_code',code=values['code'][0],client_id=client,redirect_uri=flow['redirect'],code_verifier=verifier)).encode(),limit=16384)
                finally:policy.current.reset(token)
                manager.authorize_run(run)
                value=json.loads(response['body'])
                if response['status']!=200 or response['truncated'] or value.get('token_type','').lower()!='bearer' or not isinstance(value.get('access_token'),str) or type(value.get('expires_in')) is not int or value['expires_in']<60:raise ValueError('Invalid OAuth token response')
                credential=await self.assurance.dispatch('security-credential-save',dict(engagementId=engagement['id'],targetId=target['id'],label=label,secret=value['access_token'],kind='oauth_access_token',seconds=min(3600,value['expires_in'])))
                record.update(status='completed',credentialId=credential['id'])
                status='200 OK';message='OAuth identity saved in Wixal. You can close this window.'
            except asyncio.CancelledError:
                record.update(status='interrupted');raise
            except Exception:
                if accepted:record.update(status='failed')
                status='400 Bad Request';message='OAuth callback was rejected. Inspect the flow in Wixal.'
            finally:
                if accepted:manager.workspace.publish()
                data=message.encode() if 'message' in locals() else b'OAuth callback rejected'
                try:writer.write(('HTTP/1.1 '+status+'\r\nContent-Type: text/plain\r\nCache-Control: no-store\r\nContent-Length: '+str(len(data))+'\r\nConnection: close\r\n\r\n').encode()+data);await writer.drain()
                except OSError:pass
                writer.close()
                self.callbacks.discard(task)
                try:await writer.wait_closed()
                except OSError:pass
        server=await asyncio.start_server(callback,'127.0.0.1',0,limit=8192)
        redirect='http://127.0.0.1:'+str(server.sockets[0].getsockname()[1])+'/callback'
        async def expire():
            await asyncio.sleep(300)
            flow=self.flows.pop(identifier,None)
            if flow:server.close();await server.wait_closed();record.update(status='expired');manager.workspace.publish()
        self.flows[identifier]=dict(server=server,expiry=asyncio.create_task(expire()),redirect=redirect,record=record)
        authorization=urljoin(target['address'],paths[0])+'?'+urlencode(dict(response_type='code',client_id=client,redirect_uri=redirect,scope=scope,state=state,code_challenge=challenge,code_challenge_method='S256'))
        manager.workspace.publish()
        return dict(flowId=record['id'],authorizationUrl=authorization,redirectUri=redirect,expires=record['expires'])
