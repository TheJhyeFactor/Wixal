"""Firebase account parity. Session secrets live in the macOS login Keychain."""
import asyncio
import ctypes
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class Keychain:
    def __init__(self, directory):
        self.service = ('app.wixal.native.account.' + hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:20]).encode()
        self.account = b'firebase-session'

    def api(self):
        library = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        library.SecKeychainFindGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        library.SecKeychainAddGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        library.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]
        library.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        library.SecKeychainItemModifyAttributesAndData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        for name in ('SecKeychainFindGenericPassword','SecKeychainAddGenericPassword','SecKeychainItemDelete','SecKeychainItemFreeContent','SecKeychainItemModifyAttributesAndData'):
            getattr(library,name).restype=ctypes.c_int32
        return library

    def release(self,item):
        core=ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        core.CFRelease.argtypes=[ctypes.c_void_p];core.CFRelease.restype=None
        core.CFRelease(item)

    def get(self):
        api = self.api(); size = ctypes.c_uint32(); data = ctypes.c_void_p()
        code = api.SecKeychainFindGenericPassword(None, len(self.service), self.service, len(self.account), self.account, ctypes.byref(size), ctypes.byref(data), None)
        if code == -25300: return None
        if code: raise ValueError('Cannot read the account session from macOS Keychain.')
        try: return json.loads(ctypes.string_at(data, size.value))
        finally: api.SecKeychainItemFreeContent(None, data)

    def set(self, value):
        api = self.api(); item = ctypes.c_void_p()
        code = api.SecKeychainFindGenericPassword(None, len(self.service), self.service, len(self.account), self.account, None, None, ctypes.byref(item))
        if code not in (0, -25300): raise ValueError('Cannot access macOS Keychain.')
        if code == 0:
            if value is not None:
                payload = json.dumps(value).encode()
                result = api.SecKeychainItemModifyAttributesAndData(item, None, len(payload), payload)
            else: result = api.SecKeychainItemDelete(item)
            self.release(item)
            if result: raise ValueError('Cannot save the account session to macOS Keychain.')
            return
        if value is not None:
            payload = json.dumps(value).encode()
            if api.SecKeychainAddGenericPassword(None, len(self.service), self.service, len(self.account), self.account, len(payload), payload, None):
                raise ValueError('Cannot save the account session to macOS Keychain.')


ERRORS = {'EMAIL_EXISTS':'That email already has an account. Sign in instead.', 'INVALID_LOGIN_CREDENTIALS':'Email or password is incorrect.', 'EMAIL_NOT_FOUND':'Email or password is incorrect.', 'INVALID_PASSWORD':'Email or password is incorrect.', 'TOO_MANY_ATTEMPTS_TRY_LATER':'Too many attempts. Try again later.', 'USER_DISABLED':'This account has been disabled.', 'OPERATION_NOT_ALLOWED':'Email sign-in is not enabled for this Firebase project.', 'CONFIGURATION_NOT_FOUND':'The account service is not initialized yet. Guest mode is available.', 'PERMISSION_DENIED':'Cloud access was denied. Verify your email and check Firebase rules.', 'INVALID_ID_TOKEN':'Your session expired. Sign in again.', 'TOKEN_EXPIRED':'Your session expired. Sign in again.'}


class AccountError(ValueError):
    def __init__(self, message, status=0, code=''):
        super().__init__(message); self.status=status; self.code=code


