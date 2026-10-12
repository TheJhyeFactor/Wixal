"""Bounded public Hub discovery and display metadata; never execute model cards."""
import asyncio
import copy
import json
import math
import re
import time
import urllib.parse
from collections import Counter
from . import huggingface_models as hub


def metadata(item):
    row=copy.deepcopy(item)
    source=row.get('provenance') or row
    repo=source.get('repo','')
    row['publisher']=repo.split('/')[0] if '/' in repo else 'Unknown'
    if source.get('pipelineTag'):row['pipelineTag']=source['pipelineTag']
    title=repo.split('/')[-1] if repo else row.get('name','')
    row['displayName']=re.sub(r'-GGUF$', '', title, flags=re.I)
    details=row.get('details') or {}
    text=details.get('parameter_size','') or title
    match=re.search(r'(\d+(?:\.\d+)?)\s*([BM])(?:\b|[-_])',text,re.I)
    if not row.get('parameters') and match:
        row['parameters']=float(match[1])*(1e9 if match[2].upper()=='B' else 1e6)
        row['parameterSource']='Model label'
    tags=[str(t).lower() for t in row.get('tags',[]) if isinstance(t,str)]
    caps=row.get('capabilities',[])
    types=[]
    if 'embedding' in caps or row.get('pipelineTag') in ('feature-extraction','sentence-similarity') or 'embedding' in title.lower():types.append('embedding')
    if 'vision' in caps or row.get('pipelineTag')=='image-text-to-text':types.append('vision')
    if 'completion' in caps or row.get('pipelineTag')=='text-generation':types.append('chat')
    if 'coder' in title.lower() or 'code' in tags or 'coding' in tags:types.append('coding')
    if 'thinking' in caps or 'reasoning' in tags:types.append('reasoning')
    row['types']=types
    if source.get('file'):row['quantization']=next((m.group(0).upper() for m in [re.search(r'(?:IQ|Q)\d[\w]*|BF16|F16|F32',source['file'],re.I)] if m),'Unknown')
    else:row['quantization']=details.get('quantization_level','Unknown')
    return row


def grouped(files):
    groups={}
    for file in files:
        row=metadata(file);key=row.get('repo') or row['name']
        group=groups.setdefault(key,dict(row,files=[]))
        group['files'].append(row)
    for group in groups.values():
        group['files'].sort(key=lambda f:f.get('size') or math.inf)
        group['size']=group['files'][0].get('size')
    return sorted(groups.values(),key=lambda g:g['displayName'].lower())


def page_url(value):
    if not isinstance(value,str) or len(value)>8192:raise ValueError('Invalid Hub page')
    parsed=urllib.parse.urlsplit(hub.safe_url(value))
    if parsed.hostname!='huggingface.co' or parsed.path!='/api/models':raise ValueError('Invalid Hub page')
    return value


def search_page(params):
    query=params.get('search','');author=params.get('publisher','');count=params.get('parameters','all');kind=params.get('type','all')
    if not isinstance(query,str) or len(query)>160:raise ValueError('Search must be under 160 characters')
    if not isinstance(author,str) or author and not re.fullmatch(r'[\w.-]{1,96}',author):raise ValueError('Enter a Hugging Face publisher name')
    ranges={'all':'','2':'max:2B','8':'min:2B,max:8B','large':'min:8B'}
    if count not in ranges or kind not in ('all','chat','coding','reasoning','embedding','vision'):raise ValueError('Invalid model filter')
    task=params.get('task','')
    if not isinstance(task,str) or task and not re.fullmatch(r'[a-z][a-z0-9-]{0,79}',task):raise ValueError('Invalid Hugging Face task')
    pairs=[('filter','gguf'),('limit','12'),('sort','downloads'),('direction','-1')]
    for field in ('gguf','tags','cardData','pipeline_tag','gated','sha'):pairs.append(('expand',field))
    if query:pairs.append(('search',query.strip()))
    elif kind=='coding':pairs.append(('search','coder'))
    if author:pairs.append(('author',author))
    if ranges[count]:pairs.append(('num_parameters',ranges[count]))
    if kind in ('chat','vision'):pairs.append(('pipeline_tag','text-generation' if kind=='chat' else 'image-text-to-text'))
    if kind=='embedding':pairs.append(('filter','feature-extraction'))
    if kind=='reasoning':pairs.append(('filter','reasoning'))
    if task:pairs.append(('pipeline_tag',task))
    url=page_url(params['page']) if params.get('page') else hub.HUB+'/api/models?'+urllib.parse.urlencode(pairs)
    try:
        with hub.open_hub(url) as response:
            raw=response.read(4*1024*1024+1);link=response.headers.get('Link','')
    except Exception as error:
        raise ValueError('Hugging Face search is unavailable. Try again or browse the saved catalog.') from error
    if len(raw)>4*1024*1024:raise ValueError('Hub search metadata exceeds 4 MB')
    rows=json.loads(raw)
    if not isinstance(rows,list):raise ValueError('Invalid Hub search response')
    selected=[]
    for item in rows[:12]:
        if not isinstance(item,dict):continue
        try:repo=hub.repo_id(item.get('id',''))
        except ValueError:continue
        info=item.get('gguf') or {};total=info.get('total')
        parameters=total if isinstance(total,(int,float)) and math.isfinite(total) and total>0 else None
        row=metadata(dict(name=repo,repo=repo,revision=item.get('sha','main'),parameters=parameters,parameterSource='Hub GGUF metadata' if parameters else 'Unknown',
            contextLength=info.get('context_length') if type(info.get('context_length')) is int else None,
            pipelineTag=item.get('pipeline_tag',''),tags=item.get('tags',[]),license=(item.get('cardData') or {}).get('license','unknown'),gated=bool(item.get('gated'))))
        if kind!='all' and kind not in row['types']:continue
        selected.append(row)
    match=re.search(r'<([^>]+)>;\s*rel="next"',link)
    return dict(models=selected,nextPage=page_url(match[1]) if match else '',checked=time.time()*1000)


