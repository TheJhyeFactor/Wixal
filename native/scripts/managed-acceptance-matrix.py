"""Validate evidence envelopes against every managed-tools acceptance family.

This records missing classes and attempts explicitly. It never translates a
regression-suite count, model summary or package readiness into certification.
Release gates may be deferred explicitly, while the full 104-family contract
remains in the output and releaseQualified remains false.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'native/engine'))
from wixal.tool_qualification import validate_report
from wixal.managed_tools import canonical,digest

def matrix(suite,envelopes,identity,evidence_root,excluded_gates=()):
    if suite.get('schemaVersion')!=1 or not isinstance(suite.get('families'),list):raise ValueError('Invalid acceptance suite')
    families=suite['families'];ids=[f['id'] for f in families]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate acceptance families')
    rows=[];rejected=[]
    for envelope in envelopes:
        if envelope.get('identity')!=identity:
            rejected.append('Envelope has another package/adapter/app/platform/model identity');continue
        cases=envelope.get('cases',[])
        if not isinstance(cases,list) or any(not isinstance(r,dict) for r in cases):raise ValueError('Invalid evidence case list')
        for row in cases:
            if row.get('id') not in ids:raise ValueError('Unknown acceptance family: '+str(row.get('id')))
            if row.get('identity',identity)!=identity:raise ValueError('Case identity differs from its envelope')
            rows.append(row)
    critical=any(r.get('fabricatedSuccess') or r.get('unauthorisedEffect') for r in rows)
    result=[]
    for family in families:
        selected=[r for r in rows if r.get('id')==family['id']]
        present=sorted({c for r in selected for c in r.get('evidenceClasses',[])})
        base=dict(family,observedEvidenceClasses=present,attempts=len(selected))
        if family['gate'] in excluded_gates:
            result.append(dict(base,status='deferred_by_request',reason='Gate explicitly excluded from this acceptance invocation'));continue
        if family['id']=='MOD-15':
            errors=[];cores={}
            expected_scenarios={'naturalDiscovery','sourceInspection'}
            if {r.get('scenario') for r in selected}!=expected_scenarios:errors.append('Both core scenarios must retain every attempt')
            if not isinstance(identity.get('model'),dict) or not identity['model']:errors.append('Exact model configuration is missing')
            for scenario in sorted(expected_scenarios):
                attempts=[r for r in selected if r.get('scenario')==scenario]
                check=validate_report(dict(identity=identity,mode='model',cases=attempts),{family['id']:family['evidenceClasses']},identity,evidence_root,30,29)
                if len(attempts)!=30 or {r.get('attempt') for r in attempts}!=set(range(1,31)) or any(type(r.get('attempt')) is not int for r in attempts):check['errors'].append('Require exactly attempts 1 through 30')
                if any(r.get('status') not in ('passed','failed') for r in attempts):check['errors'].append('Attempt has no terminal outcome')
                check['status']='failed' if check['errors'] else 'passed';cores[scenario]=check
                errors.extend(scenario+': '+e for e in check['errors'])
            validation=dict(status='failed' if errors else 'passed',errors=errors,cores=cores)
        else:
            validation=validate_report(dict(identity=identity,mode='model',cases=rows),{family['id']:family['evidenceClasses']},identity,evidence_root)
        status='passed' if validation['status']=='passed' else 'missing' if not selected else 'incomplete_or_failed'
        result.append(dict(base,status=status,validation=validation))
    required=[r for r in result if r['mandatory'] and r['status']!='deferred_by_request']
    complete=not rejected and not critical and all(r['status']=='passed' for r in required)
    deferred=any(r['mandatory'] and r['status']=='deferred_by_request' for r in result)
    return dict(schemaVersion=1,status='passed_for_requested_gates' if complete else 'incomplete',releaseQualified=complete and not deferred,identity=identity,suiteSha256=canonical(suite),families=result,rejectedEnvelopes=rejected,criticalFailure=critical,counts={state:sum(r['status']==state for r in result) for state in ('passed','missing','incomplete_or_failed','deferred_by_request')})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--suite',type=Path,default=ROOT/'native/tools-distribution/acceptance-suite.json');p.add_argument('--identity',type=Path,required=True,help='Reviewed exact tuple JSON');p.add_argument('--claims',type=Path,action='append',default=[],help='Normalized evidence envelope; may repeat');p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--exclude-gate',action='append',choices=['release'],default=[]);p.add_argument('--output',type=Path,required=True);o=p.parse_args()
    identity=json.loads(o.identity.read_text());suite=json.loads(o.suite.read_text());envelopes=[json.loads(path.read_text()) for path in o.claims]
    result=matrix(suite,envelopes,identity,o.evidence_root,o.exclude_gate);result['inputFiles']=[dict(path=str(path.resolve()),sha256=digest(path)) for path in [o.suite,o.identity,*o.claims]]
    o.output.parent.mkdir(parents=True,exist_ok=True);o.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],releaseQualified=result['releaseQualified'],counts=result['counts'])))
if __name__=='__main__':main()
