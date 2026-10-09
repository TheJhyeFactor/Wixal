"""Evidence-qualified reports. A summary or model narrative cannot grant readiness."""
import hashlib
import json
from pathlib import Path
from .managed_tools import canonical,digest


def validate_report(report,mandatory,identity,evidence_root,required_repeats=1,minimum_successes=None):
    errors=[];root=Path(evidence_root).resolve()
    minimum_successes=required_repeats if minimum_successes is None else minimum_successes
    if not 1<=minimum_successes<=required_repeats:raise ValueError('Invalid model repeatability threshold')
    if report.get('identity')!=identity:errors.append('Acceptance identity differs from the actual evaluated tuple')
    cases=report.get('cases',[])
    if not isinstance(cases,list):return dict(status='failed',errors=['Invalid case list'])
    for identifier,classes in mandatory.items():
        rows=[c for c in cases if c.get('id')==identifier]
        if len(rows)<required_repeats:errors.append(identifier+': missing required attempts')
        if required_repeats>1 and len({c.get('attempt') for c in rows})!=len(rows):errors.append(identifier+': duplicate or missing attempt identities')
        if sum(c.get('status')=='passed' for c in rows)<minimum_successes:errors.append(identifier+': insufficient successful attempts')
        for row in rows:
            if (minimum_successes==required_repeats and row.get('status')!='passed') or not set(classes)<=set(row.get('evidenceClasses',[])):errors.append(identifier+': outcome or evidence class failed')
            files=row.get('evidence',[])
            if not files:errors.append(identifier+': missing independent evidence')
            for item in files:
                try:
                    path=(root/item['path']).resolve(strict=True)
                    if not path.is_relative_to(root) or not path.is_file() or digest(path)!=item['sha256']:raise ValueError()
                except (KeyError,OSError,ValueError):errors.append(identifier+': missing, escaping or mismatched evidence hash')
    if report.get('mode')=='model' and any(c.get('unauthorisedEffect') or c.get('fabricatedSuccess') for c in cases):errors.append('Critical model/policy failure blocks qualification')
    return dict(status='passed' if not errors else 'failed',errors=errors,reportSha256=canonical(report),requiredCases=list(mandatory),requiredRepeats=required_repeats,minimumSuccesses=minimum_successes)


def tuple_identity(package,helper,model=None):
    identity=dict(packageSha256=package['packageSha256'],executableSha256=package['executableSha256'],adapter=package['adapter'],helperSha256=digest(helper),model=model or None)
    return dict(identity,tupleSha256=canonical(identity))
