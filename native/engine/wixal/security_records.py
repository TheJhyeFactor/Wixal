"""Investigation evidence, capability contracts and editable plans."""
import copy
import hashlib
import json
from urllib.parse import urlsplit
from .storage import identity, now
from .tools import DEFINITIONS, safe_path, validate
from .website import website_plan

COLLECTIONS = ('securityDiscoveries', 'securityFindings', 'securityResearch', 'securityPlans', 'securityTemplates', 'securityEvents', 'securityContracts')
BUILTINS = {
    'network_discover': dict(title='Discover TCP ports', types=['Website / API','Server','Network device'], tools=['network_discover'], inputs=['coverage','ports','pace','timeout_seconds']),
    'network_scan': dict(title='Network assessment', types=['Website / API','Network','Server','Network device'], tools=['network_scan'], inputs=['profile','ports','timeout_seconds']),
    'website_assess': dict(title='Website assessment', types=['Website / API'], tools=['website_assess'], inputs=['profile','max_pages','protected_paths']),
    'website_simulate': dict(title='Local simulations', types=['Website / API','Network','Server','Network device','Software'], tools=['website_simulate'], inputs=[]),
    'software_inventory': dict(title='Software inventory', types=['Software'], tools=['list_files','read_file'], inputs=[]),
    'research': dict(title='Source research', types=['Website / API','Network','Server','Network device','Software'], tools=['web_search','http_request'], inputs=['urls','automatic']),
    'analysis': dict(title='Evidence analysis', types=['Website / API','Network','Server','Network device','Software'], tools=[], inputs=[]),
    'planner': dict(title='AI plan builder', types=['Website / API','Network','Server','Network device','Software'], tools=[], inputs=[]),
}
TERMINAL = ('completed','failed','cancelled','interrupted','skipped')
FINDING_STATES = ('unreviewed','confirmed','false_positive','resolved','accepted_risk','inconclusive')
APPLICABILITY = ('needs_evidence','possibly_relevant','applicable','not_applicable')


