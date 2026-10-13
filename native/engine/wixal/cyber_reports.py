"""Wixal report renderers informed by Decepticon's reporting/export patterns."""
import hashlib
import json
import re
import zipfile
from . import engagement_evidence as evidence
from . import cyber_findings
from .storage import identity, now
from .tools import safe_path


def clean(value):
    """Remove secret-shaped fields and common credential strings, not all client data."""
    if isinstance(value,dict):
        return {k:('[REDACTED]' if k.lower() in {'token','password','secret','authorization','cookie','set-cookie','plaintext','privatekey'} else clean(v)) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,str):
        value = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*','Bearer [REDACTED]',value)
        return re.sub(r'(?i)(https?://)[^\s/@:]+:[^\s/@]+@',r'\1[REDACTED]@',value)
    return value


def snapshot(manager,engagement):
    report = evidence.report(manager,engagement)
    report['findings'] = [r for r in report['findings'] if r.get('engagementId') in (None,engagement['id'])]
    report['findingQuality'] = {r['id']:cyber_findings.quality(manager,engagement,r) for r in report['findings']}
    report['adaptation'] = dict(upstream='BitterSecurity/Decepticon',revision='00fc3b594c40f6e48e22341669cf7048c117781f',implementation='Wixal native engine')
    report['limitations'] += ['Automatic redaction is limited; review client content before sharing.',
                               'SARIF contains assessment results; source locations are included only when actually known.']
    return clean(report)


def timeline(report):
    events = [dict(time=r['created'],kind=r['kind'],detail=r.get('detail',{}),id=r['id']) for r in report['securityEngagementEvents']]
    return sorted(events,key=lambda e:(e['time'],e['id']))


def sarif(report):
    rules = {};results = []
    for row in report['findings']:
        # Observations/hypotheses remain explicit and do not become verified vulnerabilities.
        kind = row.get('resultKind','observation');rule = 'wixal.'+kind
        rules.setdefault(rule,dict(id=rule,shortDescription=dict(text=kind.replace('_',' ').title())))
        properties = {k:row[k] for k in ('targetId','resultKind','verificationState','confidence','cvssVector','cvssScore','scopeRevision','evidenceIds') if k in row}
        properties['reportQuality'] = report['findingQuality'][row['id']]
        results.append(dict(ruleId=rule,level='note' if kind in ('observation','hypothesis','negative_result') else 'warning',
                            message=dict(text=row.get('title','Untitled')+'\n'+row.get('description','')),
                            partialFingerprints={'wixalFindingId/v1':row['id']},properties=properties))
    return {'$schema':'https://json.schemastore.org/sarif-2.1.0.json','version':'2.1.0',
            'runs':[dict(tool=dict(driver=dict(name='Wixal',informationUri='https://github.com/TheJhyeFactor/Wixal',rules=list(rules.values()))),results=results)]}


def markdown(report,executive=False):
    engagement = report['engagement']
    lines = ['# '+engagement['name'],'',engagement['objective'],'',
             'Status: '+engagement['status']+' · scope revision '+str(engagement['scopeRevision']),
             '', 'Execution, technical validation, finding disposition and cleanup are separate.','']
    findings = report['findings'];checks = report['securityVerifications']
    lines += ['## Assessment status','',f'{len(report["runs"])} recorded operations; {len(findings)} finding/observation records; {len(checks)} validation records.',
              '',f'{sum(not q["valid"] for q in report["findingQuality"].values())} finding records need report-quality work.',
              '',f'{sum(c["status"] not in ("verified","accepted") for c in report["securityCleanup"])} cleanup items remain unresolved.','']
    for row in findings:
        lines += ['## '+row.get('title','Untitled'),'',row.get('description',''),'',
                  'Kind: '+row.get('resultKind','observation')+' · verification: '+row.get('verificationState','unverified'),
                  '', 'Observed impact: '+row.get('impact','Not documented'),
                  '', 'Remediation: '+row.get('remediation','Not documented')]
        if not executive:
            for key in ('assumptions','counterevidence','confidenceRationale','severityChangeConditions','retestPlan'):
                lines += ['',key+': '+row.get(key,'Not documented')]
            lines += ['', 'Evidence: '+', '.join(row.get('evidenceIds',[])),
                      '', 'Quality: '+json.dumps(report['findingQuality'][row['id']],ensure_ascii=False)]
    if not executive:
        for title,key in (('Objectives','securityObjectives'),('Scope history',None),('Validation records','securityVerifications'),
                          ('Retests','securityRetests'),('Cleanup','securityCleanup')):
            lines += ['', '## '+title,'','```json',json.dumps(report[key] if key else engagement['scopes'],indent=2,ensure_ascii=False),'```']
    lines += ['', '## Limitations','']+['- '+item for item in report['limitations']]
    return '\n'.join(lines)+'\n'


