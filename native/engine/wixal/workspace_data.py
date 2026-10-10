"""Explicit UI backup/import and privacy-bounded diagnostics. No model tool exposes these methods."""
import copy
import json
import os
import tempfile
from pathlib import Path
from .storage import now
from .migration import import_workspace

COLLECTIONS=('projects','sessions','memories','globalMemories','agentProfiles','agentWorkflows','tasks','skills','schedules','workflowRuns','skillCandidates','agentJobs')
MEMORY_EXCLUSIONS=('forgottenMemories','forgottenMemorySources','supersededMemorySources')


def backup(store,path):
    destination=Path(path).expanduser().absolute()
    if destination.suffix.lower()!='.json':raise ValueError('Save the backup as a JSON file')
    if destination.is_symlink():raise ValueError('Choose a regular backup file, not a symbolic link')
    data={key:copy.deepcopy(store.data.get(key,[])) for key in COLLECTIONS}
    data.update({key:copy.deepcopy(store.data.get(key,[])) for key in MEMORY_EXCLUSIONS})
    from .conversation import read_image
    for session in data['sessions']:
        session.pop('draft',None)
        for message in session.get('messages',[]):
            for attachment in message.get('attachments',[]):
                if attachment.get('type')=='image' and attachment.get('imageId'):
                    attachment['base64']=read_image(store,attachment['imageId'])
                    attachment.pop('imageId',None)
    # A restore is a saved-work merge. It never restores credentials or enabled permissions.
    for schedule in data['schedules']:schedule['enabled']=False
    data.update(wixalBackupVersion=1,created=now())
    encoded=json.dumps(data,ensure_ascii=False,indent=2).encode()
    if len(encoded)>128*1024*1024:raise ValueError('Backup exceeds the supported 128 MB import limit')
    fd,temporary=tempfile.mkstemp(prefix='.wixal-backup-',dir=destination.parent)
    try:
        with os.fdopen(fd,'wb') as output:output.write(encoded);output.flush();os.fsync(output.fileno())
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return dict(path=str(destination),bytes=len(encoded),counts={key:len(data[key]) for key in COLLECTIONS})


def storage(store):
    def size(directory):
        result=0
        if not directory.exists():return 0
        for base,dirs,files in os.walk(directory,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
            for name in files:
                p=Path(base)/name
                try:
                    if not p.is_symlink():result+=p.stat().st_size
                except OSError:pass
        return result
    model_path=store.directory/'local-runtime/models'
    model_bytes=size(model_path)
    return dict(workspace=str(store.directory),models=str(model_path),workspaceBytes=size(store.directory/'attachments')+sum(p.stat().st_size for p in store.directory.glob('workspace.sqlite3*') if p.is_file()),modelBytes=model_bytes)


async def dispatch(service,method,params):
    store=service.store
    if method=='workspace-diagnostics':
        from . import VERSION
        import platform
        return dict(engineVersion=VERSION,pythonVersion=platform.python_version(),platform=platform.system(),architecture=platform.machine(),runtimeStatus=service.runtime.status,
                    agentRunning=bool(service.active and not service.active.done()),manualActions=service.manual_tools,
                    counts={key:len(store.data.get(key,[])) for key in COLLECTIONS},connectedServers=len(service.mcp.connections),enabledTools=len(store.data['enabledTools']),contextSize=store.data['contextSize'],backgroundSchedules=bool(store.data.get('backgroundScheduler',{}).get('enabled')))
    if method=='workspace-storage':
        import asyncio
        return await asyncio.to_thread(storage,store)
    service.idle()
    if method=='workspace-backup':return backup(store,params.get('path',''))
    if method=='workspace-import-preview':return import_workspace(store,params.get('path',''),preview=True,preserve_preferences=True)
    if method=='workspace-import':
        digest=params.get('digest')
        if not isinstance(digest,str) or len(digest)!=64:raise ValueError('Preview the source before importing')
        result=import_workspace(store,params.get('path',''),preserve_preferences=True,expected_digest=digest)
        store.memory.sync();service.emit('state',store.data)
        return result
    raise ValueError('Unknown workspace data action')
