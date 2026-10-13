"""Evidence-disciplined findings, informed by Decepticon reporting utilities.

Original Wixal implementation; provenance in third_party/decepticon/NOTICE.md.
Report completeness, human disposition and technical verification are separate.
"""
import copy
import re
from . import engagement_evidence as evidence
from .engagement_policy import text, strings
from .storage import now

FIELDS = ('description', 'impact', 'assumptions', 'counterevidence', 'confidenceRationale',
          'severityChangeConditions', 'remediation', 'retestPlan')
KINDS = ('vulnerability', 'observation', 'hypothesis', 'negative_result', 'dependency_cve')
IDENTITY_FIELDS = ('component','componentVersion','rootCause','surface','identityId')


def bound_evidence(manager,engagement,reference,target_id):
    record,value=evidence.read(manager,engagement,reference)
    if record['kind']=='run':
        source=manager.record('securityRuns',record['source'],engagement)
        bound_target=source['targetId'];revision=source.get('scopeRevision')
    elif record['kind']=='sensor-batch':
        source=manager.record('securitySensors',value.get('sensorId'),engagement)
        bound_target=source['targetId'];revision=value.get('scopeRevision',source['scopeRevision'])
    elif record['kind'] in ('binary-analysis','external-binary-analysis','ghidra-analysis'):
        bound_target=value.get('targetId');revision=value.get('scopeRevision')
    else:
        # Untyped imports remain assertions; they cannot acquire verified status.
        return record,value
    if bound_target!=target_id or revision!=engagement['scopeRevision']:
        raise ValueError('Finding evidence belongs to another target or scope revision')
    return record,value


def finding(manager, engagement, identifier):
    row = manager.record('securityFindings', identifier, engagement)
    if row.get('engagementId') not in (None, engagement['id']):
        raise ValueError('Finding belongs to another engagement')
    return row


def quality(manager, engagement, row):
    errors = []
    for key in ('title', *FIELDS):
        if not isinstance(row.get(key), str) or not row[key].strip():errors.append('Missing '+key)
    if row.get('confidence') not in ('low', 'medium', 'high'):errors.append('Choose a confidence level')
    if row.get('resultKind') not in KINDS:errors.append('Choose a result kind')
    refs = row.get('evidenceIds', [])
    if not refs:errors.append('Retained evidence is required')
    for ref in refs:
        try:bound_evidence(manager, engagement, ref,row.get('targetId'))
        except (ValueError, OSError) as error:errors.append(str(error))
    if row.get('scopeRevision') != engagement['scopeRevision']:errors.append('Finding belongs to an older scope revision')
    if row.get('cvssVector'):
        from .security_cvss import score_vector
        try:
            score = score_vector(row['cvssVector'])
            if row.get('cvssScore') != score['base_score'] or row.get('cvssVersion') != '3.1':errors.append('CVSS vector, score and version disagree')
        except ValueError as error:errors.append(str(error))
        if row.get('resultKind') in ('negative_result', 'observation', 'hypothesis'):errors.append('Only vulnerability findings carry severity scores')
    return dict(valid=not errors, errors=errors, verificationState=row.get('verificationState', 'unverified'),
                limitation='Checks report structure and retained bytes; does not establish vulnerability truth.')


def duplicates(manager, engagement, candidate, exclude=''):
    matches = []
    cves = set(candidate.get('cveIds', []))
    words = set(re.findall(r'\w+', candidate.get('description', '').lower()))
    for row in manager.store.data['securityFindings']:
        if row.get('projectId') != engagement['projectId'] or row.get('targetId') != candidate.get('targetId') or row['id'] == exclude:continue
        if row.get('engagementId') not in (None, engagement['id']):continue
        reason = None
        if candidate.get('resultKind') == 'dependency_cve' and cves & set(row.get('cveIds', [])):
            if candidate.get('component') and (candidate.get('component'), candidate.get('componentVersion')) == (row.get('component'), row.get('componentVersion')):reason = 'same target, component, version and CVE'
        elif candidate.get('rootCause') and (candidate['rootCause'], candidate.get('surface'), candidate.get('identityId')) == (row.get('rootCause'), row.get('surface'), row.get('identityId')):reason = 'same target, root cause, surface and identity'
        elif candidate.get('title', '').strip() and candidate['title'].casefold() == row.get('title', '').casefold():reason = 'matching title; review instance identity'
        else:
            other = set(re.findall(r'\w+', row.get('description', '').lower()))
            if len(words) >= 8 and len(words & other)/max(1, len(words | other)) > .75:reason = 'similar description; review root cause'
        if reason:matches.append(dict(findingId=row['id'], reason=reason, disposition='suggestion_only'))
    return dict(matches=matches[:30], limitation='Candidates are never automatically merged or suppressed.')


