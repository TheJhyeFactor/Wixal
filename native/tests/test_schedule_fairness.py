"""Due routine fairness with real files and controller-owned schedule claims."""
import unittest
from unittest.mock import patch
import test_agents_runtime as fixtures
from wixal.scheduling import run_due

class ScheduleFairnessTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.AgentRuntimeTests.asyncSetUp
    asyncTearDown=fixtures.AgentRuntimeTests.asyncTearDown
    scripted=fixtures.AgentRuntimeTests.scripted

    async def routine(self,name,seconds,scheduled_for,policy='latest'):
        row=await self.service.dispatch('agent-schedule-save',dict(name=name,agentID='coder',prompt='Write '+name+'.txt containing '+name+' once. Do not change other files.',intervalSeconds=seconds,missedRunPolicy=policy,authority=dict(writePaths=[name+'.txt']),successCriteria=[dict(kind='file_contains',path=name+'.txt',value=name)]))
        row['nextRun']=scheduled_for;self.service.store.save();return row

    async def execute(self,name,stamp):
        context,_=self.scripted([('write_file',dict(path=name+'.txt',content=name))],name+' saved; explicit file check verifies it.')
        with patch('wixal.scheduling.now',return_value=stamp),context:
            self.assertTrue(await run_due(self.service,True))

    async def test_older_due_routine_runs_before_recent_short_interval(self):
        stamp=4_000_000
        recent=await self.routine('recent',60,stamp-10_000)
        older=await self.routine('older',7200,stamp-3_600_000)
        await self.execute('older',stamp)
        self.assertTrue((self.root/'older.txt').exists(),'The older overdue routine must run its authorised action first')
        self.assertEqual((self.root/'older.txt').read_text(),'older')
        self.assertEqual(older['lastRun']['status'],'completed')
        self.assertEqual(older['lastRun']['scheduledFor'],stamp-3_600_000)
        self.assertNotIn('lastRun',recent)
        await self.execute('recent',stamp+60_000)
        self.assertEqual((self.root/'recent.txt').read_text(),'recent')
        self.assertEqual(recent['lastRun']['status'],'completed')
        self.assertEqual(len(self.service.store.data['tasks']),2)
        with patch('wixal.scheduling.now',return_value=stamp+60_000):
            self.assertFalse(await run_due(self.service,True))

    async def test_skipped_interval_cannot_starve_older_due_job_on_next_launch(self):
        short=await self.routine('short',60,1000,'skip')
        older=await self.routine('older',7200,1000)
        with patch('wixal.scheduling.now',return_value=181_001):
            self.assertTrue(await run_due(self.service,True))
        self.assertEqual(short['lastRun']['status'],'skipped')
        self.assertEqual(short['lastRun']['missed'],3)
        self.assertEqual(self.service.store.data['tasks'],[])
        # At the following LaunchAgent interval the short routine is due again.
        # The already-waiting older job must get the claim rather than starvation.
        await self.execute('older',241_001)
        self.assertTrue((self.root/'older.txt').exists(),'The waiting job must run before another short-interval claim')
        self.assertEqual((self.root/'older.txt').read_text(),'older')
        self.assertFalse((self.root/'short.txt').exists())
        self.assertEqual(short['lastRun']['status'],'skipped')
        self.assertEqual(older['lastRun']['status'],'completed')
        self.assertEqual(len(self.service.store.data['tasks']),1)
