import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from fixture_server import Fixture
from wixal.service import ipc_socket_path

class IPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_attaches_to_running_engine_and_socket_is_private(self):
        native=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary, Fixture() as fixture:
            directory=str(Path(temporary)/("nested-"+"x"*38)/("records-"+"y"*38)/"workspace")
            Path(directory).mkdir(parents=True)
            engine=await asyncio.create_subprocess_exec(sys.executable,str(native/'engine/engine_main.py'),'--data',directory,'--endpoint',fixture.url,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=2*1024*1024)
            drain=asyncio.create_task(engine.stdout.read())
            try:
                socket=ipc_socket_path(directory)
                alias=Path(directory)/'engine.sock'
                self.assertGreater(len(str(Path(directory)/'engine.sock').encode()),100)
                for _ in range(100):
                    # Creation precedes the explicit final permissions by one await.
                    # Wait for readiness, retaining the bounded permission assertion.
                    if socket.exists() and socket.stat().st_mode & 0o777==0o600:break
                    if engine.returncode is not None:raise RuntimeError((await engine.stderr.read()).decode())
                    await asyncio.sleep(.02)
                self.assertTrue(socket.exists())
                self.assertEqual(socket.stat().st_mode & 0o777,0o600)
                self.assertTrue(alias.is_symlink())
                client=await asyncio.create_subprocess_exec(sys.executable,'-m','wixal.cli','--data',directory,env={**os.environ,'PYTHONPATH':str(native/'engine')},stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                out,error=await asyncio.wait_for(client.communicate(b'/models\n/quit\n'),10)
                self.assertEqual(client.returncode,0,error.decode())
                self.assertIn('Connected to the Wixal Native desktop engine',out.decode())
                self.assertIn('fixture',out.decode())
            finally:
                engine.stdin.close()
                await asyncio.wait_for(engine.wait(),15)
                await drain
            self.assertFalse(socket.exists())
            self.assertFalse(alias.exists() or alias.is_symlink())

if __name__=='__main__':unittest.main()
