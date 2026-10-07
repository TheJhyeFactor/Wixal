"""Prepare disposable UI state; no responses or evidence are fabricated."""
import asyncio
import importlib.util
import json
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/feature-acceptance'
spec=importlib.util.spec_from_file_location('real',ROOT/'native/scripts/real-acceptance.py');real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real);real.ART=ART;real.STATE=ART/'workspace'
async def main():
 c=real.Client(False)
 try:
  await c.start();await c.call('project-add',dict(root=str(ROOT)));await c.call('session-new');await c.call('model-use',dict(name='gemma3:1b'));await c.call('settings',dict(approvalMode='review',ui=dict(launchAnimation=False,reduceMotion=True,textSize=17)))
 finally:await c.close()
 # UI acceptance excludes legal/account first entry, which requires actual user acceptance.
 with sqlite3.connect(real.STATE/'workspace.sqlite3') as db:
  d=json.loads(db.execute('SELECT value FROM state').fetchone()[0]);d['setup']=dict(entryCompleted=True,completed=True,acceptanceFixture='Welcome/account lifecycle excluded from this UI workspace')
  db.execute('UPDATE state SET value=? WHERE id=1',(json.dumps(d),))
 print(real.STATE)
asyncio.run(main())