def request(url, body=None, method='POST', token=None):
    headers = {'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):
            raise AccountError('The account service returned an unexpected redirect.')
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            data=response.read(2*1024*1024)
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as error:
        try: value=json.loads(error.read(24000)); code=value.get('error',{}).get('message','')
        except (ValueError,AttributeError): code=''
        raise AccountError(ERRORS.get(code, 'Use a password of at least 10 characters.' if code.startswith('WEAK_PASSWORD') else 'The account service could not complete this request.'),error.code,code) from None
    except (OSError,ValueError): raise AccountError('Cannot reach the account service. Check your connection. Guest mode is available.') from None


def profile_memory(value):
    if not isinstance(value,str) or len(value)>1200: raise ValueError('Global preferences must be text of at most 1,200 characters.')
    return value.strip()


def preferences(data):
    ui=data.get('ui',{})
    if ui.get('theme') not in ('sakura','midnight','forest','paper') or ui.get('textSize') not in (13,15,17) or not isinstance(ui.get('reduceMotion'),bool) or not isinstance(ui.get('sidebarCollapsed'),bool): raise ValueError('Invalid workspace preset.')
    if data.get('contextSize') not in (4096,8192,16384,32768,65536,131072) or data.get('mode') not in ('chat','agent') or not isinstance(data.get('autoSummary'),bool): raise ValueError('Invalid workspace preset.')
    return dict(ui={key:ui[key] for key in ('theme','textSize','reduceMotion','sidebarCollapsed')},contextSize=min(32768,data['contextSize']),mode=data['mode'],autoSummary=data['autoSummary'])


class Accounts:
    def __init__(self, directory, config=None, vault=None, transport=request):
        self.config=config if config is not None else json.loads((Path(__file__).parent/'resources/firebase-config.json').read_text())
        self.vault=vault or Keychain(directory); self.transport=transport
        self.user=None; self.ready=False; self.message=''; self.presets=[]; self.global_memory=''; self.lock=asyncio.Lock()
        # Guest launches never touch Keychain. A previously selected account can
        # restore on launch through NativeIntegrations before memory is selected.

    def snapshot(self):
        user=self.user or {}
        return dict(configured=bool(self.config.get('apiKey') and self.config.get('projectId')),signedIn=self.ready,profile=dict(id=user.get('localId'),email=user.get('email',''),name=user.get('displayName') or user.get('email','').split('@')[0],verified=bool(user.get('emailVerified'))) if self.ready else None,presets=self.presets if self.ready else [],globalMemory=self.global_memory if self.ready else '',message=self.message)

    async def json(self,url,body=None,method='POST',token=None):
        return await asyncio.to_thread(self.transport,url,body,method,token)

    async def auth(self,method,body):
        if not self.snapshot()['configured']: raise ValueError('Accounts are not configured. Continue as a guest.')
        return await self.json('https://identitytoolkit.googleapis.com/v1/accounts:'+method+'?key='+urllib.parse.quote(self.config['apiKey']),body)

    async def persist(self,user):
        await asyncio.to_thread(self.vault.set,user); self.user=user

    async def token(self,force=False):
        if not self.user or self.user.get('projectId')!=self.config['projectId']: raise ValueError('Sign in to your Wixal account.')
        if force or self.user['expiresAt']<time.time()+60:
            result=await self.json('https://securetoken.googleapis.com/v1/token?key='+urllib.parse.quote(self.config['apiKey']),dict(grant_type='refresh_token',refresh_token=self.user['refreshToken']))
            await self.persist(dict(self.user,idToken=result['id_token'],refreshToken=result['refresh_token'],expiresAt=time.time()+float(result['expires_in'])))
        return self.user['idToken']

    async def lookup(self):
        result=await self.auth('lookup',dict(idToken=await self.token()))
        user=(result.get('users') or [None])[0]
        if not user: raise ValueError('Your account is unavailable. Sign in again.')
        await self.persist(dict(self.user,email=user.get('email',''),displayName=user.get('displayName',''),emailVerified=bool(user.get('emailVerified'))));self.ready=True

    async def cloud(self,kind,method='GET',body=None,id=None):
        if not self.ready or not self.user.get('emailVerified'): raise ValueError('Verify your email before using account presets or memory.')
        path='presets'+('/'+urllib.parse.quote(id,safe='') if id else '?pageSize=100') if kind=='presets' else 'profile/memory'
        url='https://firestore.googleapis.com/v1/projects/'+urllib.parse.quote(self.config['projectId'],safe='')+'/databases/(default)/documents/users/'+urllib.parse.quote(self.user['localId'],safe='')+'/'+path
        return await self.json(url,body,method,await self.token())

    async def sync(self):
        result=await self.cloud('presets'); presets=[]
        for doc in result.get('documents',[]):
            fields=doc.get('fields',{});name=fields.get('name',{}).get('stringValue','');payload=fields.get('preferences',{}).get('stringValue','')
            if not name or len(name)>60 or len(payload)>4096: raise ValueError('Invalid account preset.')
            presets.append(dict(id=doc['name'].split('/')[-1],name=name,**preferences(json.loads(payload))))
        self.presets=presets
        try:
            memory=await self.cloud('memory'); self.global_memory=profile_memory(memory.get('fields',{}).get('content',{}).get('stringValue',''))
        except AccountError as error:
            if error.status!=404: raise
            self.global_memory=''

    async def dispatch(self,method,params,store):
        if not method.startswith('account-') and method not in ('global-memory-save','global-memory-refresh'): return False,None
        if self.lock.locked(): raise ValueError('An account request is already running.')
        async with self.lock:
            if method=='account-restore':
                self.ready=False;self.presets=[];self.global_memory=''
                self.user=await asyncio.to_thread(self.vault.get)
                if self.user:
                    await self.lookup()
                    if self.user.get('emailVerified'): await self.sync()
                    self.message='Saved sign-in restored.'
                else:self.message='No saved sign-in is available. Sign in or continue as a guest.'
            elif method in ('account-sign-in','account-create'):
                email=params.get('email','').strip();password=params.get('password','');name=params.get('name','').strip()
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254: raise ValueError('Enter a valid email address.')
                create=method=='account-create'
                if not isinstance(password,str) or not (10 if create else 1)<=len(password)<=256: raise ValueError('New accounts need a password of at least 10 characters.')
                if create and not 1<=len(name)<=60: raise ValueError('Enter a display name of up to 60 characters.')
                result=await self.auth('signUp' if create else 'signInWithPassword',dict(email=email,password=password,returnSecureToken=True))
                await self.persist(dict(localId=result['localId'],email=result['email'],idToken=result['idToken'],refreshToken=result['refreshToken'],expiresAt=time.time()+float(result['expiresIn']),projectId=self.config['projectId']))
                self.ready=True;self.presets=[];self.global_memory='';self.message='Signed in.'
                if create:
                    try:
                        await self.auth('update',dict(idToken=result['idToken'],displayName=name,returnSecureToken=False))
                        await self.auth('sendOobCode',dict(requestType='VERIFY_EMAIL',idToken=result['idToken']))
                        self.message='Account created. Check your email for the verification link.'
                    except AccountError: self.message='Account created. Use Resend verification if the email did not arrive.'
                await self.lookup()
                if self.user.get('emailVerified'): await self.sync()
            elif method=='account-sign-out':
                await self.persist(None);self.ready=False;self.presets=[];self.global_memory='';self.message='Signed out. Local projects and chats are still on this Mac.'
            elif method in ('account-delete','account-password-change'):
                if not self.ready or not self.user:raise ValueError('Sign in first.')
                password=params.get('password','')
                if not isinstance(password,str) or not 1<=len(password)<=256:raise ValueError('Enter your current password to confirm your identity.')
                if method=='account-delete' and params.get('confirmation')!='DELETE':raise ValueError('Type DELETE to confirm online account deletion.')
                result=await self.auth('signInWithPassword',dict(email=self.user['email'],password=password,returnSecureToken=True))
                if result['localId']!=self.user['localId']:raise ValueError('The authenticated account changed. Sign in again.')
                await self.persist(dict(self.user,idToken=result['idToken'],refreshToken=result['refreshToken'],expiresAt=time.time()+float(result['expiresIn'])))
                if method=='account-password-change':
                    replacement=params.get('newPassword','')
                    if not isinstance(replacement,str) or not 10<=len(replacement)<=256:raise ValueError('Use a new password of at least 10 characters.')
                    changed=await self.auth('update',dict(idToken=await self.token(),password=replacement,returnSecureToken=True))
                    await self.persist(dict(self.user,idToken=changed['idToken'],refreshToken=changed['refreshToken'],expiresAt=time.time()+float(changed['expiresIn'])))
                    self.message='Password changed. Your saved sign-in was updated.'
                else:
                    # Delete owned cloud documents before deleting the identity; never claim atomic deletion.
                    if self.user.get('emailVerified'):
                        while True:
                            docs=(await self.cloud('presets')).get('documents',[])
                            if not docs:break
                            for doc in docs:await self.cloud('presets','DELETE',id=doc['name'].split('/')[-1])
                        try:await self.cloud('memory','DELETE')
                        except AccountError as error:
                            if error.status!=404:raise
                    await self.auth('delete',dict(idToken=await self.token()))
                    self.ready=False;self.presets=[];self.global_memory='';self.user=None
                    try:await self.persist(None)
                    except ValueError:self.message='Online account deleted. Keychain cleanup failed; remove the saved Wixal sign-in in Keychain Access.'
                    else:self.message='Online account and cloud presets/preferences deleted. Local projects and chats remain on this Mac.'
            elif method=='account-reset':
                email=params.get('email','').strip()
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254: raise ValueError('Enter your email address first.')
                try: await self.auth('sendOobCode',dict(requestType='PASSWORD_RESET',email=email))
                except AccountError as error:
                    if error.code!='EMAIL_NOT_FOUND': raise
                self.message='If that email has an account, a reset link has been sent.'
            elif method=='account-resend':
                await self.auth('sendOobCode',dict(requestType='VERIFY_EMAIL',idToken=await self.token()));self.message='Verification email sent.'
            elif method in ('account-refresh','account-sync'):
                await self.lookup()
                if self.user.get('emailVerified'):
                    await self.token(True);await self.sync();self.message='Email verified. Account presets refreshed.'
                else: self.message='Open the verification link in your email first.'
            elif method=='account-preset-save':
                name=params.get('name','').strip()
                if not 1<=len(name)<=60: raise ValueError('Name your preset using up to 60 characters.')
                await self.cloud('presets','PATCH',dict(fields=dict(name=dict(stringValue=name),preferences=dict(stringValue=json.dumps(preferences(store.data))))),str(uuid.uuid4()));await self.sync();self.message='Workspace preset saved.'
            elif method in ('account-preset-apply','account-preset-delete'):
                if not self.ready or not self.user.get('emailVerified'): raise ValueError('Sign in and verify your email first.')
                preset=next((p for p in self.presets if p['id']==params.get('id')),None)
                if not preset: raise ValueError('Unknown preset. Refresh your presets.')
                if method.endswith('apply'):
                    clean=preferences(preset);store.data['ui'].update(clean.pop('ui'));store.data.update(clean);self.message='Applied '+preset['name']+'.'
                else: await self.cloud('presets','DELETE',id=preset['id']);await self.sync()
            elif method=='global-memory-save':
                content=profile_memory(params.get('content',''))
                if self.ready:
                    await self.cloud('memory','PATCH',dict(fields=dict(content=dict(stringValue=content))));self.global_memory=content
                else: store.data['globalMemory']=content
                self.message='Global preferences saved.'
            elif method=='global-memory-refresh':
                if self.ready: await self.sync()
            else: raise ValueError('Unknown account action.')
        store.data['account']=self.snapshot()
        return True,self.snapshot()
