"""Public Hub GGUF discovery, revision-pinned resumable downloads and local import.

Only data files are downloaded. Repository Python, model-card instructions and
remote inference are never invoked. The runtime remains Wixal's local engine.
"""
import asyncio
import hashlib
import json
import os
import re
import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

HUB='https://huggingface.co'


def repo_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][\w.-]{0,95}/[A-Za-z0-9][\w.-]{0,95}',value) or '..' in value:
        raise ValueError('Enter a Hugging Face repository, for example Qwen/Qwen3-0.6B-GGUF')
    return value


def file_name(value):
    if not isinstance(value,str) or len(value)>250 or not re.fullmatch(r'[\w./-]+\.gguf',value,re.I) or any(p in ('','..','.') for p in value.split('/')) or value.startswith('/'):
        raise ValueError('Select a GGUF file inside the repository')
    if re.search(r'-\d{5}-of-\d{5}\.gguf$',value,re.I) or 'mmproj' in value.lower():
        raise ValueError('Split models and vision projectors require a multi-file importer; choose a single-file text GGUF')
    return value


def safe_url(url):
    parsed=urllib.parse.urlsplit(url)
    host=parsed.hostname or ''
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or not (host=='huggingface.co' or host.endswith('.huggingface.co') or host.endswith('.hf.co')):
        raise ValueError('Model download redirect is outside the Hugging Face HTTPS hosts')
    return url


class HubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        safe_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def open_hub(url,headers=None):
    return urllib.request.build_opener(HubRedirect()).open(urllib.request.Request(safe_url(url),headers={'User-Agent':'Wixal-local-model-library/1',**(headers or {})}),timeout=10)


