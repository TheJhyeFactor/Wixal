import importlib.util
import plistlib
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location('wixal_cleanup', Path(__file__).resolve().parents[1] / 'scripts/cleanup-installs.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class InstallCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.keep = self.bundle('Applications/Wixal.app', 'app.wixal.native.preview')

    def bundle(self, path, identifier):
        app = self.root / path
        (app / 'Contents').mkdir(parents=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier=identifier, WixalReleaseVersion='0.7.10-alpha.7')))
        return app

    def test_cyber_and_previous_bundles_are_found_recursively(self):
        cyber = self.bundle('release/native/Wixal Cyber Final QA.app', 'app.wixal.cyber.finalqa')
        previous = self.bundle('release/native/Wixal.app.previous', 'app.wixal.native.preview')
        rows = cleanup.inventory([self.root], self.keep)
        self.assertEqual({row['path'] for row in rows}, {str(cyber), str(previous)})

    def test_canonical_unrelated_invalid_and_symlink_bundles_are_preserved(self):
        self.bundle('Applications/Other.app', 'com.example.other')
        broken = self.root / 'release/Wixal broken.app/Contents'
        broken.mkdir(parents=True); (broken / 'Info.plist').write_text('invalid')
        invalid = self.root / 'release/Wixal invalid metadata.app/Contents'
        invalid.mkdir(parents=True); (invalid / 'Info.plist').write_bytes(plistlib.dumps(['not app metadata']))
        (self.root / 'Wixal alias.app').symlink_to(self.keep, target_is_directory=True)
        self.assertEqual(cleanup.inventory([self.root], self.keep), [])

    def test_overlapping_roots_do_not_duplicate_candidates(self):
        app = self.bundle('release/Wixal QA.app', 'app.wixal.cyber.qa')
        rows = cleanup.inventory([self.root, self.root / 'release'], self.keep)
        self.assertEqual([row['path'] for row in rows], [str(app)])

    def test_trash_models_and_archives_are_untouched(self):
        self.bundle('.Trash/Wixal retired.app', 'app.wixal.cyber.qa')
        self.bundle('local-runtime/Wixal model fixture.app', 'app.wixal.cyber.qa')
        archive = self.root / 'Wixal.zip'; archive.write_bytes(b'rollback')
        self.assertEqual(cleanup.inventory([self.root, self.root / '.Trash'], self.keep), [])
        self.assertEqual(archive.read_bytes(), b'rollback')

    def test_running_bundle_prefix_is_exact(self):
        rows = [dict(path='/release/Wixal QA.app'), dict(path='/release/Wixal QA.app.previous')]
        processes = ['/release/Wixal QA.app/Contents/MacOS/Wixal', '/release/Wixal QA.app.other/Contents/MacOS/Wixal']
        self.assertEqual(cleanup.running_candidates(rows, processes), ['/release/Wixal QA.app'])

    def test_renamed_previous_bundle_without_registration_can_retire(self):
        registrar = self.root / 'lsregister'; registrar.touch()
        result = subprocess.CompletedProcess([], 1, stdout='', stderr='failed to scan: -10814')
        with patch.object(cleanup.subprocess, 'run', return_value=result):
            self.assertEqual(cleanup.unregister(self.root / 'Wixal.app.previous', registrar), 'not_registered')

    def test_unexpected_registration_error_stops_retirement(self):
        registrar = self.root / 'lsregister'; registrar.touch()
        result = subprocess.CompletedProcess([], 1, stdout='', stderr='permission denied')
        with patch.object(cleanup.subprocess, 'run', return_value=result):
            with self.assertRaises(subprocess.CalledProcessError):
                cleanup.unregister(self.root / 'Wixal QA.app', registrar)