class Browser:
    def __init__(self,cached_filters=None):
        self.cache={};self.filter_cache=copy.deepcopy(cached_filters) if isinstance(cached_filters,dict) else {};self.provider_cache={}

    async def filters(self,params):
        query=params.get('search','');kind=params.get('kind','all')
        if not isinstance(query,str) or len(query)>96 or kind not in ('all','provider'):raise ValueError('Invalid filter search')
        query=query.strip()
        if kind=='provider' and query:
            cached=self.provider_cache.get(query.lower())
            if cached and time.time()-cached[0]<300:return copy.deepcopy(cached[1])
            raw=await asyncio.to_thread(read_hub,hub.HUB+'/api/quicksearch?'+urllib.parse.urlencode({'q':query}))
            if not isinstance(raw,dict):raise ValueError('Invalid Hub publisher search')
            providers={}
            for row in (raw.get('orgs') or [])[:30]+(raw.get('users') or [])[:30]:
                if not isinstance(row,dict):continue
                name=row.get('name') or row.get('user')
                if not isinstance(name,str) or not re.fullmatch(r'[\w.-]{1,96}',name):continue
                label=row.get('fullname')
                providers[name]=dict(id=name,label=label[:120] if isinstance(label,str) and label.strip() else name)
            result=dict(providers=list(providers.values())[:30],source=hub.HUB,checked=time.time()*1000)
            if len(self.provider_cache)>=16:self.provider_cache.pop(next(iter(self.provider_cache)))
            self.provider_cache[query.lower()]=(time.time(),copy.deepcopy(result))
            return result
        if self.filter_cache and time.time()*1000-self.filter_cache.get('checked',0)<24*3600*1000:
            return dict(copy.deepcopy(self.filter_cache),cached=True)
        try:
            tasks,models=await asyncio.gather(asyncio.to_thread(read_hub,hub.HUB+'/api/tasks'),asyncio.to_thread(read_hub,hub.HUB+'/api/models?filter=gguf&sort=downloads&direction=-1&limit=100&expand=author&expand=pipeline_tag&expand=downloads'))
            if not isinstance(tasks,dict) or not isinstance(models,list):raise ValueError('Invalid Hub filter metadata')
            labels=[]
            for identifier,row in list(tasks.items())[:200]:
                if re.fullmatch(r'[a-z][a-z0-9-]{0,79}',identifier) and isinstance(row,dict) and isinstance(row.get('label'),str):labels.append(dict(id=identifier,label=row['label'][:120]))
            types=Counter();owners=Counter()
            known={r['id'] for r in labels}
            for model in models[:100]:
                if not isinstance(model,dict):continue
                try:repo=hub.repo_id(model.get('id',''))
                except ValueError:continue
                owners[repo.split('/')[0]]+=1
                task=model.get('pipeline_tag')
                if isinstance(task,str) and task in known:types[task]+=1
            ranking=lambda counts:sorted(counts,key=lambda k:(-counts[k],k))[:5]
            lookup={r['id']:r for r in labels}
            result=dict(tasks=sorted(labels,key=lambda r:r['label'].casefold()),popularTypes=[lookup[t] for t in ranking(types)],
                providers=[dict(id=p,label=p) for p in ranking(owners)],source=hub.HUB,
                ranking='By model count in the 100 most-downloaded GGUF repositories',checked=time.time()*1000,cached=False)
            self.filter_cache=copy.deepcopy(result);return result
        except (OSError,ValueError):
            if self.filter_cache:return dict(copy.deepcopy(self.filter_cache),cached=True,stale=True)
            raise ValueError('Hugging Face filters are unavailable. Try refreshing later.')

    async def search(self,params):
        key=json.dumps(params,sort_keys=True)
        cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<300:return copy.deepcopy(cached[1])
        result=await asyncio.to_thread(search_page,params)
        semaphore=asyncio.Semaphore(4)
        async def inspect(row):
            if row.get('gated'):return dict(row,files=[],unavailable='Requires Hugging Face access; import an approved local file.')
            async with semaphore:
                try:
                    details=await asyncio.to_thread(hub.repository,row['repo'],row['revision'])
                    files=[metadata(dict(row,**file)) for file in details['files']]
                    return dict(row,files=files,size=min((f['size'] for f in files),default=None),unavailable='' if files else 'No supported single-file GGUF with a published hash.')
                except (ValueError,OSError):return dict(row,files=[],unavailable='Repository files could not be inspected. Try again.')
        result['models']=await asyncio.gather(*(inspect(row) for row in result['models']))
        if len(self.cache)>=8:self.cache.pop(next(iter(self.cache)))
        self.cache[key]=(time.monotonic(),copy.deepcopy(result))
        return result


def read_hub(url):
    with hub.open_hub(url) as response:raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise ValueError('Hub metadata exceeds 4 MB')
    return json.loads(raw)
