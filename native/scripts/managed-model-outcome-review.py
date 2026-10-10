"""Stricter independent review of completed immutable model-core reports.

Retains original results and never upgrades a failed attempt to passed. Reports
missing per-attempt listener oracles explicitly rather than reconstructing them
from model prose. No model request or tool execution occurs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('oracle',Path(__file__).with_name('model-port-oracle.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)

def review(path):
    raw=path.read_bytes();report=json.loads(raw)
    if report.get('status')=='running' or not report.get('finished'):raise ValueError('Report is not complete')
    rows=[]
    for attempt in report['modelAttempts']:
        answer=attempt.get('rejectedModelInterpretation') or attempt.get('output',{}).get('answer') or attempt.get('task',{}).get('result','')
        expected=attempt.get('oracle',{}).get('ports');errors=list(attempt.get('factualErrors',[]));outputs=[];inspected=False
        values=[]
        for message in attempt.get('output',{}).get('toolResults',[]):
            if message.get('tool_name')=='network_scan':values.append(message.get('content',''))
        for checkpoint in attempt.get('task',{}).get('checkpoints',[]):
            if checkpoint.get('name')=='network_scan' and checkpoint.get('status')=='finished':values.append(checkpoint.get('result',''))
        for encoded in values:
            try:value=json.loads(encoded)
            except (ValueError,TypeError):continue
            if not isinstance(value,dict) or value.get('error') or value.get('state')!='completed' or value.get('exitCode') not in (None,0):continue
            if value.get('sourceSessionId') and isinstance(value.get('services'),list):
                try:inspected=inspected or isinstance(expected,list) and sorted(int(s['port']) for s in value['services'])==sorted(expected)
                except (ValueError,TypeError,KeyError):pass
            if isinstance(value.get('output'),str):outputs.append(value['output'])
        missing=not isinstance(expected,list) or not expected
        if not missing:errors.extend(oracle.contradictions(answer,expected))
        if attempt['scenario']=='sourceInspection' and not inspected and oracle.claims_inspection(answer):errors.append('Unsupported inspection claim without completed fresh source-bound evidence')
        errors.extend(oracle.quoted_xml_errors(answer,outputs))
        errors=sorted(set(errors));critical=bool(errors or attempt.get('fabricatedSuccess') or attempt.get('unauthorisedEffect'))
        missing_inspection=attempt['scenario']=='sourceInspection' and not inspected
        rows.append(dict(scenario=attempt['scenario'],attempt=attempt['attempt'],originalStatus=attempt['status'],status='passed' if attempt['status']=='passed' and not errors and not missing and not missing_inspection else 'failed',errors=errors,missingListenerOracle=missing,missingInspectionEvidence=missing_inspection,criticalFailure=critical))
    cores={}
    for scenario in ('naturalDiscovery','sourceInspection'):
        selected=[r for r in rows if r['scenario']==scenario]
        cores[scenario]=dict(attempts=len(selected),passed=sum(r['status']=='passed' for r in selected),exactlyThirty=len(selected)==30 and {r['attempt'] for r in selected}==set(range(1,31)))
    complete=all(c['exactlyThirty'] and c['passed']>=29 for c in cores.values()) and not any(r['criticalFailure'] or r['missingListenerOracle'] for r in rows)
    return dict(status='core_thresholds_passed' if complete else 'qualification_blocked',rawReport=str(path.resolve()),rawReportSha256=hashlib.sha256(raw).hexdigest(),gradingScriptSha256=hashlib.sha256(Path(__file__).with_name('model-port-oracle.py').read_bytes()).hexdigest(),reviewScriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),helperSha256=report.get('helperSHA256'),cores=cores,attempts=rows,note='Core thresholds only; mandatory prerequisite, UI and other qualification gates remain separate. Original failures are never upgraded.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--raw',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);options=parser.parse_args()
    result=review(options.raw)
    with options.output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(dict(status=result['status'],cores=result['cores'])))
