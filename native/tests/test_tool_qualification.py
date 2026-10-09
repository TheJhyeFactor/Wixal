import copy
import tempfile
import unittest
from pathlib import Path
from wixal.tool_qualification import validate_report
from wixal.managed_tools import digest

class QualificationTests(unittest.TestCase):
    def test_repeatability_retains_failure_and_requires_unique_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'oracle').write_text('Unit fixture evidence; not a model evaluation')
            identity=dict(model='fixture',helper='fixture')
            rows=[dict(id='core',attempt=i,status='passed' if i<30 else 'failed',evidenceClasses=['M','L'],evidence=[dict(path='oracle',sha256=digest(root/'oracle'))]) for i in range(1,31)]
            report=dict(identity=identity,mode='model',cases=rows)
            result=validate_report(report,{'core':['M','L']},identity,root,30,29)
            self.assertEqual(result['status'],'passed');self.assertEqual(rows[-1]['status'],'failed')
            self.assertEqual(validate_report(report,{'core':['M','L']},identity,root,30)['status'],'failed')
            rows[-1]['attempt']=29
            self.assertEqual(validate_report(report,{'core':['M','L']},identity,root,30,29)['status'],'failed')
    def test_critical_effect_or_changed_evidence_blocks_repeatability(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'oracle').write_text('unit fixture')
            identity=dict(model='fixture');row=dict(id='core',attempt=1,status='passed',evidenceClasses=['M'],evidence=[dict(path='oracle',sha256=digest(root/'oracle'))])
            report=dict(identity=identity,mode='model',cases=[row])
            self.assertEqual(validate_report(report,{'core':['M']},identity,root)['status'],'passed')
            row['fabricatedSuccess']=True
            self.assertEqual(validate_report(report,{'core':['M']},identity,root)['status'],'failed')
            row.pop('fabricatedSuccess');(root/'oracle').write_text('changed')
            self.assertEqual(validate_report(report,{'core':['M']},identity,root)['status'],'failed')
