"""Structured command adapters; no model-authored installer or shell interpolation."""
import shlex
import asyncio
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlsplit
from .tools import safe_path, scan_plan

async def run(manager,tools,args,session):
    row=manager.spec(args['id']);executable=manager.executable(row)
    if not executable:raise ValueError('Missing add-on. Use addon_install and wait for verified readiness.')
    root=(tools.store.project() or {}).get('root')
    if not root:raise ValueError('Select a project for evidence and command ownership')
    identifier=row['id'];target=args.get('target','');path=args.get('path','.');seconds=args.get('timeout_seconds',180)
    if identifier in ('ffuf','nuclei'):
        parsed=urlsplit(target)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Use an authorised HTTP(S) target without credentials, query or fragment')
        if target.startswith('-') or any(c in target for c in '\n\r'):raise ValueError('Invalid target')
    if identifier=='ffuf':
        wordlist=safe_path(root,path)
        if not wordlist.is_file() or wordlist.stat().st_size>1024*1024:raise ValueError('Supply a project wordlist below 1 MB')
        argv=[executable,'-u',target.rstrip('/')+'/FUZZ','-w',str(wordlist),'-rate','10','-t','2','-maxtime',str(seconds),'-noninteractive','-s','-json']
    elif identifier=='nuclei':
        template=safe_path(root,args.get('template',''))
        if not template.is_file() or template.suffix not in ('.yaml','.yml') or template.stat().st_size>1024*1024:raise ValueError('Select an explicit signed YAML template below 1 MB')
        argv=[executable,'-u',target,'-t',str(template),'-dut','-ni','-duc','-rl','10','-c','2','-jsonl']
    elif identifier=='wireshark':
        capture=safe_path(root,path)
        if not capture.is_file() or capture.stat().st_size>100*1024*1024:raise ValueError('Select a project capture below 100 MB')
        argv=[executable,'-r',str(capture),'-q','-z','io,phs']
    elif identifier=='trivy':
        directory=safe_path(root,path)
        if not directory.is_dir():raise ValueError('Select a project directory')
        argv=[executable,'fs','--scanners','vuln,misconfig','--format','json',str(directory)]
    elif identifier=='osv-scanner':
        directory=safe_path(root,path)
        if not directory.is_dir():raise ValueError('Select a project directory')
        argv=[executable,'scan','source','--recursive','--no-ignore','--no-resolve','--no-call-analysis','go','--no-call-analysis','rust','--format','json',str(directory)]
    elif identifier=='testssl':
        # Reuse host validation; no subnet, path, credentials or arbitrary option tokens.
        scan_plan(dict(target=target,profile='ports',ports='443'))
        if '/' in target and '://' not in target:raise ValueError('TLS assessment requires one host')
        argv=[executable,'--quiet','--color','0','--warnings','batch',target]
    else:raise ValueError('This add-on requires specialist setup before execution')
    # Authority checks happen before generic command review and cannot be skipped by bypass.
    from .agent_context import profile
    from .agent_authority import target_allowed
    active=profile.get() or {}
    if active.get('_branchRoot'):raise ValueError('Add-on execution is unavailable in an isolated change branch')
    if active.get('restrictTargets'):
        if identifier in ('ffuf','nuclei','testssl') and not target_allowed(target,active.get('authority',{}).get('targets',[])):raise ValueError('Target is outside the agent authorised scope')
        if identifier in ('trivy','osv-scanner'):raise ValueError('Local advisory tools may contact external databases; use an unrestricted authorised task')
    from .managed_tools import controlled_environment,digest
    home=Path(tempfile.mkdtemp(prefix='wixal-addon-run-'))
    fingerprint=await asyncio.to_thread(digest,executable)
    async def finished(job):shutil.rmtree(home)
    try:
        result=await tools.start_command(shlex.join(argv),seconds,session,argv=argv,assessment=dict(capability='addon:'+identifier,target=target,path=path,executableSha256=fingerprint),environment=controlled_environment(home),retain_evidence=True,on_finished=finished)
        if not isinstance(result,dict):shutil.rmtree(home)
        return result
    except BaseException:shutil.rmtree(home);raise
