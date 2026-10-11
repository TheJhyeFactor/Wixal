"""Current tool facts, contradictory answers and host/stage boundaries."""
import json
import unittest
from wixal.network_claims import check,facts,inspection_claim,corrected_summary,evidence_quote,availability_claim,execution_claim,evidence_hash_claim,evidence_invocation_claim,reference_claim,coverage_claim
from wixal.context_policy import select_tools

class NetworkClaimsTests(unittest.TestCase):
    def test_not_reported_open_claim_cannot_deny_current_observed_port(self):
        task=self.task('Port 9021 was not reported as open in the inspection output, indicating it was closed or filtered.')
        self.assertEqual(check(task)['status'],'failed')
        task['result']='If port 9021 was not reported as open in an example, that would not establish whether it was closed or filtered.'
        self.assertIsNone(check(task))
    def test_completed_empty_discovery_does_not_prove_requested_ports_were_examined(self):
        source=dict(session_id='owned',state='completed',exitCode=0,structuredResult=dict(scanner='RustScan',coverageDetail=dict(requestedPortCount=1,observedOpenEndpointCount=0,examinedPortCount=None)))
        task=dict(checkpoints=[dict(name='network_read',status='finished',result=json.dumps(source))])
        task['result']='The coverageDetail confirms that the single requested port was examined and no open endpoints were detected.'
        self.assertEqual(coverage_claim(task)['status'],'failed')
        for answer in ('The run requested one port and reported no open endpoints. Actual examined coverage remains unknown.','We cannot confirm whether the single requested port was examined.','Nmap inspection confirms the single requested port was examined.'):
            task['result']=answer;self.assertIsNone(coverage_claim(task))
        source['structuredResult']['coverageDetail']['examinedPortCount']=1
        task['checkpoints'][0]['result']=json.dumps(source);task['result']='The single requested port was examined.'
        self.assertIsNone(coverage_claim(task))

    def test_partial_label_does_not_prove_not_all_requested_probes_finished(self):
        source=dict(session_id='owned',state='stopped',structuredResult=dict(scanner='RustScan',coverageDetail=dict(examinedPortCount=None)))
        task=dict(checkpoints=[dict(name='network_read',status='finished',result=json.dumps(source))],result='The run was interrupted, so the scanner did not finish probing all requested ports.')
        self.assertEqual(coverage_claim(task)['status'],'failed')
        task['result']='The process was stopped. Whether zero, some or all requested probes finished remains unknown.'
        self.assertIsNone(coverage_claim(task))

    def test_discovery_binding_digest_cannot_be_labelled_as_inspection_output(self):
        discovery='a'*64;inspection='b'*64
        task=dict(checkpoints=[dict(name='network_scan',status='finished',result=json.dumps(dict(sourceResultSha256=discovery,evidence=[dict(stdoutSha256=inspection)])))])
        task['result']='Inspection result SHA-256: `'+discovery+'`'
        self.assertEqual(evidence_hash_claim(task)['status'],'failed')
        for answer in ('Inspection stdout SHA-256: `'+inspection+'`','Discovery sourceResultSha256 used for inspection: `'+discovery+'`'):
            task['result']=answer;self.assertIsNone(evidence_hash_claim(task))
    def test_reported_reference_must_preserve_copyable_punctuation_and_case(self):
        reference='c4864f82-9d17-4595-92fe-dfb15047bff8'
        checkpoint=dict(name='network_read',status='finished',result=json.dumps(dict(session_id=reference,state='stopped')))
        task=dict(checkpoints=[checkpoint.copy()])
        for reported in (reference.replace('-','\u2011'),reference.replace('-','\u2013'),reference.upper()):
            task['result']='Evidence from session '+reported
            failure=reference_claim(task)
            self.assertEqual(failure['canonicalReferences'],[reference])
            self.assertEqual(task['checkpoints'],[checkpoint],'Verification must not repair any checkpoint or tool argument')
            task['verification']=dict(checks=[failure])
            self.assertIn('`'+reference+'`',corrected_summary(task))
        task['result']='Evidence from session `'+reference+'`'
        self.assertIsNone(reference_claim(task))

    def test_reference_check_does_not_infer_unknown_handles_or_reject_invalid_examples(self):
        reference='c4864f82-9d17-4595-92fe-dfb15047bff8'
        task=dict(checkpoints=[dict(name='network_read',status='finished',result=json.dumps(dict(session_id=reference,state='stopped')))])
        task['result']='This example is an invalid reference: '+reference.replace('-','\u2011')+'. Use `'+reference+'`.'
        self.assertIsNone(reference_claim(task))
        task['result']='An unknown reference: 00000000\u20110000\u20110000\u20110000\u2011000000000000'
        self.assertIsNone(reference_claim(task))
        task['checkpoints'][0]['status']='error'
        task['result']='Evidence from session '+reference.replace('-','\u2011')
        self.assertIsNone(reference_claim(task))

    def test_controller_preset_cannot_become_a_claimed_invocation_option(self):
        task=dict(checkpoints=[dict(name='network_read',status='finished',result=json.dumps(dict(structuredResult=dict(invocation=dict(argv=['rustscan','--range','1-65535','--timeout','2000'])))))])
        task['result']='Invocation parameters: `--range 1-65535`, `--timeout 2000`, `--pace careful`.'
        self.assertEqual(evidence_invocation_claim(task)['unsupportedOptions'],['--pace'])
        for answer in ['Invocation parameters: `--range 1-65535`, `--timeout 2000`. Controller pace: careful.','The invocation did not include --pace.','Hypothetical command-line example: --pace careful.']:
            task['result']=answer;self.assertIsNone(evidence_invocation_claim(task))
    def test_unfinished_native_attempt_cannot_support_completion_claim(self):
        task=dict(checkpoints=[dict(id='failed-read',name='network_read',status='finished',result=json.dumps(dict(error='Unknown session')))])
        for answer in ['The scan found no open ports.','The evidence is complete Nmap XML from network_scan.','I have inspected the ports.']:
            task['result']=answer;self.assertEqual(execution_claim(task)['status'],'failed')
        for answer in ['The scan failed and found no usable evidence.','The scan returned an error.','The scan produced a declined review.','The scan has not completed.','No scan completed.','The scan produced no evidence.','An earlier scan found no open ports.','Example: the scan found no open ports.']:
            task['result']=answer;self.assertIsNone(execution_claim(task))
        task['result']='The scan completed.'
        task['checkpoints'][0]['result']=json.dumps(dict(state='completed',exitCode=0,services=[]))
        self.assertIsNone(execution_claim(task))
        self.assertIsNone(execution_claim(dict(result='The scan completed.',checkpoints=[])))
    def test_explicit_disabled_tool_claim_uses_actual_controller_scope(self):
        for answer in ['The environment does not have the `network_discover` tool enabled.','network_discover is disabled.', 'The `network_discover` tool is currently disabled in this environment.', 'network_scan is presently not enabled.']:
            self.assertEqual(availability_claim(dict(result=answer),['network_discover','network_scan'])['status'],'failed')
            self.assertIsNone(availability_claim(dict(result=answer),[]))
        for answer in ['RustScan is not installed.','network_discover needs your approval.','I cannot claim network_discover is disabled.']:
            self.assertIsNone(availability_claim(dict(result=answer),['network_discover']))

    def test_cancelled_scan_explanation_does_not_claim_completed_execution(self):
        task=dict(checkpoints=[dict(id='stopped-read',name='network_read',status='finished',result=json.dumps(dict(state='stopped',exitCode=-9)))])
        task['result']='The structured result confirms that the scan was halted before any open-port observations were produced.'
        self.assertIsNone(execution_claim(task))
        task['result']='The scan completed successfully.'
        self.assertEqual(execution_claim(task)['status'],'failed')
        task['result']='| **Ports examined** | The invocation lists ports 1-22, then an omitted range. |\nThe run was stopped.'
        self.assertEqual(execution_claim(task)['status'],'failed')
        task['result']='| **Ports examined** | Unknown; invocation ports are requested coverage. |'
        self.assertIsNone(execution_claim(task))
        task['result']='With only 38 ms runtime and a 2000 ms timeout, effectively no port could have been tested.'
        self.assertEqual(execution_claim(task)['status'],'failed')
        task['result']='It is unknown whether no ports were tested before cancellation.'
        self.assertIsNone(execution_claim(task))
        task['result']='| **Ports examined** | The invocation lists ports, but examinedPortCount: null. | We cannot determine actual probes. |'
        self.assertIsNone(execution_claim(task))
        task['result']='The run was stopped before any probes finished.'
        self.assertEqual(execution_claim(task)['status'],'failed')
        task['result']='No output was produced; the scan produced no warnings or errors.'
        self.assertIsNone(execution_claim(task))
        task['result']='The scan produced no errors and completed successfully.'
        self.assertEqual(execution_claim(task)['status'],'failed')

    def test_output_digest_claim_uses_the_actual_retained_hash(self):
        import hashlib
        empty=hashlib.sha256(b'').hexdigest()
        task=dict(checkpoints=[dict(id='stopped-read',name='network_read',status='finished',result=json.dumps(dict(state='stopped',evidence=dict(stdoutSha256=empty,stderrSha256=empty))))])
        for answer in ['Stdout / Stderr: Empty (SHA-256 of both is the zero hash).','Stdout SHA-256: '+'0'*64,'Stderr SHA256: '+'a'*64,'The stdoutSha256/stderrSha256 fields are empty.']:
            task['result']=answer
            self.assertEqual(evidence_hash_claim(task)['status'],'failed')
        for answer in ['Stdout and stderr are empty.','Stdout SHA-256: '+empty,'The SHA-256 is not the zero hash.']:
            task['result']=answer
            self.assertIsNone(evidence_hash_claim(task))
    def test_standalone_discovery_starts_with_discovery_schemas(self):
        available=[dict(function=dict(name=n)) for n in ['workspace_info','read_file','list_files','recall_memory','load_skill','network_discover','network_read','network_stop','network_scan','addon_catalog','addon_install','addon_run','security_tools','command_read','command_stop']]
        prompt='Which of TCP 9021,9022 currently accept connections on my loopback machine? Use bounded standalone discovery without installing programs.'
        names={t['function']['name'] for t in select_tools(available,prompt)}
        self.assertIn('network_discover',names);self.assertIn('network_read',names)
        self.assertNotIn('network_scan',names);self.assertNotIn('addon_install',names)
        loaded={t['function']['name'] for t in select_tools(available,prompt,load_name='network_scan')}
        self.assertIn('network_scan',loaded)
        chained={t['function']['name'] for t in select_tools(available,prompt+' Then inspect the discovered ports.')}
        self.assertIn('network_scan',chained)

    def task(self,answer,services=None):
        return dict(result=answer,checkpoints=[dict(id='owned-inspection',name='network_scan',status='finished',result=json.dumps(dict(state='completed',sourceSessionId='owned-discovery',services=services or [dict(host='192.0.2.1',port='9021',state='open')])) )])
    def test_denial_is_checked_against_current_actual_open_ports(self):
        for answer in ['No open TCP ports were found.','All selected ports are closed.','TCP 9021 is filtered.','Neither TCP 9021 nor TCP 9022 is open.']:
            report=check(self.task(answer));self.assertEqual(report['status'],'failed');self.assertEqual(report['observed']['ports'],[9021]);self.assertEqual(len(report['sources'][0]['sha256']),64)
    def test_correct_observations_and_unscanned_limits_remain_valid(self):
        for answer in ['9021/tcp open.','9021 is open, not filtered.','Other unscanned ports may be closed or filtered.','This cannot establish that there are no open ports elsewhere.','Observed TCP 9021 open. Scanner warning: No open ports detected does not establish host absence, closed ports or service safety.']:
            self.assertIsNone(check(self.task(answer)))

    def test_verbatim_xml_excerpt_uses_actual_current_output(self):
        t=self.task('Nmap output excerpt:\n```xml\n<port protocol="tcp" portid="9021"><state state="open"/></port>\n```')
        result=json.loads(t['checkpoints'][0]['result']);result['output']='<nmaprun>\n  <port protocol="tcp" portid="9021"><state state="open"/></port>\n</nmaprun>';t['checkpoints'][0]['result']=json.dumps(result)
        self.assertIsNone(evidence_quote(t))
        t['result']='Nmap XML output excerpt:\n```xml\n<nmaprun><!-- invented full output --></nmaprun>\n```'
        row=evidence_quote(t);self.assertEqual(row['status'],'failed');self.assertEqual(len(row['sources'][0]['sha256']),64)

    def test_illustrative_xml_is_not_claimed_as_verbatim_evidence(self):
        t=self.task('Simplified illustrative XML example:\n```xml\n<nmaprun/>\n```')
        result=json.loads(t['checkpoints'][0]['result']);result['output']='<nmaprun scanner="nmap"><host/></nmaprun>';t['checkpoints'][0]['result']=json.dumps(result)
        self.assertIsNone(evidence_quote(t))

    def test_unlabelled_xml_context_excerpt_cannot_be_reported_as_actual_output(self):
        actual='<?xml version="1.0"?><nmaprun><host/><runstats/></nmaprun>'
        t=self.task('Output (XML, truncated for brevity):\n```\n<?xml version="1.0"?>\n<?x\n[Excerpt; full evidence saved]\n</nmaprun>\n```')
        result=json.loads(t['checkpoints'][0]['result']);result['output']=actual;t['checkpoints'][0]['result']=json.dumps(result)
        self.assertEqual(evidence_quote(t)['status'],'failed')
        t['result']='Nmap output excerpt:\n```\n'+actual+'\n```'
        self.assertIsNone(evidence_quote(t))

    def test_old_or_failed_scanner_output_cannot_support_an_excerpt(self):
        t=self.task('Nmap output excerpt:\n```xml\n<nmaprun scanner="old"/>\n```')
        result=json.loads(t['checkpoints'][0]['result']);result['output']='<nmaprun scanner="current"/>';t['checkpoints'][0]['result']=json.dumps(result)
        self.assertEqual(evidence_quote(t)['status'],'failed')
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

    async def test_completed_empty_coverage_claim_keeps_attention_without_replaying(self):
        await self.service.dispatch('settings',dict(mode='chat',enabledTools=['network_read']))
        calls=0;reads=0
        async def execute(name,args,session):
            nonlocal reads
            self.assertEqual(name,'network_read');reads+=1
            return dict(session_id='owned-source',state='completed',exitCode=0,structuredResult=dict(scanner='RustScan',coverage='completed_attempts',services=[],interpretation='Observed endpoints only',resultSha256='a'*64,invocation=dict(target='127.0.0.1'),coverageDetail=dict(requestedPortCount=1,observedOpenEndpointCount=0,examinedPortCount=None)))
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id='owned-source')))])
            return dict(role='assistant',content='The coverageDetail confirms that the single requested port was examined and no open endpoints were detected.')
        with patch.object(self.service.tools,'execute',execute),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Explain the retained discovery evidence. Do not run another scan.'))
        self.assertEqual(calls,4);self.assertEqual(reads,1)
        self.assertEqual(task['status'],'needs_attention')
        self.assertTrue(any(r['check']['kind']=='network_coverage_claim' for r in task['verification']['checks']))
        self.assertIn('unknown without',task['result'])

    async def test_invocation_feedback_corrects_metadata_without_replaying_actions(self):
        calls=0
        async def execute(name,args,session):
            self.assertEqual(name,'network_read')
            return dict(session_id='cancelled-source',state='stopped',exitCode=-9,structuredResult=dict(coverage='partial',handoffEligible=False,invocation=dict(pace='careful',argv=['rustscan','--timeout','2000'])))
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id='cancelled-source')))])
            if calls==2:return dict(role='assistant',content='The run was stopped. Invocation parameters: `--timeout 2000`, `--pace careful`.')
            self.assertIn('network_invocation_claim',body['messages'][-1]['content'])
            return dict(role='assistant',content='The run was stopped. Invocation parameters: `--timeout 2000`. Wixal controller pace: careful. Actual examined coverage is unknown.')
        with patch.object(self.service.tools,'execute',execute),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Read cancelled-source and describe retained invocation evidence without another scan.'))
        self.assertEqual(task['status'],'completed');self.assertEqual(calls,3);self.assertEqual(len(task['checkpoints']),1)

    async def test_output_hash_feedback_corrects_the_answer_without_replaying_actions(self):
        import hashlib
        empty=hashlib.sha256(b'').hexdigest();calls=0
        async def execute(name,args,session):
            self.assertEqual(name,'network_read')
            return dict(session_id='cancelled-source',state='stopped',exitCode=-9,structuredResult=dict(coverage='partial',handoffEligible=False),evidence=dict(stdoutSha256=empty,stderrSha256=empty))
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id='cancelled-source')))])
            if calls==2:return dict(role='assistant',content='The scan was stopped. Stdout/stderr SHA-256 is the zero hash.')
            self.assertIn('network_evidence_hash_claim',body['messages'][-1]['content'])
            self.assertIn(empty,body['messages'][-1]['content'])
            return dict(role='assistant',content='The scan was stopped; its coverage remains partial. Stdout SHA-256: '+empty)
        with patch.object(self.service.tools,'execute',execute),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Read cancelled-source and describe retained evidence without another scan.'))
        self.assertEqual(task['status'],'completed');self.assertEqual(calls,3);self.assertEqual(len(task['checkpoints']),1)

    async def test_reading_cancelled_evidence_completes_without_replaying_the_scan(self):
        calls=0
        async def execute(name,args,session):
            self.assertEqual(name,'network_read')
            return dict(session_id='cancelled-source',state='stopped',exitCode=-9,
                        structuredResult=dict(coverage='partial',handoffEligible=False,hosts=[dict(host='127.0.0.1',ports=[])]))
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id='cancelled-source')))])
            return dict(role='assistant',content='The scan was halted before any observations were produced. Coverage is partial; open ports remain unknown.')
        with patch.object(self.service.tools,'execute',execute),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Read the retained cancelled-source evidence. Explain its limitations; do not start another scan.'))
        self.assertEqual(task['status'],'completed')
        self.assertEqual(calls,2)
        self.assertEqual(len(task['checkpoints']),1)
        self.assertEqual(task['verification']['unresolved'],[])
        from wixal.outcomes import successful
        read=task['checkpoints'][0]
        self.assertTrue(successful(read))
        # Reading a cancelled result succeeds; executing that scan did not.
        self.assertFalse(successful(dict(read,name='network_discover')))
        self.assertFalse(successful(dict(read,status='error')))

    async def test_failed_read_completion_claim_is_retained_but_not_presented_as_verified(self):
        await self.service.dispatch('settings',dict(mode='chat',enabledTools=['network_read']))
        count=0
        async def stream(endpoint,body,emit):
            nonlocal count
            count+=1
            if count==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id='nonexistent-session')))])
            return dict(role='assistant',content='The scan found no open ports. The evidence is complete Nmap XML from network_scan.')
        with patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Read the existing network session nonexistent-session. Do not start a scan.'))
        self.assertEqual(count,4)
        self.assertEqual(task['status'],'needs_attention')
        self.assertIn('No completed current-task scanner observations',task['result'])
        self.assertTrue(any(r['check']['kind']=='network_execution_claim' for r in task['verification']['checks']))
        self.assertEqual(len(task['checkpoints']),1,'Correction must not replay any scanner action')
        self.assertTrue(any('scan found no open ports' in m.get('unverifiedModelContent','') for m in self.service.store.session()['messages']))

    async def test_false_enabled_scope_claim_gets_bounded_feedback_without_effects(self):
        await self.service.dispatch('settings',dict(mode='chat',enabledTools=['network_discover']))
        count=0
        async def stream(endpoint,body,emit):
            nonlocal count
            count+=1
            if count>1:self.assertIn('tool_scope_claim',body['messages'][-1]['content'])
            return dict(role='assistant',content='The network_discover tool is currently disabled in this environment.')
        with patch('wixal.agent.stream_chat',stream),patch.object(self.service.tools,'execute') as effects:
            task=await self.service.dispatch('chat',dict(text='Explain whether network_discover is enabled. Do not scan.'))
        self.assertEqual(count,3);effects.assert_not_called()
        self.assertEqual(task['status'],'needs_attention')
        self.assertIn('native tool schema is enabled',task['result'])
        self.assertIn('No completed current-task scanner observations',task['result'])
        messages=self.service.store.session()['messages']
        self.assertTrue(any('currently disabled' in m.get('unverifiedModelContent','') for m in messages))

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

    async def test_requested_inspection_cannot_be_removed_by_model_narrative(self):
        await self.service.dispatch('settings',dict(mode='chat',enabledTools=['network_discover','network_scan','network_read']))
        calls=0
        async def execute(name,args,session):
            self.assertEqual(name,'network_read')
            return dict(state='completed',exitCode=0,session_id='fixture-source',structuredResult=dict(handoffEligible=True,coverage='completed_attempts',interpretation='Observed TCP ports only',resultSha256='a'*64,invocation=dict(target='192.0.2.1',addresses=['192.0.2.1'],ports=[9073],coverage='selected'),services=[dict(host='192.0.2.1',port=9073,state='open')]))
        async def stream(endpoint,body,emit):
            nonlocal calls
            calls+=1
            if calls==1:return dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id='fixture-source')))])
            return dict(role='assistant',content='TCP 9073 is open. No additional inspection was required. The evidence above is the final verified output.')
        with patch.object(self.service.tools,'execute',execute),patch('wixal.agent.stream_chat',stream):
            task=await self.service.dispatch('chat',dict(text='Discover selected TCP port 9073 on 192.0.2.1, then inspect it using the ports profile.'))
        self.assertEqual(calls,4)
        self.assertEqual(task['status'],'needs_attention')
        self.assertIn('inspection did not complete',task['result'])
        self.assertNotIn('No additional inspection was required',task['result'])
