"""Build an independent Finder-launchable arm64 app; never replace Electron."""
import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

native = Path(__file__).resolve().parents[1]
root = native.parent
app = root/"release/native/Wixal Native.app"

parser=argparse.ArgumentParser(description="Build a native app; distribution requires Developer ID and notarisation.")
parser.add_argument("--development",action="store_true",help="Explicit local preview with development signing; not distributable")
parser.add_argument("--identity",help="Developer ID Application identity")
parser.add_argument("--notary-profile",help="Stored notarytool Keychain profile")
options=parser.parse_args()
if not options.development:
    if not options.identity or not options.identity.startswith("Developer ID Application:") or not options.notary_profile:
        parser.error("Distribution requires --identity 'Developer ID Application: …' and --notary-profile. Use --development only for local validation.")
    identities=subprocess.check_output(["security","find-identity","-v","-p","codesigning"],text=True)
    if options.identity not in identities:parser.error("The requested Developer ID identity is not available in this Mac's Keychain")
elif options.identity or options.notary_profile:parser.error("Development and distribution options cannot be combined")
destination=app
(root/"release/native").mkdir(parents=True,exist_ok=True)
staging=Path(tempfile.mkdtemp(prefix="wixal-native-package-",dir=root/"release/native"))
app=staging/app.name

def run(*args):
    subprocess.run([str(a) for a in args], cwd=native, check=True)

run("swift", "build", "--build-system", "native", "-c", "release")
bin_path = Path(subprocess.check_output(["swift", "build", "--build-system", "native", "-c", "release", "--show-bin-path"], cwd=native, text=True).strip())
signing=["--codesign-identity",options.identity] if options.identity else []
run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", *signing, "--name", "wixal-engine", "--paths", native/"engine",
    "--add-data", str(native/"engine/wixal/resources")+":wixal/resources", native/"engine/engine_main.py")
if app.exists():
    shutil.rmtree(app)
resources=app/"Contents/Resources";macos=app/"Contents/MacOS"
resources.mkdir(parents=True);macos.mkdir()
shutil.copy2(bin_path/"WixalNative",macos/"WixalNative")
for bundle in bin_path.glob("*.bundle"):
    shutil.copytree(bundle,resources/bundle.name,symlinks=True)
shutil.copytree(native/"dist/wixal-engine",resources/"engine",symlinks=True)
shutil.copytree(root/"runtime/ollama",resources/"ollama",symlinks=True)
shutil.copytree(root/"assets/icon-variants",resources/"icon-variants",symlinks=True)
shutil.copytree(root/"assets/audio",resources/"audio",symlinks=True)
if (root/"assets/Wixal.icns").exists():shutil.copy2(root/"assets/Wixal.icns",resources/"Wixal.icns")
with (app/"Contents/Info.plist").open("wb") as file:
    plistlib.dump(dict(CFBundleExecutable="WixalNative",CFBundleIdentifier="app.wixal.native.preview",CFBundleName="Wixal Native",
        CFBundleDisplayName="Wixal Native",CFBundlePackageType="APPL",CFBundleShortVersionString="0.7.8",CFBundleVersion="1",
        CFBundleIconFile="Wixal.icns",LSMinimumSystemVersion="14.0",LSApplicationCategoryType="public.app-category.developer-tools",
        NSHighResolutionCapable=True,NSAppTransportSecurity=dict(NSAllowsArbitraryLoads=True),
        NSHumanReadableCopyright="Wixal. Includes SwiftTerm and Ollama; see bundled notices."),file)
notices = "Wixal Native uses SwiftTerm (MIT), Swift Markdown (Apache 2.0 with Swift runtime exception), swift-cmark (CommonMark/GFM parser licenses), Ollama (MIT) and a bundled Python runtime (PSF).\nNo Hermes implementation has been copied into this port.\n"
(resources/"THIRD_PARTY_NOTICES.txt").write_text(notices)
for name, source in (("SwiftTerm-LICENSE",native/".build/checkouts/SwiftTerm/LICENSE"),("Wixal-LICENSE",root/"LICENSE")):
    if source.exists():shutil.copy2(source,resources/name)
for dependency in ("swift-markdown", "swift-cmark"):
    checkout=native/".build/checkouts"/dependency
    for notice in ("LICENSE.txt", "COPYING", "COPYING.md", "NOTICE.txt"):
        if (checkout/notice).exists():shutil.copy2(checkout/notice,resources/(dependency+"-"+notice))
python_license = Path(sys.base_prefix)/f"lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt"
if python_license.exists(): shutil.copy2(python_license,resources/"Python-LICENSE.txt")
import importlib.metadata
pyinstaller_info = importlib.metadata.distribution("pyinstaller")
for entry in pyinstaller_info.files or []:
    if str(entry).endswith("licenses/COPYING.txt"):
        shutil.copy2(pyinstaller_info.locate_file(entry),resources/"PyInstaller-COPYING.txt")
sys.path.insert(0,str(native/"engine"))
from wixal.runtime import Runtime
# Verify the vendor payload before any signing changes its bytes.
with tempfile.TemporaryDirectory() as directory:
    Runtime(directory,resources/"ollama").verify()
if options.development:
    (resources/"BUILD_MODE.txt").write_text("Local development preview. Not Developer ID signed or notarised.\n")
    run("codesign","--force","--deep","--sign","-",app)
else:
    magic={bytes.fromhex(h) for h in ("feedface","cefaedfe","feedfacf","cffaedfe","cafebabe","bebafeca","cafebabf","bfbafeca")}
    for binary in sorted(app.rglob("*"),key=lambda p:len(p.parts),reverse=True):
        if binary.is_file() and not binary.is_symlink():
            with binary.open("rb") as stream:header=stream.read(4)
            if header in magic:run("codesign","--force","--options","runtime","--timestamp","--sign",options.identity,binary)
    # The signed runtime has different bytes. Its manifest remains covered by the outer app signature.
    manifest_path=resources/"ollama/manifest.json"
    manifest=json.loads(manifest_path.read_text())
    for entry in manifest["files"]:
        if "link" not in entry:
            with (resources/"ollama"/entry["path"]).open("rb") as stream:entry["sha256"]=hashlib.file_digest(stream,"sha256").hexdigest()
    manifest_path.write_text(json.dumps(manifest,indent=2))
    for bundle in sorted(app.rglob("*.framework"),key=lambda p:len(p.parts),reverse=True):run("codesign","--force","--options","runtime","--timestamp","--sign",options.identity,bundle)
    run("codesign","--force","--options","runtime","--timestamp","--sign",options.identity,app)
run("codesign","--verify","--deep","--strict",app)
with tempfile.TemporaryDirectory() as directory:Runtime(directory,resources/"ollama").verify()
if not options.development:
    archive=staging/"Wixal-Native.zip"
    run("ditto","-c","-k","--keepParent",app,archive)
    notarisation=json.loads(subprocess.check_output(["xcrun","notarytool","submit",str(archive),"--keychain-profile",options.notary_profile,"--wait","--output-format","json"],text=True))
    if notarisation.get("status")!="Accepted":raise RuntimeError("Notarisation was not accepted: "+str(notarisation.get("status")))
    run("xcrun","stapler","staple",app)
    run("xcrun","stapler","validate",app)
    run("spctl","--assess","--type","execute","--verbose=2",app)
backup=destination.with_name(destination.name+".previous")
if backup.exists():shutil.rmtree(backup)
if destination.exists():destination.rename(backup)
try:app.rename(destination)
except BaseException:
    if backup.exists():backup.rename(destination)
    raise
shutil.rmtree(staging)
print(destination)
