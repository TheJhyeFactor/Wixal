"""Normalize measured RustScan evidence without claiming unexecuted families.

Requires completed immutable reports and the exact app used by the runs.
Installed UI, other package revisions and other tools need separate envelopes.
"""
import argparse
import json
import platform
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'native/engine'))
from wixal.managed_tools import digest

def export(art,app,core_path,life_path,prerequisite_path=None):
    art=art.resolve();app=app.resolve()
    core=json.loads(core_path.read_text());life=json.loads(life_path.read_text())
    helper=digest(app/'Contents/Resources/engine/wixal-engine')
    if core.get('status')=='running' or not core.get('finished'):raise ValueError('Core report is not complete')
    if core.get('helperSHA256')!=helper or life.get('helperSha256')!=helper:raise ValueError('Reports and app use different helpers')
    executable=core['cases']['actualDiscovery']['invocation']['executable']
    identity=dict(helperSha256=helper,sourceManifestSha256=digest(app/'Contents/Resources/SOURCE_MANIFEST.json'),packageSha256=executable['packageSha256'],executableSha256=executable['executableSha256'],adapter=executable['adapter'],model=core.get('model'),contextSize=8192,architecture=platform.machine(),macOS=platform.mac_ver()[0])
    def evidence(path):
        path=path.resolve()
        if not path.is_relative_to(art):raise ValueError('Evidence must be contained in evidence root')
        return dict(path=str(path.relative_to(art)),sha256=digest(path))
    cases=[]
    def claim(identifier,passed,classes,path,**extra):
        cases.append(dict(id=identifier,status='passed' if passed else 'failed',identity=identity,evidenceClasses=classes,evidence=[evidence(path)],**extra))
    backend=core['cases'];expected=core['listenerOracle']['ports']
    claim('TRU-01',backend['signedInstallation']['status']=='ready',['D'],core_path)
    claim('TXN-01',backend['signedInstallation']['status']=='ready',['D','L'],core_path)
    claim('RSC-01',backend['actualDiscovery']['hosts'][0]['ports']==expected and backend['actualDiscovery']['handoffEligible'],['L'],core_path)
    topology=life['cases']['actualIPv4IPv6HostSpecificHandoff']
    actual={r['target']:list(map(int,r['ports'].split(','))) for r in topology['inspection']['invocations']}
    claim('RSC-03',actual==topology['oracle'],['L'],life_path)
    claim('RSC-06',actual==topology['oracle'],['L'],life_path)
    # Partial evidence stays partial: these checks do not supply the required
    # installed UI, model interpretation, ownership-negative or service probes.
    empty=life['cases']['actualEmptyCoverage'];stop=life['cases']['actualCancellation']
    claim('RSC-04',empty['discovery']['hosts'][0]['ports']==[] and empty['inspection']['skipped'],['L'],life_path)
    claim('RSC-10',stop['result']['state']=='stopped' and not stop['result']['structuredResult']['handoffEligible'],['L'],life_path)
    for attempt in core['modelAttempts']:
        extra=dict(attempt=attempt['attempt'],scenario=attempt['scenario'],fabricatedSuccess=attempt.get('fabricatedSuccess',False),unauthorisedEffect=attempt.get('unauthorisedEffect',False))
        claim('MOD-15',attempt['status']=='passed',['M','L'],core_path,**extra)
        if attempt['scenario']=='naturalDiscovery':claim('MOD-01',attempt['status']=='passed',['M','L'],core_path,**extra)
        elif attempt['scenario']=='sourceInspection':claim('MOD-06',attempt['status']=='passed',['M','L'],core_path,**extra)
    if prerequisite_path:
        prerequisite=json.loads(prerequisite_path.read_text())
        if not prerequisite.get('finished') or prerequisite.get('helperSha256')!=helper or prerequisite.get('model')!=core.get('model'):raise ValueError('Prerequisite report is unfinished or has another configuration')
        # Only scenarios fully covered by this harness are mapped. Reading one
        # source file alone does not establish the entire context-pressure case.
        for row in prerequisite['cases']:
            identifier=row['id']
            if identifier in ('MOD-02','MOD-03','MOD-08','MOD-09','MOD-10','MOD-17','MOD-18'):
                claim(identifier,row['status']=='passed',row['evidenceClasses'],prerequisite_path)
            elif identifier.startswith('MOD-14-'):
                claim('MOD-14',row['status']=='passed',row['evidenceClasses'],prerequisite_path,variant=identifier)
    output=art/'normalized-completion';output.mkdir(exist_ok=True)
    (output/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    (output/'claims.json').write_text(json.dumps(dict(schemaVersion=1,identity=identity,cases=cases),indent=2)+'\n')
    return dict(identity=str(output/'identity.json'),claims=str(output/'claims.json'),cases=len(cases))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--app',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True);p.add_argument('--lifecycle',type=Path,required=True);p.add_argument('--prerequisites',type=Path)
    o=p.parse_args();print(json.dumps(export(o.evidence_root,o.app,o.core,o.lifecycle,o.prerequisites)))
