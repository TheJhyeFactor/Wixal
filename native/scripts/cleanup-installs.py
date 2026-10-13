"""Keep one verified Wixal installation; move obsolete app bundles to Trash.

Defaults to application folders. --include-build-copies adds repository build
folders and Desktop/Downloads; --search-root adds a reviewed location. --apply
requires the canonical app to pass strict signature verification first.
Workspace data, models, ZIP archives and reports are untouched.
"""
import argparse
import json
import os
import plistlib
import shutil
import subprocess
import time
from pathlib import Path


SKIP_DIRECTORIES = {'.git', '.Trash', 'node_modules', '.venv', '.build', 'local-runtime', '__pycache__'}


def inventory(roots, keep):
    keep = keep.expanduser().resolve()
    candidates = {}
    for root in roots:
        root = root.expanduser()
        if '.Trash' in root.parts or not root.is_dir() or root.is_symlink():
            continue
        for directory, children, _ in os.walk(root, followlinks=False):
            bundles = [name for name in children if name.lower().endswith(('.app', '.app.previous'))]
            children[:] = [name for name in children if name not in bundles and name not in SKIP_DIRECTORIES and not (Path(directory) / name).is_symlink()]
            for name in bundles:
                app = Path(directory) / name
                if app.is_symlink() or app.resolve() == keep:
                    continue
                try:
                    metadata = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
                except (OSError, ValueError):
                    continue
                if not isinstance(metadata, dict):
                    continue
                identifier = str(metadata.get('CFBundleIdentifier', ''))
                if not identifier.startswith(('app.wixal.', 'com.wixal.')):
                    continue
                candidates[str(app.resolve())] = dict(path=str(app.resolve()), bundleIdentifier=identifier,
                    version=metadata.get('WixalReleaseVersion', metadata.get('CFBundleShortVersionString')))
    return [candidates[key] for key in sorted(candidates)]


def running_candidates(candidates, processes):
    return [row['path'] for row in candidates if any(command.strip().startswith(row['path'] + '/') for command in processes)]


def unregister(app, registrar):
    if not registrar.exists():
        return 'unavailable'
    result = subprocess.run([str(registrar), '-u', str(app)], capture_output=True, text=True)
    # LaunchServices does not recognise renamed .app.previous bundles; -10814
    # means no application registration exists, so retirement can still proceed.
    if result.returncode and '-10814' in result.stderr:
        return 'not_registered'
    result.check_returncode()
    return 'unregistered'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--keep', type=Path, default=Path('/Applications/Wixal.app'))
    parser.add_argument('--include-build-copies', action='store_true')
    parser.add_argument('--search-root', type=Path, action='append', default=[])
    parser.add_argument('--report', type=Path, default=Path(__file__).resolve().parents[2] / 'artifacts/native/install-cleanup.json')
    options = parser.parse_args()
    keep = options.keep.expanduser().resolve()
    info = plistlib.loads((keep / 'Contents/Info.plist').read_bytes())
    assert info.get('CFBundleIdentifier') == 'app.wixal.native.preview', 'Keep the canonical native Wixal app'
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(keep)], check=True)
    roots = [Path('/Applications'), Path.home() / 'Applications']
    if options.include_build_copies:
        root = Path(__file__).resolve().parents[2]
        roots += [root / 'release', root / 'artifacts', root / 'output', Path.home() / 'Desktop', Path.home() / 'Downloads']
    roots += options.search_root
    candidates = inventory(roots, keep)
    report = dict(status='inventory', canonical=str(keep), version=info.get('WixalReleaseVersion'),
        searchRoots=[str(path.expanduser().resolve()) for path in roots], obsolete=candidates, moved=[])
    if options.apply:
        processes = subprocess.check_output(['ps', '-axo', 'comm='], text=True).splitlines()
        running = running_candidates(candidates, processes)
        if running:
            raise SystemExit('Quit these obsolete applications before cleanup: ' + ', '.join(running))
        if candidates:
            trash = Path.home() / '.Trash' / ('Wixal retired installs ' + time.strftime('%Y%m%d-%H%M%S'))
            trash.mkdir(parents=True, exist_ok=False)
            registrar = Path('/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister')
            for index, row in enumerate(candidates):
                app = Path(row['path']); destination = trash / app.name
                if destination.exists():
                    destination = trash / (str(index + 1) + ' ' + app.name)
                unregistration = unregister(app, registrar)
                shutil.move(str(app), str(destination))
                report['moved'].append(dict(source=str(app), trash=str(destination), unregistration=unregistration))
                options.report.parent.mkdir(parents=True, exist_ok=True)
                options.report.write_text(json.dumps(report, indent=2) + '\n')
        registrar = Path('/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister')
        if registrar.exists():
            subprocess.run([str(registrar), '-f', str(keep)], check=True, capture_output=True)
            report['canonicalRegistered'] = True
        report['status'] = 'passed'
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], canonical=report['canonical'], obsolete=len(candidates), moved=len(report['moved'])), indent=2))


if __name__ == '__main__':
    main()
