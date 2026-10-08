"""Thinking remains separate from visible answers and future model context."""
import asyncio
import json
import tempfile
import unittest
from wixal.agent import stream_chat, Agent
from wixal.context_policy import thinking_options, thinking_reserve
from wixal.storage import Store

class ThinkingStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_thinking_and_answer_stream_separately_and_persist(self):
        events=[]
        async def serve(reader,writer):
            await reader.readuntil(b'\r\n\r\n')
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\nConnection: close\r\n\r\n')
            for row in [dict(message=dict(thinking='Inspect evidence. '),done=False),dict(message=dict(thinking='Check findings.',content='Visible '),done=False),dict(message=dict(content='answer.'),done=True,eval_count=4)]:
                writer.write((json.dumps(row)+'\n').encode());await writer.drain()
            writer.close();await writer.wait_closed()
        server=await asyncio.start_server(serve,'127.0.0.1',0)
        try:
            result=await stream_chat('http://127.0.0.1:'+str(server.sockets[0].getsockname()[1]),{},lambda kind,data:events.append((kind,data['text'])))
        finally:server.close();await server.wait_closed()
        self.assertEqual(result['content'],'Visible answer.')
        self.assertEqual(result['thinking'],'Inspect evidence. Check findings.')
        self.assertEqual(''.join(v for k,v in events if k=='thinking'),result['thinking'])
        self.assertEqual(''.join(v for k,v in events if k=='token'),result['content'])
        with tempfile.TemporaryDirectory() as path:
            store=Store(path);session=store.new_session();session['messages']=[dict(role='user',content='Answer'),result];store.save();store.close()
            reopened=Store(path)
            self.assertEqual(reopened.session()['messages'][-1]['thinking'],result['thinking'])
            context=Agent(reopened,None,None,lambda *_:None).context(reopened.session())
            self.assertNotIn('Inspect evidence.',json.dumps(context))
            reopened.close()

    async def test_thinking_policy_keeps_answer_space_and_plain_models_unchanged(self):
        self.assertEqual(thinking_options(dict(capabilities=['completion'])),{})
        self.assertEqual(thinking_options(dict(capabilities=['thinking'],thinking=dict(values=[True,False]))),dict(think=True))
        metadata=dict(capabilities=['thinking'],thinking=dict(values=['low','medium','high']))
        self.assertEqual(thinking_options(metadata),dict(think='low'))
        self.assertGreaterEqual(thinking_reserve(metadata,8192),1024)
