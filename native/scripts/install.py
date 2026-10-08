"""Install a verified local app atomically, retaining the previous installed bundle."""
import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument("--development",action="store_true",help="Allow installation of the explicitly labelled local preview")
parser.add_argument("--alpha",action="store_true",help="Install the explicitly labelled public alpha")
parser.add_argument("--applications",type=Path,default=Path("/Applications"),help="Canonical installation folder")
args=parser.parse_args()
source=root/"release/native/Wixal.app"
info=plistlib.loads((source/"Contents/Info.plist").read_bytes())
channel=info.get("WixalReleaseChannel")
if channel=="alpha" and not args.alpha:parser.error("Use --alpha to install this public alpha")
if channel=="development" and not args.development:
    parser.error("This is a development preview. Pass --development for local installation.")
if subprocess.run(["pgrep","-x","WixalNative"],stdout=subprocess.DEVNULL).returncode==0:
    parser.error("Quit Wixal Native before installing. Workspace storage is retained.")
applications=args.applications.expanduser().resolve();applications.mkdir(parents=True,exist_ok=True)
destination=applications/source.name
staging=Path(tempfile.mkdtemp(prefix=".wixal-install-",dir=applications))
candidate=staging/source.name
backup_directory=Path.home()/"Library/Application Support/Wixal Release Backups"/time.strftime("%Y%m%d-%H%M%S")
backup_directory.mkdir(parents=True,exist_ok=True)
backup=backup_directory/source.name
try:
    subprocess.run(["ditto",str(source),str(candidate)],check=True)
    subprocess.run(["codesign","--verify","--deep","--strict",str(candidate)],check=True)
    def digest(path):
        with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
    evidence={}
    for relative in ("Contents/MacOS/WixalNative","Contents/Resources/engine/wixal-engine","Contents/Info.plist"):
        expected=digest(source/relative)
        if digest(candidate/relative)!=expected:raise RuntimeError("Installed file differs: "+relative)
        evidence[relative]=expected
    if destination.exists():destination.rename(backup)
    try:candidate.rename(destination)
    except BaseException:
        if backup.exists():backup.rename(destination)
        raise
    # Retain configured native schedules when the canonical app replaces a preview.
    for agent in (Path.home()/"Library/LaunchAgents").glob("app.wixal.native.scheduler.*.plist"):
        content=plistlib.loads(agent.read_bytes())
        command=content.get("ProgramArguments",[])
        if command and "/Applications/Wixal" in command[0]:
            command[0]=str(destination/"Contents/Resources/engine/wixal-engine")
            if "--runtime" in command:command[command.index("--runtime")+1]=str(destination/"Contents/Resources/ollama")
            subprocess.run(["launchctl","bootout","gui/"+str(os.getuid()),str(agent)],capture_output=True)
            agent.write_bytes(plistlib.dumps(content));agent.chmod(0o600)
            result=subprocess.run(["launchctl","bootstrap","gui/"+str(os.getuid()),str(agent)],capture_output=True)
            if result.returncode:raise RuntimeError("Installed app, but background scheduler needs re-enabling in Settings: "+agent.name)
    previous=None
    if backup.exists():
        archive=backup.with_suffix('.zip')
        subprocess.run(['ditto','-c','-k','--keepParent',str(backup),str(archive)],check=True)
        shutil.rmtree(backup)
        previous=str(archive)
    report=dict(installed=str(destination),previous=previous,development=args.development,alpha=args.alpha,sha256=evidence)
    artifact=root/"artifacts/native/install-current.json";artifact.parent.mkdir(parents=True,exist_ok=True);artifact.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
finally:shutil.rmtree(staging)
