"""Authenticated, immutable tool packages. The catalogue contains data, never code.

Only the application-owned RustScan profile is enabled in the first preview.
Production repositories require an embedded trust configuration at build time.
"""
import contextlib
import copy
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import tarfile
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.error import HTTPError,URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from . import VERSION

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANSION = 128 * 1024 * 1024
ADAPTER = 'rustscan.discovery.v1'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Package paths must be normalized relative paths')
    return value


def descriptor(row):
    required = {'schemaVersion','tool','version','revision','source','platform','target','sha256','length','unpackedSize','entrypoint','inventory','adapter','appBuilds','readiness','distribution','dependencies','state','recovery'}
    if not isinstance(row, dict) or set(row) != required: raise ValueError('Unsupported package descriptor schema')
    if row['schemaVersion'] != 1 or row['tool'] != 'rustscan' or row['adapter'] != ADAPTER or row['readiness'] != 'rustscan-version-v1': raise ValueError('Unknown application-owned capability or readiness procedure')
    for key in ('sha256',):
        if not re.fullmatch('[a-f0-9]{64}', str(row[key])): raise ValueError('Invalid package digest')
    if not isinstance(row['version'],str) or not re.fullmatch(r'2\.(3|4)\.\d+', row['version']): raise ValueError('Unsupported RustScan CLI version')
    if type(row['revision']) != int or row['revision'] < 1: raise ValueError('Invalid package revision')
    for key, maximum in (('length',MAX_ARCHIVE),('unpackedSize',MAX_EXPANSION)):
        if type(row[key]) != int or not 0 < row[key] <= maximum: raise ValueError('Package size exceeds profile limits')
    if row['platform'].keys() != {'os','arch','minimumOS','testedOS'} or row['platform']['os'] != 'Darwin' or row['platform']['arch'] != 'arm64': raise ValueError('Unsupported package platform')
    if not isinstance(row['platform']['testedOS'],list) or not all(isinstance(v,str) for v in row['platform']['testedOS']): raise ValueError('Invalid tested OS matrix')
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?',str(row['platform']['minimumOS'])): raise ValueError('Invalid minimum OS')
    if not isinstance(row['appBuilds'],list) or VERSION not in row['appBuilds']: raise ValueError('Package is unevaluated for this application build')
    if row['dependencies'] != []: raise ValueError('This single-binary profile has no runtime dependencies; dependency packages require their own adapter contract')
    relative(row['target']); relative(row['entrypoint'])
    inventory=row['inventory']
    if not isinstance(inventory,dict) or not 1 <= len(inventory) <= 32 or row['entrypoint'] not in inventory: raise ValueError('Invalid package inventory')
    if len({relative(k).casefold() for k in inventory}) != len(inventory): raise ValueError('Case-colliding inventory')
    if any(not re.fullmatch('[a-f0-9]{64}',str(v)) for v in inventory.values()): raise ValueError('Invalid inventory digest')
    if not isinstance(row['source'],dict) or set(row['source']) != {'url','commit','strategy','recipeSha256','license','notices'}: raise ValueError('Source provenance is required')
    if not row['source']['url'].startswith('https://') or not re.fullmatch('[a-f0-9]{40}',row['source']['commit']) or not re.fullmatch('[a-f0-9]{64}',row['source']['recipeSha256']): raise ValueError('Invalid source provenance')
    if row['source']['strategy'] not in ('upstream_artifact','pinned_build','patched_fork') or not row['source']['license']: raise ValueError('Unsupported distribution strategy')
    if not isinstance(row['source']['notices'],list) or not row['source']['notices'] or any(p not in inventory for p in row['source']['notices']): raise ValueError('Required licence notices are missing')
    if row['distribution'] not in ('local_preview','developer_id_notarized'): raise ValueError('Unknown distribution policy')
    if row['state'] not in ('approved','withdrawn','revoked') or not isinstance(row['recovery'],list) or any(not re.fullmatch('[a-f0-9]{64}',str(v)) for v in row['recovery']): raise ValueError('Invalid lifecycle policy')
    return copy.deepcopy(row)


def compatible(row):
    if platform.system() != row['platform']['os'] or platform.machine() != row['platform']['arch']: raise ValueError('Unsupported operating system or architecture')
    version=platform.mac_ver()[0]
    if tuple(map(int,version.split('.'))) < tuple(map(int,row['platform']['minimumOS'].split('.'))): raise ValueError('Operating system is below the minimum')
    if version not in row['platform']['testedOS']: raise ValueError('This package has not been evaluated on this OS version')


