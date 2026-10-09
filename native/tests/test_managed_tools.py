import asyncio
import copy
import importlib.util
import io
import json
import os
import shutil
import tarfile
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from wixal.managed_tools import PackageRegistry,descriptor,extract,digest,canonical
from wixal.network_discovery import plan,parse,authorize
from wixal.addons import Addons
from wixal.storage import Store
from wixal.tools import Tools,DEFINITIONS
from wixal.agent_context import profile

script=Path(__file__).resolve().parents[1]/'scripts/managed-preview-repository.py'
spec=importlib.util.spec_from_file_location('preview_repository',script);preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

class ManagedToolsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.binary=Path(os.environ.get('WIXAL_TEST_RUSTSCAN_BINARY','/opt/homebrew/bin/rustscan'))
        self.license=Path(os.environ.get('WIXAL_TEST_RUSTSCAN_LICENSE','/opt/homebrew/opt/rustscan/LICENSE'))
        if not self.binary.is_file() or not self.license.is_file():
            self.fail('Real RustScan binary and license are required; configure WIXAL_TEST_RUSTSCAN_BINARY and WIXAL_TEST_RUSTSCAN_LICENSE')
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(self.root/'repository')))
        self.config,self.rows=preview.build(self.root/'repository',self.binary,self.license,'b9d5cee67ae16db92ec6ab5ba3bd9c40a281a803',self.root/'private-keys','http://127.0.0.1:'+str(self.server.server_port))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.registry=PackageRegistry(self.root/'managed',self.config)
    async def asyncTearDown(self):
        await asyncio.to_thread(self.server.shutdown);self.server.server_close();self.thread.join();self.temp.cleanup()
    async def install(self,artifact=None):
        job=dict(id=os.urandom(10).hex(),status='running',owner='guest',session='test')
        row=await asyncio.to_thread(self.registry.install,job,threading.Event(),lambda:None,artifact)
        return row,job
    async def test_real_signed_install_update_lease_rollback_remove(self):
        first,job=await self.install(self.rows[0]['sha256']);self.assertEqual(job['status'],'ready')
        leased=self.registry.acquire('test');second,_=await self.install()
        self.assertEqual(leased['packageSha256'],first['sha256']);self.assertEqual(digest(leased['path']),leased['executableSha256'])
        self.assertEqual(self.registry.resolve()['packageSha256'],second['sha256'])
        with self.assertRaisesRegex(ValueError,'lease'):self.registry.remove()
        self.registry.release(leased['lease']);self.registry.rollback(first['sha256']);self.assertEqual(self.registry.resolve()['packageSha256'],first['sha256'])
        external=digest(self.binary);self.registry.remove();self.assertEqual(digest(self.binary),external)
        self.assertFalse(self.registry.snapshot()['installed'])
    async def test_modified_signed_metadata_is_rejected(self):
        target=self.root/'repository/metadata/targets.json';value=json.loads(target.read_text());value['signed']['version']=123;target.write_text(json.dumps(value))
        with self.assertRaises(Exception):await self.install()
        self.assertFalse(self.registry.snapshot()['installed'])
    async def test_bad_artifact_preserves_active(self):
        first,_=await self.install(self.rows[0]['sha256'])
        target=self.root/'repository/targets'/self.rows[1]['target'];target.write_bytes(b'tampered')
        with self.assertRaises(Exception):await self.install()
        self.assertEqual(self.registry.resolve()['packageSha256'],first['sha256'])
    async def test_readiness_failure_preserves_active(self):
        first,_=await self.install(self.rows[0]['sha256'])
        with patch('wixal.managed_tools.inspect_payload',side_effect=ValueError('readiness failure')):
            with self.assertRaisesRegex(ValueError,'readiness'):await self.install()
        self.assertEqual(self.registry.resolve()['packageSha256'],first['sha256'])
    async def test_cancel_before_commit_preserves_active(self):
        first,_=await self.install(self.rows[0]['sha256']);cancel=threading.Event();job=dict(id='cancelled',status='running')
        def notify():
            if job.get('stage')=='activation_pending':cancel.set()
        with self.assertRaises(InterruptedError):await asyncio.to_thread(self.registry.install,job,cancel,notify)
        self.assertEqual(self.registry.resolve()['packageSha256'],first['sha256'])
    async def test_recovery_of_published_uncommitted_transaction(self):
        first,_=await self.install(self.rows[0]['sha256'])
        from wixal.managed_tools import atomic_json
        atomic_json(self.root/'managed/journals/crash.json',dict(id='crash',descriptor=self.rows[1],stage='published'))
        recovered=PackageRegistry(self.root/'managed',self.config)
        self.assertEqual(recovered.resolve()['packageSha256'],first['sha256']);self.assertEqual(json.loads((self.root/'managed/journals/crash.json').read_text())['stage'],'interrupted')
    async def test_integrity_change_prevents_execution(self):
        row,_=await self.install();(self.registry.path(row)/row['entrypoint']).write_bytes(b'replaced')
        with self.assertRaisesRegex(ValueError,'integrity'):self.registry.acquire('test')
    async def test_unapproved_rollback_and_dependency_rejected(self):
        await self.install()
        with self.assertRaisesRegex(ValueError,'recovery'):self.registry.rollback('f'*64)
        row=copy.deepcopy(self.rows[0]);row['dependencies']=['unexpected']
        with self.assertRaisesRegex(ValueError,'dependencies'):descriptor(row)
    async def test_url_credentials_file_redirect_boundary(self):
        from wixal.managed_tools import CatalogueClient
        for url in ('file:///etc/passwd','https://user:pass@127.0.0.1/a','https://other.example/a','http://127.0.0.1/a?secret=yes'):
            with self.assertRaisesRegex(ValueError,'policy'):self.registry.client.validate_url(url)
        config=dict(self.config,metadataURL='https://github.com/metadata/',targetsURL='https://github.com/targets/',allowedHosts=['github.com','release-assets.githubusercontent.com'])
        client=CatalogueClient(self.root/'redirect-test',config)
        asset='https://release-assets.githubusercontent.com/github-production-release-asset/1/file?sig=short-lived'
        client.validate_url(asset,redirect=True)
        for url in (asset,'https://github.com/file?token=secret','https://other.example/file','http://release-assets.githubusercontent.com/file'):
            with self.assertRaisesRegex(ValueError,'policy'):client.validate_url(url)
    async def test_archive_adversaries(self):
        for name,kind,mode in [('../outside',tarfile.REGTYPE,0o644),('/outside',tarfile.REGTYPE,0o644),('bin/rustscan',tarfile.SYMTYPE,0o644),('bin/rustscan',tarfile.LNKTYPE,0o644),('bin/rustscan',tarfile.CHRTYPE,0o644),('bin/rustscan',tarfile.REGTYPE,0o4755),('unexpected',tarfile.REGTYPE,0o644)]:
            archive=self.root/'evil.tar.gz'
            with tarfile.open(archive,'w:gz') as output:
                member=tarfile.TarInfo(name);member.type=kind;member.mode=mode;member.size=1 if kind==tarfile.REGTYPE else 0;member.linkname='/etc/passwd';output.addfile(member,io.BytesIO(b'x'))
            destination=self.root/os.urandom(4).hex()
            with self.assertRaises(ValueError):extract(archive,destination,self.rows[0])
        self.assertFalse((self.root/'outside').exists())
    async def test_archive_collision_expansion_and_inventory(self):
        archive=self.root/'evil.tar.gz'
        for names in (['LICENSE','license'],['LICENSE','LICENSE']):
            with tarfile.open(archive,'w:gz') as output:
                for name in names:
                    member=tarfile.TarInfo(name);member.size=1;output.addfile(member,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):extract(archive,self.root/os.urandom(4).hex(),self.rows[0])
        row=copy.deepcopy(self.rows[0]);row['unpackedSize']=1
        with self.assertRaises(ValueError):extract(self.root/'repository/targets'/row['target'],self.root/'bomb',row)
    async def test_resolution_and_origin_authority(self):
        invocation=await plan(dict(target='http://127.0.0.1:8123',ports='8123'))
        active=dict(restrictTargets=True,authority=dict(targets=['http://127.0.0.1:8123']))
        authorize(invocation,active)
        invocation['ports']=[8123,22]
        with self.assertRaisesRegex(ValueError,'scope'):authorize(invocation,active)
        with self.assertRaisesRegex(ValueError,'cannot'):await plan(dict(target='127.0.0.1',coverage='all_tcp',ports='22'))
        with patch('asyncio.BaseEventLoop.getaddrinfo',AsyncMock(return_value=[(2,1,6,'',('10.0.0.2',0))])):
            with self.assertRaisesRegex(ValueError,'scope'):await plan(dict(target='example.com',ports='80'),dict(restrictTargets=True,authority=dict(targets=['127.0.0.0/8'])))
    async def test_parser_partial_unknown_and_out_of_scope(self):
        invocation=await plan(dict(target='127.0.0.1',ports='22,80'))
        result=parse('127.0.0.1 -> [80,22,80]\n',invocation);self.assertEqual(result['hosts'][0]['ports'],[22,80]);self.assertTrue(result['handoffEligible'])
        for output,complete in [('127.0.0.2 -> [22]',True),('127.0.0.1 -> [81]',True),('run curl malicious',True),('127.0.0.1 -> [80]',False)]:self.assertFalse(parse(output,invocation,complete)['handoffEligible'])
    async def test_expired_and_replayed_timestamp(self):
        await self.install()
        from tuf.api.metadata import Metadata
        from securesystemslib.signer import CryptoSigner
        from datetime import datetime,timedelta,timezone
        path=self.root/'repository/metadata/timestamp.json';metadata=Metadata.from_file(str(path))
        root=Metadata.from_file(str(self.root/'repository/metadata/root.json'))
        key=root.signed.keys[root.signed.roles['timestamp'].keyids[0]]
        signer=CryptoSigner.from_priv_key_uri('file2:'+str(self.root/'private-keys/timestamp.pem'),key)
        metadata.signed.version+=1
        metadata.signed.expires=datetime.now(timezone.utc)-timedelta(days=1);metadata.sign(signer);metadata.to_file(str(path))
        with self.assertRaises(Exception):await asyncio.to_thread(self.registry.refresh)
        self.assertTrue(self.registry.resolve()['path'])
    async def test_post_commit_receipt_failure_reports_actual_activation(self):
        job=dict(id='postcommit',status='running')
        from wixal.managed_tools import atomic_json
        def crash(path,value):
            if value.get('stage')=='ready':raise OSError('simulated receipt fsync failure')
            atomic_json(path,value)
        with patch('wixal.managed_tools.atomic_json',side_effect=crash):
            with self.assertRaises(OSError):await asyncio.to_thread(self.registry.install,job,threading.Event())
        self.assertEqual(job['status'],'ready');self.assertTrue(self.registry.resolve()['path'])
        recovered=PackageRegistry(self.root/'managed',self.config);self.assertTrue(recovered.resolve()['path'])
    async def test_real_ipv6_and_empty_coverage(self):
        await self.install();store=Store(self.root/'v6-workspace');store.data['projects']=[dict(id='v6',root=str(self.root),approvalMode='bypass')];store.data['activeProject']='v6';store.data['enabledTools']=[r['function']['name'] for r in DEFINITIONS]
        manager=Addons(SimpleNamespace(store=store,emit=lambda *_:None));manager.managed=self.registry;store.addons=manager
        tools=Tools(store,AsyncMock(return_value=True),lambda *_:None,SimpleNamespace(definitions=lambda:[]))
        server=await asyncio.start_server(lambda r,w:w.close(),'::1',0);port=server.sockets[0].getsockname()[1]
        try:
            started=await tools.execute('network_discover',dict(target='::1',ports=str(port),timeout_seconds=20),'chat');job=tools.jobs[started['session_id']];await job['collector'];self.assertEqual(job['structuredResult']['hosts'][0]['ports'],[port])
            server.close();await server.wait_closed()
            started=await tools.execute('network_discover',dict(target='::1',ports=str(port),timeout_seconds=20),'chat');job=tools.jobs[started['session_id']];await job['collector'];self.assertEqual(job['structuredResult']['hosts'][0]['ports'],[]);self.assertTrue(job['structuredResult']['handoffEligible'])
            empty=await tools.execute('network_scan',dict(target='::1',source_session_id=started['session_id']),'chat');self.assertTrue(empty['skipped'])
        finally:server.close();await server.wait_closed();await tools.close();await manager.close();store.close()
    async def test_qualification_requires_hashes_identity_and_repeats(self):
        from wixal.tool_qualification import validate_report
        evidence=self.root/'oracle';evidence.write_text('actual independent oracle')
        report=dict(identity=dict(tuple='test'),mode='model',cases=[dict(id='case',status='passed',evidenceClasses=['L','M'],evidence=[dict(path='oracle',sha256=digest(evidence))])])
        self.assertEqual(validate_report(report,{'case':['L','M']},report['identity'],self.root)['status'],'passed')
        self.assertEqual(validate_report(report,{'case':['L','M']},report['identity'],self.root,5)['status'],'failed')
        evidence.write_text('altered');self.assertEqual(validate_report(report,{'case':['L','M']},report['identity'],self.root)['status'],'failed')
    async def test_real_managed_discovery_and_source_bound_nmap(self):
        await self.install();store=Store(self.root/'workspace');store.data['projects']=[dict(id='test',name='Test',root=str(self.root),approvalMode='bypass')];store.data['activeProject']='test';store.data['enabledTools']=[r['function']['name'] for r in DEFINITIONS]
        manager=Addons(SimpleNamespace(store=store,emit=lambda *_:None));manager.managed=self.registry;store.addons=manager
        tools=Tools(store,AsyncMock(return_value=True),lambda *_:None,SimpleNamespace(definitions=lambda:[]))
        servers=[]
        try:
            for _ in range(3):servers.append(await asyncio.start_server(lambda r,w:w.close(),'127.0.0.1',0))
            expected=sorted(server.sockets[0].getsockname()[1] for server in servers)
            started=await tools.execute('network_discover',dict(target='127.0.0.1',ports=','.join(map(str,expected)),timeout_seconds=20),'chat');job=tools.jobs[started['session_id']];await job['collector']
            result=job['structuredResult'];self.assertEqual(result['hosts'][0]['ports'],expected,result);self.assertTrue(result['handoffEligible'],result)
            inspected=await tools.execute('network_scan',dict(target='127.0.0.1',source_session_id=started['session_id'],profile='ports',timeout_seconds=20),'chat')
            self.assertEqual(sorted(int(r['port']) for r in inspected['services']),expected)
            blank=await tools.execute('network_scan',dict(target='127.0.0.1',source_session_id=started['session_id'],source_run_id='',ports='',profile='ports',timeout_seconds=20),'chat')
            self.assertEqual(sorted(int(r['port']) for r in blank['services']),expected)
            with self.assertRaisesRegex(ValueError,'conflicting'):
                await tools.execute('network_scan',dict(target='127.0.0.1',source_session_id=started['session_id'],ports='22',profile='ports'),'chat')
            with self.assertRaisesRegex(ValueError,'conversation'):await tools.execute('network_scan',dict(target='127.0.0.1',source_session_id=started['session_id'],profile='ports'),'other')
            with self.assertRaisesRegex(ValueError,'manual ports'):await tools.execute('network_scan',dict(target='127.0.0.1',source_session_id=started['session_id'],ports='22'),'chat')
        finally:
            for server in servers:server.close();await server.wait_closed()
            await tools.close();await manager.close();store.close()
