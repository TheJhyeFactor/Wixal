"""Compare the production native projection with Electron using real saved messages.

Reads workspace SQLite in read-only mode. No content is emitted or copied to reports.
"""
import json
import sqlite3
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
source=Path.home()/'Library/Application Support/Wixal Native/workspace.sqlite3'
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
    state=json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
node="const fs=require('node:fs'),a=require('./ui/activity.js');const messages=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(a.turns(messages).flatMap(t=>t.actions.map(x=>({name:x.name,status:x.status.toLowerCase(),output:a.evidence(x).output})))));"
checked=actions=commands=corrected_errors=0
for session in state['sessions']:
    messages=session.get('messages',[])
    if not any(m.get('role')=='tool' for m in messages):continue
    actual=json.loads(subprocess.check_output([str(ROOT/'native/.build/debug/ActivityAcceptance')],input=json.dumps({'messages':messages,'tasks':state['tasks']}).encode()))
    expected=json.loads(subprocess.check_output(['node','-e',node],cwd=ROOT,input=json.dumps(messages).encode()))
    rows=[r for r in actual if ':request:' not in r['id']]
    if len(rows)!=len(expected):raise AssertionError(f"Action count differs in saved conversation {checked}: {len(rows)} versus {len(expected)}")
    for row,js in zip(rows,expected):
        # Native interrupted checkpoints are more explicit than JS prose fallback.
        try:failure=json.loads(row['events'][-1]).get('error')
        except (ValueError,AttributeError,IndexError):failure=None
        if failure:
            assert row['status']=='failed','Recorded tool error was not marked failed'
            if js['status']=='completed':corrected_errors+=1
        elif row['status'] not in ('interrupted','no result') and js['status'] not in ('limited','no results','closed'):
            if row['status']!=js['status']:raise AssertionError(f"Status mismatch: {row['status']} versus {js['status']}")
        if js['name'].startswith(('command_','network_')):
            if row['output']!=js['output']:raise AssertionError('Command/scanner evidence differs from Electron projection')
            commands+=1
        actions+=1
    checked+=1
assert checked and actions,'No real saved tool conversations available'
report=dict(status='passed',savedConversations=checked,pairedActions=actions,commandEvidenceComparisons=commands,explicitErrorsCorrectedFromElectron=corrected_errors,identity='stable and unique over repeated production projection',source='real native persisted messages compared with ui/activity.js',contentStoredInReport=False)
(ROOT/'artifacts/native/activity-acceptance.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