def controlled_environment(home):
    return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(home),'TMPDIR':str(home),'LANG':'en_US.UTF-8','LC_ALL':'en_US.UTF-8'}


def inspect_payload(directory, row, readiness=True):
    directory=Path(directory)
    files={str(p.relative_to(directory)):p for p in directory.rglob('*') if p.is_file()}
    if set(files) != set(row['inventory']) or any(p.is_symlink() or digest(p) != row['inventory'][name] for name,p in files.items()): raise ValueError('Package inventory integrity failure')
    executable=directory/row['entrypoint']
    if not os.access(executable,os.X_OK): raise ValueError('Package entrypoint is not executable')
    arch=subprocess.run(['/usr/bin/lipo','-archs',str(executable)],capture_output=True,text=True,timeout=10)
    if arch.returncode or arch.stdout.strip() != 'arm64': raise ValueError('Package entrypoint has the wrong executable architecture')
    libraries=subprocess.run(['/usr/bin/otool','-L',str(executable)],capture_output=True,text=True,timeout=10)
    if libraries.returncode or any(not line.strip().startswith(('/usr/lib/','/System/Library/')) for line in libraries.stdout.splitlines()[1:]): raise ValueError('Undeclared executable runtime dependency')
    if row['distribution']=='developer_id_notarized':
        subprocess.run(['/usr/bin/codesign','--verify','--strict',str(executable)],check=True,capture_output=True,timeout=15)
        subprocess.run(['/usr/sbin/spctl','--assess','--type','execute',str(executable)],check=True,capture_output=True,timeout=30)
    if readiness:
        result=subprocess.run([str(executable),'--version'],cwd=directory,env=controlled_environment(directory),capture_output=True,timeout=10)
        if result.returncode or result.stdout.decode().strip() != 'rustscan '+row['version']: raise ValueError('Executable readiness/version mismatch')
    return str(executable)


def extract(archive, destination, row, cancelled=lambda:False):
    destination=Path(destination); destination.mkdir(mode=0o700,parents=True)
    seen=set(); total=0
    with tarfile.open(archive,'r:gz') as stream:
        for entry in stream:
            if cancelled(): raise InterruptedError('Installation cancelled before activation')
            name=relative(entry.name); key=name.casefold()
            if key in seen or len(seen)>=64: raise ValueError('Duplicate/case-colliding archive or excessive file count')
            seen.add(key)
            if not entry.isfile() or entry.mode & 0o7000 or name not in row['inventory']: raise ValueError('Archive profile rejects links, devices, directories, modes or unexpected files')
            total+=entry.size
            if entry.size < 0 or total>row['unpackedSize'] or total>MAX_EXPANSION: raise ValueError('Archive expansion exceeds descriptor limits')
            output=destination/name; output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with stream.extractfile(entry) as source, output.open('xb') as target:
                shutil.copyfileobj(source,target,64*1024); target.flush();os.fsync(target.fileno())
            output.chmod(0o700 if name==row['entrypoint'] else 0o600)
    if total != row['unpackedSize'] or {str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()} != set(row['inventory']): raise ValueError('Archive size or inventory mismatch')


