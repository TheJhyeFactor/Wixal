"""Local, scoped memory with indexed recall, provenance and reversible suggestions.

Lexical retrieval needs no model. Optional embeddings run entirely on this Mac. Saved facts and
history are distinct; model-written history is recalled evidence, never policy.
"""
import hashlib
import json
import re
import time
from .semantic import Semantic
from .storage import identity, now

STOP = set('a an and are as at be been but by can could do does for from had has have how i if in is it its me my of on or our please that the their them then there these they this to use was we what when where which who why will with would you your tell about give'.split())
SENSITIVE = re.compile(r'(?i)(?:-----BEGIN .*PRIVATE KEY|\b(?:sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{20,})|(?:password|api[_ -]?key|access[_ -]?token|secret)\s*(?::|=|\bis\b)\s*\S+)')

def owner(store):
    account=store.data.get('account',{})
    return 'account:'+str((account.get('profile') or {}).get('id')) if account.get('signedIn') else 'guest'

def settings(store):
    project=store.project()
    mode=(project or {}).get('memoryMode','global')
    from .agent_context import profile
    active=profile.get()
    if active:
        mode={'Project only':'project','Project + global preferences':'both','Global preferences only':'global','Memory off':'off'}.get(active.get('memoryScope'),'project')

    return dict(project=bool(project and mode in ('project','both')),
                global_=bool(mode in ('global','both') and store.data.get('globalMemoryEnabled',True)),
                history=active.get('recallHistory',True) if active else (project or store.data).get('referenceHistory',True),
                suggestions=active.get('suggestMemory',False) if active else (project or store.data).get('memorySuggestions',True),
                modelReview=(project or store.data).get('memoryModelReview',False))

def terms(query):
    return list(dict.fromkeys(w for w in re.findall(r'[\w-]+',query.lower()) if len(w)>2 and w not in STOP))[:24]

def visible_notes(store, scope=None):
    policy=settings(store);result=[]
    if policy['project'] and scope != 'global':
        result += [m for m in store.memories() if m.get('scope','project')=='project' and not m.get('forgotten')]
    if policy['global_'] and scope != 'project':
        result += [m for m in store.data.get('globalMemories',[]) if m.get('owner')==owner(store) and not m.get('forgotten')]
    return result

