"""Verify public native alpha metadata, source provenance and installed parity."""
import argparse
import hashlib
import json
import plistlib
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--app',type=Path,default=root/'release/native/Wixal.app')
parser.add_argument('--installed',type=Path)
parser.add_argument('--report',type=Path,default=root/'artifacts/native/alpha-release-verification.json')
args=parser.parse_args()
app=args.app.resolve();resources=app/'Contents/Resources'
info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
release=json.loads((resources/'RELEASE.json').read_text())
assert release['version']==info['WixalReleaseVersion']
assert info['CFBundleShortVersionString']==release['version'].split('-')[0]
assert release['channel']=='alpha' and '-alpha.' in release['version']
assert info['WixalReleaseChannel']=='alpha'
assert not release['notarised'] and not release['developerIDSigned']
assert not any(key.startswith('WixalPreview') for key in info)
assert (resources/'Wixal.icns').stat().st_size>0
for notice in ('THIRD_PARTY_NOTICES.txt','Hermes-LICENSE','Hermes-NOTICE.md','Python-LICENSE.txt','SwiftTerm-LICENSE'):
    assert (resources/notice).is_file(),notice
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
architecture=subprocess.check_output(['lipo','-archs',str(app/'Contents/MacOS'/info['CFBundleExecutable'])],text=True).strip()
assert architecture=='arm64',architecture
manifest=json.loads((resources/'SOURCE_MANIFEST.json').read_text())
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
drift=[relative for relative,expected in manifest.items() if not (root/relative).is_file() or digest(root/relative)!=expected]
assert not drift,drift
assert any('ActivitySources/' in path for path in manifest)
assert any('MarkdownSources/' in path for path in manifest)
assert not list(app.rglob('workspace.sqlite3'))
assert not list(app.rglob('.env'))
for dependency in ('mcp','anyio','pydantic_core','starlette'):
    names=[path for path in (resources/'python-licenses').iterdir() if path.name.lower().replace('-','_')==dependency]
    assert names and any(path.is_file() for path in names[0].rglob('*')),dependency+' licence is missing'
files=['Contents/Info.plist','Contents/MacOS/'+info['CFBundleExecutable'],'Contents/Resources/engine/wixal-engine','Contents/Resources/SOURCE_MANIFEST.json']
hashes={relative:digest(app/relative) for relative in files}
if args.installed:
    subprocess.run(['codesign','--verify','--deep','--strict',str(args.installed)],check=True)
    assert all(digest(args.installed/relative)==expected for relative,expected in hashes.items())
report=dict(status='passed',version=release['version'],architecture=architecture,sourceFiles=len(manifest),sourceDrift=drift,installed=str(args.installed) if args.installed else None,sha256=hashes,developerIDSigned=False,notarised=False)
args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
