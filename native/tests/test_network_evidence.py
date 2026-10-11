"""Context/view regressions; these controlled cases are not model qualification."""
import copy
import json
import unittest
import test_agents_runtime as fixtures
from wixal.context_policy import bounded_evidence,token_estimate
from wixal.network_discovery import parse,ports
from wixal.network_evidence import model_view,port_ranges


def stopped_result():
    invocation=dict(target='127.0.0.1',addresses=['127.0.0.1'],ports=list(range(1,65536)),coverage='all_tcp',argv=['rustscan','--range','1-65535'])
    return dict(session_id='9c893842-416c-47e3-89d9-41d7045dcac5',state='stopped',exitCode=-9,
                structuredResult=parse('',invocation,False),output='',evidence=dict(stdoutSha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'))


class EvidenceViewTests(unittest.TestCase):
    def test_compact_range_preserves_exact_requested_set(self):
        for values in ([1,2,3,8,10,11,65535],list(range(1,65536))):
            self.assertEqual(ports(port_ranges(values)),values)

    def test_unknown_examined_coverage_and_identity_survive_all_tcp_view(self):
        source=stopped_result();original=copy.deepcopy(source);view=json.loads(model_view('network_read',json.dumps(source)))
        self.assertLess(len(json.dumps(view)),2500)
        self.assertEqual(view['session_id'],source['session_id'])
        self.assertEqual(view['structuredResult']['invocation']['requestedPorts'],'1-65535')
        self.assertEqual(view['structuredResult']['invocation']['requestedPortCount'],65535)
        self.assertIsNone(view['structuredResult']['coverageDetail']['examinedPortCount'])
        self.assertFalse(view['structuredResult']['handoffEligible'])
        self.assertEqual(source,original)

    def test_generic_bound_is_real_for_nested_and_escaped_content(self):
        value=dict(state='stopped',session_id='exact-reference',structuredResult=stopped_result(),nested=[stopped_result()]*5,quoted='"\\\n'*5000)
        for limit in (400,1000,2400,6000):
            result=bounded_evidence(json.dumps(value),limit)
            self.assertLessEqual(len(result),limit)
            self.assertTrue(json.loads(result)['excerpt'])
        self.assertLessEqual(len(bounded_evidence(json.dumps([value]*4),400)),400)

    def test_output_pagination_uses_actual_unicode_prefix_not_excerpt_marker(self):
        result=dict(session_id='reader',state='completed',evidence=dict(stdoutSha256='saved-digest'),offset=40,more=False,output='😀x'*2000)
        view=json.loads(model_view('network_read',json.dumps(result)))
        self.assertEqual(view['output'],result['output'][:1600])
        self.assertEqual(view['outputRange'],dict(offset=40,next_offset=2440,more=True))
        self.assertTrue(view['outputExcerpt'])
        self.assertEqual(view['evidence'][0]['stdoutSha256'],'saved-digest')

    def test_small_xml_is_exact_and_large_endpoint_sets_are_explicitly_incomplete(self):
        xml='<?xml version="1.0"?><nmaprun><host/></nmaprun>\n'
        value=dict(sourceSessionId='discovery',state='completed',output=xml,evidenceReport=dict(stage='inspection',observedEndpoints=[dict(host='127.0.0.1',port=p,state='open')for p in range(1,1001)]))
        view=json.loads(model_view('network_scan',json.dumps(value)))
        self.assertEqual(view['output'],xml);self.assertFalse(view['outputExcerpt'])
        self.assertEqual(view['evidenceReport']['omittedEndpoints'],976)
        self.assertEqual(len(view['evidenceReport']['observedEndpoints']),24)

    def test_non_scanner_tools_are_unchanged(self):
        content=json.dumps(stopped_result())
        self.assertEqual(model_view('read_file',content),content)


class PreparedScannerRequestTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown

    async def test_all_tcp_read_fits_8192_without_changing_history_or_tools(self):
        await self.service.dispatch('settings',dict(enabledTools=['network_read']))
        agent=self.service.agent;agent.model_info=dict(name='fixture',capabilities=['tools','thinking'])
        session=self.service.store.session();result=stopped_result()
        prompt='Read retained cancelled discovery evidence with network_read. Do not start another scan.'
        session['messages']=[dict(role='user',content=prompt),dict(role='assistant',content='',tool_calls=[dict(function=dict(name='network_read',arguments=dict(session_id=result['session_id'])))]),dict(role='tool',tool_name='network_read',content=json.dumps(result))]
        original=copy.deepcopy(session['messages'])
        for context in (8192,4096):
            agent.effective_context=lambda:context
            body=agent.request_body(session,supports_tools=True)
            self.assertLessEqual(token_estimate(body['messages'],body.get('tools',[]))[0]+body['options']['num_predict'],context)
            tool=next(m for m in body['messages']if m['role']=='tool')
            view=json.loads(tool['content']);self.assertEqual(view['session_id'],result['session_id'])
            coverage=view.get('coverageDetail',view.get('structuredResult',{}).get('coverageDetail',{}))
            self.assertIn('examinedPortCount',coverage);self.assertIsNone(coverage['examinedPortCount'])
            self.assertEqual(session['messages'],original)
            self.assertIn('network_read',[d['function']['name']for d in body['tools']])
