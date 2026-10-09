"""Cross-engine socket reservations tied to actual process identities."""
import asyncio
import contextlib
import os
import sqlite3
import uuid
from pathlib import Path
from .managed_tools import PackageRegistry

class SocketBudget:
    def __init__(self,root=None,limit=256):
        directory=Path(root or os.environ.get('WIXAL_MANAGED_TOOLS_ROOT') or Path.home()/'Library/Application Support/Wixal/ManagedTools')
        directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path=directory/'socket-budget.sqlite3';self.limit=limit
        with self.database() as db:db.execute('CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,count INTEGER NOT NULL,pid INTEGER NOT NULL,identity TEXT NOT NULL)')
        self.path.chmod(0o600)
    @contextlib.contextmanager
    def database(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def reserve(self,count):
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            for identifier,pid,identity in db.execute('SELECT id,pid,identity FROM reservations').fetchall():
                if PackageRegistry.process_identity(pid)!=identity:db.execute('DELETE FROM reservations WHERE id=?',(identifier,))
            used=db.execute('SELECT COALESCE(SUM(count),0) FROM reservations').fetchone()[0]
            if used+count>self.limit:return None
            identifier=uuid.uuid4().hex;pid=os.getpid()
            db.execute('INSERT INTO reservations VALUES (?,?,?,?)',(identifier,count,pid,PackageRegistry.process_identity(pid)))
            return identifier
    async def acquire(self,count):
        if type(count)!=int or not 1<=count<=self.limit:raise ValueError('Socket reservation exceeds the shared budget')
        while True:
            work=asyncio.create_task(asyncio.to_thread(self.reserve,count))
            try:identifier=await asyncio.shield(work)
            except asyncio.CancelledError:
                identifier=await work
                if identifier:await self.release(count,identifier)
                raise
            if identifier:return identifier
            await asyncio.sleep(.05)
    async def bind(self,identifier,pid):
        def update():
            with self.database() as db:db.execute('UPDATE reservations SET pid=?,identity=? WHERE id=?',(pid,PackageRegistry.process_identity(pid),identifier))
        await asyncio.to_thread(update)
    async def release(self,count,identifier):
        def remove():
            with self.database() as db:db.execute('DELETE FROM reservations WHERE id=?',(identifier,))
        await asyncio.to_thread(remove)
