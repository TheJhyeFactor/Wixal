"""Independent qualification review preserves failures and missing evidence."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('review',Path(__file__).parents[1]/'scripts/managed-model-outcome-review.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)

class ModelOutcomeReviewTests(unittest.TestCase):
    def report(self):
        def evidence(scenario):
            return [] if scenario=='naturalDiscovery' else [dict(tool_name='network_scan',content=json.dumps(dict(state='completed',sourceSessionId='fixture-source',services=[dict(port=8123),dict(port=8124)])))]
        return dict(status='passed',finished=1,modelAttempts=[dict(scenario=scenario,attempt=i,status='passed',oracle=dict(ports=[8123,8124]),output=dict(answer='Observed 8123 and 8124 open.',toolResults=evidence(scenario))) for scenario in ('naturalDiscovery','sourceInspection') for i in range(1,31)])

    def check(self,report):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report.json';path.write_text(json.dumps(report));original=path.read_bytes()
            result=review.review(path);self.assertEqual(path.read_bytes(),original)
            return result

    def test_threshold_allows_retained_honest_failure(self):
        report=self.report();report['modelAttempts'][0]['status']='failed'
        result=self.check(report)
        self.assertEqual(result['status'],'core_thresholds_passed')
        self.assertEqual(result['cores']['naturalDiscovery']['passed'],29)
        self.assertEqual(result['attempts'][0]['status'],'failed')

    def test_rejected_interpretation_is_checked_even_with_truthful_controller_answer(self):
        report=self.report();attempt=report['modelAttempts'][30]
        attempt['output']['toolResults']=[]
        attempt.update(status='failed',rejectedModelInterpretation='The inspection confirms that the only ports discovered are the three specified, all of which are open.',task=dict(result='Inspection did not complete.',checkpoints=[dict(name='network_scan',status='finished',result=json.dumps(dict(state='failed',sourceSessionId='fixture',services=[])))]))
        result=self.check(report);self.assertEqual(result['status'],'qualification_blocked')
        self.assertTrue(result['attempts'][30]['criticalFailure'])

    def test_missing_oracle_is_not_reconstructed_from_prose(self):
        report=self.report();report['modelAttempts'][0].pop('oracle')
        result=self.check(report);self.assertEqual(result['status'],'qualification_blocked')
        self.assertTrue(result['attempts'][0]['missingListenerOracle'])

    def test_duplicate_attempt_ids_cannot_complete_thirty(self):
        report=self.report();report['modelAttempts'][1]['attempt']=1
        self.assertFalse(self.check(report)['cores']['naturalDiscovery']['exactlyThirty'])

    def test_running_report_is_refused(self):
        report=self.report();report['status']='running'
        with self.assertRaises(ValueError):self.check(report)

    def test_original_pass_cannot_replace_missing_inspection_evidence(self):
        report=self.report()
        for attempt in report['modelAttempts']:attempt['output']['toolResults']=[]
        result=self.check(report)
        self.assertEqual(result['status'],'qualification_blocked')
        self.assertEqual(result['cores']['sourceInspection']['passed'],0)
