import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from wixal.addons import Addons, definitions
from wixal.storage import Store
from wixal.tools import Tools
from wixal.agent_context import profile, automatic
from wixal.addon_execution import run

class AddonTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'state')
        self.project=dict(id='test',root=str(self.root),approvalMode='bypass');self.store.data['projects']=[self.project];self.store.data['activeProject']='test'
        self.store.data['enabledTools']=[d['function']['name'] for d in definitions()]+['command_read','command_stop']
        self.service=SimpleNamespace(store=self.store,emit=lambda *_:None)
        self.manager=Addons(self.service);self.store.addons=self.manager
        self.store.data["addonPolicy"]["automaticInstall"]=False
        self.tools=Tools(self.store,AsyncMock(return_value=True),lambda *_:None,SimpleNamespace(definitions=lambda:[]))
        self.service.tools=self.tools
    async def asyncTearDown(self):
        await self.manager.close();await self.tools.close();self.store.close();self.temp.cleanup()
    async def test_catalog_owner_and_idempotent_workflow(self):
        self.assertEqual(len(self.manager.snapshot()['packages']),11)
        first=self.manager.workflow('web-assessment');second=self.manager.workflow('web-assessment')
        self.assertEqual(first['id'],second['id']);self.assertEqual(len(self.store.data['skills']),1)
        self.assertIn('addon_catalog',[d['function']['name'] for d in self.tools.catalog()])
        with self.assertRaisesRegex(ValueError,'curated'):self.manager.spec('evil; curl attacker')
        with self.assertRaisesRegex(ValueError,'installation policy'):await self.manager.dispatch('addon-policy',dict(automaticInstall='yes'))
    async def test_invalid_discovery_query_and_read_only_stop(self):
        with self.assertRaisesRegex(ValueError,'simple Homebrew'):
            await self.manager.discover('https://untrusted.example/install.sh')
        self.store.data['addonJobs'].append(dict(id='owned',owner='guest',session='chat',status='running'))
        token=profile.set(dict(reviewPolicy='Read only'))
        try:
            with self.assertRaisesRegex(ValueError,'Read-only'):
                await self.manager.job(dict(id='owned',action='stop'),'chat')
        finally:profile.reset(token)
    async def test_declined_installer_and_no_shell(self):
        self.tools.approve.return_value=False
        with patch.object(self.manager,'executable',return_value=None),patch.object(self.manager,'snapshot',return_value=dict(brew='/fake/brew',packages=[dict(registryURL='https://formulae.brew.sh/formula/nmap')]*10)):
            job=await self.manager.install(dict(id='nmap',reason='Need ports'),self.tools,'chat')
        self.assertEqual(job['status'],'declined');self.assertFalse(self.manager.tasks)
        with self.assertRaisesRegex(ValueError,'another conversation'):await self.manager.job(dict(id=job['id']),'other')
    async def test_real_process_installer_lifecycle_and_pinned_registry(self):
        executable=self.root/'installed';brew=self.root/'brew'
        brew.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nprintf "#!/bin/sh\\necho fixture-version\\n" > "'+str(executable)+'"\nchmod +x "'+str(executable)+'"\n')
        brew.chmod(0o700)
        def detect(_):return str(executable) if executable.exists() else None
        with patch.object(self.manager,'executable',side_effect=detect),patch.object(self.manager,'snapshot',return_value=dict(brew=str(brew),packages=[dict(registryURL='https://formulae.brew.sh/formula/nmap')]*10)):
            job=await self.manager.install(dict(id='nmap',reason='Fixture lifecycle'),self.tools,'chat')
            task=self.manager.tasks[job['id']];await task
        result=await self.manager.job(dict(id=job['id']),'chat')
        self.assertEqual(result['status'],'ready');self.assertEqual(result['argv'],[str(brew),'install','homebrew/core/nmap'])
        self.assertIn('homebrew/core/nmap',result['output']);self.assertEqual(result['path'],str(executable))
    async def test_boundaries_and_real_adapter_arguments(self):
        self.root.joinpath('words.txt').write_text('known\n')
        token=profile.set(dict(reviewPolicy='Read only'))
        try:
            with self.assertRaisesRegex(ValueError,'boundary'):await self.manager.install(dict(id='nmap',reason='Test'),self.tools,'chat')
        finally:profile.reset(token)
        token=profile.set(dict(restrictTargets=True,authority=dict(targets=['https://allowed.example'])))
        try:
            with patch.object(self.manager,'executable',return_value='/fake/ffuf'):
                with self.assertRaisesRegex(ValueError,'scope'):await run(self.manager,self.tools,dict(id='ffuf',target='https://outside.example',path='words.txt'),'chat')
        finally:profile.reset(token)
        self.tools.start_command=AsyncMock(return_value=dict(state='running'))
        with patch.object(self.manager,'executable',return_value='/usr/bin/true'):
            await run(self.manager,self.tools,dict(id='ffuf',target='https://allowed.example',path='words.txt'),'chat')
            with self.assertRaises((ValueError,OSError)):await run(self.manager,self.tools,dict(id='ffuf',target='https://allowed.example',path='../words.txt'),'chat')
        argv=self.tools.start_command.call_args.kwargs['argv']
        self.assertIn('https://allowed.example/FUZZ',argv);self.assertIn('-rate',argv);self.assertNotIn('/bin/zsh',argv)
        await self.tools.start_command.call_args.kwargs['on_finished']({})
    async def test_automatic_formula_policy_and_cancellation(self):
        self.store.data['addonPolicy']['automaticInstall']=True
        async def collect(job,*_):
            try:await asyncio.sleep(30)
            finally:job['status']='cancelled'
        with patch.object(self.manager,'executable',return_value=None),patch.object(self.manager,'collect',side_effect=collect):
            job=await self.manager.install(dict(id='nmap',reason='Policy check'),self.tools,'chat')
            await asyncio.sleep(0)
            await self.manager.job(dict(id=job['id'],action='stop'),'chat')
        self.tools.approve.assert_not_called()
        self.assertEqual(self.store.data['addonJobs'][0]['status'],'cancelled')

    async def test_global_workflow_metadata_and_removal(self):
        self.manager.workflow('network-assessment')
        snapshot=self.manager.snapshot()
        self.assertEqual(snapshot['scope'],'global')
        pack=next(p for p in snapshot['workflows'] if p['id']=='network-assessment')
        self.assertEqual(pack['category'],'Network');self.assertTrue(pack['skillId'])
        self.store.data['activeProject']=None
        self.assertTrue(next(p for p in self.manager.snapshot()['workflows'] if p['id']==pack['id'])['installed'])
        await self.manager.dispatch('addon-workflow-remove',dict(id=pack['id']))
        self.assertFalse(next(p for p in self.manager.snapshot()['workflows'] if p['id']==pack['id'])['installed'])

    async def test_management_jobs_pin_package_and_operation(self):
        executable=self.root/'managed';executable.write_text('#!/bin/sh\necho managed-version\n');executable.chmod(0o700)
        brew=self.root/'brew';brew.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nif [ "$1" = uninstall ]; then rm "'+str(executable)+'"; fi\n');brew.chmod(0o700)
        with patch.object(self.manager,'executable',side_effect=lambda _:str(executable) if executable.exists() else None),patch.object(self.manager,'snapshot',return_value=dict(brew=str(brew))):
            for operation in ('upgrade','reinstall','uninstall'):
                job=await self.manager.dispatch('addon-manage',dict(id='nmap',operation=operation))
                await self.manager.tasks[job['id']]
                result=await self.manager.job(dict(id=job['id']))
                self.assertEqual(result['argv'],[str(brew),operation,'homebrew/core/nmap'])
                self.assertEqual(result['status'],'removed' if operation=='uninstall' else 'ready')
            with self.assertRaisesRegex(ValueError,'update, repair'):
                await self.manager.dispatch('addon-manage',dict(id='nmap',operation='shell'))

    async def test_manual_install_and_ai_install_policy_are_separate(self):
        with patch.object(self.manager,'executable',return_value=None),patch.object(self.manager,'collect',new=AsyncMock()):
            job=await self.manager.install(dict(id='nmap',reason='User clicked Install'),self.tools,'native-library',manual=True)
            await self.manager.tasks[job['id']]
        self.tools.approve.assert_not_called()
        self.store.data['addonJobs']=[]
        with patch.object(self.manager,'executable',return_value=None),patch.object(self.manager,'collect',new=AsyncMock()):
            job=await self.manager.install(dict(id='nmap',reason='AI needs tool'),self.tools,'chat')
            await self.manager.tasks[job['id']]
        self.assertTrue(self.tools.approve.call_args.args[0]['installationReview'])

    async def test_install_prompt_is_not_bypassed_by_execution_policy(self):
        from wixal.service import Service
        service=SimpleNamespace(store=self.store,ask=AsyncMock(return_value=False))
        self.assertFalse(await Service.approve(service,dict(name='addon_install',installationReview=True)))
        service.ask.assert_awaited_once()
        self.assertTrue(await Service.approve(service,dict(name='command_start')))
