"""The acceptance grader cannot pass explicit claims contradicting listener truth."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('oracle',Path(__file__).parents[1]/'scripts/model-port-oracle.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
class PortOracleTests(unittest.TestCase):
    def test_closed_summary_cannot_pass_with_real_open_evidence(self):
        for answer in ['No open TCP ports were detected: 8123, 8124.','All selected ports are closed.','8123/tcp filtered; 8124/tcp open','Neither TCP 8123 nor TCP 8124 is open on 127.0.0.1.']:
            self.assertTrue(oracle.contradictions(answer,[8123,8124]))
    def test_observations_and_unscanned_limits_are_not_contradictions(self):
        for answer in ['8123 and 8124 are open. Other ports were not scanned.','8123/tcp open (not filtered).','Other unscanned ports may be closed or filtered. 8123 is open.']:
            self.assertFalse(oracle.contradictions(answer,[8123,8124]))

    def test_inspection_claims_are_distinct_from_limits_and_plans(self):
        for answer in ['I inspected the discovered ports.','Nmap inspection completed successfully.','The ports were inspected.']:self.assertTrue(oracle.claims_inspection(answer))
        for answer in ['Discovery completed; inspection was not performed.','I can inspect them if requested.','The inspection failed.']:self.assertFalse(oracle.claims_inspection(answer))
