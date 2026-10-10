"""Single-owner SQLite state, preserving the existing Wixal data vocabulary."""
import copy
import hashlib
import fcntl
import json
import os
import sqlite3
import time
import uuid
import signal
import subprocess
from pathlib import Path


def identity():
    return str(uuid.uuid4())


def now():
    return int(time.time() * 1000)


class Store:
    def __init__(self, directory, startup=None):
        self.directory = Path(directory).expanduser()
        report = startup or (lambda info: None)
        database_path = str((self.directory / "workspace.sqlite3").absolute())
        report(dict(phase="workspace directory", database=database_path, pid=os.getpid()))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        report(dict(phase="workspace owner lock", database=database_path, pid=os.getpid()))
        self.owner_lock = (self.directory / ".engine.lock").open("a+")
        try:
            fcntl.flock(self.owner_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Opening the foreground app may interrupt only our verified background owner.
            acquired=False
            if not os.environ.get('WIXAL_BACKGROUND'):
                self.owner_lock.seek(0)
                try:
                    holder=json.loads(self.owner_lock.read());pid=int(holder['pid'])
                    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True,timeout=2)
                    if holder.get('background') and '--background' in command and ('wixal-engine' in command or 'engine_main.py' in command):
                        os.kill(pid,signal.SIGTERM)
                        for _ in range(100):
                            try:fcntl.flock(self.owner_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;break
                            except BlockingIOError:time.sleep(.1)
                except (OSError,ValueError,KeyError,subprocess.SubprocessError):pass
            if not acquired:
                self.owner_lock.close()
                raise RuntimeError("This native workspace is already open. Close the other client or choose a separate --data directory.")
        self.owner_lock.seek(0);self.owner_lock.truncate()
        self.owner_lock.write(json.dumps(dict(pid=os.getpid(),background=bool(os.environ.get('WIXAL_BACKGROUND')))));self.owner_lock.flush()
        # Bound waits on database-level locks during cold start. The sqlite3
        # default is five seconds; spelling it out here makes startup behavior
        # intentional and keeps the PRAGMA below on the same deadline.
        try:
            report(dict(phase="SQLite file open", database=database_path, pid=os.getpid()))
            self.db = sqlite3.connect(self.directory / "workspace.sqlite3", timeout=3.0)
            self.db.execute("PRAGMA busy_timeout=3000")
            os.chmod(self.directory / "workspace.sqlite3", 0o600)
            report(dict(phase="SQLite journal setup", database=database_path, pid=os.getpid()))
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            row = self.db.execute("SELECT value FROM state WHERE id=1").fetchone()
            self.data = json.loads(row[0]) if row else {}
        except BaseException:
            if hasattr(self, "db"):
                self.db.close()
            self.owner_lock.close()
            raise
        self.session_digests={};self.session_revisions={}
        had_setup = "setup" in self.data
        defaults = dict(projects=[], sessions=[], memories=[], tasks=[], schedules=[], skills=[], agentProfiles=[],agentWorkflows=[],workflowRuns=[],agentJobs=[],skillCandidates=[],notifications=[],
                        enabledTools=[], activeProject=None, activeSession=None, model="", mode="agent",
                        contextSize=8192, autoSummary=True, globalMemory="", globalMemoryEnabled=True,
                        setup=dict(entryCompleted=False, completed=False),assessmentResults=[],
                        mcpServers=[], ui=dict(theme="sakura", textSize=13, reduceMotion=False, launchAnimation=True, launchSound=True, sidebarCollapsed=False, appIcon="theme"))
        for key, value in defaults.items():
            self.data.setdefault(key, value)
        for session in self.data["sessions"]:
            session.setdefault("mode", self.data["mode"])
        self.data["provider"] = "ollama"
        if "usage" not in self.data:
            self.data["usage"]=[dict(**m["usage"],sessionId=s["id"],model=self.data.get("model",""),created=m.get("created"),kind="conversation") for s in self.data["sessions"] for m in s.get("messages",[]) if isinstance(m.get("usage"),dict)][-2000:]
        if not had_setup and (self.data.get("migration") or self.data.get("projects")):
            self.data["setup"].update(entryCompleted=True,completed=True)
        for task in self.data["tasks"]:
            if task.get("status") in ("running", "waiting_review"):
                task["status"] = "interrupted"
        for run in self.data['workflowRuns']:
            if run.get('status') in ('running','waiting_review'):
                run.update(status='interrupted',error='Engine restarted; inspect retained stage evidence before resuming')
                for stage in run.get('stages',[]):
                    if stage.get('status') in ('running','waiting_review'):
                        stage.update(status='interrupted',error='Stage interrupted by engine restart')
        for job in self.data['agentJobs']:
            if job.get('status')=='running':job.update(status='interrupted',error='Engine restarted; inspect retained effects before restarting')
        for schedule in self.data['schedules']:
            if schedule.get('lastRun',{}).get('status')=='running':schedule['lastRun'].update(status='interrupted',finished=now())
        self.save()
        from .memory import Memory
        self.memory = Memory(self)
        report(dict(phase="workspace ready", database=database_path, pid=os.getpid()))

    def save(self):
        for session in self.data.get('sessions', []):
            for message in session.get('messages', []):
                message.setdefault('id', identity())
            # Only recall-relevant fields change the search index revision.
            searchable={k:session.get(k) for k in ('id','projectId','memoryOwner','title','archivedAt','memoryExcluded')}
            searchable['messages']=[{k:m.get(k) for k in ('id','role','content','displayContent','handoff','memoryReferences','tool_name')} for m in session.get('messages',[])]
            digest=hashlib.sha256(json.dumps(searchable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if self.session_digests.get(session['id'])!=digest:
                self.session_digests[session['id']]=digest;self.session_revisions[session['id']]=self.session_revisions.get(session['id'],0)+1
        with self.db:
            self.db.execute("INSERT INTO state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",
                            (json.dumps(self.data, ensure_ascii=False),))

    def record_usage(self,usage,session_id,kind="conversation"):
        self.data.setdefault("usage",[]).append(dict(**usage,sessionId=session_id,model=self.data["model"],created=now(),kind=kind))
        self.data["usage"]=self.data["usage"][-2000:]
        self.save()

    def close(self):
        # A failed final write must still release SQLite and the workspace
        # owner lock, so a corrected disk/lock condition can be retried.
        try:
            self.save()
        finally:
            try:
                self.db.close()
            finally:
                self.owner_lock.close()

    def active_memory(self):
        account = self.data.get("account", {})
        return account.get("globalMemory", "") if account.get("signedIn") else self.data.get("globalMemory", "")

    def project(self):
        return next((p for p in self.data["projects"] if p["id"] == self.data["activeProject"]), None)

    def session(self):
        return next((s for s in self.data["sessions"] if s["id"] == self.data["activeSession"]), None)

    def new_session(self):
        from .memory import owner
        session = dict(id=identity(), projectId=self.data["activeProject"], memoryOwner=owner(self), mode=self.data.get("mode","agent"), title="New conversation", created=now(), messages=[])
        self.data["sessions"].append(session)
        self.data["activeSession"] = session["id"]
        self.save()
        return session

    def select_project(self, project_id):
        if project_id is not None and not any(p["id"] == project_id for p in self.data["projects"]):
            raise ValueError("Unknown project")
        self.data["activeProject"] = project_id
        sessions = [s for s in self.data["sessions"] if s.get("projectId") == project_id and not s.get("archivedAt")]
        self.data["activeSession"] = sessions[-1]["id"] if sessions else None
        if sessions:
            self.data["mode"] = sessions[-1].get("mode", self.data.get("mode", "agent"))
        if not sessions:
            self.new_session()
        self.save()

    def add_project(self, root):
        root = str(Path(root).expanduser().resolve(strict=True))
        if not Path(root).is_dir():
            raise ValueError("Choose a project directory")
        project = next((p for p in self.data["projects"] if p["root"] == root), None)
        if not project:
            project = dict(id=identity(), name=Path(root).name, root=root, created=now(), memoryMode="project", memorySize=24000)
            self.data["projects"].append(project)
        self.select_project(project["id"])
        return project

    def approval_mode(self):
        return (self.project() or {}).get("approvalMode", self.data.get("personalApprovalMode", "review"))

    def memories(self):
        return [m for m in self.data["memories"] if m.get("projectId") == self.data["activeProject"]]

    def remember(self, content):
        project = self.project() or {}
        if project.get("memoryMode") in ("off", "global"):
            raise ValueError("Project memory is disabled")
        if not isinstance(content, str) or not content.strip() or len(content) > 4000:
            raise ValueError("Memory must contain 1–4,000 characters")
        if sum(len(m["content"]) for m in self.memories()) + len(content) > project.get("memorySize", 24000):
            raise ValueError("Project memory budget is full")
        self.data["memories"].append(dict(id=identity(), projectId=self.data["activeProject"], content=content.strip(), created=now()))
        self.save()

    def import_legacy(self, source):
        from .migration import import_workspace
        return import_workspace(self, source)
