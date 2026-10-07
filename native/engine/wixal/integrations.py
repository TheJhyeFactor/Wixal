"""Account, setup, legal and explicit companion actions for Service."""
from pathlib import Path
import asyncio
from .account import Accounts
from .companion import Companion
from .storage import now

class NativeIntegrations:
    def __init__(self,service):
        self.service=service;self.account=Accounts(service.store.directory);self.companion=Companion(service)
        service.store.data.setdefault('restoreAccountOnLaunch',bool(service.store.data.get('account',{}).get('signedIn')))
        self.restored_on_launch=False
        service.store.data.setdefault('setup',dict(entryCompleted=False,completed=False))
        self.refresh()

    async def restore_if_needed(self):
        if self.restored_on_launch:return
        self.restored_on_launch=True
        if not self.service.store.data.get('restoreAccountOnLaunch'):return
        self.service.emit('activity',dict(text='Restoring saved Wixal sign-in…'))
        try:
            # Restoring may refresh a token and read two cloud collections. Give
            # those cold connections a bounded deadline within the host hello budget.
            async with asyncio.timeout(45):
                await self.account.dispatch('account-restore',{},self.service.store)
            if not self.account.ready:
                self.account.message='Saved sign-in is unavailable. Restore or sign in from Account to use account preferences.'
        except Exception:
            self.account.ready=False
            self.account.message='Saved sign-in could not be restored. Restore or sign in from Account; guest preferences are active.'
        self.refresh();self.service.store.save()

    def refresh(self):
        self.service.store.data['account']=self.account.snapshot()
        self.service.store.data['companion'].update(self.companion.snapshot())

    async def dispatch(self,method,params):
        if method=='legal-document':
            document=params.get('id');names={'terms':'Terms & Conditions','privacy':'Privacy Policy'}
            if document not in names:raise ValueError('Unknown legal document.')
            return True,dict(title=names[document],version='2026-10-06-draft',status='draft',markdown=(Path(__file__).parent/'resources/legal'/ (document+'.md')).read_text())
        if method in ('entry-complete','setup-complete'):
            if method=='entry-complete':
                if params.get('choice') not in ('guest','account'):raise ValueError('Choose guest or account.')
                if params.get('choice')=='account' and not self.account.ready:raise ValueError('Sign in first or continue as guest.')
                if params.get('legalAccepted') is not True:raise ValueError('Review and accept the Terms and Privacy Policy to continue.')
                if params['choice']=='guest' and self.account.ready:
                    await self.account.dispatch('account-sign-out',{},self.service.store)
                if params['choice']=='guest':self.service.store.data['restoreAccountOnLaunch']=False
                self.service.store.data['setup'].update(entryCompleted=True,entryChoice=params['choice'],legalAcceptedAt=now(),legalVersion='2026-10-06-draft')
            else:
                if not self.service.store.data['setup'].get('entryCompleted'):raise ValueError('Complete the welcome step first.')
                self.service.store.data['setup'].update(completed=True,completedAt=now())
            handled,result=True,self.service.store.data['setup']
        else:
            try:
                handled,result=await self.account.dispatch(method,params,self.service.store)
            except BaseException:
                # Account creation may succeed before verification/sync fails.
                # Preserve and show that truthful partial result for recovery.
                self.refresh();self.service.store.save();self.service.emit('state',self.service.store.data)
                raise
            if not handled:handled,result=await self.companion.dispatch(method,params)
        if handled:
            if method in ('account-restore','account-sign-in','account-create'):
                self.service.store.data['restoreAccountOnLaunch']=self.account.ready
            elif method in ('account-sign-out','account-delete'):self.service.store.data['restoreAccountOnLaunch']=False
            for session in self.service.store.data["sessions"]: session.pop("contextInfo",None)
            self.refresh();self.service.store.save();self.service.emit('state',self.service.store.data)
        return handled,result

    async def close(self):await self.companion.stop()
