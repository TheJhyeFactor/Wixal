import importlib.util
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from wixal.security_worker import LinuxWorker

spec=importlib.util.spec_from_file_location('worker_bootstrap',Path(__file__).resolve().parents[1]/'worker/entrypoint.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)


class WorkerPolicyTests(unittest.TestCase):
    def config(self):return dict(addresses=['192.0.2.8','2001:db8::8'],ports=[443,8443],profile='ports',seconds=30,engagementId='engagement',runId='run',scopeRevision=2)
    def test_default_drop_and_explicit_address_port_sets(self):
        rules=bootstrap.rules(self.config())
        self.assertIn('policy drop',rules);self.assertIn('ip daddr { 192.0.2.8 } tcp dport { 443, 8443 }',rules)
        self.assertIn('ip6 daddr { 2001:db8::8 }',rules);self.assertNotIn('dport 53',rules)
    def test_unbounded_commands_ports_and_loopback_are_rejected(self):
        for fields in (dict(addresses=['127.0.0.1']),dict(ports=[True]),dict(ports=list(range(1,1026))),dict(profile='checks'),dict(seconds=601),dict(command='anything')):
            config=self.config();config.update(fields)
            with self.assertRaises(ValueError):bootstrap.validate(config)
    def test_nft_failure_never_launches_a_scan(self):
        import io,json
        source=SimpleNamespace(buffer=io.BytesIO(json.dumps(self.config()).encode()))
        with patch.object(bootstrap.sys,'stdin',source),patch.object(bootstrap.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['nft'])) as execute:
            with self.assertRaises(subprocess.CalledProcessError):bootstrap.main()
        self.assertEqual(execute.call_count,1);self.assertEqual(execute.call_args.args[0],['nft','-f','-'])
    def test_nft_receipt_precedes_unprivileged_nmap(self):
        import io,json
        source=SimpleNamespace(buffer=io.BytesIO(json.dumps(self.config()).encode()));calls=[]
        def execute(argv,**kwargs):calls.append(argv);return SimpleNamespace(stdout=b'{"nftables":[]}',returncode=0)
        with patch.object(bootstrap.sys,'stdin',source),patch.object(bootstrap.subprocess,'run',side_effect=execute),patch('builtins.print') as output:
            with self.assertRaises(SystemExit) as end:bootstrap.main()
        self.assertEqual(end.exception.code,0);self.assertEqual(calls[0][:2],['nft','-f']);self.assertEqual(calls[1][:3],['nft','-j','list'])
        self.assertEqual(calls[2][0],'setpriv');self.assertIn('--bounding-set=-all',calls[2]);self.assertIn('-n',calls[2]);self.assertIn('enforcement-receipt',output.call_args.args[0])


class WorkerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_runtime_is_unavailable_without_installation(self):
        manager=SimpleNamespace(store=SimpleNamespace(data={}),workspace=SimpleNamespace(publish=lambda:None))
        worker=LinuxWorker(manager)
        with patch.object(worker,'executable',return_value=None):
            result=await worker.inspect()
        self.assertFalse(result['available']);self.assertIn('no runtime is installed',result['error'])
    async def test_cleanup_does_not_remove_another_owners_container(self):
        import json
        worker=LinuxWorker(None);run=dict(id='own-run',engagementId='own-engagement',workerContainer='owned-name')
        worker.command=AsyncMock(side_effect=[json.dumps([dict(Config=dict(Labels={'wixal.run':'another','wixal.engagement':'another'}))]),'owned-name'])
        with self.assertRaisesRegex(ValueError,'ownership mismatch'):await worker.cleanup(run)
        self.assertFalse(any('rm' in call.args for call in worker.command.call_args_list))
    async def test_absent_owned_objects_are_reconciled_without_delete(self):
        worker=LinuxWorker(None);run=dict(id='run',engagementId='engagement',workerContainer='missing')
        worker.command=AsyncMock(side_effect=[ValueError('not found'),''])
        result=await worker.cleanup(run)
        self.assertTrue(result[0]['absent']);self.assertFalse(any('rm' in call.args for call in worker.command.call_args_list))

    async def test_reconcile_absence_preserves_unknown_target_effects(self):
        worker=LinuxWorker(None);run=dict(id='run',engagementId='engagement',workerContainer='missing',effectState='unknown')
        worker.command=AsyncMock(return_value='')
        result=await worker.reconcile(run)
        self.assertTrue(result['environmentClean']);self.assertEqual(result['effectState'],'unknown')
        self.assertFalse(any('rm' in call.args for call in worker.command.call_args_list))

    async def test_reconcile_checks_ownership_before_exposing_liveness(self):
        import json
        worker=LinuxWorker(None);run=dict(id='run',engagementId='engagement',workerContainer='existing')
        worker.command=AsyncMock(side_effect=['existing',json.dumps([dict(Config=dict(Labels={'wixal.run':'another','wixal.engagement':'another'}))])])
        with self.assertRaisesRegex(ValueError,'ownership mismatch'):await worker.reconcile(run)

    async def test_runtime_configuration_requires_owned_unix_socket_and_review(self):
        import socket,tempfile
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'docker.sock';server=socket.socket(socket.AF_UNIX);server.bind(str(path))
            service=SimpleNamespace(ask=AsyncMock(return_value=True))
            manager=SimpleNamespace(store=SimpleNamespace(data={}),workspace=SimpleNamespace(publish=lambda:None,service=service))
            worker=LinuxWorker(manager)
            try:
                with self.assertRaises(ValueError):await worker.configure('tcp://remote:2375')
                regular=Path(temp)/'file';regular.write_text('not a socket')
                with self.assertRaises(ValueError):await worker.configure(str(regular))
                result=await worker.configure(str(path))
                self.assertEqual(result['socket'],str(path.resolve()));service.ask.assert_awaited_once()
                self.assertFalse(manager.store.data['securityWorkerReadiness']['available'])
            finally:server.close()
