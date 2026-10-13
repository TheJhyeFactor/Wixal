"""Native Decepticon-inspired capabilities behind Wixal authority and IPC."""
import hashlib
import json
import re
from . import engagement_evidence as evidence
from . import cyber_findings as findings
from . import cyber_planning as planning
from . import cyber_reports as reports
from .engagement_policy import strings, text
from .storage import now
from .tools import safe_path

READ_ACTIONS = ('catalog','snapshot','evidence','finding_quality','duplicates','rank_paths','dossier','sessions','sensors','analysis_readiness')
WRITE_ACTIONS = ('finding_save','finding_score','finding_complete','retest','planning_save','export','report_import','skills','sensor_enroll','sensor_start','sensor_stop','sensor_collect','sensor_archive','sensor_configure','binary_triage','binary_decompile','analysis_import')
PARAMS = {'catalog':set(),'snapshot':set(),'evidence':{'evidenceId','offset'},'finding_quality':{'findingId'},'duplicates':{'findingId'},
          'rank_paths':{'fromId','toId'},'dossier':set(),'sessions':set(),'sensors':set(),'analysis_readiness':set(),
          'finding_save':{'findingId','baseRevision','targetId','title','resultKind','confidence','evidenceIds','cveIds','component','componentVersion','rootCause','surface','identityId','objectiveId',*findings.FIELDS},
          'finding_score':{'findingId','vector','rationale'},
          'finding_complete':{'findingId','baseRevision'},'retest':{'findingId','verificationIds','fixDescription','limitations'},
          'planning_save':{'baseRevision',*planning.PLAN_FIELDS},'export':{'includeEvidence'},'report_import':{'path'},'skills':set(),
          'sensor_archive':{'sensorId'},'sensor_configure':{'sensorId','rules'},
          'sensor_enroll':{'path','targetId'},'sensor_start':{'sensorId'},'sensor_stop':{'sensorId'},'sensor_collect':{'sensorId'},
          'binary_triage':{'path','targetId'},'binary_decompile':{'path','targetId'},'analysis_import':{'path','binaryPath','targetId'}}


