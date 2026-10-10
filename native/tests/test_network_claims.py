"""Current tool facts, contradictory answers and host/stage boundaries."""
import json
import unittest
from wixal.network_claims import check,facts,inspection_claim,corrected_summary
from wixal.context_policy import select_tools

class NetworkClaimsTests(unittest.TestCase):
    def task(self,answer,services=None):
        return dict(result=answer,checkpoints=[dict(id='owned-inspection',name='network_scan',status='finished',result=json.dumps(dict(state='completed',sourceSessionId='owned-discovery',services=services or [dict(host='192.0.2.1',port='9021',state='open')])) )])
    def test_denial_is_checked_against_current_actual_open_ports(self):
        for answer in ['No open TCP ports were found.','All selected ports are closed.','TCP 9021 is filtered.','Neither TCP 9021 nor TCP 9022 is open.']:
            report=check(self.task(answer));self.assertEqual(report['status'],'failed');self.assertEqual(report['observed']['ports'],[9021]);self.assertEqual(len(report['sources'][0]['sha256']),64)
    def test_correct_observations_and_unscanned_limits_remain_valid(self):
        for answer in ['9021/tcp open.','9021 is open, not filtered.','Other unscanned ports may be closed or filtered.','This cannot establish that there are no open ports elsewhere.']:
            self.assertIsNone(check(self.task(answer)))
    def test_later_inspection_state_supersedes_earlier_discovery(self):
        t=self.task('TCP 9021 is closed.');t['checkpoints'].append(dict(id='later',name='network_scan',status='finished',result=json.dumps(dict(state='completed',services=[dict(host='192.0.2.1',port=9021,state='closed')]))))
        self.assertIsNone(check(t));self.assertEqual(facts(t)[0]['192.0.2.1'][9021],'closed')
    def test_multiple_hosts_do_not_share_a_port_state(self):
        t=self.task('9021 is closed on the second host.',[dict(host='192.0.2.1',port=9021,state='open'),dict(host='192.0.2.2',port=9021,state='closed')]);self.assertIsNone(check(t))
    def test_incomplete_results_cannot_supply_completed_observations(self):
        t=self.task('9021 is closed.');value=json.loads(t['checkpoints'][0]['result']);value['state']='failed';t['checkpoints'][0]['result']=json.dumps(value);self.assertEqual(facts(t)[0],{})
    def test_failed_inspection_claim_replaced_by_actual_stage_summary(self):
        self.assertTrue(inspection_claim('The same session was used for inspection; the scan completed successfully.'))
        t=self.task('Inspection completed.');t['verification']=dict(checks=[dict(check=dict(kind='requested_discovery_inspection'),status='failed')]);summary=corrected_summary(t)
        self.assertIn('9021',summary);self.assertIn('inspection did not complete',summary)
    def test_json_verification_schema_is_not_added_for_scan_report_verbs(self):
        available=[dict(function=dict(name=n)) for n in ['workspace_info','verify_json','network_discover','network_scan','network_read','network_stop','run_command','command_read','read_file']]
        names={t['function']['name'] for t in select_tools(available,'Discover and inspect ports, then report evidence.')};self.assertNotIn('verify_json',names)
        names={t['function']['name'] for t in select_tools(available,'Run a command to verify report.json against package.json.')};self.assertIn('verify_json',names)

    def test_mixed_port_states_are_kept_separate_in_one_summary(self):
        t=self.task('9021 open, 9022 closed; other ports were not scanned.',[dict(host='192.0.2.1',port=9021,state='open'),dict(host='192.0.2.1',port=9022,state='closed')]);self.assertIsNone(check(t))
        t['result']='9022 is open.';self.assertEqual(check(t)['status'],'failed')
    def test_empty_discovery_does_not_support_a_positive_open_port_claim(self):
        t=dict(result='9021/tcp is open.',checkpoints=[dict(id='empty',name='network_read',status='finished',result=json.dumps(dict(state='completed',exitCode=0,session_id='owned-empty',structuredResult=dict(handoffEligible=True,invocation=dict(coverage='selected',addresses=['192.0.2.1'],ports=[9021]),services=[]))))])
        self.assertEqual(check(t)['status'],'failed')
        t['result']='No open TCP ports were observed. This does not establish that the port is closed.';self.assertIsNone(check(t))

    def test_reading_an_old_discovery_does_not_override_later_inspection(self):
        discovery=dict(state='completed',finished=100,structuredResult=dict(handoffEligible=True,invocation=dict(coverage='selected',addresses=['192.0.2.1'],ports=[9021]),services=[dict(host='192.0.2.1',port=9021,state='open')]))
        t=self.task('9021 is closed.',[dict(host='192.0.2.1',port=9021,state='closed')]);t['checkpoints'][0]['finished']=200
        t['checkpoints'].append(dict(id='old-reread',name='network_read',status='finished',finished=300,result=json.dumps(discovery)))
        self.assertIsNone(check(t));self.assertEqual(facts(t)[0]['192.0.2.1'][9021],'closed')
    def test_udp_observations_are_not_reported_as_tcp(self):
        self.assertEqual(facts(self.task('9021 TCP is closed.',[dict(host='192.0.2.1',port=9021,state='open',protocol='udp')]))[0],{})

    def test_uncertain_scanner_states_are_not_claimed_as_definite_open(self):
        t=self.task('9021/tcp open|filtered.',[dict(host='192.0.2.1',port=9021,state='open|filtered')]);self.assertIsNone(check(t))
        t['result']='9021 is open.';self.assertEqual(check(t)['status'],'failed')

import test_agents_runtime as fixtures
from unittest.mock import patch

class ProductionNetworkClaimTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def run_claim(self,recover):
        await self.service.dispatch('settings',dict(mode='chat',enabledTools=['network_scan']))
        count=0;effects=0
        async def execute(name,args,session):
            nonlocal effects
            self.assertEqual(name,'network_scan');effects+=1
            return dict(state='completed',sourceSessionId='fixture-source',services=[dict(host='192.0.2.1',port='9073',state='open',protocol='tcp')])
        async def stream(endpoint,body,emit):
            nonlocal count
            count+=1
            if count==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_scan',arguments=dict(target='192.0.2.1',ports='9073',profile='ports')))])
            if recover and count>=3:
                self.assertIn('Controller verification found unfinished work',body['messages'][-1]['content'])
                return dict(role='assistant',content='Observed TCP port 9073 open in the selected scan.')
            return dict(role='assistant',content='No open TCP ports were observed.')
        with patch.object(self.service.tools,'execute',execute),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Scan selected TCP port 9073 on 192.0.2.1 and report its actual state.'))
        self.assertEqual(effects,1,'The claim check must not replay the scan')
        return task,count

    async def test_contradiction_feedback_recovers_without_replaying_effects(self):
        task,count=await self.run_claim(True)
        self.assertEqual(count,3);self.assertEqual(task['status'],'completed');self.assertIn('9073 open',task['result'])
    async def test_exhausted_correction_keeps_attention_and_controller_facts(self):
        task,count=await self.run_claim(False)
        self.assertEqual(count,4);self.assertEqual(task['status'],'needs_attention');self.assertIn('9073',task['result']);self.assertNotIn('No open TCP ports',task['result'])
        self.assertEqual(task['verification']['checks'][0]['check']['kind'],'network_port_claim')
