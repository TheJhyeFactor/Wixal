import asyncio
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock
from wixal.service import Service
from wixal.agent_context import profile, automatic
from wixal.cyber_findings import FIELDS
from wixal.cyber_planning import PLAN_FIELDS
from wixal import engagement_evidence as evidence


class CyberTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.state=Path(self.temp.name)/'state'
        self.service=Service(self.state,Path('/nonexistent/ollama'),lambda *_:None)
        await self.service.dispatch('project-add',dict(root=str(self.root)))
        self.service.ask=AsyncMock(return_value=True)
        self.target=await self.service.dispatch('security-target-add',dict(type='Server',address='127.0.0.1',objective='Owned test'))
        self.engagement=await self.service.dispatch('security-engagement-create',dict(name='Cyber test',objective='Test evidence discipline',targetIds=[self.target['id']]))
        self.manager=self.service.security_workspace.engagements
        self.ref=evidence.retain(self.manager,self.engagement,dict(signal='test',token='private-value'),'external-untrusted','fixture')

    async def asyncTearDown(self):
        await self.service.close();self.temp.cleanup()

    async def call(self,action,read=False,**params):
        return await self.service.dispatch('security-cyber-read' if read else 'security-cyber-manage',dict(engagementId=self.engagement['id'],action=action,parameters=params))

    def draft(self,**changes):
        value=dict(targetId=self.target['id'],title='Synthetic finding',resultKind='observation',confidence='low',evidenceIds=[self.ref['id']])
        value.update({key:'Documented '+key for key in FIELDS});value.update(changes);return value

    async def approve(self):
        await self.service.dispatch('security-engagement-approve',dict(engagementId=self.engagement['id'],baseRevision=self.engagement['scopeRevision']))

    async def test_catalog_and_progressive_model_schema(self):
        result=await self.call('catalog',True);self.assertIn('finding_save',result['manageActions'])
        self.assertEqual(result['engagements'][0]['id'],self.engagement['id'])
        from wixal.context_policy import select_tools,category,requires_project
        names={t['function']['name'] for t in select_tools(self.service.tools.catalog(),'Review cyber engagement findings')}
        self.assertTrue({'cyber_read','cyber_manage'}<=names)
        self.assertEqual(category('cyber_read'),'security');self.assertTrue(requires_project('cyber_read'))

    async def test_unknown_actions_and_fields_rejected(self):
        for action,values in [('approve',{}),('finding_save',{'shell':'whoami'}),('export',{'includeEvidence':1})]:
            with self.assertRaises(ValueError):await self.call(action,**values)
        with self.assertRaises(ValueError):await self.call('finding_save',True,**self.draft())

    async def test_complete_draft_does_not_confirm_claim(self):
        result=await self.call('finding_save',**self.draft());row=result['finding']
        self.assertTrue(result['quality']['valid']);self.assertEqual(row['verificationState'],'unverified')
        await self.call('finding_complete',findingId=row['id'],baseRevision=1)
        self.assertEqual(row['reportStatus'],'complete');self.assertEqual(row['status'],'candidate');self.assertTrue(row['needsReview'])

    async def test_missing_counterevidence_no_mutation(self):
        with self.assertRaises(ValueError):await self.call('finding_save',**self.draft(counterevidence=''))
        self.assertEqual(self.service.store.data['securityFindings'],[])

    async def test_revision_history_invalidates_disposition(self):
        row=(await self.call('finding_save',**self.draft()))['finding'];row.update(cvssScore=7,verificationState='validated',reviewed=1)
        with self.assertRaisesRegex(ValueError,'revision'):await self.call('finding_save',**self.draft(findingId=row['id'],baseRevision=0))
        row=(await self.call('finding_save',**self.draft(findingId=row['id'],baseRevision=1,title='Updated')))['finding']
        self.assertEqual(row['revision'],2);self.assertEqual(len(row['history']),1)
        self.assertNotIn('cvssScore',row);self.assertNotIn('reviewed',row);self.assertEqual(row['verificationState'],'unverified')

    async def test_tampered_evidence_rejects_completion(self):
        row=(await self.call('finding_save',**self.draft()))['finding']
        (self.state/'engagement-evidence'/self.engagement['id']/(self.ref['sha256']+'.json')).write_text('{}')
        self.assertFalse((await self.call('finding_quality',True,findingId=row['id']))['valid'])
        with self.assertRaises(ValueError):await self.call('finding_complete',findingId=row['id'],baseRevision=1)

    async def test_duplicate_suggestions_do_not_merge(self):
        first=(await self.call('finding_save',**self.draft()))['finding'];second=await self.call('finding_save',**self.draft())
        self.assertEqual(second['duplicates']['matches'][0]['findingId'],first['id']);self.assertEqual(len(self.service.store.data['securityFindings']),2)

    async def test_cve_match_respects_component(self):
        await self.call('finding_save',**self.draft(title='First',resultKind='dependency_cve',cveIds=['CVE-2026-12345'],component='lib-a',componentVersion='1'))
        result=await self.call('finding_save',**self.draft(title='Different',description='Different content',resultKind='dependency_cve',cveIds=['CVE-2026-12345'],component='lib-b',componentVersion='1'))
        self.assertEqual(result['duplicates']['matches'],[])

    async def test_planning_revision_and_scope_staleness(self):
        values={key:'Documented '+key for key in PLAN_FIELDS};await self.call('planning_save',baseRevision=0,**values)
        with self.assertRaises(ValueError):await self.call('planning_save',baseRevision=0,**values)
        self.engagement['scopeRevision']+=1
        result=await self.call('dossier',True);self.assertTrue(result['stale']);self.assertFalse(result['missingFields'])

    async def test_report_integrity_redaction_and_project_exclusion(self):
        await self.call('finding_save',**self.draft(description='Bearer abcdefghijklmn'))
        (self.root/'unrelated-private.txt').write_text('must-not-export')
        result=await self.call('export',includeEvidence=True)
        with zipfile.ZipFile(result['paths'][0]) as archive:
            manifest=json.loads(archive.read('manifest.json'));self.assertTrue(manifest['evidenceIncluded'])
            for name,info in manifest['files'].items():self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),info['sha256'])
            self.assertNotIn('unrelated-private.txt',' '.join(archive.namelist()))
            content=b' '.join(archive.read(name) for name in archive.namelist())
            self.assertNotIn(b'private-value',content);self.assertNotIn(b'abcdefghijklmn',content)
            sarif=json.loads(archive.read('results.sarif'));self.assertEqual(sarif['version'],'2.1.0')
            self.assertEqual(sarif['runs'][0]['results'][0]['properties']['verificationState'],'unverified')

    async def test_export_without_evidence_and_exclusive_names(self):
        one=await self.call('export');two=await self.call('export');self.assertNotEqual(one['paths'],two['paths'])
        with zipfile.ZipFile(one['paths'][0]) as archive:self.assertFalse(any(p.startswith('evidence/') for p in archive.namelist()))

    async def test_cross_project_denied(self):
        other=Path(self.temp.name)/'other';other.mkdir();await self.service.dispatch('project-add',dict(root=str(other)))
        with self.assertRaises(ValueError):await self.call('snapshot',True)

    async def test_closed_records_are_immutable_but_exportable(self):
        self.engagement['status']='completed'
        with self.assertRaises(ValueError):await self.call('finding_save',**self.draft())
        self.assertTrue((await self.call('export'))['paths'])

    async def test_model_review_denial_and_read_only(self):
        self.service.tools.approve=AsyncMock(return_value=False);token=automatic.set(True)
        try:
            result=await self.service.tools.execute('cyber_manage',dict(action='finding_save',engagement_id=self.engagement['id'],parameters_json=json.dumps(self.draft())),'chat')
            self.assertEqual(result['status'],'declined');self.assertFalse(self.service.store.data['securityFindings'])
            context=profile.set(dict(reviewPolicy='Read only'))
            try:
                with self.assertRaises(ValueError):await self.service.tools.execute('cyber_manage',dict(action='export',engagement_id=self.engagement['id']),'chat')
            finally:profile.reset(context)
        finally:automatic.reset(token)

    async def test_delegate_and_target_authority(self):
        for active in ({'_delegateTools':['cyber_read']},{'restrictTargets':True,'authority':{'targets':['192.0.2.1']}}):
            token=profile.set(active)
            try:
                with self.assertRaises(ValueError):await self.service.tools.execute('cyber_read',dict(action='snapshot',engagement_id=self.engagement['id']),'chat')
            finally:profile.reset(token)

    async def enroll(self,content):
        (self.root/'service.log').write_bytes(content)
        return await self.call('sensor_enroll',targetId=self.target['id'],path='service.log')

    async def test_sensor_retains_raw_records_without_replay(self):
        row=await self.enroll(b'{"message":"authentication failed"}\n{"message":"ok"}\n');await self.approve()
        await self.call('sensor_collect',sensorId=row['id']);self.assertEqual(row['delivered'],2)
        state=await self.call('sensors',True);self.assertEqual(len(state['incidents']),1);self.assertEqual(state['incidents'][0]['status'],'lead')
        await self.call('sensor_collect',sensorId=row['id']);self.assertEqual(len(self.manager.rows('securityIncidents',self.engagement)),1)
        _,value=evidence.read(self.manager,self.engagement,row['lastEvidenceId']);self.assertIn('rawText',value)

    async def test_sensor_partial_record_and_rotation(self):
        complete=b'{"message":"ok"}\n';row=await self.enroll(complete+b'partial');await self.approve()
        await self.call('sensor_collect',sensorId=row['id']);self.assertEqual(row['delivered'],1);self.assertEqual(row['offset'],len(complete))
        (self.root/'service.log').write_text('rotated\n');await self.call('sensor_collect',sensorId=row['id'])
        self.assertEqual(row['status'],'paused');self.assertIn('rotated',row['gap'])

    async def test_sensor_malformed_and_oversize_no_silent_loss(self):
        row=await self.enroll(b'{broken}\n{"message":"ok"}\n');await self.approve();await self.call('sensor_collect',sensorId=row['id'])
        self.assertEqual(row['malformed'],1);self.assertIn('Malformed',row['gap'])
        (self.root/'large.log').write_bytes(b'x'*1048576);second=await self.call('sensor_enroll',targetId=self.target['id'],path='large.log')
        await self.call('sensor_collect',sensorId=second['id']);self.assertEqual(second['offset'],0);self.assertEqual(second['status'],'paused')

    async def test_sensor_scope_and_restart(self):
        row=await self.enroll(b'ok\n')
        with self.assertRaises(ValueError):await self.call('sensor_collect',sensorId=row['id'])
        await self.approve();await self.call('sensor_start',sensorId=row['id']);await asyncio.sleep(.02)
        self.assertEqual(row['status'],'monitoring');await self.service.close()
        self.service=Service(self.state,Path('/nonexistent/ollama'),lambda *_:None);self.manager=self.service.security_workspace.engagements
        self.assertEqual(self.service.store.data['securitySensors'][0]['status'],'paused');self.assertEqual(self.service.store.data['securityEngagements'][0]['status'],'paused')

    async def test_sensor_denial_and_sensitive_path(self):
        self.service.ask=AsyncMock(return_value=False)
        with self.assertRaises(ValueError):await self.enroll(b'ok\n')
        self.assertFalse(self.service.store.data['securitySensors']);(self.root/'.env').write_text('secret')
        with self.assertRaises(ValueError):await self.call('sensor_enroll',targetId=self.target['id'],path='.env')

    async def test_binary_triage_is_source_bound_and_inert(self):
        binary=self.root/'sample';binary.write_bytes(b'\x7fELFhello-static-string\0')
        ref=await self.call('binary_triage',path='sample',targetId=self.target['id']);_,value=evidence.read(self.manager,self.engagement,ref['id'])
        self.assertEqual(value['format'],'ELF');self.assertEqual(value['sha256'],hashlib.sha256(binary.read_bytes()).hexdigest())
        self.assertFalse((await self.call('analysis_readiness',True))['runtimeStarted'])

    async def test_analysis_import_requires_exact_source(self):
        (self.root/'sample').write_bytes(b'123');path=self.root/'analysis.json'
        path.write_text(json.dumps(dict(provider='external',sourceSha256='bad',observations=[])))
        with self.assertRaises(ValueError):await self.call('analysis_import',path='analysis.json',binaryPath='sample',targetId=self.target['id'])
        path.write_text(json.dumps(dict(provider='external',sourceSha256=hashlib.sha256(b'123').hexdigest(),observations=[])))
        result=await self.call('analysis_import',path='analysis.json',binaryPath='sample',targetId=self.target['id']);self.assertEqual(result['kind'],'external-binary-analysis')

    async def test_retest_rejects_model_only_scalar_claim(self):
        row=(await self.call('finding_save',**self.draft()))['finding']
        check=self.manager.add('securityVerifications',self.engagement,status='discriminated',scopeRevision=1)
        with self.assertRaises(ValueError):await self.call('retest',findingId=row['id'],verificationIds=[check['id']],fixDescription='Fix',limitations='Synthetic')

    async def test_skills_idempotent_and_attributed(self):
        one=await self.call('skills');two=await self.call('skills');self.assertEqual(one,two);self.assertEqual(len(one['skillIds']),18)
        new=[s for s in self.service.store.data['skills'] if s.get('source')=='wixal:cyber-skills:v2']
        self.assertEqual(len(new),13);self.assertTrue(all(s['provenance']['revision'].startswith('00fc3b') for s in new))

    async def test_model_reads_exact_project_engagement_ids(self):
        token=automatic.set(True)
        try:
            result=await self.service.tools.execute('cyber_read',dict(action='catalog'),'chat');self.assertEqual(result['engagements'][0]['id'],self.engagement['id'])
        finally:automatic.reset(token)

    async def test_rank_paths_explains_assumptions_without_execution(self):
        objective=await self.service.dispatch('security-objective-save',dict(engagementId=self.engagement['id'],targetId=self.target['id'],title='Question',hypothesis='Test',successSignal='Signal'))
        await self.service.dispatch('security-relation-add',dict(engagementId=self.engagement['id'],fromId=self.target['id'],toId=objective['id'],kind='supports',state='inferred',evidenceIds=[],rationale='Unverified prerequisite'))
        result=await self.call('rank_paths',True,fromId=self.target['id'],toId=objective['id'])
        self.assertEqual(result['paths'][0]['unresolvedAssumptions'],1);self.assertEqual(result['paths'][0]['state'],'candidate')
        self.assertTrue(result['paths'][0]['nextChecks']);self.assertFalse(self.manager.workspace.runs)

    async def test_score_only_vulnerabilities_and_no_confirmation(self):
        row=(await self.call('finding_save',**self.draft()))['finding']
        vector='CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'
        with self.assertRaises(ValueError):await self.call('finding_score',findingId=row['id'],vector=vector,rationale='Synthetic')
        row=(await self.call('finding_save',**self.draft(findingId=row['id'],baseRevision=1,resultKind='vulnerability')))['finding']
        await self.call('finding_score',findingId=row['id'],vector=vector,rationale='Synthetic arithmetic only')
        self.assertEqual(row['cvssScore'],9.8);self.assertEqual(row['verificationState'],'unverified')

    async def test_defensive_specialist_consumes_only_bound_sensor_evidence(self):
        from wixal.engagement_evidence import specialist_source
        row=await self.enroll(b'{"message":"authentication failed"}\n');await self.approve()
        await self.call('sensor_collect',sensorId=row['id'])
        source=specialist_source(self.manager,self.engagement,row['lastEvidenceId'],'defensive_analyst',self.target['id'])
        self.assertNotIn('rawText',source['result']);self.assertEqual(source['sourceEvidenceId'],row['lastEvidenceId'])
        with self.assertRaises(ValueError):specialist_source(self.manager,self.engagement,row['lastEvidenceId'],'verifier',self.target['id'])
        self.service.runtime.catalog=AsyncMock(return_value=[dict(name='test')]);await self.service.dispatch('security-queue-settings',dict(paused=True))
        assignment=await self.service.dispatch('security-specialist-assign',dict(engagementId=self.engagement['id'],targetId=self.target['id'],role='defensive_analyst',question='Review lead and coverage',model='test',evidenceIds=[row['lastEvidenceId']]))
        run=self.manager.record('securityRuns',assignment['runId'],self.engagement)
        context=self.manager.workspace.evidence_context(run)
        self.assertEqual(context[0]['evidenceId'],row['lastEvidenceId']);self.assertNotIn('runId',context[0])
        self.assertEqual(context[0]['capability'],'retained_analysis')

    async def test_capability_retest_requires_linked_objective(self):
        from wixal.storage import identity,now
        objective=await self.service.dispatch('security-objective-save',dict(engagementId=self.engagement['id'],targetId=self.target['id'],title='Port state',hypothesis='State changes',successSignal='Comparable states'))
        row=(await self.call('finding_save',**self.draft(objectiveId=objective['id'])))['finding']
        refs=[]
        for state in ('open','closed'):
            run=dict(id=identity(),projectId=self.engagement['projectId'],engagementId=self.engagement['id'],targetId=self.target['id'],scopeRevision=1,
                     capability='network_scan',environment='test',status='completed',arguments=dict(profile='ports'),result=dict(services=[dict(host='127.0.0.1',port=80,state=state)]),finished=now())
            self.manager.workspace.runs.append(run);self.manager.finished(run);refs.append(run['retainedEvidenceId'])
        contract=self.manager.add('securityValidationContracts',self.engagement,objectiveId=objective['id'],targetId=self.target['id'],scopeRevision=1,
                                  validator='network_port_state',config=dict(host='127.0.0.1',port=80,positiveState='open',baselineState='closed'))
        check=self.manager.assurance.validate(self.engagement,dict(contractId=contract['id'],evidenceIds=refs))
        result=await self.call('retest',findingId=row['id'],verificationIds=[check['id']],fixDescription='Synthetic state change',limitations='Fixture only; no real remediation')
        self.assertEqual(result['status'],'declared_checks_passed');self.assertEqual(row['verificationState'],'unverified')
        row['objectiveId']='another-objective'
        with self.assertRaises(ValueError):await self.call('retest',findingId=row['id'],verificationIds=[check['id']],fixDescription='Synthetic',limitations='Fixture')

    async def test_model_evidence_reader_distinguishes_original_from_derivative(self):
        result=await self.call('evidence',True,evidenceId=self.ref['id'])
        self.assertNotIn('private-value',result['content']);self.assertIn('[REDACTED]',result['content'])
        self.assertEqual(result['sourceSha256'],self.ref['sha256'])
        self.assertNotEqual(result['sourceSha256'],result['derivativeSha256'])
        with self.assertRaises(ValueError):await self.call('evidence',True,evidenceId=self.ref['id'],offset=-1)

    async def test_finding_edit_preserves_omitted_identity_and_objective(self):
        objective=await self.service.dispatch('security-objective-save',dict(engagementId=self.engagement['id'],targetId=self.target['id'],title='Identity',hypothesis='Test',successSignal='Signal'))
        details=dict(component='library',componentVersion='1.2',rootCause='cause',surface='api',identityId='guest',cveIds=['CVE-2026-12345'],objectiveId=objective['id'])
        row=(await self.call('finding_save',**self.draft(**details)))['finding']
        updated=(await self.call('finding_save',**self.draft(findingId=row['id'],baseRevision=1,title='Edited')))['finding']
        for key,value in details.items():self.assertEqual(updated[key],value)

    async def test_finding_rejects_stale_and_cross_target_binary_evidence(self):
        (self.root/'sample').write_bytes(b'\x7fELFtest')
        ref=await self.call('binary_triage',path='sample',targetId=self.target['id'])
        other=await self.service.dispatch('security-target-add',dict(type='Server',address='127.0.0.2',objective='Other'))
        self.engagement['targetIds'].append(other['id'])
        with self.assertRaisesRegex(ValueError,'another target'):await self.call('finding_save',**self.draft(targetId=other['id'],evidenceIds=[ref['id']]))
        self.engagement['scopeRevision']+=1
        with self.assertRaisesRegex(ValueError,'scope revision'):await self.call('finding_save',**self.draft(evidenceIds=[ref['id']]))

    async def test_report_roundtrip_preserves_untrusted_boundary(self):
        await self.call('finding_save',**self.draft())
        exported=await self.call('export',includeEvidence=True)
        result=await self.call('report_import',path=Path(exported['paths'][0]).name)
        _,value=evidence.read(self.manager,self.engagement,result['id'])
        self.assertEqual(result['kind'],'external-report-package')
        self.assertEqual(len(self.service.store.data['securityFindings']),1)
        self.assertIsNone(self.engagement['approval'])
        self.assertIn('Untrusted external',value['provenance'])
        from docx import Document
        document=Document(next(p for p in exported['paths'] if p.endswith('technical-report.docx')))
        self.assertIn('Synthetic finding','\n'.join(p.text for p in document.paragraphs))

    async def test_report_import_rejects_tamper_traversal_and_unlisted_members(self):
        exported=await self.call('export')
        for mode in ('tamper','traversal','unlisted'):
            bad=self.root/(mode+'.zip')
            with zipfile.ZipFile(exported['paths'][0]) as source,zipfile.ZipFile(bad,'w') as target:
                for name in source.namelist():target.writestr(name,b'{}' if mode=='tamper' and name=='engagement.json' else source.read(name))
                if mode!='tamper':target.writestr('../escape' if mode=='traversal' else 'unlisted.json','{}')
            with self.assertRaises(ValueError):await self.call('report_import',path=bad.name)
        self.assertFalse(self.manager.rows('securityEvidence',self.engagement)[1:])

    async def test_sensor_grouping_configuration_archive_and_http_bounds(self):
        row=await self.enroll((b'{"message":"authentication failed"}\n'*500)+b'{"message":"invalid status","status":900}\n')
        await self.approve();await self.call('sensor_configure',sensorId=row['id'],rules=['authentication_failure','http_server_error'])
        await self.call('sensor_collect',sensorId=row['id'])
        incidents=self.manager.rows('securityIncidents',self.engagement)
        self.assertEqual(len(incidents),1);self.assertEqual(incidents[0]['count'],500)
        await self.call('sensor_archive',sensorId=row['id'])
        with self.assertRaisesRegex(ValueError,'archived'):await self.call('sensor_collect',sensorId=row['id'])
        evidence.read(self.manager,self.engagement,row['lastEvidenceId'])

    async def test_planning_reports_scope_contradictions(self):
        values={key:'Documented '+key for key in PLAN_FIELDS}
        await self.call('planning_save',baseRevision=0,**values)
        self.engagement['scopes'][-1]['policy']['contacts']='Different approved contact'
        result=await self.call('dossier',True)
        self.assertEqual(result['consistencyChecks'][0]['status'],'differs_from_approved_scope')
        self.assertFalse(result['executionReady'])

    async def test_model_run_derivative_puts_limits_before_normalized_scripts(self):
        value=dict(runId='run',result=dict(output='x'*20000,structuredResult=dict(interpretation='Support only; NLA requirement unverified',services=[dict(host='127.0.0.1',port='3389',scripts=[dict(id='rdp-enum-encryption',output='CredSSP SUCCESS')])])))
        ref=evidence.retain(self.manager,self.engagement,value,'run','run')
        result=await self.call('evidence',True,evidenceId=ref['id'])
        self.assertTrue(result['content'].startswith('{\n  "interpretation"'))
        self.assertIn('CredSSP SUCCESS',result['content']);self.assertNotIn('x'*100,result['content'])
        self.assertFalse(result['more']);self.assertEqual(result['sourceSha256'],ref['sha256'])
