"""Keep one verified Wixal installation; move obsolete app bundles to Trash.

Defaults to an inventory. --apply requires the canonical app to pass strict
signature verification first. Workspace data, models and reports are untouched.
"""
import argparse
import json
import plistlib
import shutil
import subprocess
import time
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply',action='store_true')
parser.add_argument('--keep',type=Path,default=Path('/Applications/Wixal.app'))
parser.add_argument('--report',type=Path,default=Path(__file__).resolve().parents[2]/'artifacts/native/install-cleanup.json')
options=parser.parse_args()
keep=options.keep.expanduser().resolve()
info=plistlib.loads((keep/'Contents/Info.plist').read_bytes())
assert info.get('CFBundleIdentifier')=='app.wixal.native.preview', 'Keep the canonical native Wixal app'
subprocess.run(['codesign','--verify','--deep','--strict',str(keep)],check=True)
candidates=[]
for directory in (Path('/Applications'),Path.home()/'Applications'):
    for app in sorted(directory.glob('Wixal*.app')):
        if app.is_symlink() or app.resolve()==keep:continue
        try:metadata=plistlib.loads((app/'Contents/Info.plist').read_bytes())
        except (OSError,ValueError):continue
        if not str(metadata.get('CFBundleIdentifier','')).startswith('app.wixal.'):continue
        candidates.append(dict(path=str(app),bundleIdentifier=metadata['CFBundleIdentifier'],version=metadata.get('WixalReleaseVersion',metadata.get('CFBundleShortVersionString'))))
report=dict(status='inventory',canonical=str(keep),version=info.get('WixalReleaseVersion'),obsolete=candidates,moved=[])
if options.apply:
    # Never move a bundle while one of its executables is still running.
    processes=subprocess.check_output(['ps','-axo','comm='],text=True).splitlines()
    running=[row['path'] for row in candidates if any(command.strip().startswith(row['path']+'/') for command in processes)]
    if running:raise SystemExit('Quit these obsolete applications before cleanup: '+', '.join(running))
    trash=Path.home()/'.Trash'/('Wixal retired installs '+time.strftime('%Y%m%d-%H%M%S'))
    trash.mkdir(parents=True,exist_ok=False)
    registrar=Path('/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister')
    for row in candidates:
        app=Path(row['path']);destination=trash/app.name
        if destination.exists():destination=trash/(app.stem+' user applications.app')
        if registrar.exists():subprocess.run([str(registrar),'-u',str(app)],check=True,capture_output=True)
        shutil.move(str(app),str(destination));report['moved'].append(dict(source=str(app),trash=str(destination)))
        options.report.parent.mkdir(parents=True,exist_ok=True);options.report.write_text(json.dumps(report,indent=2)+'\n')
    report['status']='passed'
options.report.parent.mkdir(parents=True,exist_ok=True);options.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status=report['status'],canonical=report['canonical'],obsolete=len(candidates),moved=len(report['moved'])),indent=2))
