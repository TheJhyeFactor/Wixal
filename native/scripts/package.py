"""Build the canonical native macOS app, with explicit alpha or distribution signing."""
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
app = root/"release/native/Wixal.app"

parser=argparse.ArgumentParser(description="Build a native app; distribution requires Developer ID and notarisation.")
parser.add_argument("--development",action="store_true",help="Explicit local preview with development signing; not distributable")
parser.add_argument("--alpha",action="store_true",help="Public alpha with ad-hoc signing and explicit non-notarised release metadata")
parser.add_argument("--identity",help="Developer ID Application identity")
parser.add_argument("--notary-profile",help="Stored notarytool Keychain profile")
parser.add_argument("--output",type=Path,help="Independent app destination for isolated validation")
parser.add_argument("--display-name",default="Wixal")
parser.add_argument("--bundle-identifier",default="app.wixal.native.preview",help="Retains the native preview identity and saved macOS preferences")
parser.add_argument("--executable-name",default="WixalNative")
parser.add_argument("--preview-data",type=Path,help="Development preview workspace retained across Finder launches")
parser.add_argument("--preview-endpoint",help="Loopback model endpoint for an isolated preview")
parser.add_argument("--managed-repository",type=Path,help="Reviewed repository config and bootstrap root to embed; local preview endpoints require --development")
options=parser.parse_args()
sys.path.insert(0,str(native/"engine"))
managed_configuration=None
managed_root=None
if options.managed_repository:
    managed_configuration=json.loads(options.managed_repository.read_text())
    from urllib.parse import urlsplit
    if managed_configuration.get("preview") and not options.development:parser.error("Preview tool repositories require --development")
    from wixal.managed_tools import CatalogueClient
    CatalogueClient(Path(tempfile.gettempdir()),managed_configuration)
    managed_root=Path(managed_configuration["trustedRoot"]).read_bytes()
    from tuf.api.metadata import Metadata,Root
    if not isinstance(Metadata.from_bytes(managed_root).signed,Root):parser.error("Trusted bootstrap must be TUF root metadata")
sys.path.insert(0,str(native/"engine"))
from wixal import VERSION
if options.alpha and options.development:parser.error("Choose --alpha or --development")
if options.alpha and "-alpha." not in VERSION:parser.error("--alpha requires an alpha engine version")
if not options.executable_name.isalnum():parser.error("Use an alphanumeric executable name")
if (options.preview_data or options.preview_endpoint) and not options.development:parser.error("Preview configuration requires --development")
if options.preview_endpoint and not options.preview_endpoint.startswith(("http://127.0.0.1:","http://localhost:")):parser.error("Preview endpoint must use loopback")
if options.output:app=options.output.expanduser().resolve()
if not (options.development or options.alpha):
    if not options.identity or not options.identity.startswith("Developer ID Application:") or not options.notary_profile:
        parser.error("Notarised distribution requires --identity and --notary-profile. Choose --alpha for an explicitly non-notarised alpha, or --development for local validation.")
    identities=subprocess.check_output(["security","find-identity","-v","-p","codesigning"],text=True)
    if options.identity not in identities:parser.error("The requested Developer ID identity is not available in this Mac's Keychain")
elif options.identity or options.notary_profile:parser.error("Ad-hoc and Developer ID signing options cannot be combined")
destination=app
destination.parent.mkdir(parents=True,exist_ok=True)
staging=Path(tempfile.mkdtemp(prefix="wixal-native-package-",dir=destination.parent))
app=staging/app.name

source_paths=sorted(list((native/"Sources").rglob("*.swift"))+list((native/"ActivitySources").rglob("*.swift"))+list((native/"MarkdownSources").rglob("*.swift"))+list((native/"engine").rglob("*.py"))+list((native/"engine/wixal/resources").rglob("*.json"))+list((native/"engine/wixal/resources").rglob("*.md"))+[native/"Package.swift",native/"Package.resolved",native/"requirements-build.txt",Path(__file__).resolve()])
source_hashes={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}

def run(*args):
    subprocess.run([str(a) for a in args], cwd=native, check=True)

run("swift", "build", "--build-system", "native", "-c", "release")
bin_path = Path(subprocess.check_output(["swift", "build", "--build-system", "native", "-c", "release", "--show-bin-path"], cwd=native, text=True).strip())
signing=["--codesign-identity",options.identity] if options.identity else []
run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", *signing, "--name", "wixal-engine", "--paths", native/"engine",
    "--hidden-import", "wixal.tool_qualification", "--collect-all", "tuf", "--collect-all", "securesystemslib", "--collect-all", "cryptography", "--collect-all", "urllib3",
    "--add-data", str(native/"engine/wixal/resources")+":wixal/resources", native/"engine/engine_main.py")
if app.exists():
    shutil.rmtree(app)
resources=app/"Contents/Resources";macos=app/"Contents/MacOS"
resources.mkdir(parents=True);macos.mkdir()
shutil.copy2(bin_path/"WixalNative",macos/options.executable_name)
for bundle in bin_path.glob("*.bundle"):
    shutil.copytree(bundle,resources/bundle.name,symlinks=True)
