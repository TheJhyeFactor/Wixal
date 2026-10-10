"""Cold-start behavior for long workspaces, SQLite lock contention and catch-up."""
import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from wixal.scheduling import due
from wixal.service import ipc_socket_path
from wixal.storage import Store


class StartupRecoveryTests(unittest.TestCase):
    def test_restart_marks_parent_workflows_and_stages_interrupted_without_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(temporary)
            completed=dict(id='done',status='completed',taskId='retained-task',result='Already committed')
            store.data['workflowRuns']=[dict(id='flow',status='running',stages=[completed,dict(id='pending',status='running',taskId='branch-task',childId='child')]),dict(id='review',status='waiting_review',stages=[])]
            store.close();restored=Store(temporary)
            try:
                self.assertTrue(all(r['status']=='interrupted' for r in restored.data['workflowRuns']))
                stages=restored.data['workflowRuns'][0]['stages']
                self.assertEqual(stages[0],completed)
                self.assertEqual(stages[1]['status'],'interrupted');self.assertEqual(stages[1]['childId'],'child')
            finally:restored.close()

    def test_failed_final_save_releases_database_and_owner_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(temporary)
            store.data['globalMemory']='last committed value';store.save()
            store.db.execute("CREATE TRIGGER reject_state_update BEFORE UPDATE ON state BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END")
            store.db.commit()
            store.data['globalMemory']='uncommitted value'
            with self.assertRaisesRegex(sqlite3.IntegrityError,'simulated write failure'):store.close()
            self.assertTrue(store.owner_lock.closed)
            with self.assertRaises(sqlite3.ProgrammingError):store.db.execute('SELECT 1')
            repair=sqlite3.connect(Path(temporary)/'workspace.sqlite3')
            repair.execute('DROP TRIGGER reject_state_update');repair.commit();repair.close()
            restored=Store(temporary)
            try:self.assertEqual(restored.data['globalMemory'],'last committed value')
            finally:restored.close()

    def test_startup_reports_exact_database_before_open_and_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            reports=[]
            store=Store(Path(temporary)/"state", startup=reports.append)
            try:
                phases=[r["phase"] for r in reports]
                self.assertLess(phases.index("SQLite file open"), phases.index("SQLite journal setup"))
                self.assertEqual(phases[-1],"workspace ready")
                self.assertTrue(all(r["database"]==str((Path(temporary)/"state/workspace.sqlite3").absolute()) for r in reports))
            finally:store.close()

    def test_long_workspace_maps_to_private_short_socket_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / ("workspace-" + "x" * 75) / ("nested-" + "y" * 35)
            data.mkdir(parents=True)
            endpoint = ipc_socket_path(data)
            self.assertLess(len(str(endpoint).encode()), 104)
            self.assertEqual(endpoint.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(endpoint.parent.stat().st_uid, __import__('os').getuid())

    def test_sqlite_lock_wait_is_bounded_and_retry_reopens_persisted_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "state"
            data.mkdir()
            path = data / "workspace.sqlite3"
            blocker = sqlite3.connect(path, isolation_level=None)
            blocker.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            blocker.execute("INSERT INTO state VALUES(1, '{}')")
            blocker.execute("BEGIN EXCLUSIVE")
            started = time.monotonic()
            with self.assertRaises(sqlite3.OperationalError):
                Store(data)
            elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, 2.5)
            # Some SQLite versions wait twice while changing journal mode;
            # allow both bounded waits plus shared-runner scheduling overhead.
            self.assertLess(elapsed, 8.0)
            blocker.execute("ROLLBACK")
            blocker.close()
            restored = Store(data)
            self.assertEqual(restored.db.execute("PRAGMA busy_timeout").fetchone()[0], 3000)
            self.assertIn("schedules", restored.data)
            restored.close()

    def test_catch_up_calculation_after_sleep_is_latest_interval_or_skip(self):
        now_ms = 4_000_000
        schedule = dict(enabled=True, intervalSeconds=60, nextRun=now_ms - 10 * 60_000)
        latest = due(schedule, now_ms)
        self.assertEqual(latest["missed"], 10)
        self.assertFalse(latest["skip"])
        self.assertEqual(latest["nextRun"], now_ms + 60_000)
        skipped = due({**schedule, "missedRunPolicy": "skip"}, now_ms)
        self.assertTrue(skipped["skip"])


class CatchupPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_sign_in_does_not_block_workspace_handshake(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from wixal.integrations import NativeIntegrations, ACCOUNT_RESTORE_TIMEOUT_SECONDS
        self.assertLess(ACCOUNT_RESTORE_TIMEOUT_SECONDS, 30)
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(Path(temporary)/"state")
            store.data["restoreAccountOnLaunch"]=True
            cancelled=asyncio.Event()
            async def unavailable(*args):
                try: await asyncio.Event().wait()
                finally: cancelled.set()
            integration=NativeIntegrations.__new__(NativeIntegrations)
            integration.service=SimpleNamespace(store=store,emit=lambda *args:None)
            integration.restored_on_launch=False
            integration.account=SimpleNamespace(ready=True,message="",dispatch=unavailable)
            integration.refresh=lambda:None
            with patch("wixal.integrations.ACCOUNT_RESTORE_TIMEOUT_SECONDS",0.01):
                await asyncio.wait_for(integration.restore_if_needed(),1)
            self.assertTrue(cancelled.is_set())
            self.assertFalse(integration.account.ready)
            self.assertIn("guest preferences are active",integration.account.message)
            self.assertTrue(store.data["restoreAccountOnLaunch"])
            store.close()

    async def test_claim_survives_restart_after_failed_run_and_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(Path(temporary) / "state")
            store.data["schedules"] = [dict(id="schedule-1", owner="guest", enabled=True,
                intervalSeconds=60, nextRun=1, prompt="Run my saved task", missedRunPolicy="latest")]
            store.save()
            store.close()

            restored = Store(Path(temporary) / "state")
            schedule = restored.data["schedules"][0]
            claim = due(schedule, int(time.time() * 1000))
            schedule.update(nextRun=claim["nextRun"], lastRun={**claim, "status": "running"})
            restored.save()
            restored.close()

            after_restart = Store(Path(temporary) / "state")
            saved = after_restart.data["schedules"][0]
            self.assertEqual(saved["lastRun"]["status"], "interrupted")
            self.assertIsNone(due(saved, int(time.time() * 1000)))
            after_restart.close()


if __name__ == "__main__":
    unittest.main()