def save(manager, engagement, params):
    allowed = {'findingId','baseRevision','targetId','title','resultKind','confidence','evidenceIds','cveIds',
               'component','componentVersion','rootCause','surface','identityId','objectiveId',*FIELDS}
    if set(params)-allowed:raise ValueError('Unknown finding fields')
    old = finding(manager, engagement, params['findingId']) if params.get('findingId') else None
    if old and params.get('baseRevision') != old.get('revision', 0):raise ValueError('Finding revision changed; reload before editing')
    target = manager.record('securityTargets', params.get('targetId'), engagement)
    if old and old['targetId'] != target['id']:raise ValueError('Finding target cannot change')
    objective_id=params.get('objectiveId',(old or {}).get('objectiveId',''))
    if objective_id:
        objective=manager.record('securityObjectives',objective_id,engagement)
        if objective['targetId']!=target['id'] or objective['scopeRevision']!=engagement['scopeRevision']:raise ValueError('Choose a current objective for the finding target')
    row = dict(targetId=target['id'], title=text(params.get('title'),'Finding title',200),
               resultKind=params.get('resultKind'), confidence=params.get('confidence'))
    if row['resultKind'] not in KINDS or row['confidence'] not in ('low','medium','high'):raise ValueError('Invalid finding kind or confidence')
    for key in FIELDS:row[key] = text(params.get(key),key)
    refs = strings(params.get('evidenceIds', []), 'finding evidence', 32)
    if not refs:raise ValueError('Select retained evidence')
    for ref in refs:
        bound_evidence(manager,engagement,ref,target['id'])
    row['evidenceIds'] = refs
    row['objectiveId'] = objective_id
    row['cveIds'] = strings(params.get('cveIds', (old or {}).get('cveIds',[])), 'CVE identifiers', 32)
    if any(not re.fullmatch(r'CVE-\d{4}-\d{4,}', c) for c in row['cveIds']):raise ValueError('Invalid CVE identifier')
    for key in IDENTITY_FIELDS:
        value = params.get(key, (old or {}).get(key,''))
        if not isinstance(value,str) or len(value)>1000:raise ValueError('Invalid '+key)
        row[key] = value
    row.update(engagementId=engagement['id'], scopeRevision=engagement['scopeRevision'],
               revision=(old or {}).get('revision',0)+1, updated=now(), reportStatus='draft',
               verificationState='unverified', needsReview=True, status='candidate')
    if old:
        history = copy.deepcopy(old.get('history', []))
        history.append({k:copy.deepcopy(v) for k,v in old.items() if k!='history'})
        row['history'] = history[-32:]
        # Changing claim content invalidates previous technical/disposition metadata.
        for key in ('cvssVector','cvssScore','cvssVersion','severity','severityRationale','verificationIds','reviewed'):
            old.pop(key,None)
        old.update(row);row = old
    else:row = manager.add('securityFindings', engagement, **{k:v for k,v in row.items() if k!='engagementId'})
    manager.event(engagement,'finding_draft_saved',dict(findingId=row['id'],revision=row['revision']))
    return dict(finding=row, quality=quality(manager,engagement,row), duplicates=duplicates(manager,engagement,row,row['id']))


def retest(manager, engagement, params):
    row = finding(manager,engagement,params.get('findingId'))
    if row.get('scopeRevision') != engagement['scopeRevision']:raise ValueError('Retest requires a current-scope finding')
    refs = strings(params.get('verificationIds', []),'retest verifications',16)
    if not refs:raise ValueError('Retest requires validation records')
    checks = [manager.record('securityVerifications',ref,engagement) for ref in refs]
    for check in checks:
        if check.get('scopeRevision') != engagement['scopeRevision'] or not check.get('contractId'):raise ValueError('Retest needs current capability-specific validation contracts')
        contract = manager.record('securityValidationContracts',check['contractId'],engagement)
        if contract['targetId'] != row['targetId'] or not row.get('objectiveId') or contract['objectiveId']!=row['objectiveId']:raise ValueError('Retest must evaluate the finding target and linked objective')
        for key in ('positiveId','baselineId'):evidence.read(manager,engagement,check[key])
    result = manager.add('securityRetests',engagement,findingId=row['id'],findingRevision=row.get('revision',0),
                         scopeRevision=engagement['scopeRevision'],verificationIds=refs,
                         fixDescription=text(params.get('fixDescription'),'Fix description'),
                         limitations=text(params.get('limitations'),'Retest limitations'),
                         status='declared_checks_passed' if all(c['status']=='validated' for c in checks) else 'inconclusive',
                         limitation='Only supplied validation contracts were evaluated; this does not automatically close the finding.')
    manager.event(engagement,'finding_retested',dict(retestId=result['id'],status=result['status']))
    return result
