"""Exercise production timeline projection over real persisted tool workloads.

No messages or tool results are inserted. Reports contain counts/timings only.
The longest real transcript is also replayed repeatedly to measure sustained use.
Run after building ActivityAcceptance from the current source.
"""
import argparse
import json
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--state', type=Path, default=Path.home() / 'Library/Application Support/Wixal Native/workspace.sqlite3')
parser.add_argument('--binary', type=Path, default=ROOT / 'native/.build/debug/ActivityAcceptance')
parser.add_argument('--replays', type=int, default=30)
options = parser.parse_args()
assert 1 <= options.replays <= 100, 'Choose 1-100 complete projection replays'
report_path = ROOT / 'artifacts/native/activity-workload.json'
report_path.parent.mkdir(parents=True, exist_ok=True)
report = dict(status='running',source='read-only real persisted native conversations',resultsInserted=False,checks=[])
report_path.write_text(json.dumps(report, indent=2))
try:
    with sqlite3.connect(options.state.resolve().as_uri() + '?mode=ro', uri=True) as db:
        state = json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
    sessions = [s for s in state.get('sessions', []) if any(m.get('role') == 'tool' for m in s.get('messages', []))]
    assert sessions, 'No real tool transcripts available; acceptance cannot pass'
    elapsed = []
    count = events = 0
    longest = max(sessions, key=lambda s: len(json.dumps(s['messages'])))
    for session in sessions + [longest] * options.replays:
        payload = json.dumps(dict(messages=session['messages'],tasks=state.get('tasks',[]),sessionID=session['id'])).encode()
        start = time.perf_counter()
        rows = json.loads(subprocess.check_output([str(options.binary)], input=payload, timeout=30))
        elapsed.append(time.perf_counter() - start)
        assert len({r['id'] for r in rows}) == len(rows), 'Duplicate activity IDs'
        captured = [e for r in rows for e in r['events']]
        # Tool evidence must survive projection exactly, including errors and stopped results.
        for message in session['messages']:
            if message.get('role') == 'tool':
                assert message.get('content','') in captured, 'Persisted tool result missing from activity'
                events += 1
        count += len(rows)
    ordered = sorted(elapsed)
    report.update(status='passed',savedConversations=len(sessions),sustainedReplays=options.replays,totalProjectedMilestones=count,toolEvidenceChecks=events,longestTranscriptMessages=len(longest['messages']),longestTranscriptBytes=len(json.dumps(longest['messages']).encode()),medianSeconds=ordered[len(ordered)//2],maxSeconds=max(elapsed),totalSeconds=sum(elapsed),checks=['Stable unique IDs validated twice inside production acceptance binary','Every persisted tool result retained exactly','Repeated longest real transcript completed within 30 seconds per replay'],limits=['Measures existing real workload size; does not certify synthetic 30000-message chat','Does not certify scrolling, keyboard, layouts or VoiceOver'])
except BaseException as exc:
    report.update(status='failed',error=str(exc))
    raise
finally:
    report_path.write_text(json.dumps(report, indent=2))
print(json.dumps(report))
