"""Persistent workspace and retrieval workload benchmark, never model-quality evidence.

Generated histories and vectors live only in temporary storage. Every result identifies
fixture data separately from live-model acceptance. Assertions check persistence,
incremental indexing, source isolation and vector scoring rather than timing alone.
"""
import json
import math
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store
from wixal.semantic import digest
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/native/memory-scale.json';OUT.parent.mkdir(parents=True,exist_ok=True)
report=dict(status='running',source='Generated workload fixtures in temporary workspace; no model inference',measurements=[],semanticInference='Not exercised by this scoring benchmark; see memory-quality acceptance')
def timed(work):
    start=time.monotonic();value=work();return value,time.monotonic()-start
try:
    with tempfile.TemporaryDirectory() as folder:
        store=Store(folder);store.add_project(folder)
        for count in (100,1000,5000):
            project=store.data['activeProject']
            store.data['sessions']=[dict(id=str(i),projectId=project,memoryOwner='guest',title='History '+str(i),messages=[dict(id=f'{i}-{j}',role='user' if j%2==0 else 'assistant',content=f'Invoice database decision {i}: PostgreSQL. '+('Measured historical passage. '*20)) for j in range(6)]) for i in range(count)]
            _,save=timed(store.save);_,initial=timed(store.memory.sync)
            assert store.db.execute('SELECT count(*) FROM memory_search').fetchone()[0]==count*6
            found,steady=timed(lambda:store.memory.recall('invoice database decision'))
            assert found and all(r['scope']=='project' for r in found)
            assert store.memory.index_metrics['changedSessions']==0
            row=dict(sessions=count,passages=count*6,stateBytes=len(json.dumps(store.data).encode()),fullSaveSeconds=save,initialSeconds=initial,steadyRecallSeconds=steady,steadyIndex=dict(store.memory.index_metrics))
            store.data['sessions'][-1]['messages'][-1]['content']='Invoice database updated to SQLite';_,changed_save=timed(store.save)
            found,changed=timed(lambda:store.memory.recall('SQLite'))
            assert any('SQLite' in r['content'] for r in found)
            assert store.memory.index_metrics['changedSessions']==1
            row.update(changedSaveSeconds=changed_save,changedRecallSeconds=changed,changedIndex=dict(store.memory.index_metrics))
            # 768-dimensional vectors stress production cosine/scoring code, not inference.
            documents=store.memory.documents('project');version='workload-768'
            vector=[math.sin(i+1) for i in range(768)];encoded=json.dumps(vector)
            start=time.monotonic()
            with store.db:
                store.db.executemany('INSERT OR REPLACE INTO memory_vectors VALUES(?,?,?,?)',((key,digest(text),version,encoded) for key,text in documents))
            row['vectorWriteSeconds']=time.monotonic()-start
            semantic=store.memory.semantic;semantic.query='scale scoring';semantic.vector=vector;semantic.version=version
            scores,score_time=timed(lambda:semantic.scores('scale scoring',documents))
            assert len(scores)==count*6 and all(abs(score-1)<1e-9 for score in scores.values())
            row.update(semanticScoringSeconds=score_time,vectorDimensions=768,scoredPassages=len(scores),vectors='Generated deterministic workload vectors; no model inference')
            # Changed text must never reuse its stale embedding.
            changed_documents=documents[:-1]+[(documents[-1][0],documents[-1][1]+' changed')]
            assert documents[-1][0] not in semantic.scores('scale scoring',changed_documents)
            _,close=timed(store.close);store,reopen=timed(lambda:Store(folder));_,restart_index=timed(store.memory.sync)
            assert len(store.data['sessions'])==count and 'SQLite' in store.data['sessions'][-1]['messages'][-1]['content']
            assert store.memory.index_metrics['changedSessions']==0
            row.update(closeSeconds=close,reopenSeconds=reopen,restartIndexSeconds=restart_index)
            # Scope must exclude every passage after switching projects, even at scale.
            other=Path(folder)/'other';other.mkdir(exist_ok=True);store.add_project(str(other))
            assert store.memory.recall('invoice database decision')==[]
            store.select_project(project)
            report['measurements'].append(row);OUT.write_text(json.dumps(report,indent=2));print(json.dumps(row),flush=True)
        store.close()
    report['status']='passed'
except BaseException as error:
    report.update(status='failed',error=str(error));raise
finally:OUT.write_text(json.dumps(report,indent=2))