class SecurityRecords:
    def initialize_records(self):
        for key in COLLECTIONS:self.store.data.setdefault(key, [])
        # Idempotent migration: historical evidence becomes inspectable records.
        for run in self.runs:
            if run.get('status') == 'completed' and not run.get('indexed'):
                self.ingest(run)

    def record(self, collection, record_id):
        row=next((r for r in self.store.data[collection] if r['id']==record_id),None)
        if not row or row['projectId']!=self.store.data.get('activeProject'):
            raise ValueError('Choose an item in the active project')
        return row

    def audit(self, target, action, detail):
        self.store.data['securityEvents'].append(dict(id=identity(),projectId=target['projectId'],targetId=target['id'],action=action,detail=detail,created=now()))
        self.store.data['securityEvents']=self.store.data['securityEvents'][-1500:]

    def capability_catalog(self, target):
        enabled=set(self.store.data.get('enabledTools',[]))
        definitions={d['function']['name']:d['function'] for d in self.service.tools.catalog()}
        rows=[]
        for name, spec in BUILTINS.items():
            if target['type'] not in spec['types']:continue
            missing=[t for t in spec['tools'] if t not in enabled]
            manager=getattr(self.store,'addons',None)
            if name=='network_discover' and (not manager or not manager.executable(manager.spec('rustscan'))):missing.append('Install compatible RustScan')
            rows.append(dict(id=name,**spec,available=not missing,missing=missing))
        manager=getattr(self.store,'addons',None)
        if manager:
            for identifier in ('ffuf','nuclei','trivy','osv-scanner','testssl','wireshark'):
                contract=self.addon_contract(identifier)
                if target['type'] not in contract['types']:continue
                spec=manager.spec(identifier);missing=[] if manager.executable(spec) else ['Install '+spec['name']]
                if 'addon_run' not in enabled:missing.append('addon_run')
                rows.append(dict(id=contract['id'],title=contract['name'],types=contract['types'],tools=['addon_run'],available=not missing,missing=missing,inputs=definitions.get('addon_run',{}).get('parameters',{}),instructions=contract['instructions']))
        for contract in self.store.data['securityContracts']:
            if contract['projectId']!=target['projectId'] or target['type'] not in contract['types']:continue
            missing=[] if contract['tool'] in enabled and contract['tool'] in definitions else [contract['tool']]
            rows.append(dict(id=contract['id'],title=contract['name'],types=contract['types'],tools=[contract['tool']],available=not missing,missing=missing,inputs=definitions.get(contract['tool'],{}).get('parameters',{}),instructions=contract.get('instructions','')))
        return rows

    def addon_contract(self,identifier):
        manager=getattr(self.store,'addons',None)
        if not manager:raise ValueError('Capability library is unavailable')
        spec=manager.spec(identifier)
        if identifier not in ('ffuf','nuclei','trivy','osv-scanner','testssl','wireshark'):raise ValueError('No structured investigation adapter')
        types=['Software'] if identifier in ('trivy','osv-scanner','wireshark') else ['Website / API'] if identifier in ('ffuf','nuclei') else ['Website / API','Server','Network device']
        return dict(id='addon:'+identifier,name=spec['name'],tool='addon_run',types=types,binding='path' if identifier in ('trivy','osv-scanner','wireshark') else 'target',defaults=dict(id=identifier),instructions=spec['description'])

    def contract(self, capability, target):
        if not isinstance(capability,str):raise ValueError('Choose a capability')
        if capability.startswith('addon:'):
            row=self.addon_contract(capability.split(':',1)[1])
        elif capability in BUILTINS:
            row=BUILTINS[capability]
        else:
            row=next((c for c in self.store.data['securityContracts'] if c['id']==capability and c['projectId']==target['projectId']),None)
        if not row or target['type'] not in row['types']:raise ValueError('Capability does not support this target')
        return row

    def upsert_observation(self, run, kind, key, values):
        target=next(t for t in self.store.data['securityTargets'] if t['id']==run['targetId'])
        rows=self.store.data['securityDiscoveries']
        item=next((d for d in rows if d['targetId']==target['id'] and d['kind']==kind and d['key']==key and d.get('simulation',False)==(run['capability']=='website_simulate')),None)
        stamp=dict(runId=run['id'],created=run.get('finished',now()),values=copy.deepcopy(values))
        if item is None:
            item=dict(id=identity(),projectId=run['projectId'],targetId=run['targetId'],kind=kind,key=key,firstSeen=now(),observations=[],simulation=run['capability']=='website_simulate')
            rows.append(item)
        previous=item.get('values')
        projected=copy.deepcopy(values)
        if kind=='service' and previous and previous.get('service') and not projected.get('service'):
            projected['service']=copy.deepcopy(previous['service']);projected['identityHistorical']=True;projected['identitySourceRun']=item.get('identitySourceRun') or (item['observations'][-1]['runId'] if item['observations'] else None)
        elif kind=='service' and projected.get('service'):projected.update(identitySourceRun=run['id'],identityHistorical=projected.get('state')!='open')
        item.update(values=projected,lastSeen=now(),change='new' if previous is None else 'changed' if previous!=values else 'unchanged')
        if not any(o['runId']==run['id'] for o in item['observations']):
            item['observations']=(item['observations']+[stamp])[-30:]
        return item

    def ingest(self, run):
        result=run.get('result',{})
        if not isinstance(result,dict):return
        for row in result.get('services',[]):
            self.upsert_observation(run,'host',row['host'],dict(address=row['host'],confidence='observed scanner response'))
            self.upsert_observation(run,'service',row['host']+':'+str(row['port'])+'/'+row['protocol'],row)
        report=result.get('report',result)
        for request in report.get('requests',[]):
            if request.get('url'):
                self.upsert_observation(run,'route',request['url'],{k:request.get(k) for k in ('url','method','status','contentType','bodySha256','error') if k in request})
        for form in report.get('inputs',[]):
            self.upsert_observation(run,'input',form['page']+'|'+form['action']+'|'+form['method'],form)
        for component in result.get('components',[]):
            self.upsert_observation(run,'component',component['manifest']+':'+component['name'],component)
        for row in report.get('findings',[]):
            key=str(row.get('id',''))+'|'+str(row.get('url',run['address']))
            findings=self.store.data['securityFindings']
            item=next((f for f in findings if f['targetId']==run['targetId'] and f['key']==key and f.get('simulation',False)==(run['capability']=='website_simulate')),None)
            if item is None:
                item=dict(id=identity(),projectId=run['projectId'],targetId=run['targetId'],key=key,status='unreviewed',notes='',created=now(),runIds=[],simulation=run['capability']=='website_simulate')
                findings.append(item)
            if item.get('status')=='resolved' and run['id'] not in item['runIds']:
                item['needsReview']=True
            item.update(title=row.get('title',key),severity=row.get('severity','unknown'),confidence=row.get('confidence','needs review'),evidence=row.get('evidence'),remediation=row.get('remediation',''),url=row.get('url',run['address']),lastSeen=now())
            item['runIds']=list(dict.fromkeys(item['runIds']+[run['id']]))
        run['indexed']=True

    def evidence_context(self, run):
        allowed=run.get('evidenceIds',[])
        rows=[r for r in self.runs if r['targetId']==run['targetId'] and r['status']=='completed' and (run['capability']!='planner' or r['capability'] not in ('analysis','research','planner')) and (not allowed or r['id'] in allowed)]
        # Prefer compact structured evidence, no recursive sources or repeated raw XML.
        context=[]
        remaining=30000
        for row in reversed(rows):
            result=copy.deepcopy(row.get('result',{}))
            if isinstance(result,dict):
                result={k:v for k,v in result.items() if k not in ('sources','output','usage')}
            encoded=json.dumps(result,ensure_ascii=False)
            if len(encoded)>6000:result=dict(excerpt=encoded[:6000],truncated=True)
            item=dict(runId=row['id'],name=row['name'],capability=row['capability'],result=result)
            size=len(json.dumps(item))
            if size>remaining:break
            context.insert(0,item);remaining-=size
            if len(context)>=12:break
        inventory=[dict(id=d['id'],kind=d['kind'],values=d['values'],sourceRuns=[o['runId'] for o in d['observations']]) for d in self.store.data['securityDiscoveries'] if d['targetId']==run['targetId'] and not d.get('simulation') and (not allowed or any(o['runId'] in allowed for o in d['observations']))]
        context.append(dict(discoveries=inventory[:60],inventoryTruncated=len(inventory)>60))
        sources=[r for r in self.store.data['securityResearch'] if r['targetId']==run['targetId'] and (not allowed or r['runId'] in allowed)]
        context.append(dict(retrievedSources=[dict(id=r['id'],url=r['url'],status=r.get('status'),content=r.get('content','')[:4000],applicability=r['applicability'],rationale=r.get('rationale',''),error=r.get('error'),excerpt=True) for r in sources[-6:]]))
        return context

    def dependencies_ready(self, run):
        dependencies=run.get('dependencies') or ([run['dependency']] if run.get('dependency') else [])
        parents=[next((p for p in self.runs if p['id']==d),None) for d in dependencies]
        if any(p is None for p in parents):return False,'blocked','Prerequisite is unavailable'
        if any(p['status'] not in TERMINAL for p in parents):return False,'blocked','Waiting for prerequisites'
        if any(p['status']!='completed' for p in parents):return False,'blocked','A prerequisite did not complete'
        condition=run.get('condition',{})
        if not condition:return True,'queued',''
        kind=condition['kind']
        discoveries=[d for d in self.store.data['securityDiscoveries'] if d['targetId']==run['targetId'] and not d.get('simulation') and (not dependencies or any(o['runId'] in dependencies for o in d['observations']))]
        if dependencies:
            discoveries=[dict(d,values=next(o['values'] for o in reversed(d['observations']) if o['runId'] in dependencies)) for d in discoveries]
        if kind=='service_open':
            match=any(d['kind']=='service' and d['values'].get('state')=='open' and str(d['values'].get('port'))==str(condition['value']) for d in discoveries)
        elif kind=='http_status':
            match=any(d['kind']=='route' and str(d['values'].get('status'))==str(condition['value']) for d in discoveries)
        else:
            match=any(f['targetId']==run['targetId'] and f['key'].split('|')[0]==str(condition['value']) and (not dependencies or any(r in dependencies for r in f['runIds'])) for f in self.store.data['securityFindings'])
        return (True,'queued','') if match else (False,'skipped','Required evidence was not observed')

    def validate_condition(self, condition):
        if not isinstance(condition,dict) or set(condition)-{'kind','value'}:raise ValueError('Invalid evidence condition')
        if condition and (condition.get('kind') not in ('service_open','http_status','finding_present') or not isinstance(condition.get('value'),(str,int)) or isinstance(condition.get('value'),bool) or len(str(condition['value']))>160):raise ValueError('Choose a supported evidence condition')

    def validate_plan(self, target, nodes):
        if not isinstance(nodes,list) or not 1<=len(nodes)<=16:raise ValueError('Plan needs 1–16 steps')
        ids=[n.get('id') for n in nodes if isinstance(n,dict)]
        if len(ids)!=len(nodes) or any(not isinstance(i,str) or not i or len(i)>80 for i in ids) or len(set(ids))!=len(ids):raise ValueError('Step IDs must be unique text')
        available={c['id'] for c in self.capability_catalog(target)}
        for node in nodes:
            if set(node)-{'id','name','stage','capability','arguments','prompt','dependencies','condition','reason','model','evidenceIds','bindings','source_node_id'}:raise ValueError('Unknown plan step field')
            if node.get('capability') not in available or node.get('stage') not in ('Recon','Research','Attacks'):raise ValueError('Plan uses an unsupported stage or capability')
            if not isinstance(node.get('arguments',{}),dict) or len(json.dumps(node))>16000:raise ValueError('Step arguments exceed limits')
            for field in ('name','prompt','reason','model'):
                if field in node and (not isinstance(node[field],str) or len(node[field])>8000):raise ValueError('Plan text field is invalid or too long')
            deps=node.get('dependencies',[])
            if not isinstance(deps,list) or any(d not in ids or d==node['id'] for d in deps):raise ValueError('Plan dependencies must refer to other steps')
            source=node.get('source_node_id')
            if source and (node['capability']!='network_scan' or source not in deps or next(n for n in nodes if n['id']==source)['capability']!='network_discover' or 'ports' in node.get('arguments',{})):raise ValueError('Inspection source must be an explicit discovery dependency without manual ports')
            self.validate_condition(node.get('condition',{}))
        remaining={n['id']:set(n.get('dependencies',[])) for n in nodes};ordered=[]
        while remaining:
            ready=[k for k,v in remaining.items() if not v]
            if not ready:raise ValueError('Plan contains a dependency cycle')
            for key in ready:
                ordered.append(next(n for n in nodes if n['id']==key));remaining.pop(key)
            for deps in remaining.values():deps.difference_update(ready)
        return copy.deepcopy(ordered)

    def resolve_bindings(self,target,args,bindings):
        if not isinstance(bindings,dict) or len(bindings)>8:raise ValueError('Bindings must be up to eight argument mappings')
        provenance=[]
        for argument,binding in bindings.items():
            if argument in ('url','target','path','directory','report_prefix') or not isinstance(argument,str):raise ValueError('Bindings cannot change the pinned target or evidence paths')
            if not isinstance(binding,dict) or set(binding)!={'discoveryId','field'}:raise ValueError('Binding needs discoveryId and field')
            row=self.record('securityDiscoveries',binding['discoveryId'])
            if row['targetId']!=target['id'] or row.get('simulation'):raise ValueError('Choose live evidence from this target')
            field=binding['field']
            if field not in ('port','protocol','status','name','version'):raise ValueError('Choose a supported discovery field')
            value=row['values'].get(field,row['values'].get('service',{}).get(field))
            if value is None:raise ValueError('Discovery does not contain the selected field')
            args[argument]=str(value) if argument=='ports' else value
            provenance.append(dict(argument=argument,discoveryId=row['id'],field=field,value=value,sourceRuns=[o['runId'] for o in row['observations']]))
        return provenance

    async def records_dispatch(self, method, params):
        if method=='security-capabilities':return True,self.capability_catalog(self.target(params.get('targetId')))
        if method=='security-target-update':
            target=self.target(params.get('id'))
            if set(params)-{'id','objective','notes','archived','models'}:raise ValueError('Address is immutable; create a new target to preserve history')
            for key in ('objective','notes'):
                if key in params:
                    if not isinstance(params[key],str) or len(params[key])>8000:raise ValueError('Target text exceeds 8,000 characters')
                    target[key]=params[key]
            if 'archived' in params:
                if type(params['archived']) is not bool:raise ValueError('Invalid archive state')
                if params['archived'] and any(r['targetId']==target['id'] and r['status'] in ('queued','blocked','running','waiting_review','waiting_model') for r in self.runs):raise ValueError('Stop target work before archiving')
                target['archived']=params['archived']
            if 'models' in params:
                if not isinstance(params['models'],dict) or set(params['models'])-{'default','Recon','Research','Attacks'} or any(not isinstance(m,str) or len(m)>200 for m in params['models'].values()):raise ValueError('Invalid model preferences')
                target['models']=params['models']
            self.audit(target,'target_updated',dict(fields=list(params)));self.publish();return True,target
        if method=='security-discovery-promote':
            d=self.record('securityDiscoveries',params.get('id'))
            if d.get('simulation') or d['kind']!='host':raise ValueError('Only observed live hosts can become device targets')
            result=await self.dispatch('security-target-add',dict(type='Network device',address=d['values']['address'],parentId=d['targetId'],objective='Investigate discovered host'))
            return True,result
        if method=='security-finding-update':
            row=self.record('securityFindings',params.get('id'))
            if params.get('status',row['status']) not in FINDING_STATES or not isinstance(params.get('notes',''),str) or len(params.get('notes',''))>8000:raise ValueError('Invalid finding review')
            row.update(needsReview=False,status=params.get('status',row['status']),notes=params.get('notes',row['notes']),reviewed=now())
            self.audit(self.target(row['targetId']),'finding_reviewed',dict(id=row['id'],status=row['status']));self.publish();return True,row
        if method=='security-research-update':
            row=self.record('securityResearch',params.get('id'))
            if params.get('applicability') not in APPLICABILITY or not isinstance(params.get('rationale',''),str) or len(params.get('rationale',''))>8000:raise ValueError('Supply an applicability decision and evidence rationale')
            row.update(applicability=params['applicability'],rationale=params.get('rationale',''),reviewed=now());self.publish();return True,row
        if method in ('security-plan-save','security-template-save'):
            target=self.target(params.get('targetId'))
            nodes=self.validate_plan(target,params.get('nodes'))
            name=params.get('name','Investigation plan').strip()
            if not name or len(name)>160:raise ValueError('Enter a plan name below 160 characters')
            if method=='security-template-save' and any(n.get('bindings') or n.get('evidenceIds') for n in nodes):raise ValueError('Remove target-specific evidence bindings before saving a reusable template')
            collection='securityTemplates' if method=='security-template-save' else 'securityPlans'
            row=self.record(collection,params['id']) if params.get('id') else dict(id=identity(),projectId=target['projectId'],targetId=target['id'],created=now())
            if row['targetId']!=target['id']:raise ValueError('Plan belongs to a different target')
            row.update(name=name,nodes=nodes,status='draft',updated=now(),targetType=target['type'])
            if row not in self.store.data[collection]:self.store.data[collection].append(row)
            self.audit(target,'plan_saved',dict(id=row['id'],steps=len(nodes)));self.publish();return True,row
        if method=='security-template-apply':
            template=self.record('securityTemplates',params.get('id'));target=self.target(params.get('targetId'))
            if template['targetType']!=target['type']:raise ValueError('Template target type does not match')
            return True,await self.dispatch('security-plan-save',dict(targetId=target['id'],name=template['name'],nodes=template['nodes']))
        if method=='security-plan-run':
            if self.service.active and not self.service.active.done():raise ValueError('Finish the current chat or agent before starting this plan')
            plan=self.record('securityPlans',params.get('id'));target=self.target(plan['targetId'])
            if plan['status']!='draft':raise ValueError('Duplicate this plan to run again')
            nodes=self.validate_plan(target,plan['nodes'])
            # Validate the complete graph before any process starts.
            prepared=[]
            for node in nodes:
                catalog=next(c for c in self.capability_catalog(target) if c['id']==node['capability'])
                if not catalog['available']:raise ValueError('Unavailable capability: enable '+', '.join(catalog['missing']))
                payload=dict(node,targetId=target['id'],model=node.get('model') or target.get('models',{}).get(node['stage']) or params.get('model') or target.get('models',{}).get('default',''))
                payload.pop('id',None);payload.pop('reason',None);payload.pop('source_node_id',None);payload['dependencies']=[]
                prepared.append(await self.prepare_run(payload))
            mapping={n['id']:r['id'] for n,r in zip(nodes,prepared)}
            for node,run in zip(nodes,prepared):
                run.update(dependencies=[mapping[d] for d in node.get('dependencies',[])],planId=plan['id'],nodeId=node['id'],reason=node.get('reason',''))
                if node.get('source_node_id'):run['arguments']['source_run_id']=mapping[node['source_node_id']]
                run['status']='blocked' if run['dependencies'] else 'queued'
                self.commit_run(run)
            plan.update(status='running',runIds=[r['id'] for r in prepared]);self.audit(target,'plan_started',dict(id=plan['id']));self.publish();self.pump();return True,plan
        if method=='security-plan-stop':
            plan=self.record('securityPlans',params.get('id'))
            for run_id in plan.get('runIds',[]):
                await self.dispatch('security-run-stop',dict(id=run_id))
            plan.update(status='cancelled',finished=now());self.publish();return True,plan
        if method=='security-run-copy':
            run=self.record('securityRuns',params.get('id'))
            return True,await self.dispatch('security-plan-save',dict(targetId=run['targetId'],name='Retry '+run['name'],nodes=[dict(id='retry',name=run['name'],stage=run['stage'] if run['stage']!='Results' else 'Research',capability=run['capability'],arguments={k:v for k,v in run['arguments'].items() if k not in ('target','url','report_prefix')},prompt=run.get('prompt',''),model=run.get('model',''),dependencies=[])]))
        if method=='security-contract-save':
            target=self.target(params.get('targetId'));tool=params.get('tool')
            definition=next((d['function'] for d in self.service.tools.catalog() if d['function']['name']==tool),None)
            if not definition:raise ValueError('Choose an installed tool')
            binding=params.get('binding','')
            if binding and binding not in definition.get('parameters',{}).get('properties',{}):raise ValueError('Target binding must be a tool input')
            types=params.get('types',[target['type']])
            if not isinstance(types,list) or not types or any(t not in ('Website / API','Network','Server','Network device','Software') for t in types):raise ValueError('Choose supported target types')
            name=params.get('name','').strip();instructions=params.get('instructions','')
            if not name or len(name)>160 or not isinstance(instructions,str) or len(instructions)>8000:raise ValueError('Enter bounded capability name and instructions')
            defaults=params.get('defaults',{})
            if not isinstance(defaults,dict) or len(json.dumps(defaults))>16000:raise ValueError('Defaults must be a bounded object')
            row=dict(id='contract:'+identity(),projectId=target['projectId'],name=name,tool=tool,binding=binding,types=types,defaults=defaults,instructions=instructions,created=now())
            self.store.data['securityContracts'].append(row);self.audit(target,'capability_registered',dict(id=row['id'],tool=tool));self.publish();return True,row
        if method=='security-report-export':
            target=self.target(params.get('targetId'));project=self.store.project()
            rows={key:[copy.deepcopy(r) for r in self.store.data[key] if r.get('targetId')==target['id']] for key in ('securityDiscoveries','securityFindings','securityResearch','securityPlans','securityEvents')}
            rows['runs']=[{k:v for k,v in r.items() if k not in ('output',)} for r in self.runs if r['targetId']==target['id']]
            report=dict(schema=2,target=copy.deepcopy(target),exported=now(),**rows)
            prefix='security-report-'+target['id']
            destination=safe_path(project['root'],prefix+'.json',True)
            # Do not overwrite existing evidence: each export gets a unique suffix.
            prefix+='-'+identity()[:8]
            json_path=safe_path(project['root'],prefix+'.json',True);md_path=safe_path(project['root'],prefix+'.md',True)
            json_path.write_text(json.dumps(report,indent=2))
            lines=['# Investigation: '+target['address'],'',target.get('objective',''),'','Execution completion is not proof of exploitation. Simulation evidence is explicitly labelled.','']
            for f in rows['securityFindings']:
                lines += ['## '+f['title'],'',f"Severity: {f['severity']} · Review: {f['status']} · Simulation: {f.get('simulation',False)}",'',str(f['evidence']),'',f['remediation'],'',f['notes'],'','Source runs: '+', '.join(f['runIds']),'']
            lines += ['## Inventory and research','',json.dumps({k:rows[k] for k in ('securityDiscoveries','securityResearch')},indent=2)]
            md_path.write_text('\n'.join(lines));self.audit(target,'report_exported',dict(paths=[str(json_path),str(md_path)]));self.publish();return True,dict(paths=[str(json_path),str(md_path)])
        if method=='security-investigate':
            target=self.target(params.get('targetId'));model=params.get('model') or target.get('models',{}).get('default','')
            kind=target['type'];recon='software_inventory' if kind=='Software' else 'website_assess' if kind=='Website / API' else 'network_scan'
            arguments=dict(profile='discovery' if kind=='Network' else 'services') if recon=='network_scan' else dict(profile='baseline',max_pages=4) if recon=='website_assess' else {}
            nodes=[dict(id='recon',name='Initial recon',stage='Recon',capability=recon,arguments=arguments,dependencies=[],reason='Gather actual target evidence before planning'),
                dict(id='review',name='Research discoveries',stage='Research',capability='research',arguments={'automatic':True},prompt='Research the observed products and versions. Verify source content and explain applicability.',dependencies=['recon'],reason='Research actual recon observations'),
                dict(id='plan',name='Build next test plan',stage='Research',capability='planner',arguments={},prompt=target.get('objective') or 'Propose evidence-based next checks',dependencies=['review'],reason='Produce editable steps using connected capabilities')]
            plan=await self.dispatch('security-plan-save',dict(targetId=target['id'],name='AI investigation',nodes=nodes))
            return True,await self.dispatch('security-plan-run',dict(id=plan['id'],model=model))
        return False,None

    async def software_inventory(self, target, tools, session_id):
        path=safe_path(self.store.project()['root'],target['address'])
        files=[target['address']] if path.is_file() else await tools.execute('list_files',dict(directory=target['address']),session_id)
        if isinstance(files,str):raise ValueError(files)
        manifests=[f for f in files if f.rsplit('/',1)[-1] in ('package.json','requirements.txt','pyproject.toml','Cargo.toml','go.mod')][:24]
        components=[];errors=[]
        for file in manifests:
            try:
                data=await tools.execute('read_file',dict(path=file),session_id)
                if isinstance(data,str):raise ValueError(data)
                if data.get('more'):raise ValueError('Manifest exceeds bounded read; inspect manually')
                text=data['content'];name=file.rsplit('/',1)[-1]
                if name=='package.json':
                    doc=json.loads(text)
                    pairs=[(k,v,category) for category in ('dependencies','devDependencies','peerDependencies') for k,v in doc.get(category,{}).items()]
                elif name in ('pyproject.toml','Cargo.toml'):
                    import tomllib
                    doc=tomllib.loads(text)
                    pairs=[(v.split('>')[0].split('=')[0].split('<')[0].split('[')[0],v,'declared') for v in doc.get('project',{}).get('dependencies',[])] if name=='pyproject.toml' else [(k,str(v),'declared') for k,v in doc.get('dependencies',{}).items()]
                elif name=='requirements.txt':
                    pairs=[(line.split('=')[0].split('>')[0].split('<')[0].split('[')[0],line,'declared') for line in text.splitlines() if line.strip() and not line.lstrip().startswith(('#','-'))]
                else:
                    pairs=[(parts[0],parts[1],'declared') for line in text.splitlines() if len(parts:=line.strip().split())==2 and parts[1].startswith('v')]
                for name,version,category in pairs[:150]:components.append(dict(name=name,version=str(version),category=category,manifest=file,confidence='declared dependency; installed version unverified'))
            except (ValueError,TypeError) as error:errors.append(dict(path=file,error=str(error)))
        return dict(components=components,manifests=manifests,errors=errors,limitations=['Declared dependencies do not establish installed or vulnerable versions.','Bounded to 24 manifests and 150 declarations per manifest; binary/runtime analysis requires a registered capability.'])
