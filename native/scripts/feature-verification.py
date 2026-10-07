"""Run packaged feature acceptance against one unchanged, installed local build."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'artifacts/native'
HELPER = ROOT / 'release/native/Wixal Native.app/Contents/Resources/engine/wixal-engine'
INSTALLED = Path.home() / 'Applications/Wixal Native.app/Contents/Resources/engine/wixal-engine'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen3:4b', help='Installed tool-capable model for broader acceptance')
    args = parser.parse_args()
    if subprocess.run(['pgrep', '-x', 'WixalNative'], capture_output=True).returncode == 0:
        parser.error('Quit Wixal Native before testing actual closed-app scheduling')
    expected = digest(HELPER)
    if digest(INSTALLED) != expected:
        parser.error('Install the current development package before running acceptance')
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / 'final-feature-verification.json'
    if path.exists():
        path.rename(ART / ('feature-verification-previous-' + str(time.time_ns()) + '.json'))
    report = dict(status='running', helperSHA256=expected, started=time.time(), checks=[])

    def save():
        path.write_text(json.dumps(report, indent=2))

    checks = [
        ('semantic-memory', 'memory-quality-acceptance.py', ['--packaged']),
        ('local-model-memory-review', 'memory-review-acceptance.py', ['--packaged']),
        ('remote-mcp-background-scheduling', 'feature-acceptance.py', []),
        ('encrypted-folder-sync', 'sync-acceptance.py', []),
        ('broader-small-model', 'real-acceptance.py', ['--model', args.model]),
        ('packaged-workflows', 'smoke.py', []),
    ]
    report['checks']=[dict(name=name,status='pending',log=name+'-final-run.log') for name,_,_ in checks]
    save()
    try:
        for index,(name, script, arguments) in enumerate(checks):
            if digest(HELPER) != expected or digest(INSTALLED) != expected:
                raise RuntimeError('The installed/package helper changed during acceptance')
            print('START', name, flush=True)
            log = ART / (name + '-final-run.log')
            report['checks'][index]['status']='running';save()
            with log.open('w') as output:
                result=subprocess.run([sys.executable, str(ROOT / 'native/scripts' / script), *arguments],
                                      stdout=output, stderr=subprocess.STDOUT)
            if digest(HELPER) != expected or digest(INSTALLED) != expected:
                raise RuntimeError('The installed/package helper changed during acceptance')
            report['checks'][index].update(status='passed' if result.returncode==0 else 'failed',exitCode=result.returncode)
            save()
            print('PASS' if result.returncode==0 else 'FAIL', name, flush=True)
        report['status'] = 'passed' if all(c['status']=='passed' for c in report['checks']) else 'failed'
    except BaseException as error:
        report.update(status='failed', error=str(error))
        for check in report['checks']:
            if check['status'] in ('pending','running'):check.update(status='blocked',error=str(error))
        raise
    finally:
        report['finished'] = time.time()
        save()
    if report['status']!='passed':raise SystemExit(1)


if __name__ == '__main__':
    main()
