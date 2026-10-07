import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.scheduling import due

class ScheduleTests(unittest.TestCase):
    def test_latest_coalesces_missed_runs_and_preserves_cadence(self):
        row=dict(enabled=True,nextRun=1000,intervalSeconds=60)
        result=due(row,181001)
        self.assertEqual(result['missed'],3);self.assertFalse(result['skip']);self.assertEqual(result['nextRun'],241000)
        self.assertIsNone(due(row,999))
    def test_skip_is_explicit(self):
        self.assertTrue(due(dict(enabled=True,nextRun=1000,intervalSeconds=60,missedRunPolicy='skip'),121000)['skip'])
        self.assertIsNone(due(dict(enabled=False,nextRun=1000,intervalSeconds=60),121000))
