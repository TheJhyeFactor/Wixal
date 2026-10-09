import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from wixal.socket_budget import SocketBudget

class SocketBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_independent_engines_share_reservations_and_cancel_waiter(self):
        with tempfile.TemporaryDirectory() as temp:
            first=SocketBudget(temp,limit=4);second=SocketBudget(temp,limit=4)
            identifier=await first.acquire(3)
            waiting=asyncio.create_task(second.acquire(2));await asyncio.sleep(.1)
            self.assertFalse(waiting.done());waiting.cancel()
            with self.assertRaises(asyncio.CancelledError):await waiting
            await first.release(3,identifier);other=await second.acquire(4);await second.release(4,other)
    async def test_real_child_retains_budget_until_it_exits(self):
        with tempfile.TemporaryDirectory() as temp:
            budget=SocketBudget(temp,limit=2);identifier=await budget.acquire(2)
            child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'])
            try:
                await budget.bind(identifier,child.pid)
                self.assertIsNone(await asyncio.to_thread(budget.reserve,1))
            finally:child.terminate();await asyncio.to_thread(child.wait)
            recovered=await budget.acquire(2);await budget.release(2,recovered)
    async def test_invalid_allocation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            budget=SocketBudget(temp)
            for count in [0,257,-1,True]:
                with self.assertRaises(ValueError):await budget.acquire(count)
