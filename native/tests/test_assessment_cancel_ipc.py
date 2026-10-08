"""Exercise the same IPC cancellation route the desktop Stop button uses."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from wixal.requests import Requests
from wixal.service import Service


class AssessmentCancelIPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_cancels_inflight_http_and_returns_persisted_partial_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'project'
            root.mkdir()
            requests_seen = 0
            second_request = asyncio.Event()
            emitted = asyncio.Queue()

            async def site(reader, writer):
                nonlocal requests_seen
                try:
                    request = await reader.readuntil(b'\r\n\r\n')
                    requests_seen += 1
                    if requests_seen >= 2:
                        second_request.set()
                    # Hold each response open long enough to cancel inside an
                    # active socket read, rather than racing a fast fixture.
                    await asyncio.sleep(1.5)
                    path = request.split(b' ', 2)[1].decode()
                    page = int(path.rsplit('/', 1)[-1] or 0)
                    next_link = f'<a href="/{page + 1}">next</a>' if page < 11 else ''
                    body = f'<html>{next_link}</html>'.encode()
                    writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                    await writer.drain()
                except (asyncio.CancelledError, ConnectionError, asyncio.IncompleteReadError):
                    pass
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except (ConnectionError, asyncio.CancelledError):
                        pass

            server = await asyncio.start_server(site, '127.0.0.1', 0)
            url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/"

            def emit(event, data):
                emitted.put_nowait((event, data))

            service = Service(Path(temporary) / 'state', Path(temporary) / 'runtime', emit)
            ipc = Requests(service, emit)
            owner = object()
            unrelated = None

            async def event_where(predicate, timeout=8):
                async with asyncio.timeout(timeout):
                    while True:
                        event = await emitted.get()
                        if predicate(*event):
                            return event

            try:
                await service.dispatch('project-add', {'root': str(root)})
                run_id = 'visible-stop-assessment-run'
                ipc.start(owner, {'id': run_id, 'method': 'assessment-run', 'params': {
                    'name': 'website_assess',
                    'arguments': {'url': url, 'max_pages': 12, 'report_prefix': 'must-not-save'},
                }})
                review_event = await event_where(lambda event, data: event == 'review')
                ipc.start(owner, {'id': 'approve-assessment', 'method': 'respond', 'params': {
                    'id': review_event[1]['id'], 'value': True,
                }})
                await second_request.wait()
                # Simulate another engine action replacing the general-purpose
                # active-operation alias while this request remains live.
                # Stop must target the dedicated assessment handle and leave
                # unrelated work alone.
                unrelated = asyncio.create_task(asyncio.sleep(60))
                service.active = unrelated
                # This goes through Requests.start -> Service.dispatch -> the
                # same workspace action called by EngineClient's Stop button.
                ipc.start(owner, {'id': 'visible-stop-click', 'method': 'assessment-cancel', 'params': {}})

                run_response = await event_where(lambda event, data: event == 'response' and data.get('id') == run_id)
                result = run_response[1]['result']
                self.assertTrue(result['partial'])
                self.assertEqual(result['status'], 'cancelled')
                self.assertTrue(result['cases'])
                self.assertLess(len(result['cases']), 12)
                self.assertEqual(service.store.data['assessmentResults'][-1]['status'], 'cancelled')
                self.assertEqual(service.store.data['assessmentResults'][-1]['result'], result)
                self.assertFalse(list(root.glob('must-not-save.*')))
                self.assertFalse(unrelated.done(), 'Assessment Stop must not cancel unrelated engine work')
                seen_at_stop = requests_seen
                await asyncio.sleep(1.7)
                self.assertEqual(requests_seen, seen_at_stop, 'Stop must close the in-flight request and prevent later pages')
                cancel_response = await event_where(lambda event, data: event == 'response' and data.get('id') == 'visible-stop-click')
                self.assertTrue(cancel_response[1]['result'])
            finally:
                await ipc.close(owner)
                if unrelated and not unrelated.done():
                    unrelated.cancel()
                    await asyncio.gather(unrelated, return_exceptions=True)
                await service.close()
                server.close()
                await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
