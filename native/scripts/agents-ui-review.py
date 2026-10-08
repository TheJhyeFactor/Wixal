"""Open the complete Agents preview with its matching frozen engine.

The earlier launcher copied an old packaged helper beside a new Swift binary.
Runtime acceptance now requires the complete verified package, with persistent
preview workspace configuration retained across Finder launches.
"""
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
installed=Path.home()/'Applications/Wixal Agents.app'
packaged=root/'artifacts/native/agents-runtime/Wixal Agents.app'
app=installed if installed.exists() else packaged
if not app.exists():
    raise SystemExit('Build the complete Agents package first; see native/AGENTS_RUNTIME_ACCEPTANCE_2026-10-08.md.')
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
subprocess.run(['open',str(app)],check=True)
print(json.dumps(dict(app=str(app),workspace=str(root/'artifacts/native/agents-runtime/verified-workspace')),indent=2))