def repository(repo,revision='main'):
    repo=repo_id(repo)
    if not isinstance(revision,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',revision):raise ValueError('Invalid repository revision')
    try:
        with open_hub(f'{HUB}/api/models/{repo}/revision/{urllib.parse.quote(revision,safe="")}?blobs=true') as response:
            raw=response.read(4*1024*1024+1)
    except urllib.error.HTTPError as error:
        raise ValueError('Hugging Face repository is unavailable or requires access. Use a public GGUF repository, or download gated files through your approved Hugging Face account and import locally.') from error
    if len(raw)>4*1024*1024:raise ValueError('Repository metadata exceeds 4 MB')
    data=json.loads(raw);commit=data.get('sha','')
    if not re.fullmatch(r'[a-f0-9]{40}',commit):raise ValueError('Hub did not return a pinned commit identity')
    files=[]
    for row in data.get('siblings',[])[:10000]:
        try:name=file_name(row.get('rfilename'))
        except ValueError:continue
        lfs=row.get('lfs') or {};sha=lfs.get('sha256','');size=lfs.get('size')
        if not re.fullmatch(r'[a-f0-9]{64}',sha) or type(size) is not int or not 8<=size<=100*1024**3:continue
        files.append(dict(repo=repo,revision=commit,file=name,sha256=sha,size=size,name=local_name(repo,name,sha),source=f'{HUB}/{repo}/blob/{commit}/{urllib.parse.quote(name,safe="/")}',license=(data.get('cardData') or {}).get('license','unknown')))
    return dict(repo=repo,revision=commit,files=files,source=f'{HUB}/{repo}',license=(data.get('cardData') or {}).get('license','unknown'))


def local_name(repo,file,sha):
    stem=re.sub(r'[^a-z0-9._-]','-',PurePosixPath(file).stem.lower())[:80]
    return 'hf/'+repo.split('/')[0].lower()+'/'+stem+':'+sha[:12]


def resolve(params,catalog):
    suggested=next((m for m in catalog if m['name']==params.get('name')),None)
    repo=repo_id(params.get('repo') or (suggested or {}).get('repo',''))
    file=file_name(params.get('file') or (suggested or {}).get('file',''))
    result=repository(repo,params.get('revision') or (suggested or {}).get('revision','main'))
    selected=next((f for f in result['files'] if f['file']==file),None)
    if not selected:raise ValueError('Choose a single-file GGUF with a published SHA-256 and size')
    if suggested and suggested.get('sha256') and selected['sha256']!=suggested['sha256']:raise ValueError('Catalogue identity changed; inspect the repository again')
    return dict(provider='huggingface',**selected)


def download(selection,directory,cancelled,progress):
    repo_id(selection['repo']);file_name(selection['file'])
    sha=selection['sha256'];size=selection['size'];revision=selection['revision']
    if not re.fullmatch(r'[a-f0-9]{64}',sha) or not re.fullmatch(r'[a-f0-9]{40}',revision) or type(size) is not int or not 8<=size<=100*1024**3:raise ValueError('Invalid pinned model identity')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    final=directory/(sha+'.gguf');partial=directory/(sha+'.part')
    if any(p.is_symlink() for p in (final,partial)):raise ValueError('Model cache link is not allowed')
    def verify(path):
        checksum=hashlib.sha256()
        with path.open('rb') as stream:
            if stream.read(4)!=b'GGUF':raise ValueError('Downloaded file is not GGUF')
            stream.seek(0)
            while chunk:=stream.read(1024*1024):
                if cancelled.is_set():raise InterruptedError('Download paused')
                checksum.update(chunk)
        if path.stat().st_size!=size or checksum.hexdigest()!=sha:raise ValueError('Model size or SHA-256 does not match the pinned Hub metadata')
    if final.exists():verify(final);progress(size,size);return final
    offset=partial.stat().st_size if partial.exists() else 0
    if offset>size:partial.unlink();offset=0
    if shutil.disk_usage(directory).free<size-offset+256*1024**2:raise ValueError('Insufficient free disk space for this model')
    if offset<size:
        url=f'{HUB}/{selection["repo"]}/resolve/{revision}/{urllib.parse.quote(selection["file"],safe="/")}'
        try:
            with open_hub(url,{'Range':f'bytes={offset}-'} if offset else {}) as response:
                status=response.status
                if offset and status==206:
                    if response.headers.get('Content-Range')!=f'bytes {offset}-{size-1}/{size}':raise ValueError('Invalid resume range returned by Hub')
                elif status==200:offset=0
                else:raise ValueError('Unexpected model transfer response')
                with partial.open('ab' if offset else 'wb') as stream:
                    progress(offset,size)
                    while chunk:=response.read(256*1024):
                        if cancelled.is_set():raise InterruptedError('Download paused')
                        if offset+len(chunk)>size:raise ValueError('Model transfer exceeds published size')
                        stream.write(chunk);offset+=len(chunk);progress(offset,size)
                    stream.flush();os.fsync(stream.fileno())
        except urllib.error.HTTPError as error:raise ValueError('Hub transfer failed; inspect repository access and retry') from error
    try:verify(partial)
    except ValueError:
        partial.unlink(missing_ok=True);raise
    partial.replace(final);final.chmod(0o600);return final


async def import_local(runtime,path,name):
    """Use the trusted bundled CLI with an exact local FROM path, never a registry tag."""
    endpoint=await runtime.endpoint()
    if urllib.parse.urlsplit(endpoint).hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('Downloaded models require a local engine endpoint')
    manifest=Path(path).with_suffix('.Modelfile');manifest.write_text('FROM '+json.dumps(str(Path(path).resolve()))+'\n')
    executable=runtime.payload/'ollama'
    env=dict(os.environ,OLLAMA_HOST=endpoint)
    process=None
    try:
        process=await asyncio.create_subprocess_exec(str(executable),'create',name,'-f',str(manifest),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,env=env)
        async with asyncio.timeout(600):
            output=bytearray()
            while chunk:=await process.stdout.read(65536):
                output.extend(chunk)
                if len(output)>2*1024*1024:raise ValueError('Model import output exceeds bound')
            code=await process.wait()
        if code:raise ValueError('Local model import failed: '+bytes(output).decode(errors='replace')[-1200:])
    finally:
        if process and process.returncode is None:process.kill();await process.wait()
        manifest.unlink(missing_ok=True)
