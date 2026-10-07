"""Optional local embeddings. No chat model is asked to maintain a second context."""
import asyncio
import hashlib
import json
import math
import time
from .runtime import request_json


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def cosine(a, b):
    if len(a) != len(b) or not a: return 0.0
    denominator=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denominator if denominator else 0.0


class Semantic:
    def __init__(self, store):
        self.store=store; self.query=None; self.vector=None; self.metrics={}; self.cached_queries={}
        store.db.execute('CREATE TABLE IF NOT EXISTS memory_vectors (key TEXT PRIMARY KEY, digest TEXT, model TEXT, vector TEXT)')

    async def prepare(self, query, runtime, documents):
        model=self.store.data.get('memoryEmbeddingModel','')
        self.query=query;self.vector=None
        if not model:
            self.metrics=dict(mode='lexical',pending=0);return
        started=time.monotonic();indexed=0
        try:
            endpoint=await runtime.endpoint()
            # Bind vectors to the actual installed weights, not a mutable model tag.
            tags=await asyncio.to_thread(request_json,endpoint+'/api/tags',None,5)
            tag=next((m for m in tags.get('models',[]) if m['name']==model or m['name']==model+':latest'),None)
            if not tag:raise ValueError('Download the selected embedding model in Models first')
            version=model+':'+tag['digest']
            existing={k:(d,m) for k,d,m in self.store.db.execute('SELECT key,digest,model FROM memory_vectors')}
            missing=[(k,text) for k,text in documents if existing.get(k)!=(digest(text),version)]
            # Bounded incremental work; expose backlog instead of delaying a chat indefinitely.
            for offset in range(0,min(len(missing),32),16):
                batch=missing[offset:offset+16]
                response=await asyncio.to_thread(request_json,endpoint+'/api/embed',dict(model=model,input=[t for _,t in batch],truncate=False,keep_alive=0),15)
                vectors=response.get('embeddings',[])
                if len(vectors)!=len(batch):raise ValueError('Embedding count mismatch')
                with self.store.db:
                    for (key,text),vector in zip(batch,vectors):
                        self.validate(vector)
                        self.store.db.execute('INSERT OR REPLACE INTO memory_vectors VALUES(?,?,?,?)',(key,digest(text),version,json.dumps(vector)))
                indexed+=len(batch)
            query_key=(version,query)
            if query and query_key not in self.cached_queries:
                response=await asyncio.to_thread(request_json,endpoint+'/api/embed',dict(model=model,input=query,truncate=True,keep_alive=0),10)
                vector=response['embeddings'][0];self.validate(vector)
                if len(self.cached_queries)>=64:self.cached_queries.pop(next(iter(self.cached_queries)))
                self.cached_queries[query_key]=vector
            self.vector=self.cached_queries.get(query_key)
            self.version=version
            self.metrics=dict(mode='semantic',model=model,indexed=indexed,pending=max(0,len(missing)-indexed),milliseconds=round((time.monotonic()-started)*1000))
        except (OSError,ValueError,KeyError,IndexError) as error:
            self.metrics=dict(mode='lexical',model=model,error=str(error)[:160],milliseconds=round((time.monotonic()-started)*1000))

    @staticmethod
    def validate(vector):
        if not isinstance(vector,list) or not 1<=len(vector)<=4096 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in vector):
            raise ValueError('Invalid local embedding')

    def scores(self, query, documents):
        if query!=self.query or self.vector is None:return {}
        result={}
        for key,text in documents:
            row=self.store.db.execute('SELECT digest,model,vector FROM memory_vectors WHERE key=?',(key,)).fetchone()
            if row and row[0]==digest(text) and row[1]==self.version:
                result[key]=cosine(self.vector,json.loads(row[2]))
        return result

    def related_scores(self,content,notes):
        if not self.store.data.get('memoryEmbeddingModel') or not getattr(self,'version',None):return {}
        vectors={}
        for note in notes:
            row=self.store.db.execute('SELECT digest,model,vector FROM memory_vectors WHERE key=?',('note:'+note['id'],)).fetchone()
            if row and row[0]==digest(note['content']) and row[1]==self.version:vectors[note['id']]=json.loads(row[2])
        anchor=self.vector if content==self.query else next((vectors[n['id']] for n in notes if n['content']==content and n['id'] in vectors),None)
        return {key:cosine(anchor,value) for key,value in vectors.items()} if anchor else {}
