"""Versioned JSON-line IPC shared by the native desktop and terminal clients."""
import argparse
import copy
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from . import VERSION
from .agent import Agent
from .mcp import MCP
from .runtime import Runtime, request_json
from .storage import Store, identity, now
from .tools import Tools, DEFINITIONS
from . import conversation, workspace
from .model_manager import ModelManager
from .integrations import NativeIntegrations
from .requests import Requests


def ipc_socket_path(directory):
    """Return a per-user short socket path and a workspace-local compatibility alias.

    macOS sockaddr_un.sun_path is short. Application Support paths, especially
    nested acceptance workspaces, can exceed it even though the filesystem path
    itself is valid. Keep the real endpoint in a private temporary directory and
    expose the historical engine.sock name as a symlink for existing clients.
    """
    data = Path(directory).expanduser().resolve()
    root = Path(tempfile.gettempdir()) / f"wxipc-{os.getuid()}"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if not root.is_dir() or root.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("The private Wixal IPC directory is not safe to use")
    digest = hashlib.sha256(str(data).encode()).hexdigest()[:24]
    return root / f"e-{digest}.sock"


class Service:
    def __init__(self, directory, payload, emit, endpoint=None):
        from .diagnostics import Diagnostics
        self.diagnostics = None
        transport_emit = emit
        def emit(event, data):
            if self.diagnostics:
                try:self.diagnostics.event(event, data, getattr(self, 'store', None))
                except Exception:pass
            transport_emit(event, data)
        self.emit = emit
        self.store = Store(directory, startup=lambda info:emit("startup-progress",info))
        self.diagnostics = Diagnostics(directory)
        from .community_reports import CommunityReports
        self.community_reports = CommunityReports(self)
        if not self.store.data.get("nativeInitialized"):
            self.store.data["enabledTools"] = [t["function"]["name"] for t in DEFINITIONS]
            self.store.data["nativeInitialized"] = True
            self.store.save()
        migration = self.store.data.get("migration",{})
        if migration.get("source") and self.store.data.get("appearanceVersion",0)<2:
            try:
                appearance = json.loads(Path(migration["source"]).read_text()).get("ui",{})
                if appearance.get("theme") in ("sakura","midnight","paper","forest"):
                    self.store.data["ui"]["theme"] = appearance["theme"]
                for key in ("textSize","reduceMotion","launchAnimation","launchSound","sidebarCollapsed","appIcon"):
                    value=appearance.get(key)
                    if key=="textSize" and value in (13,15,17) or key in ("reduceMotion","launchAnimation","launchSound","sidebarCollapsed") and isinstance(value,bool) or key=="appIcon" and value in ("theme","sakura","midnight","pearl","copper"):
                        self.store.data["ui"][key]=value
                self.store.data["appearanceImported"] = True
                self.store.data["appearanceVersion"] = 2
                self.store.save()
            except (OSError,ValueError): pass
        self.runtime = Runtime(Path(directory)/"local-runtime", payload, emit, endpoint)
        self.mcp = MCP(self.store.directory,self.open_external)
        self.pending = {}
        self.tools = Tools(self.store, self.approve, emit, self.mcp, self.host)
        if not self.store.data.get('memoryToolsVersion'):
            enabled=self.store.data['enabledTools']
            if 'search_history' in enabled and 'recall_memory' not in enabled:enabled.append('recall_memory')
            if 'save_memory' in enabled and 'forget_memory' not in enabled:enabled.append('forget_memory')
            self.store.data['memoryToolsVersion']=1;self.store.save()
        from .addons import Addons
        self.addons=Addons(self)
        self.store.addons=self.addons
        if not self.store.data.get('networkDiscoveryVersion'):
            self.store.data['enabledTools']=list(dict.fromkeys(self.store.data['enabledTools']+['network_discover','network_read','network_stop']))
            self.store.data['networkDiscoveryVersion']=1;self.store.save()
        if not self.store.data.get('addonToolsVersion'):
            self.store.data['enabledTools']=list(dict.fromkeys(self.store.data['enabledTools']+[t['function']['name'] for t in DEFINITIONS if t['function']['name'].startswith('addon_')]))
            self.store.data['addonToolsVersion']=1;self.store.save()
        self.tools.runtime=self.runtime
        self.agent = Agent(self.store, self.runtime, self.tools, emit)
        self.tools.delegate = self.delegate
        from .agents import Agents
        self.agents=Agents(self)
        self.tools.management=self.agents
        self.active = None
        from .security_workspace import SecurityWorkspace
        self.security_workspace = SecurityWorkspace(self)
        self.assessment_task = None
        self.manual_tools = 0
        self.scheduler = None
        self.model_manager = ModelManager(self.runtime, self.store, emit, self.idle)
        self.integrations = NativeIntegrations(self)
        from .scheduling import Background
        self.background=Background(self)
        from .sync import Sync
        self.sync=Sync(self.store)
        self.store.data["backgroundScheduler"]=self.background.snapshot()

    async def ask(self, kind, payload):
        request_id = identity()
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        self.emit(kind, dict(id=request_id, **payload))
        try:
            return await asyncio.wait_for(future, 600)
        finally:
            self.pending.pop(request_id, None)
            self.emit("request-closed", dict(id=request_id))

    async def approve(self, details):
        # Install requests follow the global installation preference, independently
        # of a project's command/execution bypass setting.
        if details.pop('installationReview',False):
            return bool(await self.ask('review',details))
        # Bypass is an explicit user preference; default is review.
        if self.store.approval_mode() == "bypass":
            return True
        return bool(await self.ask("review", details))

    async def open_external(self,url):
        return await self.host("open-external",dict(url=url))

    async def host(self, method, params):
        result = await self.ask("host", dict(method=method, params=params))
        if isinstance(result, dict) and result.get("error"):
            raise ValueError(result["error"])
        return result

    def idle(self):
        if getattr(self, 'security_workspace', None) and self.security_workspace.busy:
            raise ValueError('Stop or finish security runs before changing workspace execution settings')
        if getattr(self,"sync",None) and self.sync.lock.locked():raise ValueError("Finish workspace sync first")
        if self.manual_tools or self.active and not self.active.done():
            raise ValueError("Stop or finish the current agent task first")
        if getattr(self, "model_manager", None) and self.model_manager.busy:
            raise ValueError("Finish importing or stop the benchmark first")

    async def dispatch(self, method, params):
        params = params or {}
        if method.startswith('community-report-'):return await self.community_reports.dispatch(method,params)
        if method == 'diagnostic-log': return self.diagnostics.snapshot()
        if method == 'diagnostic-export':
            from .bug_reports import dispatch
            return await dispatch(self, params)
        if method == 'diagnostic-ui-event':
            event = params.get('event')
            if event not in ('details-open', 'details-close', 'action-select', 'action-deselect'):
                raise ValueError('Unknown diagnostic UI event')
            self.diagnostics.write(event, sessionId=self.store.data.get('activeSession'))
            return True
        if method.startswith('addon-'):return await self.addons.dispatch(method,params)
        if method.startswith('security-') and method != 'security-readiness':
            return await self.security_workspace.dispatch(method, params)
        if method == "hello":
            await self.integrations.restore_if_needed()
            return dict(version=VERSION, protocol=1, state=self.store.data, tools=self.tools.catalog(), storage=str(self.store.directory))
        if method == "ping": return True
        if method == 'agent-guide':
            task=self.agents.find('tasks',params.get('id'))
            if not task.get('agentId') or task['status'] not in ('running','waiting_review') or self.agent.current_task_id!=task['id'] or not self.active or self.active.done():raise ValueError('No active agent run accepts guidance')
            from .agents import text
            task.setdefault('pendingGuidance',[]).append(text(params.get('text'),'guidance',4000))
            self.store.save();self.emit('state',self.store.data);return dict(queued=True)
        if method in ('agent-starter-pack','agent-save','agent-run','workflow-save','workflow-run','workflow-resume','agent-schedule-save','agent-schedule-toggle','agent-schedule-run','agent-schedule-delete','agent-resume','agent-verify','agent-enqueue','agent-job-cancel','skill-propose','skill-evaluate','skill-promote','skill-rollback','workflow-merge'):
            return await self.agents.dispatch(method,params)
        if method in ('workspace-backup','workspace-import-preview','workspace-import','workspace-storage','workspace-diagnostics'):
            from .workspace_data import dispatch
            return await dispatch(self,method,params)
        if method == 'settings' and set(params) == {'ui'}:
            from .preferences import validate_ui
            # Appearance does not alter the active request. Permit it during generation,
            # but avoid racing a sync snapshot transaction.
            if self.sync.lock.locked():raise ValueError('Finish workspace sync first')
            self.store.data['ui'].update(validate_ui(params['ui']))
            self.store.save();self.emit('state',self.store.data);return self.store.data
        if method in ('sync-settings','sync-run','sync-resolve','sync-status'):
            self.idle()
            if method=='sync-settings':result=await self.sync.configure(params)
            elif method=='sync-run':result=await self.sync.run()
            elif method=='sync-resolve':result=self.sync.resolve(params)
            else:return self.sync.snapshot()
            self.emit('state',self.store.data);return result
        if method=='project-relocate':
            self.idle()
            project=next((p for p in self.store.data['projects'] if p['id']==params.get('id')),None)
            root=Path(params.get('root','')).expanduser().resolve(strict=True)
            if not project or not root.is_dir():raise ValueError('Choose the local folder for this project')
            project.update(root=str(root),syncRootRequired=False);self.store.save();self.emit('state',self.store.data);return project
        if method=='background-settings':
            self.idle()
            if not isinstance(params.get('enabled'),bool):raise ValueError('Choose enabled or disabled')
            result=await self.background.configure(params['enabled']);self.emit('state',self.store.data);return result
        if method=='memory-semantic':
            self.idle()
            model=params.get('model','').strip()
            if model:
                catalog=await self.runtime.catalog()
                if not any(m['name']==model and 'embedding' in m.get('capabilities',[]) for m in catalog):raise ValueError('Choose an installed model marked embedding')
            self.store.data['memoryEmbeddingModel']=model;self.store.save()
            return self.store.memory.snapshot()
        if method=='memory-index':
            self.idle()
            await self.store.memory.prepare('',self.runtime,params.get('scope'))
            return self.store.memory.snapshot()
        if method=='memory-review':
            self.idle()
            async def review_conversation():
                from .memory_review import review
                from .model_manager import safe_context
                session=self.store.session()
                if not session:raise ValueError('Open a conversation to review its decisions')
                info=next((m for m in await self.runtime.catalog() if m['name']==self.store.data['model']),{})
                context=safe_context(info,self.model_manager.device,self.store.data['contextSize'])
                result=await review(self.store,session,self.runtime,info,context,self.emit,force=True)
                self.emit('state',self.store.data);return result
            self.active=asyncio.create_task(review_conversation())
            return await self.active
        if method=='memory-consolidate':
            self.idle()
            from .memory import visible_notes
            await self.store.memory.semantic.prepare('',self.runtime,[('note:'+n['id'],n['content']) for n in visible_notes(self.store,params.get('scope'))])
        if method=='memory-recall':
            self.idle()
            await self.store.memory.prepare(params.get('query',''),self.runtime,params.get('scope'))
        if method in ('memory-status','memory-recall','memory-save','memory-forget','memory-suggestion','memory-policy','memory-consolidate'):
            if method not in ('memory-status','memory-recall'):self.idle()
            result=self.store.memory.dispatch(method,params)
            if method not in ('memory-status','memory-recall'):self.emit('state',self.store.data)
            return result
        if method == "context-info":
            session = self.store.session()
            if not session: return dict(estimatedTokens=0, limit=self.store.data["contextSize"], estimated=True)
            name = self.store.data["model"]
            metadata = next((value[1] for key, value in self.runtime.metadata.items() if key[0] == name), {})
            if name and not metadata:
                model = next((m for m in await self.runtime.catalog() if m["name"] == name), {})
                metadata = model
            skill = next((s for s in self.store.data["skills"] if s["name"] == params.get("skill")), None)
            result = self.agent.context_info(session, skill, "tools" in metadata.get("capabilities", []))
            result["sessionId"] = session["id"]
            return result
        if method == "security-readiness":
            import shutil
            path = shutil.which("nmap") or "/opt/homebrew/bin/nmap"
            return dict(installed=os.path.isfile(path) and os.access(path, os.X_OK), discoveryEnabled="security_tools" in self.store.data["enabledTools"], rustscan=self.addons.snapshot("rustscan")["packages"])
        if method == "respond":
            future = self.pending.get(params["id"])
            if not future or future.done():
                raise ValueError("Review expired or was cancelled")
            future.set_result(params.get("value"))
            return True
        if method == "stop":
            if params.get('taskId') and params.get('runId'):raise ValueError('Choose a single active run to stop')
            if params.get('taskId') or params.get('runId'):
                row=self.agents.find('workflowRuns' if params.get('runId') else 'tasks',params.get('runId') or params['taskId'])
                if row.get('status') not in ('running','waiting_review'):
                    raise ValueError('This run has already stopped; no other run was cancelled')
                if params.get('taskId') and row.get('workflowRunId'):
                    raise ValueError('Stop this run from its parent workflow')
                current=self.agents.active_workflow_id if params.get('runId') else self.agent.current_task_id
                if current!=row['id'] or not self.active or self.active.done():raise ValueError('This is not the active run; no other run was cancelled')
            if self.active and not self.active.done():
                self.active.cancel()
                await asyncio.gather(self.active, return_exceptions=True)
            return True
        if method.startswith(("account-", "global-memory-", "companion-")) or method in ("entry-complete", "setup-complete", "legal-document"):
            if method not in ("legal-document", "companion-stop", "account-reset", "account-refresh", "global-memory-refresh"):
                self.idle()
            handled, result = await self.integrations.dispatch(method, params)
            if handled:return result
        if method == "task-start":
            self.idle()
            task = next((t for t in self.store.data["tasks"] if t["id"]==params.get("id")),None)
            if not task or task["status"] not in ("queued","failed","interrupted","cancelled","paused","needs_attention"):
                raise ValueError("This task cannot be started")
            if task.get("agentSnapshot",{}).get("_branchRoot"):raise ValueError("Resume this task through its isolated workflow")
            if task.get("agentId"):
                self.agents.find("tasks",task["id"])
                self.active=asyncio.create_task(self.agents.run(task["agentId"],task["prompt"],task.get("projectId"),snapshot=task["agentSnapshot"],resume_task=task));return await self.active
            await self.tools.close()
            self.store.select_project(task.get("projectId"));self.store.data["mode"]="agent";self.store.new_session()
            self.active = asyncio.create_task(self.agent.run(task["prompt"],queued_task=task))
            return await self.active
        if method == "chat":
            self.idle()
            self.active = asyncio.create_task(self.agent.run(params["text"], params.get("resume"), params.get("skill"), params.get("attachments")))
            return await self.active
        if method in ("session-handoff", "summary-clear"):
            self.idle()
        if method == "session-handoff":
            self.emit("operation", dict(name="session-handoff", running=True))
            self.active = asyncio.create_task(conversation.dispatch(self.store, method, params, self.runtime, self.emit))
            try:
                handled, result = await self.active
            finally:
                self.emit("operation", dict(name="session-handoff", running=False))
        else:
            handled, result = await conversation.dispatch(self.store, method, params, self.runtime, self.emit)
        if handled:
            if method not in ("context-info","image-read"):self.emit("state", self.store.data)
            return result
        handled, result = await workspace.dispatch(self, method, params)
        if handled:
            if method not in ("session-copy", "mcp-status", "assessment-cancel"):self.emit("state", self.store.data)
            return result
        if self.model_manager.handles(method):
            return await self.model_manager.dispatch(method, params)
        if method == "models":
            return await self.runtime.catalog()
        if method == "model-imports":
            return await asyncio.to_thread(self.runtime.imports)
        if method == "model-import":
            self.idle()
            await asyncio.to_thread(self.runtime.import_model, params)
            return await self.runtime.catalog()
        if method == "model-pull":
            self.idle()
            name = params["name"].strip()
            if not name or len(name)>200:
                raise ValueError("Enter a model name")
            endpoint = await self.runtime.endpoint()
            # Nonstream pull still runs outside event loop; IPC and cancellation stay responsive.
            return await asyncio.to_thread(request_json, endpoint+"/api/pull", dict(model=name, stream=False), 3600)
        if method == "tool":
            self.idle()
            self.manual_tools += 1
            try:
                return await self.tools.execute(params["name"], params.get("arguments", {}), (self.store.session() or self.store.new_session())["id"])
            finally:
                self.manual_tools -= 1
        self.idle()
        if method == "project-create":
            name=params.get("name", "")
            if not isinstance(name,str):raise ValueError("Enter a project name")
            name=name.strip()
            if not name or len(name)>120 or name.startswith('.') or any(c in name for c in '/\\:') or any(ord(c)<32 for c in name):
                raise ValueError("Use a project name under 120 characters without slashes or special characters")
            projects=self.store.directory / "Projects"
            projects.mkdir(exist_ok=True)
            root=projects / name
            try:root.mkdir()
            except FileExistsError:raise ValueError("A project with that name already exists. Choose another name.")
            self.store.add_project(str(root))
        elif method == "project-add":
            mode,size=params.get("memoryMode","project"),params.get("memorySize",24000)
            if mode not in ("off","project","global","both") or size not in (8000,24000,48000):raise ValueError("Choose a memory scope and budget")
            root=str(Path(params["root"]).expanduser().resolve(strict=True))
            existing=any(p["root"]==root for p in self.store.data["projects"])
            project=self.store.add_project(root)
            if not existing:
                project.update(memoryMode=mode,memorySize=size)
                name=params.get("name")
                if isinstance(name,str) and name.strip() and len(name.strip())<=120:project["name"]=name.strip()
        elif method == "project-select":
            await self.tools.close()
            await self.mcp.close()
            self.store.select_project(params.get("id"))
        elif method == "session-new":
            mode=params.get("mode", self.store.data["mode"])
            if mode not in ("chat", "agent"):raise ValueError("Unknown conversation mode")
            self.store.data["mode"]=mode
            current=self.store.session() or {}
            draft=current.get("draft") or {}
            reusable=(current.get("projectId")==self.store.data["activeProject"] and current.get("mode")==mode
                      and not current.get("archivedAt") and not current.get("messages") and not draft.get("text", "").strip()
                      and not any(job.get("owner")==current.get("id") for job in self.tools.jobs.values())
                      and not draft.get("attachments") and current.get("title")=="New conversation")
            if not reusable:self.store.new_session()
        elif method == "session-select":
            selected = next(s for s in self.store.data["sessions"] if s["id"]==params["id"] and s.get("projectId")==self.store.data["activeProject"])
            await self.tools.close()
            self.store.data["activeSession"] = selected["id"]
            self.store.data["mode"] = selected.get("mode", self.store.data["mode"])
        elif method == "session-archive":
            session = next(s for s in self.store.data["sessions"] if s["id"]==params["id"])
            session["archivedAt"] = None if params.get("restore") else now()
            if self.store.data["activeSession"]==session["id"] and not params.get("restore"):
                self.store.new_session()
        elif method == "settings":
            for session in self.store.data["sessions"]: session.pop("contextInfo", None)
            if "globalMemory" in params:
                await self.integrations.dispatch("global-memory-save", dict(content=params["globalMemory"]))
            for key in ("model", "mode", "globalMemoryEnabled", "autoSummary"):
                if key in params:
                    if key in ("model", "globalMemory") and (not isinstance(params[key], str) or len(params[key])>24000):
                        raise ValueError("Invalid setting")
                    if key in ("globalMemoryEnabled", "autoSummary") and not isinstance(params[key], bool):
                        raise ValueError("Invalid setting")
                    if key=="mode" and params[key] not in ("chat", "agent"):
                        raise ValueError("Unknown chat mode")
                    self.store.data[key] = params[key]
                    if key=="mode" and self.store.session():self.store.session()["mode"]=params[key]
            if "ui" in params:
                from .preferences import validate_ui
                self.store.data["ui"].update(validate_ui(params["ui"]))
            if "contextSize" in params:
                if params["contextSize"] not in (4096,8192,16384,32768):
                    raise ValueError("Choose a bounded model context")
                self.store.data["contextSize"] = params["contextSize"]
            if "enabledTools" in params:
                valid = {t["function"]["name"] for t in self.tools.catalog()}
                from .mcp_names import prefix
                configured=[prefix(c["id"]) for c in self.store.data["mcpServers"]]
                valid.update(name for name in self.store.data["enabledTools"] if any(name.startswith(p) for p in configured))
                if not isinstance(params["enabledTools"], list) or set(params["enabledTools"])-valid:
                    raise ValueError("Unknown tools")
                self.store.data["enabledTools"] = params["enabledTools"]
            if "approvalMode" in params:
                if params["approvalMode"] not in ("review", "bypass"):
                    raise ValueError("Invalid review mode")
                project = self.store.project()
                if project:
                    project["approvalMode"] = params["approvalMode"]
                else:
                    self.store.data["personalApprovalMode"] = params["approvalMode"]
            if "memoryMode" in params and self.store.project():
                if params["memoryMode"] not in ("project", "global", "both", "off"):
                    raise ValueError("Invalid memory mode")
                self.store.project()["memoryMode"] = params["memoryMode"]
        elif method == "legacy-import":
            result=self.store.import_legacy(params.get("path", str(Path.home()/"Library/Application Support/Wixal/workspace.json")))
            self.emit("state",self.store.data)
            return result
        elif method == "memory-delete":
            self.store.memory.forget(params['id'])
        elif method == "skill-add":
            path = Path(params["path"]).expanduser().resolve(strict=True)
            if path.stat().st_size>24000 or path.suffix.lower()!=".md":
                raise ValueError("Select a Markdown skill below 24 KB")
            content = path.read_text()
            self.store.data["skills"].append(dict(id=identity(), name=path.parent.name if path.name=="SKILL.md" else path.stem, description=content.splitlines()[0][:200], content=content, source=str(path)))
        elif method == "skill-delete":
            self.store.data["skills"] = [s for s in self.store.data["skills"] if s["id"]!=params["id"]]
        elif method == "schedule-add":
            seconds = int(params["intervalSeconds"])
            if seconds<60 or seconds>31*86400 or not params["prompt"].strip():
                raise ValueError("Schedules need a prompt and an interval from 1 minute to 31 days")
            from .memory import owner
            policy=params.get('missedRunPolicy','latest')
            if policy not in ('latest','skip'):raise ValueError('Choose latest or skip for missed runs')
            self.store.data["schedules"].append(dict(id=identity(), prompt=params["prompt"], intervalSeconds=seconds, nextRun=now()+seconds*1000, enabled=True, projectId=self.store.data["activeProject"],owner=owner(self.store),model=self.store.data['model'],missedRunPolicy=policy))
        elif method == "schedule-delete":
            self.store.data["schedules"] = [s for s in self.store.data["schedules"] if s["id"]!=params["id"]]
        elif method == 'mcp-oauth-clear':
            from .remote_mcp import Vault
            config=next(s for s in self.store.data['mcpServers'] if s['id']==params['id'])
            await self.mcp.disconnect(config['id']);await Vault(self.store.directory,config['id']).clear()
            self.emit('catalog',self.tools.catalog())
        elif method in ('mcp-add','mcp-update'):
            from .preferences import server_config
            config=server_config(params)
            if method=='mcp-add':self.store.data['mcpServers'].append(dict(id=identity(),**config))
            else:
                existing=next((v for v in self.store.data['mcpServers'] if v['id']==params.get('id')),None)
                if existing is None:raise ValueError('Server no longer exists')
                if any(existing.get(k)!=config.get(k) for k in ('transport','url','clientId','oauth')):
                    from .remote_mcp import Vault
                    await Vault(self.store.directory,existing['id']).clear()
                await self.mcp.disconnect(existing['id'])
                server_id=existing['id'];existing.clear();existing.update(id=server_id,**config)
                self.emit('catalog',self.tools.catalog())
        elif method == "mcp-connect":
            config = next(s for s in self.store.data["mcpServers"] if s["id"]==params["id"])
            await self.mcp.connect(config, (self.store.project() or {}).get("root"))
            self.emit("catalog", self.tools.catalog())
        elif method == "mcp-disconnect":
            await self.mcp.disconnect(params["id"])
            self.emit("catalog", self.tools.catalog())
        else:
            raise ValueError("Unknown engine method: " + method)
        self.store.save()
        self.emit("state", self.store.data)
        return self.store.data

    async def delegate(self, prompt):
        project = self.store.project()
        if not project: raise ValueError("Open a project before delegating")
        child_id = identity()
        child_store = Store(self.store.directory / "delegates" / child_id)
        child_store.data.update(projects=[copy.deepcopy(project)],activeProject=project["id"],model=self.store.data["model"],
            enabledTools=[t for t in self.store.data["enabledTools"] if t in ("workspace_info","list_files","read_file","search_files","load_skill")],
            skills=copy.deepcopy(self.store.data["skills"]),globalMemory=self.store.active_memory(),contextSize=self.store.data["contextSize"])
        child_store.new_session()
        async def no_review(details): return False
        child_tools = Tools(child_store, no_review, lambda *_: None, self.mcp, None)
        child = Agent(child_store,self.runtime,child_tools,lambda *_:None)
        child.turn_budget = 8
        from .agent_context import profile as active_profile
        inherited=active_profile.get()
        token=active_profile.set(dict(inherited,reviewPolicy='Read only',maxTurns=8) if inherited else dict(id=child_id,name='Project delegate',instructions='Inspect the project and report source evidence. Do not modify anything.',reviewPolicy='Read only',memoryScope='Memory off',skills=[]))
        try:
            task = await child.run(prompt)
            result = next((m["content"] for m in reversed(child_store.session()["messages"]) if m["role"]=="assistant"),"")
            return dict(childId=child_id,status=task["status"],result=result,tools=child_store.data["enabledTools"],checkpoints=task["checkpoints"])
        finally:
            if token is not None:active_profile.reset(token)
            await child_tools.close()
            child_store.close()

    async def tick(self):
        while True:
            await asyncio.sleep(5)
            from .scheduling import run_due
            from .agent_jobs import run_next
            if not await run_due(self):await run_next(self)
            if self.store.data['syncState']['enabled'] and not (self.active and not self.active.done()) and now()-self.store.data['syncState'].get('lastAttempt',0)>60000:
                self.store.data['syncState']['lastAttempt']=now()
                try:await self.sync.run();self.emit('state',self.store.data)
                except Exception as error:
                    self.store.data['syncState']['warnings']=[str(error)];self.store.save();self.emit('state',self.store.data)

    async def close(self):
        await self.addons.close()
        await self.security_workspace.close()
        if self.scheduler:
            self.scheduler.cancel()
            await asyncio.gather(self.scheduler, return_exceptions=True)
        await self.dispatch("stop", {})
        for future in self.pending.values():
            if not future.done():
                future.cancel()
        await self.tools.close()
        await self.mcp.close()
        await self.integrations.close()
        await self.model_manager.close()
        await self.runtime.stop()
        self.store.close()
        self.diagnostics.close()