class CatalogueClient:
    def __init__(self, root, configuration):
        self.root=Path(root); self.configuration=configuration
        if set(configuration) != {'channel','metadataURL','targetsURL','trustedRoot','allowedHosts','preview'}: raise ValueError('Invalid trusted repository configuration')
        if configuration['channel'] not in ('preview','stable'): raise ValueError('Unsupported channel')
        self.validate_url(configuration['metadataURL']);self.validate_url(configuration['targetsURL'])

    def validate_url(self,url):
        parsed=urlsplit(url)
        local=self.configuration['preview'] and parsed.hostname in ('127.0.0.1','localhost','::1')
        if parsed.username or parsed.password or parsed.fragment or parsed.query or parsed.hostname not in self.configuration['allowedHosts'] or (parsed.scheme!='https' and not (local and parsed.scheme=='http')): raise ValueError('Repository URL is outside the trusted download policy')

    def updater(self,cancelled=lambda:False):
        from tuf.ngclient import Updater
        from tuf.ngclient.fetcher import FetcherInterface
        from tuf.ngclient.config import UpdaterConfig
        client=self
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        class BoundedFetcher(FetcherInterface):
            def _fetch(self,url):
                client.validate_url(url)
                from tuf.api.exceptions import DownloadHTTPError,DownloadError
                try:response=build_opener(ProxyHandler({}),NoRedirect()).open(Request(url,headers={'User-Agent':'Wixal-Tools/1'}),timeout=15)
                except HTTPError as error:
                    error.close()
                    raise DownloadHTTPError(str(error),error.code) from error
                except URLError as error:raise DownloadError(str(error)) from error
                with response:
                    total=0;deadline=time.monotonic()+30
                    while True:
                        if cancelled():raise InterruptedError('Installation cancelled during download')
                        if time.monotonic()>deadline:raise DownloadError('Download exceeded its overall deadline')
                        chunk=response.read1(64*1024) if hasattr(response,'read1') else response.read(64*1024)
                        if not chunk:break
                        total+=len(chunk)
                        if total>MAX_ARCHIVE: raise ValueError('Download exceeds application bounds')
                        yield chunk
        channel=self.root/'metadata'/self.configuration['channel'];channel.mkdir(parents=True,exist_ok=True)
        return Updater(str(channel),self.configuration['metadataURL'],target_dir=str(self.root/'downloads'),target_base_url=self.configuration['targetsURL'],fetcher=BoundedFetcher(),config=UpdaterConfig(max_root_rotations=32),bootstrap=Path(self.configuration['trustedRoot']).read_bytes())

    def refresh(self,cancelled=lambda:False):
        updater=self.updater(cancelled);updater.refresh()
        target=updater.get_targetinfo('catalogue.json')
        if target is None or target.length>1024*1024: raise ValueError('Authenticated catalogue unavailable or too large')
        path=updater.download_target(target)
        value=json.loads(Path(path).read_text())
        if set(value)!={'schemaVersion','packages'} or value['schemaVersion']!=1 or not isinstance(value['packages'],list) or len(value['packages'])>100: raise ValueError('Unsupported catalogue schema')
        rows=[]; errors=[]
        for row in value['packages']:
            try: rows.append(descriptor(row))
            except (ValueError,TypeError,KeyError,AttributeError) as error: errors.append(str(error))
        return updater,rows,errors


