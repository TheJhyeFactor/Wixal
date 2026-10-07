"""Synthetic history scale benchmark; does not claim real model acceptance."""
import json
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from wixal.storage import Store
ROOT=Path(__file__).resolve().parents[2];results=[]
with tempfile.TemporaryDirectory() as folder:
    store=Store(folder);store.add_project(folder)
    for count in (100,1000,5000):
        store.data['sessions']=[dict(id=str(i),projectId=store.data['activeProject'],memoryOwner='guest',title='History '+str(i),messages=[dict(id=f'{i}-{j}',role='user' if j%2==0 else 'assistant',content=f'Invoice database decision {i}: PostgreSQL. '+('Measured historical passage. '*20)) for j in range(6)]) for i in range(count)]
        store.save();start=time.monotonic();store.memory.sync();initial=time.monotonic()-start
        start=time.monotonic();store.memory.recall('invoice database decision');steady=time.monotonic()-start
        metrics=dict(store.memory.index_metrics)
        store.data['sessions'][-1]['messages'][-1]['content']='Invoice database updated to SQLite';store.save()
        start=time.monotonic();store.memory.recall('invoice database decision');changed=time.monotonic()-start
        results.append(dict(sessions=count,passages=count*6,initialSeconds=initial,steadyRecallSeconds=steady,steadyIndex=metrics,changedRecallSeconds=changed,changedIndex=store.memory.index_metrics))
    store.close()
(ROOT/'artifacts/native/memory-scale.json').write_text(json.dumps(dict(status='passed',source='synthetic scale workload, no inference',measurements=results),indent=2));print(json.dumps(results,indent=2))