async def serve(args):
    clients = set()
    def emit(event, data):
        line = json.dumps(dict(event=event, data=data), ensure_ascii=False)
        try:
            print(line, flush=True)
        except BrokenPipeError:
            pass
        for writer in list(clients):
            if writer.is_closing() or writer.transport.get_write_buffer_size()>64*1024*1024:
                clients.discard(writer); writer.close()
            else:
                writer.write((line+"\n").encode())
    service = Service(args.data, args.runtime, emit, args.endpoint)
    service.scheduler = asyncio.create_task(service.tick())
    requests = Requests(service, service.emit)
    async def connect(reader, writer):
        clients.add(writer)
        try:
            while line := await reader.readline():
                message = json.loads(line)
                requests.start(writer, message)
        except (ValueError, OSError):
            pass
        finally:
            await requests.close(writer)
            clients.discard(writer); writer.close()
            await writer.wait_closed()
    socket_path = ipc_socket_path(service.store.directory)
    compatibility_path = service.store.directory / "engine.sock"
    if compatibility_path.exists() or compatibility_path.is_symlink(): compatibility_path.unlink()
    if socket_path.exists() or socket_path.is_symlink():
        endpoint = socket_path.lstat()
        if not socket_path.is_socket() or endpoint.st_uid != os.getuid():
            raise RuntimeError("A non-owned file occupies the Wixal IPC endpoint")
        socket_path.unlink()
    socket_server = await asyncio.start_unix_server(connect, path=socket_path, limit=24*1024*1024)
    os.chmod(socket_path,0o600)
    compatibility_path.symlink_to(socket_path)
    try:
        while line := await asyncio.to_thread(sys.stdin.buffer.readline, 24*1024*1024):
            try:
                message = json.loads(line)
                requests.start("desktop", message)
            except ValueError:
                emit("error", dict(message="Invalid engine request"))
    finally:
        socket_server.close(); await socket_server.wait_closed()
        for writer in list(clients): writer.close()
        socket_path.unlink(missing_ok=True)
        compatibility_path.unlink(missing_ok=True)
        await requests.close()
        await service.close()


def parser():
    result = argparse.ArgumentParser(description="Wixal native Python agent engine")
    result.add_argument("--data", default=str(Path.home()/"Library/Application Support/Wixal Native"))
    result.add_argument("--runtime", default=str(Path(__file__).resolve().parents[3]/"runtime/ollama"))
    result.add_argument("--endpoint", help="Explicit local model endpoint for development/testing")
    return result


def main():
    os.umask(0o077)
    args = parser().parse_args()
    if args.endpoint and not args.endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise SystemExit("Development endpoint must use loopback")
    asyncio.run(serve(args))
