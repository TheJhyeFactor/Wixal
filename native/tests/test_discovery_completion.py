import json
import unittest
from wixal.outcomes import discovery_follow_up

class DiscoveryCompletionTests(unittest.TestCase):
    def task(self,prompt='Discover the TCP ports and then inspect the discovered ports'):
        return dict(prompt=prompt,checkpoints=[dict(name='network_read',status='finished',result=json.dumps(dict(session_id='fresh-source',state='completed',structuredResult=dict(handoffEligible=True))))])
    def test_missing_requested_inspection_is_detected(self):
        result=discovery_follow_up(self.task());self.assertEqual(result['status'],'failed');self.assertEqual(result['sourceSessions'],['fresh-source'])
    def test_discovery_only_does_not_gain_authority_for_inspection(self):
        for prompt in ['Discover these ports. Do not inspect service versions.','Discover TCP ports. Do not install tools or inspect service versions.','Use discovery without Nmap','Explain discovery and inspection','Discover ports; no service enumeration']:
            task=self.task(prompt)
            if prompt.startswith('Explain'):task['checkpoints']=[]
            self.assertIsNone(discovery_follow_up(task))
    def test_old_or_unrelated_inspection_cannot_complete_new_source(self):
        task=self.task();task['checkpoints'].append(dict(name='network_scan',status='finished',result=json.dumps(dict(sourceSessionId='old-source',exitCode=0))))
        self.assertEqual(discovery_follow_up(task)['status'],'failed')
        task['checkpoints'][-1]['result']=json.dumps(dict(sourceSessionId='fresh-source',state='completed',services=[]))
        self.assertEqual(discovery_follow_up(task)['status'],'passed')
    def test_partial_discovery_does_not_request_handoff(self):
        task=self.task();task['checkpoints'][0]['result']=json.dumps(dict(session_id='source',state='stopped',structuredResult=dict(handoffEligible=False)))
        self.assertIsNone(discovery_follow_up(task))
