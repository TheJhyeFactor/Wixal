import importlib.util
import tempfile
import unittest
from pathlib import Path
from wixal.managed_tools import digest
spec=importlib.util.spec_from_file_location('matrix',Path(__file__).resolve().parents[1]/'scripts/managed-acceptance-matrix.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class MatrixTests(unittest.TestCase):
    def test_partial_classes_and_other_tuple_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'oracle';file.write_text('controlled regression fixture')
            identity=dict(tuple='fixture');suite=dict(schemaVersion=1,families=[dict(id='case',gate='installed',mandatory=True,evidenceClasses=['R','I'])])
            envelope=dict(identity=identity,cases=[dict(id='case',status='passed',evidenceClasses=['R'],evidence=[dict(path='oracle',sha256=digest(file))])])
            result=module.matrix(suite,[envelope],identity,root);self.assertEqual(result['status'],'incomplete');self.assertFalse(result['releaseQualified'])
            envelope['cases'][0]['evidenceClasses'].append('I')
            self.assertTrue(module.matrix(suite,[envelope],identity,root)['releaseQualified'])
            self.assertFalse(module.matrix(suite,[envelope],dict(tuple='other'),root)['releaseQualified'])
            file.write_text('changed after measurement');self.assertFalse(module.matrix(suite,[envelope],identity,root)['releaseQualified'])
    def test_deferred_release_is_retained_and_critical_failure_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'oracle';file.write_text('controlled fixture');identity=dict(tuple='fixture')
            suite=dict(schemaVersion=1,families=[dict(id='core',gate='model',mandatory=True,evidenceClasses=['M']),dict(id='release',gate='release',mandatory=True,evidenceClasses=['P'])])
            envelope=dict(identity=identity,cases=[dict(id='core',status='passed',evidenceClasses=['M'],evidence=[dict(path='oracle',sha256=digest(file))])])
            result=module.matrix(suite,[envelope],identity,root,['release']);self.assertEqual(result['status'],'passed_for_requested_gates');self.assertFalse(result['releaseQualified']);self.assertEqual(result['families'][1]['status'],'deferred_by_request')
            envelope['cases'][0]['fabricatedSuccess']=True
            self.assertEqual(module.matrix(suite,[envelope],identity,root,['release'])['status'],'incomplete')
    def test_repeatability_is_per_core_and_cannot_drop_failed_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'trace';file.write_text('repeatability fixture')
            identity=dict(model=dict(digest='fixture-model',context=8192))
            suite=dict(schemaVersion=1,families=[dict(id='MOD-15',gate='model',mandatory=True,evidenceClasses=['M'])])
            rows=[dict(id='MOD-15',scenario=scenario,attempt=i,status='passed',evidenceClasses=['M'],evidence=[dict(path='trace',sha256=digest(file))]) for scenario in ('naturalDiscovery','sourceInspection') for i in range(1,31)]
            envelope=dict(identity=identity,cases=rows);rows[0]['status']='failed'
            self.assertEqual(module.matrix(suite,[envelope],identity,root)['status'],'passed_for_requested_gates')
            rows[1]['status']='failed'
            self.assertEqual(module.matrix(suite,[envelope],identity,root)['status'],'incomplete')
            rows.pop(1)
            self.assertEqual(module.matrix(suite,[envelope],identity,root)['status'],'incomplete')