shutil.copytree(native/"dist/wixal-engine",resources/"engine",symlinks=True)
if managed_configuration:
    tool_resources=resources/"engine/_internal/wixal/resources"
    tool_resources.mkdir(parents=True,exist_ok=True)
    configuration=dict(managed_configuration,trustedRoot="managed-root.json")
    (tool_resources/"managed-repository.json").write_text(json.dumps(configuration,indent=2))
    (tool_resources/"managed-root.json").write_bytes(managed_root)
    (resources/"TOOL_TRUST_MANIFEST.json").write_text(json.dumps(dict(configurationSha256=hashlib.sha256((tool_resources/"managed-repository.json").read_bytes()).hexdigest(),bootstrapRootSha256=hashlib.sha256(managed_root).hexdigest(),channel=configuration["channel"],preview=configuration["preview"]),indent=2))
shutil.copytree(root/"runtime/ollama",resources/"ollama",symlinks=True)
shutil.copytree(root/"assets/icon-variants",resources/"icon-variants",symlinks=True)
shutil.copytree(root/"assets/audio",resources/"audio",symlinks=True)
if (root/"assets/Wixal.icns").exists():shutil.copy2(root/"assets/Wixal.icns",resources/"Wixal.icns")
with (app/"Contents/Info.plist").open("wb") as file:
    plistlib.dump(dict(CFBundleExecutable=options.executable_name,CFBundleIdentifier=options.bundle_identifier,CFBundleName=options.display_name,
        CFBundleDisplayName=options.display_name,CFBundlePackageType="APPL",CFBundleShortVersionString=VERSION.split("-")[0],CFBundleVersion="1",WixalReleaseVersion=VERSION,WixalReleaseChannel="alpha" if options.alpha else "development" if options.development else "release",
        CFBundleIconFile="Wixal.icns",LSMinimumSystemVersion="14.0",LSApplicationCategoryType="public.app-category.developer-tools",
        NSHighResolutionCapable=True,NSAppTransportSecurity=dict(NSAllowsArbitraryLoads=True),
        NSHumanReadableCopyright="Wixal. Includes SwiftTerm and Ollama; see bundled notices."),file)
if options.preview_data or options.preview_endpoint:
    info_path=app/"Contents/Info.plist"
    info=plistlib.loads(info_path.read_bytes())
    if options.preview_data:info["WixalPreviewData"]=str(options.preview_data.expanduser().resolve())
    if options.preview_endpoint:info["WixalPreviewEndpoint"]=options.preview_endpoint
    info_path.write_bytes(plistlib.dumps(info))
changed=[str(path.relative_to(root)) for path in source_paths if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hashes[str(path.relative_to(root))]]
if changed:raise RuntimeError("Source changed during packaging; rerun after edits finish: "+", ".join(changed))
(resources/"SOURCE_MANIFEST.json").write_text(json.dumps(source_hashes,indent=2))
notices = "Wixal Native uses SwiftTerm (MIT), Swift Markdown (Apache 2.0 with Swift runtime exception), swift-cmark (CommonMark/GFM parser licenses), Ollama (MIT) and a bundled Python runtime (PSF).\nIncludes an adapted Hermes duration parser (MIT, Nous Research). See Hermes-NOTICE.md and Hermes-LICENSE.\n"
(resources/"THIRD_PARTY_NOTICES.txt").write_text(notices)
for name, source in (("Hermes-LICENSE",native/"third_party/hermes/LICENSE"),("Hermes-NOTICE.md",native/"third_party/hermes/NOTICE.md"),("SwiftTerm-LICENSE",native/".build/checkouts/SwiftTerm/LICENSE"),("Wixal-LICENSE",root/"LICENSE")):
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
# Include dependency licence texts even when a freezing hook omits dist-info.
for distribution in importlib.metadata.distributions():
    name=distribution.metadata.get("Name", "dependency")
    for entry in distribution.files or []:
        relative=str(entry).partition(".dist-info/")[2]
        if not relative or ".." in Path(relative).parts:continue
        if not any(part.upper().startswith(("LICENSE", "COPYING", "NOTICE")) for part in Path(relative).parts):continue
        source=Path(distribution.locate_file(entry))
        if source.is_file():
            target=resources/"python-licenses"/name/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
sys.path.insert(0,str(native/"engine"))
from wixal.runtime import Runtime
# Verify the vendor payload before any signing changes its bytes.
with tempfile.TemporaryDirectory() as directory:
    Runtime(directory,resources/"ollama").verify()
if options.development or options.alpha:
    (resources/"BUILD_MODE.txt").write_text("Public native alpha. Ad-hoc signed; not Developer ID signed or notarised.\n" if options.alpha else "Local development preview. Not Developer ID signed or notarised.\n")
    (resources/"RELEASE.json").write_text(json.dumps(dict(version=VERSION,channel="alpha" if options.alpha else "development",architecture="arm64",minimumMacOS="14.0",developerIDSigned=False,notarised=False),indent=2))
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
if not (options.development or options.alpha):
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
