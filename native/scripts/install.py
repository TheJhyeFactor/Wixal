"""Install a verified local app atomically, retaining the previous installed bundle."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument("--development",action="store_true",help="Allow installation of the explicitly labelled local preview")
args=parser.parse_args()
source=root/"release/native/Wixal Native.app"
if (source/"Contents/Resources/BUILD_MODE.txt").exists() and not args.development:
    parser.error("This is a development preview. Pass --development for local installation.")
if subprocess.run(["pgrep","-x","WixalNative"],stdout=subprocess.DEVNULL).returncode==0:
    parser.error("Quit Wixal Native before installing. Workspace storage is retained.")
applications=Path.home()/"Applications";applications.mkdir(exist_ok=True)
destination=applications/source.name
staging=Path(tempfile.mkdtemp(prefix=".wixal-install-",dir=applications))
candidate=staging/source.name
backup=applications/f"Wixal Native previous {time.strftime('%Y%m%d-%H%M%S')}.app"
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
    report=dict(installed=str(destination),previous=str(backup) if backup.exists() else None,development=args.development,sha256=evidence)
    artifact=root/"artifacts/native/install-current.json";artifact.parent.mkdir(parents=True,exist_ok=True);artifact.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
finally:shutil.rmtree(staging)