class PackageRegistry:
    def __init__(self,root=None,configuration=None):
        self.root=Path(root or os.environ.get('WIXAL_MANAGED_TOOLS_ROOT') or Path.home()/'Library/Application Support/Wixal/ManagedTools').expanduser().resolve()
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        for name in ('downloads','staging','packages','journals','metadata'): (self.root/name).mkdir(mode=0o700,exist_ok=True)
        self.configuration=configuration
        if configuration is None:
            config_path=Path(__file__).parent/'resources/managed-repository.json'
            if config_path.exists():
                configuration=json.loads(config_path.read_text());configuration['trustedRoot']=str(config_path.parent/configuration['trustedRoot']);self.configuration=configuration
        self.client=CatalogueClient(self.root,self.configuration) if self.configuration else None
        with self.lock(),self.database() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS packages(digest TEXT PRIMARY KEY, descriptor TEXT NOT NULL, verified REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS active(tool TEXT PRIMARY KEY, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS leases(id TEXT PRIMARY KEY, digest TEXT NOT NULL, pid INTEGER NOT NULL, identity TEXT NOT NULL, owner TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            PRAGMA user_version=1;''')
            self.recover(db)

    @contextlib.contextmanager
    def database(self):
        db=sqlite3.connect(self.root/'registry.sqlite3',timeout=30)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db: yield db
        finally: db.close()

    @contextlib.contextmanager
    def lock(self):
        with (self.root/'transaction.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle,fcntl.LOCK_UN)

    def path(self,row): return self.root/'packages'/row['tool']/row['sha256']

    def recover(self,db):
        for path in (self.root/'journals').glob('*.json'):
            journal=json.loads(path.read_text()); row=descriptor(journal['descriptor'])
            active=db.execute('SELECT digest FROM active WHERE tool=?',(row['tool'],)).fetchone()
            # Publication without commit is harmless: keep a previous active pointer.
            if journal['stage']!='ready':
                journal['stage']='ready' if active and active['digest']==row['sha256'] else 'interrupted'
                atomic_json(path,journal)
            staging=self.root/'staging'/journal['id']
            if staging.exists():shutil.rmtree(staging)
        for row in db.execute('SELECT id,pid,identity FROM leases').fetchall():
            if self.process_identity(row['pid']) != row['identity']:db.execute('DELETE FROM leases WHERE id=?',(row['id'],))

    @staticmethod
    def process_identity(pid):
        result=subprocess.run(['/bin/ps','-p',str(pid),'-o','lstart=','-o','command='],capture_output=True,text=True,timeout=5)
        return result.stdout.strip() if result.returncode==0 else ''

    def persist_job(self,job):
        with self.database() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(job['id'],json.dumps(job)))

    def snapshot(self,tool='rustscan'):
        with self.database() as db:
            pointer=db.execute('SELECT p.* FROM packages p JOIN active a ON a.digest=p.digest WHERE a.tool=?',(tool,)).fetchone()
            cached=db.execute("SELECT value FROM settings WHERE key='catalogue'").fetchone()
            checked=db.execute("SELECT value FROM settings WHERE key='catalogueChecked'").fetchone()
            freshness_error=db.execute("SELECT value FROM settings WHERE key='catalogueError'").fetchone()
            selected=db.execute('SELECT value FROM settings WHERE key=?',('provider:'+tool,)).fetchone()
            versions=[json.loads(r['descriptor']) for r in db.execute('SELECT descriptor FROM packages')]
        row=json.loads(pointer['descriptor']) if pointer else None
        return dict(configured=bool(self.client),provider=selected['value'] if selected else 'external_homebrew',installed=bool(row),active=row,versions=versions,catalogue=json.loads(cached['value']) if cached else [],lastCatalogueCheck=float(checked['value']) if checked else None,catalogueError=freshness_error['value'] if freshness_error else None,verifiedAt=pointer['verified'] if pointer else None,modelEvaluation='unevaluated')

    def select_provider(self,provider):
        if provider not in ('managed','external_homebrew'):raise ValueError('Unknown provider')
        if provider=='managed':self.resolve()
        with self.lock(),self.database() as db:db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('provider:rustscan',provider))

    def refresh(self):
        if not self.client:raise ValueError('Managed repository is not configured in this build. External providers remain available.')
        with self.lock(),self.database() as db:
            _,rows,errors=self.client.refresh()
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogue',json.dumps(rows)))
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogueChecked',str(time.time())))
        return dict(packages=rows,errors=errors)

    def resolve(self):
        state=self.snapshot();row=state['active']
        if not row:raise ValueError('No managed RustScan package is active')
        compatible(row)
        current=next((p for p in state['catalogue'] if p['sha256']==row['sha256']),row)
        if current['state']=='revoked':raise ValueError('Managed package has been revoked')
        path=inspect_payload(self.path(row),row,readiness=False)
        return dict(path=path,provider='managed',packageSha256=row['sha256'],executableSha256=row['inventory'][row['entrypoint']],version=row['version'],adapter=ADAPTER,lastCatalogueCheck=state['lastCatalogueCheck'],catalogueError=state['catalogueError'])

    def acquire(self,owner):
        with self.lock(),self.database() as db:
            if self.client:
                try:
                    _,rows,_=self.client.refresh()
                    db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogue',json.dumps(rows)))
                    db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogueChecked',str(time.time())))
                    db.execute("DELETE FROM settings WHERE key='catalogueError'")
                    db.commit()
                except (ValueError,OSError) as error:
                    db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogueError',str(error)))
                    db.commit()
                except Exception as error:
                    from tuf.api.exceptions import RepositoryError,DownloadError
                    if not isinstance(error,(RepositoryError,DownloadError)):raise
                    db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogueError',str(error)));db.commit()
            handle=self.resolve();lease=uuid.uuid4().hex;pid=os.getpid()
            db.execute('INSERT INTO leases VALUES (?,?,?,?,?)',(lease,handle['packageSha256'],pid,self.process_identity(pid),owner))
            return dict(handle,lease=lease)

    def bind_lease(self,lease,pid):
        with self.database() as db:db.execute('UPDATE leases SET pid=?,identity=? WHERE id=?',(pid,self.process_identity(pid),lease))

    def release(self,lease):
        with self.database() as db:db.execute('DELETE FROM leases WHERE id=?',(lease,))

    def install(self,job,cancelled,notify=lambda:None,artifact=None):
        if not self.client:raise ValueError('Managed repository is not configured')
        def stage(name):
            job['stage']=name;self.persist_job(job);notify()
            if cancelled.is_set():raise InterruptedError('Installation cancelled before activation')
        with self.lock():
            stage('resolving');updater,rows,errors=self.client.refresh(cancelled.is_set)
            with self.database() as db:
                db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogue',json.dumps(rows)))
                db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('catalogueChecked',str(time.time())))
            candidates=[]
            for candidate in rows:
                if candidate['state']!='approved' or artifact and candidate['sha256']!=artifact:continue
                try:compatible(candidate)
                except ValueError:continue
                candidates.append(candidate)
            if not candidates:raise ValueError('No approved compatible package: '+ '; '.join(errors))
            row=max(candidates,key=lambda r:(tuple(map(int,r['version'].split('.'))),r['revision']))
            if shutil.disk_usage(self.root).free < row['length']+row['unpackedSize']+16*1024*1024:raise ValueError('Insufficient free space for package transaction')
            job.update(packageSha256=row['sha256'],totalBytes=row['length']);journal=dict(id=job['id'],descriptor=row,stage='requested');journal_path=self.root/'journals'/(job['id']+'.json');atomic_json(journal_path,journal)
            archive=self.root/'downloads'/(job['id']+'.part');staging=self.root/'staging'/job['id'];final=self.path(row)
            try:
                stage('downloading');info=updater.get_targetinfo(row['target'])
                if info is None or info.length!=row['length'] or info.hashes.get('sha256')!=row['sha256']:raise ValueError('Descriptor and authenticated target disagree')
                updater.download_target(info,str(archive));job['downloadedBytes']=archive.stat().st_size
                stage('verifying')
                if archive.stat().st_size != row['length'] or digest(archive)!=row['sha256']:raise ValueError('Artifact integrity mismatch')
                stage('extracting');extract(archive,staging,row,cancelled.is_set)
                stage('checking_readiness');inspect_payload(staging,row)
                stage('activation_pending');final.parent.mkdir(parents=True,exist_ok=True)
                if final.exists():
                    try:inspect_payload(final,row)
                    except (ValueError,OSError):
                        with self.database() as db:
                            if db.execute('SELECT 1 FROM leases WHERE digest=?',(row['sha256'],)).fetchone():raise ValueError('Repair blocked by an active execution lease')
                        shutil.rmtree(final)
                    else:shutil.rmtree(staging)
                if staging.exists():os.rename(staging,final)
                fd=os.open(final.parent,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
                journal['stage']='published';atomic_json(journal_path,journal)
                if cancelled.is_set():raise InterruptedError('Installation cancelled before activation')
                with self.database() as db:
                    db.execute('INSERT OR REPLACE INTO packages VALUES (?,?,?)',(row['sha256'],json.dumps(row),time.time()))
                    db.execute('INSERT OR REPLACE INTO active VALUES (?,?)',(row['tool'],row['sha256']))
                    db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('provider:rustscan','managed'))
                job.update(status='ready',stage='ready',version=row['version'],path=str(final/row['entrypoint']))
                journal['stage']='ready';atomic_json(journal_path,journal)
                self.persist_job(job);notify()
                return row
            finally:
                archive.unlink(missing_ok=True)
                if staging.exists():shutil.rmtree(staging)

    def rollback(self,artifact):
        with self.lock(),self.database() as db:
            state=self.snapshot();current=state['active']
            row=next((p for p in state['versions'] if p['sha256']==artifact),None)
            known=next((p for p in state['catalogue'] if p['sha256']==artifact),None)
            if not current or artifact not in current['recovery'] or not row or not known or known['state']!='approved':raise ValueError('Rollback requires a retained, approved recovery artifact')
            compatible(row);inspect_payload(self.path(row),row)
            db.execute('INSERT OR REPLACE INTO active VALUES (?,?)',('rustscan',artifact))
        return self.snapshot()

    def remove(self,artifact=None):
        with self.lock():
            with self.database() as db:
                self.recover(db);state=self.snapshot();rows=[r for r in state['versions'] if artifact is None or r['sha256']==artifact]
                if any(db.execute('SELECT 1 FROM leases WHERE digest=?',(r['sha256'],)).fetchone() for r in rows):raise ValueError('Removal blocked by an active execution lease')
                for row in rows:db.execute('DELETE FROM active WHERE digest=?',(row['sha256'],))
            for row in rows:
                path=self.path(row)
                if path.exists():shutil.rmtree(path)
        return dict(status='removed',provider='managed',historicalEvidenceRetained=True)