def export(manager,engagement,include_evidence=False):
    from . import cyber_documents
    report = snapshot(manager,engagement)
    planning=engagement.get('planning',{})
    planning_text='# Engagement planning\n\n'+engagement['objective']+'\n\nScope revision: '+str(engagement['scopeRevision'])+'\n\n'
    planning_text+='\n\n'.join('## '+key+'\n\n'+str(value) for key,value in clean(planning).items())
    planning_text+='\n\nPlanning is separate from approval of current scope.\n'
    payloads = {'engagement.json':json.dumps(report,indent=2,ensure_ascii=False).encode(),
                'planning.md':planning_text.encode(),
                'technical-report.md':markdown(report).encode(),'executive-summary.md':markdown(report,True).encode(),
                'results.sarif':json.dumps(sarif(report),indent=2).encode(),
                'timeline.json':json.dumps(timeline(report),indent=2).encode()}
    payloads.update({'technical-report.pdf':cyber_documents.pdf(report),
                     'technical-report.docx':cyber_documents.docx(report),
                     'executive-summary.pdf':cyber_documents.pdf(report,True),
                     'executive-summary.docx':cyber_documents.docx(report,True)})
    if include_evidence:
        for row in manager.rows('securityEvidence',engagement):
            _,value = evidence.read(manager,engagement,row['id'])
            # Original retained bytes remain private. Export derivatives with explicit identities.
            payloads['evidence/'+row['id']+'.json'] = json.dumps(clean(value),ensure_ascii=False,indent=2).encode()
            if sum(map(len,payloads.values()))>32*1024*1024:raise ValueError('Selected evidence export exceeds 32 MB; export a smaller engagement')
    if sum(map(len,payloads.values()))>32*1024*1024:raise ValueError('Report export exceeds 32 MB')
    manifest = dict(schema=1,engagementId=engagement['id'],scopeRevision=engagement['scopeRevision'],created=now(),
                    files={name:dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)) for name,data in payloads.items()},
                    sourceEvidence=[dict(id=r['id'],sha256=r['sha256']) for r in manager.rows('securityEvidence',engagement)],
                    evidenceIncluded=include_evidence,evidenceForm='redacted derivatives; source SHA-256 values identify private originals',
                    limitation='Hashes establish byte identity, not truth. Review exported content before sharing.')
    payloads['manifest.json'] = json.dumps(manifest,indent=2).encode()
    prefix = 'cyber-'+engagement['id']+'-'+identity()[:8]
    root = manager.store.project()['root'];archive = safe_path(root,prefix+'.zip',True)
    paths = []
    # Exclusive creation and fixed member names; never walks or bundles the project.
    try:
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zf:
            for name,data in payloads.items():zf.writestr(name,data)
        paths.append(str(archive))
        for name in ('technical-report.md','executive-summary.md','results.sarif','technical-report.pdf','technical-report.docx','executive-summary.pdf','executive-summary.docx'):
            target = safe_path(root,prefix+'-'+name,True)
            with target.open('xb') as f:f.write(payloads[name])
            target.chmod(0o600);paths.append(str(target))
        archive.chmod(0o600)
    except BaseException:
        for path in paths:
            from pathlib import Path
            Path(path).unlink(missing_ok=True)
        raise
    manager.event(engagement,'cyber_report_exported',dict(paths=paths,evidenceIncluded=include_evidence))
    return dict(paths=paths,manifest=manifest)


def import_package(manager,engagement,path):
    """Verify a report archive without extraction or restoration of authority."""
    from pathlib import PurePosixPath
    source=safe_path(manager.store.project()['root'],path)
    if not source.is_file() or source.stat().st_size>32*1024*1024:raise ValueError('Choose a report ZIP below 32 MB')
    raw=source.read_bytes()
    if len(raw)>32*1024*1024:raise ValueError('Report ZIP changed beyond bounds')
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(infos)>256 or len(set(names))!=len(names):raise ValueError('Report ZIP has duplicate or excessive members')
        if sum(i.file_size for i in infos)>32*1024*1024:raise ValueError('Report ZIP expansion exceeds 32 MB')
        for info in infos:
            name=PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename or info.is_dir() or info.flag_bits&1:
                raise ValueError('Unsafe report ZIP member')
            if info.file_size>16*1024*1024:raise ValueError('Report ZIP member exceeds 16 MB')
        if 'manifest.json' not in names or 'engagement.json' not in names:raise ValueError('Report ZIP is missing its manifest or snapshot')
        manifest=json.loads(archive.read('manifest.json'))
        files=manifest.get('files') if isinstance(manifest,dict) else None
        if not isinstance(files,dict) or set(files)!=set(names)-{'manifest.json'}:raise ValueError('Report ZIP manifest does not cover every member')
        for name,expected in files.items():
            data=archive.read(name)
            if not isinstance(expected,dict) or expected.get('bytes')!=len(data) or expected.get('sha256')!=hashlib.sha256(data).hexdigest():
                raise ValueError('Report ZIP member digest mismatch')
        report=json.loads(archive.read('engagement.json'))
        if not isinstance(report,dict) or not isinstance(report.get('engagement'),dict):raise ValueError('Report ZIP snapshot is invalid')
        value=dict(archiveSha256=hashlib.sha256(raw).hexdigest(),manifest=manifest,
                   snapshot=clean(report),provenance='Untrusted external report; hashes identify bytes only. No scope, approvals, credentials or verified findings were restored.')
        result=evidence.retain(manager,engagement,value,'external-report-package',path)
        manager.event(engagement,'cyber_report_imported',dict(evidenceId=result['id'],archiveSha256=value['archiveSha256']))
        return result