class Cyber:
    def __init__(self,manager):
        self.manager=manager
        for key in ('securityRetests','securitySensors','securityIncidents'):manager.store.data.setdefault(key,[])
        from .cyber_sensors import Sensors
        self.sensors=Sensors(manager)

    def readiness(self):
        from .cyber_ghidra import provider
        launcher,java=provider()
        mcp=self.manager.workspace.service.mcp
        available=[dict(name=t['function']['name'],description=t['function'].get('description','')[:200]) for t in mcp.definitions()
                   if any(word in t['function']['name'].lower() for word in ('rea','ghidra'))]
        return dict(binaryTriage=True,ghidraInstalled=bool(launcher),ghidraLauncher=str(launcher) if launcher else None,externalAnalysisTools=available,
                    externalProviderReady=bool(available),runtimeStarted=False,
                    limitation='External analysis requires an explicitly configured MCP provider and separate tool review. No provider is installed or started here.')

    def triage(self,engagement,params):
        target=self.manager.record('securityTargets',params.get('targetId'),engagement)
        path=text(params.get('path'),'Binary project path',1000)
        source=safe_path(self.manager.store.project()['root'],path);size=source.stat().st_size
        if not source.is_file() or size>32*1024*1024:raise ValueError('Choose a regular binary below 32 MB')
        data=source.read_bytes()
        if len(data)>32*1024*1024:raise ValueError('Binary changed beyond analysis bounds')
        magic=data[:4];kind='ELF' if magic==b'\x7fELF' else 'PE candidate' if data[:2]==b'MZ' else 'Mach-O' if magic in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xce\xfa\xed\xfe') else 'unknown'
        value=dict(path=path,targetId=target['id'],sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),format=kind,
                   strings=[clean.decode('ascii') for clean in re.findall(rb'[\x20-\x7e]{8,200}',data[:1024*1024])[:100]],
                   provider='Wixal bounded static triage',scopeRevision=engagement['scopeRevision'],
                   limitation='Header and bounded string observations only. The file was not executed or decompiled; no vulnerability is established.')
        return evidence.retain(self.manager,engagement,reports.clean(value),'binary-analysis',path)

    def import_analysis(self,engagement,params):
        self.manager.record('securityTargets',params.get('targetId'),engagement)
        source=safe_path(self.manager.store.project()['root'],params.get('path'))
        binary=safe_path(self.manager.store.project()['root'],params.get('binaryPath'))
        if not source.is_file() or source.stat().st_size>4*1024*1024 or not binary.is_file() or binary.stat().st_size>32*1024*1024:raise ValueError('Analysis bundle or binary exceeds bounds')
        raw=source.read_bytes();data=binary.read_bytes()
        if len(raw)>4*1024*1024 or len(data)>32*1024*1024:raise ValueError('Analysis files changed beyond bounds')
        value=json.loads(raw)
        if not isinstance(value,dict) or value.get('sourceSha256')!=hashlib.sha256(data).hexdigest():raise ValueError('Analysis source digest does not match the selected binary')
        if not isinstance(value.get('provider'),str) or not isinstance(value.get('observations'),list) or len(value['observations'])>1000:raise ValueError('Analysis bundle needs provider and bounded observations')
        return evidence.retain(self.manager,engagement,dict(bundle=value,bundleSha256=hashlib.sha256(raw).hexdigest(),
                    targetId=params['targetId'],scopeRevision=engagement['scopeRevision'],
                    provenance='External assertions bound to selected binary bytes; provider authenticity and findings remain unverified'),
                    'external-binary-analysis',params['path'])

    async def dispatch(self,method,params):
        if method not in ('security-cyber-read','security-cyber-manage'):return NotImplemented
        if not isinstance(params,dict) or set(params)-{'engagementId','action','parameters'}:raise ValueError('Invalid cyber request')
        action=params.get('action');values=params.get('parameters',{})
        allowed=READ_ACTIONS if method.endswith('read') else WRITE_ACTIONS
        if action not in allowed or not isinstance(values,dict):raise ValueError('Unknown cyber action or parameters')
        if set(values)-PARAMS[action]:raise ValueError('Unknown parameters for '+action+'. Use exact camelCase keys: '+', '.join(sorted(PARAMS[action])))
        if action=='catalog':
            project=self.manager.store.project()
            if not project:raise ValueError('Choose a project')
            return dict(readActions=READ_ACTIONS,manageActions=WRITE_ACTIONS,
                        engagements=[dict(id=e['id'],name=e['name'],status=e['status'],scopeRevision=e['scopeRevision']) for e in self.manager.store.data['securityEngagements'] if e['projectId']==project['id']],
                        findingFields=['targetId','title','resultKind','confidence','evidenceIds','objectiveId',*findings.FIELDS],planningFields=planning.PLAN_FIELDS,
                        actionParameters={key:sorted(fields) for key,fields in PARAMS.items()},
                        provenance=dict(project='BitterSecurity/Decepticon',revision='00fc3b594c40f6e48e22341669cf7048c117781f'),
                        authority='Use retained evidence. Drafts, skills and candidate paths cannot grant scope or establish vulnerability truth.')
        engagement=self.manager.get(params.get('engagementId'))
        if action in WRITE_ACTIONS and engagement['status'] in ('completed','closed_incomplete','cancelled') and action not in ('export','sensor_stop'):raise ValueError('Closed engagements are immutable')
        if action=='snapshot':return reports.snapshot(self.manager,engagement)
        if action=='evidence':
            record,value=evidence.read(self.manager,engagement,values.get('evidenceId'))
            if isinstance(value,dict):value={k:v for k,v in value.items() if k!='rawText'}
            if record['kind']=='run' and isinstance(value.get('result'),dict):
                result=value['result']
                if isinstance(result.get('structuredResult'),dict):
                    # Avoid duplicate raw XML before the interpretation and normalized
                    # scripts. Immutable originals remain available to the operator.
                    normalized=result['structuredResult']
                    value=dict(interpretation=normalized.get('interpretation'),
                               **{k:v for k,v in value.items() if k!='result'},
                               result={k:v for k,v in normalized.items() if k!='interpretation'})
            content=json.dumps(reports.clean(value),ensure_ascii=False,indent=2)
            offset=values.get('offset',0)
            if type(offset) is not int or not 0<=offset<=len(content):raise ValueError('Invalid evidence offset')
            return dict(evidenceId=record['id'],kind=record['kind'],sourceSha256=record['sha256'],
                        derivativeSha256=hashlib.sha256(content.encode()).hexdigest(),content=content[offset:offset+6000],
                        nextOffset=min(len(content),offset+6000),more=offset+6000<len(content),
                        limitation='Redacted model-facing derivative; source hash identifies private originals. Raw log text is excluded.')
        if action=='finding_quality':return findings.quality(self.manager,engagement,findings.finding(self.manager,engagement,values.get('findingId')))
        if action=='duplicates':
            row=findings.finding(self.manager,engagement,values.get('findingId'))
            return findings.duplicates(self.manager,engagement,row,row['id'])
        if action=='rank_paths':return planning.ranked_paths(self.manager,engagement,values)
        if action=='dossier':return planning.dossier(self.manager,engagement)
        if action=='sessions':return planning.sessions(self.manager,engagement)
        if action=='sensors':return self.sensors.snapshot(engagement)
        if action=='analysis_readiness':return self.readiness()
        if action=='finding_save':result=findings.save(self.manager,engagement,values)
        elif action=='finding_score':
            row=findings.finding(self.manager,engagement,values.get('findingId'))
            if row.get('resultKind') not in ('vulnerability','dependency_cve'):raise ValueError('Only vulnerability findings carry severity scores')
            if row.get('scopeRevision')!=engagement['scopeRevision']:raise ValueError('Finding belongs to an older scope')
            result=await self.manager.dispatch('security-engagement-finding',dict(engagementId=engagement['id'],**values))
            row['reportStatus']='draft'
        elif action=='finding_complete':
            row=findings.finding(self.manager,engagement,values.get('findingId'))
            if values.get('baseRevision')!=row.get('revision',0):raise ValueError('Finding revision changed')
            result=findings.quality(self.manager,engagement,row)
            if not result['valid']:raise ValueError('; '.join(result['errors']))
            row['reportStatus']='complete';row['reportCompleted']=now()
            self.manager.event(engagement,'finding_report_completed',dict(findingId=row['id']))
        elif action=='retest':result=findings.retest(self.manager,engagement,values)
        elif action=='planning_save':result=planning.save(self.manager,engagement,values)
        elif action=='export':
            if type(values.get('includeEvidence',False)) is not bool:raise ValueError('Choose whether to include evidence')
            result=reports.export(self.manager,engagement,values.get('includeEvidence',False))
        elif action=='skills':return await self.manager.dispatch('security-engagement-skills',{})
        elif action=='report_import':result=reports.import_package(self.manager,engagement,values.get('path'))
        elif action=='sensor_enroll':result=await self.sensors.enroll(engagement,values)
        elif action in ('sensor_start','sensor_stop','sensor_collect'):
            row=self.sensors.source(engagement,values.get('sensorId'))
            result=await self.sensors.start(engagement,row) if action=='sensor_start' else await self.sensors.stop(row) if action=='sensor_stop' else self.sensors.collect(engagement,row)
        elif action in ('sensor_archive','sensor_configure'):
            row=self.sensors.source(engagement,values.get('sensorId'))
            result=await self.sensors.archive(engagement,row) if action=='sensor_archive' else await self.sensors.configure(engagement,row,values.get('rules'))
        elif action=='binary_triage':result=self.triage(engagement,values)
        elif action=='binary_decompile':
            from .cyber_ghidra import decompile
            result=await decompile(self.manager,engagement,values)
        elif action=='analysis_import':result=self.import_analysis(engagement,values)
        self.manager.workspace.publish();return result
