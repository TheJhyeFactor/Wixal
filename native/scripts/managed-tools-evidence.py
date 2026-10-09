"""Export hash-checked preview envelopes from independently checked live reports.

This export cannot certify the complete release/model matrix.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/managed-tools';sys.path.insert(0,str(ROOT/'native/engine'))
from wixal.managed_tools import digest,canonical
from wixal.tool_qualification import validate_report
app=Path('/Applications/Wixal Tools Preview.app');report=json.loads((ART/'packaged/report.json').read_text());life=json.loads((ART/'lifecycle/report.json').read_text());install=json.loads((ART/'install.json').read_text())
assert report['helperSHA256']==digest(app/'Contents/Resources/engine/wixal-engine')==install['sha256']['Contents/Resources/engine/wixal-engine']
identity=dict(helperSha256=report['helperSHA256'],sourceManifestSha256=digest(app/'Contents/Resources/SOURCE_MANIFEST.json'),packageSha256=report['cases']['actualDiscovery']['invocation']['executable']['packageSha256'],executableSha256=report['cases']['actualDiscovery']['invocation']['executable']['executableSha256'],adapter='rustscan.discovery.v1',model=report.get('model'),contextSize=8192,architecture=platform.machine(),macOS=platform.mac_ver()[0])
(ART/'listener-oracles.json').write_text(json.dumps(dict(backend=report['listenerOracle'],connectionLedger=report['connectionLedger'],modelAttempts=[dict(scenario=a['scenario'],attempt=a['attempt'],oracle=a.get('oracle')) for a in report['modelAttempts']],dualHost=life['cases']['actualIPv4IPv6HostSpecificHandoff']['oracle']),indent=2))
def evidence(path):return dict(path=str(path.relative_to(ART)),sha256=digest(path))
shared=[evidence(ART/'listener-oracles.json'),evidence(ART/'packaged/report.json'),evidence(ART/'lifecycle/report.json'),evidence(ART/'install.json')]
backend=report['cases'];expected=report['listenerOracle']['ports'];topology=life['cases']['actualIPv4IPv6HostSpecificHandoff'];empty=life['cases']['actualEmptyCoverage'];stop=life['cases']['actualCancellation']
checks={'signed_install':backend['signedInstallation']['status']=='ready','discovery':backend['actualDiscovery']['hosts'][0]['ports']==expected and backend['actualDiscovery']['handoffEligible'],'inspection':sorted(int(s['port']) for s in backend['sourceBoundInspection']['services'])==expected,'investigation':len(backend['linkedInvestigation'])==2 and all(r['status']=='completed' for r in backend['linkedInvestigation']),'dual_host':{r['target']:list(map(int,r['ports'].split(','))) for r in topology['inspection']['invocations']}==topology['oracle'],'empty':empty['discovery']['hosts'][0]['ports']==[] and empty['inspection']['skipped'],'stop':stop['result']['state']=='stopped' and not stop['result']['structuredResult']['handoffEligible']}
envelope=dict(schemaVersion=1,suiteId='managed-rustscan-local-preview',mode='backend',identity=identity,cases=[dict(id=k,status='passed' if v else 'failed',evidenceClasses=['D','L'],evidence=shared) for k,v in checks.items()])
envelope['validation']=validate_report(envelope,{k:['D','L'] for k in checks},identity,ART);envelope['status']=envelope['validation']['status'];(ART/'backend-envelope.json').write_text(json.dumps(envelope,indent=2))
model=dict(schemaVersion=1,suiteId='managed-rustscan-two-core-model-preview',mode='model',identity=identity,cases=[dict(id=a['scenario'],attempt=a['attempt'],status=a['status'],evidenceClasses=['M','L'],evidence=shared,fabricatedSuccess=a.get('fabricatedSuccess',False)) for a in report['modelAttempts']])
model['validation']=validate_report(model,{'naturalDiscovery':['M','L'],'sourceInspection':['M','L']},identity,ART,5);model['status']=model['validation']['status'];model['completeMatrixQualified']=False;(ART/'model-envelope.json').write_text(json.dumps(model,indent=2))
print(json.dumps(dict(backend=envelope['status'],twoCoreModelSuite=model['status'],completeReleaseMatrixQualified=False,helperSha256=identity['helperSha256']),indent=2))
