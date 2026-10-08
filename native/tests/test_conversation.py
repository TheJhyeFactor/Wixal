import asyncio
import base64
import json
import tempfile
import unittest
from pathlib import Path
from wixal.conversation import attachments, dispatch, estimate
from wixal.storage import Store
from wixal.agent import Agent, stream_chat
from fixture_server import Fixture


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.store.new_session()
    async def asyncTearDown(self):
        self.store.close()
        self.temp.cleanup()
    async def test_drafts_are_per_session_and_persisted(self):
        first = self.store.session()["id"]
        selected = [dict(type="file",name="README.md",content="Selected context",path="/project/README.md")]
        await dispatch(self.store,"draft-save",dict(sessionId=first,text="first draft",attachments=selected))
        second = self.store.new_session()["id"]
        await dispatch(self.store,"draft-save",dict(sessionId=second,text="second draft"))
        self.assertEqual(self.store.data["sessions"][0]["draft"]["text"],"first draft")
        self.assertEqual(self.store.session()["draft"]["text"],"second draft")
        row=json.loads(self.store.db.execute("SELECT value FROM state").fetchone()[0])
        self.assertEqual(row["sessions"][0]["draft"]["attachments"][0]["content"],"Selected context")
        with self.assertRaises(ValueError):
            await dispatch(self.store,"draft-save",dict(sessionId="missing",text="lost"))
    async def test_attachment_bounds_and_image_magic(self):
        image=base64.b64encode(b"\x89PNG\r\n\x1a\n"+b"content").decode()
        self.assertEqual(attachments([dict(type="image",name="test.png",base64=image)])[0]["base64"],image)
        for value in ([dict(type="image",base64="not-valid!")],[dict(type="image",base64=base64.b64encode(b"plain text").decode())],[dict(type="file",content="x"*24001)],[dict(type="file",name=".env",path=".env",content="secret")], [dict(type="file",content="x")]*9):
            with self.assertRaises(ValueError): attachments(value)
    async def test_handoff_fallback_preserves_original_and_records_provenance(self):
        original=self.store.session()
        original["messages"]=[dict(role="user",content="Keep the file path /project/main.py and check the pending change"),dict(role="assistant",content="The change has not been verified.")]
        self.store.save()
        saved=json.loads(json.dumps(original))
        handled,new=await dispatch(self.store,"session-handoff",{})
        self.assertTrue(handled)
        self.assertNotEqual(new["id"],saved["id"])
        self.assertEqual(original,saved)
        self.assertEqual(new["handoff"]["sourceSession"],saved["id"])
        self.assertEqual(new["summary"]["method"],"excerpts")
        self.assertIn("not a verified summary",new["summary"]["content"])
        self.assertIn("/project/main.py",new["summary"]["content"])
        await dispatch(self.store,"summary-clear",{})
        self.assertNotIn("summary",new)
    async def test_context_retains_complete_latest_turn_after_summary(self):
        session=self.store.session()
        session["messages"]=[dict(role="user",content="old"),dict(role="assistant",content="old result"),dict(role="user",content="current"),dict(role="assistant",content="",tool_calls=[dict(function=dict(name="read_file",arguments={}))]),dict(role="tool",tool_name="read_file",content="evidence")]
        session["summary"]=dict(content="Earlier decision",messageCount=2)
        agent=Agent(self.store,None,None,lambda *_:None)
        context=agent.context(session)
        self.assertIn("Earlier decision",context[0]["content"])
        self.assertEqual([m["role"] for m in context[1:]],["user","assistant","tool"])
        self.assertEqual(context[1]["content"],"current")
        info=estimate(session,8192)
        self.assertTrue(info["estimated"])
        self.assertGreater(info["estimatedTokens"],0)
    async def test_image_vault_keeps_base64_out_of_persisted_state(self):
        image=base64.b64encode(b"\x89PNG\r\n\x1a\n"+b"image content").decode()
        _,draft=await dispatch(self.store,"draft-save",dict(text="Look",attachments=[dict(type="image",name="diagram.png",base64=image)]))
        saved=draft["attachments"][0]
        self.assertNotIn("base64",saved)
        image_id=saved["imageId"]
        path=self.store.directory/"attachments"/image_id
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        _,loaded=await dispatch(self.store,"image-read",dict(id=image_id))
        self.assertEqual(loaded["base64"],image)
        await dispatch(self.store,"draft-save",dict(text="Restored",attachments=[saved]))
        self.assertEqual(self.store.session()["draft"]["attachments"][0]["imageId"],image_id)
        with self.assertRaises(ValueError):await dispatch(self.store,"image-read",dict(id="../../secret"))
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"changed"):await dispatch(self.store,"image-read",dict(id=image_id))
    async def test_vision_rejection_does_not_create_a_running_task(self):
        class Runtime:
            async def catalog(self):return [dict(name="text-model",capabilities=["tools"])]
        self.store.data["model"]="text-model"
        agent=Agent(self.store,Runtime(),None,lambda *_:None)
        image=base64.b64encode(b"\x89PNG\r\n\x1a\n"+b"image content").decode()
        with self.assertRaisesRegex(ValueError,"Images"):
            await agent.run("Look",attachments=[dict(type="image",name="a.png",base64=image)])
        self.assertEqual(self.store.data["tasks"],[])
        self.assertEqual(self.store.session()["messages"],[])
    async def test_auto_summary_retains_latest_turn_and_records_model_method(self):
        from unittest.mock import AsyncMock,patch
        class Runtime:
            async def endpoint(self):return "http://127.0.0.1:1"
            async def catalog(self):return [dict(name="fixture",capabilities=["tools"])]
        class Tools:
            def catalog(self):return []
            def environment(self):return dict(shell='/bin/zsh -l',executables={})
        self.store.data.update(model="fixture",contextSize=4096,autoSummary=True)
        self.store.session()["messages"]=[dict(role="user" if i%2==0 else "assistant",content="Old evidence "*1000) for i in range(6)]
        agent=Agent(self.store,Runtime(),Tools(),lambda *_:None)
        with patch("wixal.agent.stream_chat",new=AsyncMock(side_effect=[dict(role="assistant",content="Prior verified decision"),dict(role="assistant",content="Done",usage={})])) as stream:
            await agent.run("Current request")
        summary=self.store.session()["summary"]
        self.assertEqual(summary["method"],"model")
        self.assertEqual(summary["messageCount"],6)
        context=stream.call_args_list[1].args[1]["messages"]
        self.assertIn("Prior verified decision",context[0]["content"])
        self.assertEqual(context[-1]["content"],"Current request")
        self.assertEqual(len(context),2)
    async def test_memory_scope_and_retrieval_budget(self):
        project=self.store.add_project(self.temp.name)
        self.store.data["globalMemory"]="UNIQUE_GLOBAL_PROFILE"
        self.store.data["memories"]=[dict(id="one",projectId=project["id"],content="UNIQUE_PROJECT_NOTE "*300,created=1)]
        self.store.session()["messages"]=[dict(role="user",content="UNIQUE_PROJECT_NOTE") ]
        agent=Agent(self.store,None,None,lambda *_:None)
        for mode,global_expected,project_expected in (("off",False,False),("project",False,True),("global",True,False),("both",True,True)):
            project["memoryMode"]=mode;project["memorySize"]=8000
            content=agent.context(self.store.session())[0]["content"]
            self.assertEqual("UNIQUE_GLOBAL_PROFILE" in content,global_expected)
            self.assertEqual("UNIQUE_PROJECT_NOTE" in content,project_expected)
            if project_expected:self.assertLess(content.count("UNIQUE_PROJECT_NOTE"),60)
    async def test_fixture_stream_metrics_are_retained(self):
        with Fixture() as fixture:
            response=await stream_chat(fixture.url,dict(model="fixture",messages=[dict(role="user",content="hello")],stream=True),lambda *_:None)
        self.assertIn("usage",response)
        self.assertGreaterEqual(response["usage"]["elapsedSeconds"],0)
        self.assertIn("created",response)