class Memory:
    def __init__(self,store):
        self.store=store
        self.semantic=Semantic(store)
        self.session_revisions={}
        self.index_metrics={}
        store.data.setdefault('globalMemories',[])
        store.data.setdefault('memorySuggestionsPending',[])
        store.data.setdefault('forgottenMemorySources',[])
        store.data.setdefault('forgottenMemories',[])
        store.data.setdefault('supersededMemorySources',[])
        store.db.execute('CREATE TABLE IF NOT EXISTS memory_source_roles (source TEXT PRIMARY KEY, role TEXT, tool TEXT)')
        store.db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(key UNINDEXED, scope UNINDEXED, owner UNINDEXED, session UNINDEXED, source UNINDEXED, title, content, tokenize="porter unicode61")')
        store.db.execute('CREATE TABLE IF NOT EXISTS memory_search_revision (key TEXT PRIMARY KEY, digest TEXT NOT NULL)')
        store.db.execute('CREATE TABLE IF NOT EXISTS memory_search_rows (key TEXT PRIMARY KEY, rowid INTEGER, session TEXT)')
        store.db.execute('CREATE INDEX IF NOT EXISTS memory_search_session ON memory_search_rows(session)')
        store.db.execute('CREATE TABLE IF NOT EXISTS memory_session_revisions (session TEXT PRIMARY KEY, digest TEXT)')
        store.db.execute('INSERT OR IGNORE INTO memory_search_rows SELECT key,rowid,session FROM memory_search')
        self.session_revisions=dict(store.db.execute('SELECT session,digest FROM memory_session_revisions'))
        store.db.commit()

    def sync(self):
        started=time.monotonic();store=self.store;changed=0;live=set()
        forgotten=set(store.data['forgottenMemorySources']+store.data['supersededMemorySources'])
        exclusions=hashlib.sha256(json.dumps([sorted(forgotten),sorted(store.data['forgottenMemories'])]).encode()).hexdigest()
        def remove(sid):
            for key,rowid in store.db.execute('SELECT key,rowid FROM memory_search_rows WHERE session=?',(sid,)).fetchall():
                store.db.execute('DELETE FROM memory_search WHERE rowid=?',(rowid,))
                store.db.execute('DELETE FROM memory_search_revision WHERE key=?',(key,))
                store.db.execute('DELETE FROM memory_vectors WHERE key=?',(key,))
            store.db.execute('DELETE FROM memory_search_rows WHERE session=?',(sid,))
        with store.db:
            for session in store.data['sessions']:
                sid=session['id'];live.add(sid)
                revision=store.session_digests.get(sid,'')+exclusions
                if self.session_revisions.get(sid)==revision:continue
                remove(sid);changed+=1
                if not session.get('archivedAt') and not session.get('memoryExcluded'):
                    for message in session.get('messages',[]):
                        source=message.get('id')
                        if message.get('role') not in ('user','assistant','tool') or message.get('handoff') or not source:continue
                        if source in forgotten or set(message.get('memoryReferences',[])) & set(store.data['forgottenMemories']):continue
                        content=message.get('displayContent',message.get('content',''))
                        if not content or SENSITIVE.search(content):continue
                        store.db.execute('INSERT OR REPLACE INTO memory_source_roles VALUES(?,?,?)',(source,message.get('role'),message.get('tool_name')))
                        for offset in range(0,len(content),1400):
                            key=f'{sid}:{source}:{offset}'
                            row=(key,session.get('projectId') or 'personal',session.get('memoryOwner','guest'),sid,source,session['title'],content[offset:offset+1800])
                            cursor=store.db.execute('INSERT INTO memory_search VALUES(?,?,?,?,?,?,?)',row)
                            store.db.execute('INSERT INTO memory_search_rows VALUES(?,?,?)',(key,cursor.lastrowid,sid))
                self.session_revisions[sid]=revision
                store.db.execute('INSERT OR REPLACE INTO memory_session_revisions VALUES(?,?)',(sid,revision))
            for sid in set(self.session_revisions)-live:
                remove(sid);del self.session_revisions[sid]
                store.db.execute('DELETE FROM memory_session_revisions WHERE session=?',(sid,))
        self.index_metrics=dict(changedSessions=changed,milliseconds=round((time.monotonic()-started)*1000))

    def documents(self,scope=None,exclude_session=None):
        self.sync();policy=settings(self.store);scopes=[]
        if policy['project'] and scope!='global':scopes.append(self.store.data['activeProject'])
        if policy['global_'] and scope!='project':scopes.append('personal')
        documents=[('note:'+n['id'],n['content']) for n in visible_notes(self.store,scope)]
        if scopes and policy['history']:
            marks=','.join('?' for _ in scopes)
            documents += self.store.db.execute(f'SELECT key,content FROM memory_search WHERE scope IN ({marks}) AND owner=? AND session!=?',(*scopes,owner(self.store),exclude_session or '')).fetchall()
        return documents

    async def prepare(self,query,runtime,scope=None,exclude_session=None):
        await self.semantic.prepare(query,runtime,self.documents(scope,exclude_session))

    def recall(self,query,scope=None,limit=6,include_history=True,exclude_session=None):
        store=self.store;policy=settings(store);words=terms(query)
        ranked=[]
        semantic=self.semantic.scores(query,self.documents(scope,exclude_session)) if self.store.data.get('memoryEmbeddingModel') else {}
        for note in visible_notes(store,scope):
            matches=set(words)&set(terms(note['content']))
            persistent=bool(note.get('pinned'))
            similarity=semantic.get('note:'+note['id'],0)
            if matches or similarity>=0.55 or persistent:
                ranked.append((len(matches)/max(1,len(words))+similarity+int(persistent),dict(id=note['id'],kind='saved',sourceRole='user',relevance=round(similarity,3),scope=note.get('scope','project'),content=note['content'],sourceSession=note.get('sourceSession'),sourceMessage=note.get('sourceMessage'),updated=note.get('updated',note['created']))))
        ranked.sort(key=lambda item:(item[0],item[1]['updated']),reverse=True)
        results=[item for _,item in ranked[:limit]]
        if not include_history or not policy['history'] or not words:return results
        scopes=[]
        if policy['project'] and scope != 'global':scopes.append(store.data['activeProject'])
        # Global history is personal-workspace history, never another project's history.
        if policy['global_'] and scope != 'project':scopes.append('personal')
        if not scopes:return results
        self.sync()
        match=' OR '.join('"'+word.replace('"','')+'"' for word in words)
        marks=','.join('?' for _ in scopes)
        rows=store.db.execute(f'SELECT key,scope,session,source,title,content,bm25(memory_search,0,0,0,0,0,2,1) FROM memory_search WHERE memory_search MATCH ? AND scope IN ({marks}) AND owner=? AND session!=? ORDER BY bm25(memory_search,0,0,0,0,0,2,1) LIMIT ?', (match,*scopes,owner(store),exclude_session or '',limit*3)).fetchall()
        if semantic:
            candidates=store.db.execute(f'SELECT key,scope,session,source,title,content,0 FROM memory_search WHERE scope IN ({marks}) AND owner=? AND session!=?',(*scopes,owner(store),exclude_session or '')).fetchall()
            by_key={row[0]:row for row in rows}
            for row in candidates:
                if semantic.get(row[0],0)>=0.55:by_key[row[0]]=row
            rows=sorted(by_key.values(),key=lambda row:semantic.get(row[0],0)+(len(set(words)&set(terms(row[5])))/max(1,len(words)))*0.2,reverse=True)
        saved_answers=any(r.get('relevance',0)>=0.55 or len(set(words)&set(terms(r['content'])))>=min(2,len(words)) for r in results) and not re.search(r'(?i)\b(?:history|previous|earlier|conversation)\b',query)
        seen=set();seen_text={item["content"].casefold() for item in results}
        for key,record_scope,session,source,title,content,_ in rows:
            if source in seen or content.casefold() in seen_text:continue
            seen.add(source);seen_text.add(content.casefold())
            role=store.db.execute('SELECT role,tool FROM memory_source_roles WHERE source=?',(source,)).fetchone() or ('unknown',None)
            if saved_answers and role[0]=='assistant':continue
            results.append(dict(id=key,kind='history',sourceRole=role[0],tool=role[1],relevance=round(semantic.get(key,0),3),scope='global' if record_scope=='personal' else 'project',sourceSession=session,sourceMessage=source,title=title,content=content))
            if len(results)>=limit:break
        return results[:limit]

    def context(self,query,session,limit):
        # Literal output requests need no recalled facts. Historical copies of the
        # same command can confuse small models, and remain searchable separately.
        if re.match(r'(?is)^\s*(?:reply|respond|say|return|output|repeat)\s+(?:with\s+)?exactly\s*:',query):return '',[]
        wants_history=bool(re.search(r'(?i)\b(?:history|earlier|previous|did we|did i)\b',query))
        fresh_action=bool(re.search(r'(?:^|\s)@[a-zA-Z][a-zA-Z0-9_]*',query)) and not wants_history
        results=self.recall(query,limit=12,exclude_session=session['id'],include_history=not fresh_action)
        wants_questions=bool(re.search(r'(?i)\b(?:did i ask|previous questions?|earlier questions?|conversation history)\b',query))
        if not wants_questions:
            # Prior requests are searchable history, but repeating a question is not evidence for its answer.
            results=[r for r in results if not (r['kind']=='history' and r.get('sourceRole')=='user' and re.match(r'(?is)^(?:what|how|when|where|why|which|who|can|could|do|does|is|are)\b.*\?',r['content']) and not re.search(r'(?i)\b(?:remember|we decided|we agreed|i prefer)\b',r['content']))]
        results=results[:6]
        lines=[];sources=[];used=0
        for item in results:
            room=limit-used-90
            if room<120:break
            excerpt=item['content'][:min(1500,room)]
            lines.append(f'[{item["scope"]} {item["kind"]} {item.get('sourceRole','user')} {item["id"]}] {excerpt}')
            sources.append({k:v for k,v in item.items() if k!='content'}|dict(excerpt=excerpt))
            used+=len(lines[-1])+1
        return '\n'.join(lines),sources

    def save(self,content,scope='project',source_session=None,source_message=None,replace=None):
        store=self.store;policy=settings(store)
        if scope not in ('project','global') or not policy['project' if scope=='project' else 'global_']:
            raise ValueError('This memory scope is disabled. Change the Memory scope first.')
        if not isinstance(content,str) or not content.strip() or len(content)>4000:raise ValueError('Memory must contain 1–4,000 characters')
        if SENSITIVE.search(content):raise ValueError('Credentials cannot be saved as memory')
        content=content.strip()
        collection=store.data['memories'] if scope=='project' else store.data['globalMemories']
        notes=[n for n in collection if (n.get('projectId')==store.data['activeProject'] if scope=='project' else n.get('owner')==owner(store))]
        existing=next((n for n in notes if n['id']==replace),None) if replace else next((n for n in notes if n['content'].casefold()==content.casefold()),None)
        if replace and not existing:raise ValueError('Choose a saved memory in the active scope')
        budget=(store.project() or {}).get('memorySize',24000) if scope=='project' else 8000
        if sum(len(n['content']) for n in notes if n is not existing)+len(content)>budget:raise ValueError('Saved memory budget is full; edit or forget an older note')
        if existing:
            previous_source=dict(session=existing.get('sourceSession'),message=existing.get('sourceMessage'))
            if existing['content']!=content:
                existing.setdefault('revisions',[]).append({k:existing.get(k) for k in ('content','sourceSession','sourceMessage','updated')})
                old=existing.get('sourceMessage')
                for session in store.data['sessions']:
                    allowed=session.get('projectId')==existing.get('projectId') if scope=='project' else session.get('projectId') is None and session.get('memoryOwner','guest')==owner(store)
                    if not allowed:continue
                    superseded_turn=False
                    for message in session.get('messages',[]):
                        if message.get('role')=='user':superseded_turn=bool(old and message.get('id')==old and old!=source_message)
                        if message.get('id')!=source_message and (superseded_turn or set([existing['id'],*existing.get('mergedIds',[])]) & set(message.get('memoryReferences',[])) or existing['content'].casefold() in message.get('content','').casefold()):
                            store.data['supersededMemorySources'].append(message['id'])
                store.data['supersededMemorySources']=list(dict.fromkeys(store.data['supersededMemorySources']))
                existing.setdefault('sources',[]).append(dict(session=source_session,message=source_message,created=now()))
                existing.update(sourceSession=source_session,sourceMessage=source_message)
            for source in (previous_source,dict(session=source_session,message=source_message)):
                if source['session'] or source['message']:
                    if not any(n.get('session')==source['session'] and n.get('message')==source['message'] for n in existing.setdefault('sources',[])):existing['sources'].append(source|dict(created=now()))
            existing.update(content=content,updated=now())
            note=existing
        else:
            note=dict(id=identity(),scope=scope,content=content,created=now(),owner=owner(store),projectId=store.data['activeProject'] if scope=='project' else None,sourceSession=source_session,sourceMessage=source_message)
            collection.append(note)
        store.save();return note

    def forget(self,note_id):
        store=self.store
        note=next((n for n in visible_notes(store) if n['id']==note_id),None)
        # Deletion stays available even while recall is disabled.
        if not note:
            note=next((n for n in store.memories() if n['id']==note_id),None) or next((n for n in store.data['globalMemories'] if n['id']==note_id and n.get('owner')==owner(store)),None)
        if not note:raise ValueError('Choose a memory from this workspace or identity')
        if note.get('sourceMessage'):store.data['forgottenMemorySources'].append(note['sourceMessage'])
        store.data['forgottenMemories'].extend([note_id,*note.get('mergedIds',[])])
        store.data['forgottenMemorySources'].extend(s['message'] for s in note.get('sources',[]) if s.get('message'))
        # Suppress literal copies in old history; deletion must not restore the same fact next turn.
        for session in store.data['sessions']:
            allowed=session.get('projectId')==note.get('projectId') if note.get('scope','project')=='project' else session.get('projectId') is None and session.get('memoryOwner','guest')==owner(store)
            if allowed:
                forget_turn=False
                for message in session.get('messages',[]):
                    if message.get('role')=='user':forget_turn=message.get('id')==note.get('sourceMessage')
                    if forget_turn and message.get('id'):store.data['forgottenMemorySources'].append(message['id'])
                    if note['content'].casefold() in message.get('content','').casefold() and message.get('id'):store.data['forgottenMemorySources'].append(message['id'])
        store.data['forgottenMemorySources']=list(dict.fromkeys(store.data['forgottenMemorySources']))
        for key in ('memories','globalMemories'):store.data[key]=[n for n in store.data[key] if n['id']!=note_id]
        store.save();self.sync();return True

    def suggest(self,text,session):
        policy=settings(self.store)
        if not policy['suggestions'] or not (policy['project'] or policy['global_']):return
        # Suggestions quote only the human's own durable preference/remember request.
        plain=re.sub(r'```.*?```','',text,flags=re.S)
        for line in re.split(r'[\n]+|(?<=[.!?])\s+',plain):
            if not re.search(r'(?i)\b(remember (?:that|to|this)|i prefer|always use|for future|from now on|we (?:decided|agreed|chose|will use)|the (?:decision|deadline|requirement) is|(?:use|switch to) .+ instead|no longer)\b',line) or len(line)>2000 or SENSITIVE.search(line):continue
            scope='global' if re.search(r'(?i)\b(across (?:all )?projects|global|in every project)\b',line) else 'project' if policy['project'] else 'global'
            if not policy['project' if scope=='project' else 'global_']:continue
            if any(n['content'].casefold()==line.strip().casefold() for n in visible_notes(self.store)):continue
            source=next((m for m in reversed(session['messages']) if m['role']=='user'),{})
            if any(n.get('sourceMessage')==source.get('id') for n in visible_notes(self.store)):continue
            if source.get('id') in self.store.data['forgottenMemorySources']:continue
            pending=self.store.data['memorySuggestionsPending']
            if any(n.get('sourceMessage')==source.get('id') and n.get('extraction')=='local-model' for n in pending):continue
            if any(n['content']==line.strip() and n.get('owner')==owner(self.store) and n.get('projectId')==session.get('projectId') for n in pending):continue
            related=self.related(line.strip(),scope)
            pending.append(dict(**related,id=identity(),content=line.strip(),scope=scope,owner=owner(self.store),projectId=session.get('projectId'),sourceSession=session['id'],sourceMessage=source.get('id'),created=now()))
        self.store.data['memorySuggestionsPending']=self.store.data['memorySuggestionsPending'][-50:]
        self.store.save()

    def related(self,content,scope,exclude=None):
        candidates=[]
        from difflib import SequenceMatcher
        notes=visible_notes(self.store,scope)
        semantic=self.semantic.related_scores(content,notes)
        for note in notes:
            if note['id']==exclude:continue
            a,b=set(terms(content)),set(terms(note['content']))
            overlap=len(a&b)/max(1,min(len(a),len(b)))
            similarity=SequenceMatcher(None,content.casefold(),note['content'].casefold()).ratio()
            meaning=semantic.get(note['id'],0)
            if overlap>=0.6 and similarity>=0.45 or meaning>=0.80:
                conflict=similarity<0.88 or a!=b or bool(re.search(r'(?i)\b(instead|no longer|replaces|now|not|never)\b',content)) or (set(re.findall(r'\d+',content))!=set(re.findall(r'\d+',note['content'])))
                candidates.append((max(similarity,meaning),dict(relatedId=note['id'],relatedDigest=hashlib.sha256(note['content'].encode()).hexdigest(),previousContent=note['content'],reason='Possible superseded decision' if conflict else 'Possible duplicate',action='replace' if conflict else 'merge')))
        return max(candidates,key=lambda x:x[0])[1] if candidates else {}

    def snapshot(self):
        store=self.store;session=store.session() or {}
        pending=[n for n in store.data['memorySuggestionsPending'] if n['owner']==owner(store) and n.get('projectId')==store.data['activeProject']]
        notes=visible_notes(store)
        return dict(review=store.data.get('memoryReviewLast',{}),retrieval=self.semantic.metrics,index=self.index_metrics,embeddingModel=store.data.get('memoryEmbeddingModel',''),policy=settings(store),notes=notes,suggestions=pending,sources=session.get('memorySources',[]),globalUsed=sum(len(n['content']) for n in store.data['globalMemories'] if n.get('owner')==owner(store)),globalBudget=8000)

    def dispatch(self,method,params):
        if method=='memory-status':return self.snapshot()
        if method=='memory-consolidate':
            pending=self.store.data['memorySuggestionsPending'];seen=set()
            for note in visible_notes(self.store,params.get('scope')):
                relation=self.related(note['content'],note.get('scope','project'),note['id'])
                if not relation:continue
                pair=tuple(sorted((note['id'],relation['relatedId'])))
                if pair in seen or any(n.get('candidateId')==note['id'] for n in pending):continue
                seen.add(pair)
                pending.append(dict(**relation,candidateId=note['id'],id=identity(),content=note['content'],scope=note.get('scope','project'),owner=owner(self.store),projectId=self.store.data['activeProject'],sourceSession=note.get('sourceSession'),sourceMessage=note.get('sourceMessage'),created=now()))
            self.store.save();return self.snapshot()
        if method=='memory-recall':return self.recall(params.get('query',''),params.get('scope'))
        if method=='memory-save':return self.save(params.get('content'),params.get('scope','project'),replace=params.get('id'))
        if method=='memory-forget':return self.forget(params.get('id'))
        if method=='memory-suggestion':
            item=next((n for n in self.snapshot()['suggestions'] if n['id']==params.get('id')),None)
            if not item:raise ValueError('This suggestion is no longer available')
            if params.get('accept'):
                replacement=item.get('relatedId') if params.get('consolidate') else None
                if replacement:
                    previous=next((n for n in visible_notes(self.store,item['scope']) if n['id']==replacement),None)
                    if not previous or hashlib.sha256(previous['content'].encode()).hexdigest()!=item.get('relatedDigest'):raise ValueError('The related note changed. Review the current note before consolidating.')
                content=item['content']
                operation=params.get('operation',item.get('action'))
                if replacement and operation not in ('merge','replace'):raise ValueError('Choose replacement or combination')
                if replacement and operation=='merge':content=item['previousContent']+'\n'+content
                self.save(content,item['scope'],item['sourceSession'],item['sourceMessage'],replace=replacement)
                if replacement and item.get('candidateId'):
                    # Merge source links, then retire the duplicate without forgetting its evidence.
                    candidate=next((n for n in visible_notes(self.store,item['scope']) if n['id']==item['candidateId']),None)
                    target=next(n for n in visible_notes(self.store,item['scope']) if n['id']==replacement)
                    if candidate:
                        target['mergedIds']=list(dict.fromkeys(target.get('mergedIds',[])+[candidate['id']]+candidate.get('mergedIds',[])))
                        target.setdefault('sources',[]).extend(candidate.get('sources',[])+[dict(session=candidate.get('sourceSession'),message=candidate.get('sourceMessage'),created=candidate['created'])])
                        collection='memories' if item['scope']=='project' else 'globalMemories'
                        self.store.data[collection]=[n for n in self.store.data[collection] if n['id']!=candidate['id']]
            else:self.store.data['forgottenMemorySources'].append(item['sourceMessage'])
            self.store.data['memorySuggestionsPending']=[n for n in self.store.data['memorySuggestionsPending'] if n['id']!=item['id']]
            self.store.save();return self.snapshot()
        if method=='memory-policy':
            target=self.store.project() or self.store.data
            for key in ('referenceHistory','memorySuggestions','memoryModelReview'):
                if key in params:
                    if not isinstance(params[key],bool):raise ValueError('Choose enabled or disabled')
                    target[key]=params[key]
            self.store.save();return self.snapshot()
        raise ValueError('Unknown memory operation')
