import asyncio
import json
import unittest
from unittest.mock import AsyncMock,patch
from wixal.github_reporting import GitHubReporting,REPOSITORY

class GitHubReportingTests(unittest.IsolatedAsyncioTestCase):
    def client(self):return GitHubReporting('1234567890abcdef')
    async def authorize(self,client):
        client.call=AsyncMock(side_effect=[dict(device_code='private-device-code',user_code='ABCD-EFGH',verification_uri='https://github.com/login/device',interval=5,expires_in=900),dict(access_token='private-token',scope='public_repo'),dict(login='Contributor')])
        result=await client.start(dict(authorize=True));self.assertNotIn('private-device-code',json.dumps(result))
        client.flow['nextPoll']=0
        result=await client.poll();self.assertTrue(result['signedIn']);self.assertNotIn('private-token',json.dumps(result))
    async def test_registration_and_authorization_are_required(self):
        with self.assertRaisesRegex(ValueError,'registered'):await GitHubReporting('').start(dict(authorize=True))
        with self.assertRaisesRegex(ValueError,'Confirm'):await self.client().start({})
    async def test_pending_backoff_expiration_and_cancellation(self):
        c=self.client();c.call=AsyncMock(side_effect=[dict(device_code='code',user_code='USER',verification_uri='https://github.com/login/device',interval=5,expires_in=900),dict(error='authorization_pending'),dict(error='slow_down')])
        await c.start(dict(authorize=True));await c.poll();self.assertEqual(c.call.await_count,1)
        c.flow['nextPoll']=0;self.assertEqual((await c.poll())['status'],'pending')
        c.flow['nextPoll']=0;self.assertEqual((await c.poll())['interval'],10)
        c.flow['deadline']=0;self.assertEqual((await c.poll())['status'],'expired')
        self.assertEqual(c.cancel()['status'],'cancelled')
    async def test_unsafe_verification_endpoint_and_wrong_scope_rejected(self):
        c=self.client();c.call=AsyncMock(return_value=dict(verification_uri='https://other.example/device'))
        with self.assertRaisesRegex(ValueError,'verification'):await c.start(dict(authorize=True))
        c.flow=dict(code='code',deadline=10**12,nextPoll=0,interval=5);c.call=AsyncMock(return_value=dict(access_token='token',scope='read:user'))
        with self.assertRaisesRegex(ValueError,'permission'):await c.poll()
        self.assertFalse(c.status()['signedIn'])
    async def test_exact_review_consent_fixed_destination_and_single_submission(self):
        c=self.client();await self.authorize(c)
        draft=dict(id='draft',digest='reviewed-digest',title='Observed bug',body='Sanitized evidence')
        for params in ({},dict(publish=True,reviewedDigest='changed')):
            with self.assertRaisesRegex(ValueError,'Review'):await c.submit(draft,params)
        c.call=AsyncMock(return_value=dict(number=42,html_url='https://github.com/'+REPOSITORY+'/issues/42'))
        result=await c.submit(draft,dict(publish=True,reviewedDigest=draft['digest']))
        self.assertEqual(result['status'],'published')
        self.assertEqual(c.call.call_args.args,('https://api.github.com/repos/'+REPOSITORY+'/issues',dict(title=draft['title'],body=draft['body']),'private-token'))
        with self.assertRaisesRegex(ValueError,'already'):await c.submit(draft,dict(publish=True,reviewedDigest=draft['digest']))
        c.sign_out();self.assertFalse(c.status()['signedIn']);self.assertIsNone(c.token)
    async def test_unknown_post_outcome_is_never_automatically_retried(self):
        c=self.client();await self.authorize(c);c.call=AsyncMock(side_effect=ValueError('Connection lost'))
        draft=dict(digest='digest',title='Bug',body='Evidence')
        with self.assertRaises(ValueError):await c.submit(draft,dict(publish=True,reviewedDigest='digest'))
        self.assertEqual(draft['submission']['status'],'unknown')
        with self.assertRaises(ValueError):await c.submit(draft,dict(publish=True,reviewedDigest='digest'))
        self.assertEqual(c.call.await_count,1)
    async def test_concurrent_submit_has_one_effect(self):
        c=self.client();await self.authorize(c)
        async def submit(*args):await asyncio.sleep(.02);return dict(number=1,html_url='https://github.com/'+REPOSITORY+'/issues/1')
        c.call=AsyncMock(side_effect=submit);draft=dict(digest='digest',title='Bug',body='Evidence')
        result=await asyncio.gather(*(c.submit(draft,dict(publish=True,reviewedDigest='digest')) for _ in range(2)),return_exceptions=True)
        self.assertEqual(sum(isinstance(r,ValueError) for r in result),1);self.assertEqual(c.call.await_count,1)
