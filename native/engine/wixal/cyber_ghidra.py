"""Optional installed Ghidra adapter: copy, statically analyse, retain, clean up."""
import asyncio
import hashlib
import json
import os
import shutil
import signal
import tempfile
from pathlib import Path
from . import engagement_evidence as evidence
from .tools import safe_path


def provider():
    launcher=next((Path(p) for p in (shutil.which('analyzeHeadless'),'/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless','/usr/local/opt/ghidra/libexec/support/analyzeHeadless') if p and Path(p).is_file()),None)
    java=next((Path(p) for p in ('/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home','/usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home') if (Path(p)/'bin/java').is_file()),None)
    return launcher,java


async def decompile(manager,engagement,params):
    launcher,java=provider()
    if not launcher:raise ValueError('Install Ghidra and its supported Java runtime before decompilation')
    target=manager.record('securityTargets',params.get('targetId'),engagement)
    path=params.get('path');source=safe_path(manager.store.project()['root'],path)
    if not source.is_file() or source.stat().st_size>8*1024*1024:raise ValueError('Select a binary below 8 MB')
    data=source.read_bytes()
    if len(data)>8*1024*1024:raise ValueError('Binary changed beyond bounds')
    revision=engagement['scopeRevision'];sha=hashlib.sha256(data).hexdigest()
    if not await manager.workspace.service.ask('review',dict(name='cyber_binary_decompile',path=path,sha256=sha,provider=str(launcher),seconds=120,access='Static Ghidra import of a private copy; sample is never executed')):
        raise ValueError('Static decompilation was not approved')
    if engagement['scopeRevision']!=revision:raise ValueError('Scope changed during analysis review')
    script=Path(__file__).parent/'resources/WixalDecompile.java'
    with tempfile.TemporaryDirectory(prefix='wixal-ghidra-') as directory:
        root=Path(directory).resolve();root.chmod(0o700);binary=root/'sample';binary.write_bytes(data);binary.chmod(0o600)
        output=root/'analysis.json';log=root/'provider.log';env=dict(os.environ)
        env.update(HOME=str(root),TMPDIR=str(root),XDG_CONFIG_HOME=str(root/'config'),XDG_CACHE_HOME=str(root/'cache'),JAVA_TOOL_OPTIONS='-XX:-UsePerfData')
        env['JAVA_TOOL_OPTIONS']+=' -Duser.home='+str(root)+' -Djava.io.tmpdir='+str(root)+' -Dapplication.tempdir='+str(root)+' -Dapplication.cachedir='+str(root/'cache')+' -Dapplication.settingsdir='+str(root/'settings')
        if java:env.update(JAVA_HOME=str(java),PATH=str(java/'bin')+os.pathsep+env.get('PATH',''))
        argv=[str(launcher),str(root),'analysis','-import',str(binary),'-scriptPath',str(script.parent),'-postScript',script.name,str(output),'-analysisTimeoutPerFile','60','-max-cpu','2','-deleteProject']
        sandbox=Path('/usr/bin/sandbox-exec')
        if not sandbox.is_file():raise ValueError('Ghidra analysis requires the macOS offline analysis sandbox')
        sandbox_profile='(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath '+json.dumps(str(root))+') (literal "/dev/null"))'
        argv=[str(sandbox),'-p',sandbox_profile,*argv]
        with log.open('wb') as stream:
            process=await asyncio.create_subprocess_exec(*argv,stdout=stream,stderr=asyncio.subprocess.STDOUT,env=env,start_new_session=True)
            try:
                await asyncio.wait_for(process.wait(),120)
            except BaseException:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await process.wait();raise
        log_bytes=log.read_bytes()
        if process.returncode or not output.is_file():raise ValueError('Ghidra did not produce analysis: '+log_bytes[-2000:].decode(errors='replace'))
        if output.stat().st_size>2*1024*1024:raise ValueError('Ghidra export exceeded bounds')
        if engagement['scopeRevision']!=revision:raise ValueError('Scope changed during static analysis')
        result=json.loads(output.read_bytes())
        value=dict(targetId=target['id'],scopeRevision=revision,path=path,sourceSha256=sha,sourceBytes=len(data),provider='Ghidra headless',
                   launcherSha256=hashlib.sha256(launcher.read_bytes()).hexdigest(),scriptSha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                   analysis=result,providerLog=log_bytes[-16000:].decode(errors='replace'),sandbox='Network denied; writes restricted to disposable analysis directory',
                   limitation='Static decompiler interpretation of at most 32 functions. The sample was not executed; no vulnerability or runtime behavior is verified.')
        return evidence.retain(manager,engagement,value,'ghidra-analysis',path)
