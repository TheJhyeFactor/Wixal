"""Contributor OAuth device flow and explicit, reviewed public issue submission.

Tokens and device codes stay in this process. No maintainer credentials, agent
tools, automatic submission, or reusable upload consent are involved.
"""
import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPOSITORY='TheJhyeFactor/Wixal'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def request(url,data=None,token=None):
    allowed={'https://github.com/login/device/code','https://github.com/login/oauth/access_token',
             'https://api.github.com/user','https://api.github.com/repos/'+REPOSITORY+'/issues'}
    if url not in allowed:raise ValueError('Unsupported GitHub reporting endpoint')
    headers={'Accept':'application/json','User-Agent':'Wixal-Native-Reporting',
             'X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']='Bearer '+token
    if data is not None:
        payload=json.dumps(data).encode() if url.startswith('https://api.github.com/') else urlencode(data).encode()
        headers['Content-Type']='application/json' if url.startswith('https://api.github.com/') else 'application/x-www-form-urlencoded'
    else:payload=None
    try:
        with build_opener(NoRedirect()).open(Request(url,data=payload,headers=headers),timeout=20) as response:
            raw=response.read(256*1024+1)
            if len(raw)>256*1024:raise ValueError('GitHub response exceeds its bound')
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError('Invalid GitHub response')
            return value
    except HTTPError as error:
        code=error.code;error.close()
        raise ValueError('GitHub reporting returned HTTP '+str(code)+'. No automatic retry was made.') from None
    except (URLError,OSError,TimeoutError):raise ValueError('GitHub could not be reached. No automatic retry was made.') from None

class GitHubReporting:
    def __init__(self,client_id=None):
        if client_id is None:
            configuration=Path(__file__).parent/'resources/github-oauth.json'
            client_id=json.loads(configuration.read_text()).get('clientId','') if configuration.exists() else ''
        if client_id and not re.fullmatch(r'[A-Za-z0-9]{16,80}',client_id):raise ValueError('Invalid GitHub OAuth client ID')
        self.client_id=client_id;self.flow=None;self.token=None;self.login=None;self.lock=asyncio.Lock()
    def status(self):
        return dict(configured=bool(self.client_id),signedIn=bool(self.token),login=self.login,
                    repository=REPOSITORY,scope='public_repo',remembered=False,
                    message='' if self.client_id else 'GitHub reporting needs a registered Wixal OAuth client ID with Device Flow enabled.')
    async def call(self,url,data=None,token=None):return await asyncio.to_thread(request,url,data,token)
    async def start(self,params):
        if params.get('authorize') is not True:raise ValueError('Confirm contributor GitHub sign-in and public_repo permission')
        if not self.client_id:raise ValueError(self.status()['message'])
        async with self.lock:
            result=await self.call('https://github.com/login/device/code',dict(client_id=self.client_id,scope='public_repo'))
            if result.get('verification_uri')!='https://github.com/login/device':raise ValueError('Unexpected GitHub verification URL')
            code=result.get('device_code');user_code=result.get('user_code')
            if not isinstance(code,str) or not isinstance(user_code,str) or not code or len(code)>256 or len(user_code)>40:raise ValueError('Invalid GitHub device code')
            interval=max(5,min(60,int(result.get('interval',5))));expires=max(1,min(900,int(result.get('expires_in',900))))
            self.flow=dict(code=code,deadline=time.monotonic()+expires,interval=interval,nextPoll=time.monotonic()+interval)
            return dict(status='pending',userCode=user_code,verificationURL=result['verification_uri'],interval=interval,expiresIn=expires)
    async def poll(self):
        async with self.lock:
            if not self.flow:return dict(status='signed_in' if self.token else 'cancelled',**self.status())
            flow=self.flow
            if time.monotonic()>=flow['deadline']:self.flow=None;return dict(status='expired')
            if time.monotonic()<flow['nextPoll']:return dict(status='pending',interval=flow['interval'])
            flow['nextPoll']=time.monotonic()+flow['interval']
            result=await self.call('https://github.com/login/oauth/access_token',dict(client_id=self.client_id,device_code=flow['code'],grant_type='urn:ietf:params:oauth:grant-type:device_code'))
            error=result.get('error')
            if error=='authorization_pending':return dict(status='pending',interval=flow['interval'])
            if error=='slow_down':flow['interval']+=5;flow['nextPoll']=time.monotonic()+flow['interval'];return dict(status='pending',interval=flow['interval'])
            if error:self.flow=None;return dict(status='denied' if error=='access_denied' else 'expired')
            token=result.get('access_token')
            scopes=set(re.split(r'[, ]+',result.get('scope','')))
            if not isinstance(token,str) or not 1<=len(token)<=1024 or 'public_repo' not in scopes:raise ValueError('GitHub did not grant public issue submission permission')
            # Identity is verified before the session becomes available to submit.
            profile=await self.call('https://api.github.com/user',token=token)
            login=profile.get('login')
            if not isinstance(login,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}',login):raise ValueError('Invalid GitHub contributor identity')
            self.token=token;self.login=login;self.flow=None
            return dict(status='signed_in',**self.status())
    def cancel(self):self.flow=None;return dict(status='cancelled')
    def sign_out(self):self.flow=None;self.token=None;self.login=None;return self.status()
    async def submit(self,draft,params):
        if params.get('publish') is not True or params.get('reviewedDigest')!=draft.get('digest'):raise ValueError('Review this exact report and explicitly confirm public submission')
        if draft.get('submission'):raise ValueError('This report was already submitted or its outcome is uncertain. Check GitHub before creating another issue.')
        if not self.token:raise ValueError('Sign in with your contributor GitHub account first')
        async with self.lock:
            if draft.get('submission'):raise ValueError('Report submission already started')
            payload=dict(title=draft['title'],body=draft['body'])
            draft['submission']=dict(status='submitting',contributor=self.login)
            try:
                result=await self.call('https://api.github.com/repos/'+REPOSITORY+'/issues',payload,self.token)
                number=result.get('number');url=result.get('html_url')
                if type(number)!=int or url!='https://github.com/'+REPOSITORY+'/issues/'+str(number):raise ValueError('Unexpected GitHub issue response')
                draft['submission'].update(status='published',url=url,number=number)
                return dict(draft['submission'])
            except BaseException:
                draft['submission']['status']='unknown'
                raise
