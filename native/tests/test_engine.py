import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from wixal.service import Service
from wixal.storage import Store
from wixal.tools import safe_path, scan_plan
from fixture_server import Fixture

PAYLOAD=Path(__file__).resolve().parents[2]/"runtime/ollama"

class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/"project";self.root.mkdir()
        self.fixture=Fixture().__enter__();self.events=[]
        def emit(event,data):
            self.events.append((event,json.loads(json.dumps(data))))
            if event=="review":asyncio.create_task(self.service.dispatch("respond",dict(id=data["id"],value=True)))
        self.service=Service(Path(self.temp.name)/"data",PAYLOAD,emit,self.fixture.url)
        await self.service.dispatch("project-add",dict(root=str(self.root)))
        await self.service.dispatch("settings",dict(model="fixture"))
    async def asyncTearDown(self):
        await self.service.close();self.fixture.__exit__();self.temp.cleanup()
    async def test_appearance_preferences_validate_and_persist(self):
        ui=dict(theme="forest",textSize=17,reduceMotion=True,launchAnimation=False,launchSound=False,sidebarCollapsed=True,appIcon="pearl")
        await self.service.dispatch("settings",dict(ui=ui))
        self.assertEqual({key:self.service.store.data["ui"][key] for key in ui},ui)
        for patch in (dict(appIcon="unknown"),dict(launchSound="yes"),dict(sidebarCollapsed=1),dict(textSize=999),dict(theme="other")):
            with self.assertRaises(ValueError): await self.service.dispatch("settings",dict(ui=patch))
        import sqlite3
        db=sqlite3.connect(f"file:{self.service.store.directory}/workspace.sqlite3?mode=ro",uri=True)
        persisted=json.loads(db.execute("SELECT value FROM state").fetchone()[0]);db.close()
        self.assertEqual({key:persisted["ui"][key] for key in ui},ui)
    async def test_agent_streams_reviews_writes_and_reopens_sqlite(self):
        task=await self.service.dispatch("chat",dict(text="Write smoke.txt"))
        self.assertEqual(task["status"],"completed")
        self.assertEqual((self.root/"smoke.txt").read_text(),"native-agent-ok\n")
        self.assertTrue(any(e=="review" and d["name"]=="write_file" for e,d in self.events))
        self.assertTrue(any(e=="token" for e,d in self.events))
        self.assertEqual(task["checkpoints"][0]["status"],"finished")
        self.service.store.save()
        # Separate readonly inspection proves persisted data, without claiming concurrent engine ownership.
        import sqlite3
        db=sqlite3.connect(f"file:{self.service.store.directory}/workspace.sqlite3?mode=ro",uri=True)
        persisted=json.loads(db.execute("SELECT value FROM state").fetchone()[0]);db.close()
        self.assertEqual(persisted["tasks"][-1]["status"],"completed")
    async def test_decline_and_stale_write_review(self):
        async def decline(details):return False
        self.service.tools.approve=decline
        result=await self.service.dispatch("tool",dict(name="write_file",arguments=dict(path="declined.txt",content="no")))
        self.assertIn("declined",result);self.assertFalse((self.root/"declined.txt").exists())
        (self.root/"existing.txt").write_text("before")
        async def mutate(details):
            (self.root/"existing.txt").write_text("changed externally");return True
        self.service.tools.approve=mutate
        with self.assertRaisesRegex(ValueError,"changed during review"):
            await self.service.dispatch("tool",dict(name="write_file",arguments=dict(path="existing.txt",content="replacement")))
        self.assertEqual((self.root/"existing.txt").read_text(),"changed externally")
    async def test_commands_have_real_output_exit_and_owner_isolation(self):
        result=await self.service.dispatch("tool",dict(name="run_command",arguments=dict(command="printf command-ok; exit 7")))
        self.assertEqual(result["exitCode"],7);self.assertEqual(result["output"],"command-ok")
        await self.service.dispatch("session-new",{})
        with self.assertRaisesRegex(ValueError,"another conversation"):
            await self.service.dispatch("tool",dict(name="command_read",arguments=dict(session_id=result["session_id"],wait_ms=0)))
    async def test_disabled_tools_unknown_args_and_symlinks_are_rejected(self):
        await self.service.dispatch("settings",dict(enabledTools=["read_file"]))
        with self.assertRaisesRegex(ValueError,"switched off"):
            await self.service.dispatch("tool",dict(name="write_file",arguments=dict(path="no.txt",content="x")))
        with self.assertRaisesRegex(ValueError,"Unknown tool argument"):
            await self.service.dispatch("tool",dict(name="read_file",arguments=dict(path="missing",override=True)))
        outside=Path(self.temp.name)/"secret";outside.write_text("secret")
        (self.root/"link").symlink_to(outside)
        for name in ("link","../secret",".env","/etc/passwd"):
            with self.assertRaises((ValueError,FileNotFoundError)):safe_path(self.root,name)
    async def test_legacy_import_is_idempotent_and_does_not_copy_credentials(self):
        legacy=Path(self.temp.name)/"legacy.json"
        data=dict(projects=[dict(id="legacy",name="Legacy",root=str(self.root))],sessions=[],memories=[],credentials="do-not-copy")
        legacy.write_text(json.dumps(data));original=legacy.read_bytes()
        await self.service.dispatch("legacy-import",dict(path=str(legacy)))
        await self.service.dispatch("legacy-import",dict(path=str(legacy)))
        self.assertEqual(sum(p["id"]=="legacy" for p in self.service.store.data["projects"]),1)
        self.assertNotIn("credentials",self.service.store.data);self.assertEqual(legacy.read_bytes(),original)
    async def test_cancellation_during_review_leaves_paused_checkpoint(self):
        async def wait(details):await asyncio.Event().wait()
        self.service.tools.approve=wait
        run=asyncio.create_task(self.service.dispatch("chat",dict(text="Write smoke.txt")))
        for _ in range(100):
            await asyncio.sleep(.01)
            if self.service.store.data["tasks"] and self.service.store.data["tasks"][-1]["checkpoints"]:break
        await self.service.dispatch("stop",{})
        await asyncio.gather(run,return_exceptions=True)
        self.assertEqual(self.service.store.data["tasks"][-1]["status"],"paused")
        self.assertFalse((self.root/"smoke.txt").exists())

    async def test_chat_mode_enabled_tools_still_require_controller_review(self):
        await self.service.dispatch("settings",dict(mode="chat"))
        task=await self.service.dispatch("chat",dict(text="Write smoke.txt in chat mode"))
        self.assertEqual(task["status"],"completed")
        self.assertEqual((self.root/"smoke.txt").read_text(),"native-agent-ok\n")
        self.assertTrue(any(e=="review" and d["name"]=="write_file" for e,d in self.events))

    async def test_mcp_catalog_execution_and_disconnect(self):
        import sys
        await self.service.dispatch("mcp-add",dict(name="Fixture",command=sys.executable,args=[str(Path(__file__).with_name("mcp_fixture.py"))]))
        server=self.service.store.data["mcpServers"][0]
        await self.service.dispatch("mcp-connect",dict(id=server["id"]))
        name=self.service.mcp.definitions()[0]["function"]["name"]
        await self.service.dispatch("settings",dict(enabledTools=[name]))
        result=await self.service.dispatch("tool",dict(name=name,arguments=dict(text="mcp-ok")))
        self.assertEqual(result,"mcp-ok")
        await self.service.dispatch("mcp-disconnect",dict(id=server["id"]))
        self.assertEqual(self.service.mcp.definitions(),[])
        await self.service.dispatch("settings",dict(enabledTools=[name]))
        self.assertIn(name,self.service.store.data["enabledTools"])
        with self.assertRaises(ValueError):await self.service.dispatch("tool",dict(name=name,arguments=dict(text="disconnected")))
        await self.service.dispatch("mcp-add",dict(name="Second fixture",command=sys.executable,args=[str(Path(__file__).with_name("mcp_fixture.py"))]))
        other=self.service.store.data['mcpServers'][-1]
        await self.service.dispatch('mcp-connect',dict(id=other['id']))
        other_name=self.service.mcp.definitions()[0]['function']['name']
        await self.service.dispatch('settings',dict(enabledTools=[name,other_name]))
        await self.service.dispatch('mcp-disconnect',dict(id=other['id']))
        await self.service.dispatch('mcp-delete',dict(id=server['id']))
        self.assertEqual(self.service.store.data['enabledTools'],[other_name])

    async def test_child_agent_cannot_write_and_parent_session_stays_selected(self):
        session=self.service.store.data["activeSession"]
        result=await self.service.dispatch("tool",dict(name="delegate_task",arguments=dict(prompt="Investigate files")))
        self.assertNotIn("write_file",result["tools"])
        self.assertEqual(result["checkpoints"][0]["status"],"error")
        self.assertFalse((self.root/"smoke.txt").exists())
        self.assertEqual(self.service.store.data["activeSession"],session)
    async def test_store_lock_and_skill_progressive_loading(self):
        with self.assertRaisesRegex(RuntimeError,"already open"):
            Store(self.service.store.directory)
        skill=self.root/"inspect.md";skill.write_text("# Inspect carefully\nRead files before drawing conclusions.")
        await self.service.dispatch("skill-add",dict(path=str(skill)))
        result=await self.service.dispatch("tool",dict(name="load_skill",arguments=dict(name="inspect")))
        self.assertIn("Read files",result["instructions"])

if __name__=="__main__":unittest.main()
