import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from test_security_workspace import SecurityWorkspaceTests
from wixal.simulation import WebsiteFixture
from wixal.storage import identity, now
import unittest


class SecurityRecordsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=SecurityWorkspaceTests.asyncSetUp
    asyncTearDown=SecurityWorkspaceTests.asyncTearDown
    wait_for=SecurityWorkspaceTests.wait_for

    def bypass(self):
        self.service.store.project()['approvalMode']='bypass'
        self.service.store.data['enabledTools']=[d['function']['name'] for d in self.service.tools.catalog()]

    def node(self,identifier,**values):
        row=dict(id=identifier,name=identifier,stage='Attacks',capability='website_simulate',arguments={},dependencies=[])
        row.update(values);return row

    async def plan(self,nodes):
        return await self.service.dispatch('security-plan-save',dict(targetId=self.target['id'],name='Validation plan',nodes=nodes))

    async def test_cycle_atomicity_and_join_conditions(self):
        self.bypass()
        with self.assertRaisesRegex(ValueError,'cycle'):
            await self.plan([self.node('a',dependencies=['b']),self.node('b',dependencies=['a'])])
        self.assertFalse(self.service.store.data['securityPlans'])
        plan=await self.plan([self.node('a'),self.node('b'),self.node('join',dependencies=['a','b'],condition=dict(kind='service_open',value='443'))])
        await self.service.dispatch('security-plan-run',dict(id=plan['id']))
        await self.wait_for(lambda:plan['status']=='completed')
        rows=[r for r in self.service.security_workspace.runs if r.get('planId')==plan['id']]
        self.assertEqual(rows[-1]['status'],'skipped')
        self.assertTrue(all(r['status']=='completed' for r in rows[:2]))
        bad=await self.plan([self.node('valid'),self.node('bad',capability='analysis',model='not-installed')])
        count=len(self.service.security_workspace.runs)
        with self.assertRaisesRegex(ValueError,'model'):await self.service.dispatch('security-plan-run',dict(id=bad['id']))
        self.assertEqual(len(self.service.security_workspace.runs),count)

    async def test_inventory_change_history_and_evidence_binding(self):
        manager=self.service.security_workspace
        run=dict(id=identity(),projectId=self.target['projectId'],targetId=self.target['id'],address='127.0.0.1',capability='network_scan',result=dict(services=[dict(host='127.0.0.1',port='443',protocol='tcp',state='open',service=dict(name='https',version='1'))]),status='completed',created=now())
        manager.runs.append(run);manager.ingest(run);manager.ingest(run)
        rows=self.service.store.data['securityDiscoveries']
        self.assertEqual(len(rows),2);self.assertEqual(len(rows[1]['observations']),1)
        newer=dict(run,id=identity(),result=dict(services=[dict(host='127.0.0.1',port='443',protocol='tcp',state='closed',service=dict(name='https'))]))
        manager.runs.append(newer);manager.ingest(newer)
        self.assertEqual(rows[1]['change'],'changed');self.assertEqual(len(rows[1]['observations']),2)
        # Conditions evaluate the prerequisite's snapshot, not stale/latest unrelated evidence.
        step=dict(targetId=self.target['id'],dependencies=[run['id']],condition=dict(kind='service_open',value='443'))
        self.assertTrue(manager.dependencies_ready(step)[0])
        bound={}
        provenance=manager.resolve_bindings(self.target,bound,dict(ports=dict(discoveryId=rows[1]['id'],field='port')))
        self.assertEqual(bound['ports'],'443')
        self.assertEqual(provenance[0]['sourceRuns'],[run['id'],newer['id']])
        with self.assertRaisesRegex(ValueError,'pinned target'):
            manager.resolve_bindings(self.target,{},dict(target=dict(discoveryId=rows[0]['id'],field='name')))
        promoted=await self.service.dispatch('security-discovery-promote',dict(id=rows[0]['id']))
        self.assertEqual(promoted['parentId'],self.target['id'])
        await self.service.dispatch('security-target-update',dict(id=promoted['id'],archived=True,notes='Reviewed',models={'default':'fixture'}))
        self.assertTrue(promoted['archived'])

    async def test_actual_website_findings_review_and_exports(self):
        self.bypass()
        async with WebsiteFixture(False) as fixture:
            target=await self.service.dispatch('security-target-add',dict(type='Website / API',address=fixture.origin))
            run=await self.service.dispatch('security-run-add',dict(targetId=target['id'],stage='Recon',capability='website_assess',arguments=dict(profile='baseline',max_pages=1)))
            await self.wait_for(lambda:run['status'] in ('completed','failed'))
        self.assertEqual(run['status'],'completed',run)
        findings=[f for f in self.service.store.data['securityFindings'] if f['targetId']==target['id']]
        self.assertTrue(findings)
        finding=findings[0]
        await self.service.dispatch('security-finding-update',dict(id=finding['id'],status='inconclusive',notes='Configuration observation needs impact validation'))
        self.assertEqual(finding['status'],'inconclusive')
        first=await self.service.dispatch('security-report-export',dict(targetId=target['id']))
        second=await self.service.dispatch('security-report-export',dict(targetId=target['id']))
        self.assertNotEqual(first['paths'],second['paths'])
        doc=json.loads(Path(first['paths'][0]).read_text())
        self.assertEqual(doc['securityFindings'][0]['runIds'],[run['id']])
        self.assertIn('inconclusive',Path(first['paths'][1]).read_text())

    async def test_software_contract_and_real_source_fetch(self):
        self.bypass()
        (self.root/'package.json').write_text(json.dumps(dict(dependencies={'example-package':'^2.0.0'})))
        target=await self.service.dispatch('security-target-add',dict(type='Software',address='package.json'))
        inventory=await self.service.dispatch('security-run-add',dict(targetId=target['id'],stage='Recon',capability='software_inventory'))
        await self.wait_for(lambda:inventory['status'] in ('completed','failed'))
        self.assertEqual(inventory['status'],'completed',inventory)
        self.assertEqual(inventory['result']['components'][0]['version'],'^2.0.0')
        contract=await self.service.dispatch('security-contract-save',dict(targetId=target['id'],name='Read manifest',tool='read_file',binding='path',defaults={},types=['Software']))
        run=await self.service.dispatch('security-run-add',dict(targetId=target['id'],stage='Recon',capability=contract['id'],arguments={'path':'../escape'}))
        await self.wait_for(lambda:run['status'] in ('completed','failed'))
        self.assertEqual(run['arguments']['path'],'package.json')
        self.assertEqual(run['status'],'completed')
        source=await self.service.dispatch('security-run-add',dict(targetId=target['id'],stage='Research',capability='research',model='fixture',prompt='Review source content',arguments=dict(urls=[self.fixture.url+'/api/version'])))
        await self.wait_for(lambda:source['status'] in ('completed','failed'))
        self.assertEqual(source['status'],'completed',source)
        row=self.service.store.data['securityResearch'][0]
        self.assertEqual(row['status'],200);self.assertTrue(row['contentSHA256'])
        self.assertEqual(row['applicability'],'needs_evidence')
        await self.service.dispatch('security-research-update',dict(id=row['id'],applicability='not_applicable',rationale='Fixture metadata, not an advisory'))
        self.assertEqual(row['applicability'],'not_applicable')

    async def test_planner_validates_model_proposal_before_executable_draft(self):
        self.bypass()
        response=dict(role='assistant',content=json.dumps(dict(name='Evidence review',nodes=[self.node('review',stage='Research',capability='analysis',prompt='Explain limitations')])),usage={'eval_count':12})
        with patch('wixal.security_workspace.stream_chat',new=AsyncMock(return_value=response)):
            run=await self.service.dispatch('security-run-add',dict(targetId=self.target['id'],stage='Research',capability='planner',model='fixture'))
            await self.wait_for(lambda:run['status'] in ('completed','failed'))
        self.assertEqual(run['status'],'completed',run)
        self.assertEqual(self.service.store.data['securityPlans'][-1]['status'],'draft')
        self.assertTrue(run['result']['planId'])
        response['content']=json.dumps(dict(nodes=[self.node('bad',capability='invented_exploit')]))
        with patch('wixal.security_workspace.stream_chat',new=AsyncMock(return_value=response)):
            failed=await self.service.dispatch('security-run-add',dict(targetId=self.target['id'],stage='Research',capability='planner',model='fixture'))
            await self.wait_for(lambda:failed['status']=='failed')
        self.assertIn('not an executable plan',failed['error'])

class SecurityInputEvidenceTests(unittest.TestCase):
    def test_form_inventory_omits_values_and_external_actions(self):
        from wixal.website import observed_inputs
        html='<form action="/login?token=private"><input name="password" type="password" value="secret"><input name="user" value="private"></form><form action="https://other.example/"><input name="external"></form>'
        forms=observed_inputs(html,'https://owned.example/')
        self.assertEqual(len(forms),1)
        self.assertEqual(forms[0]['action'],'https://owned.example/login')
        self.assertNotIn('secret',json.dumps(forms))
        self.assertNotIn('private',json.dumps(forms))
