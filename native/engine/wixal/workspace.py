"""Workspace UI actions, distinct from model-controlled tools."""
import asyncio
import copy
import json
from .storage import identity, now


async def dispatch(service, method, params):
    store = service.store
    if method == "assessment-cancel":
        if service.active and not service.active.done():
            service.active.cancel()
            await asyncio.gather(service.active, return_exceptions=True)
        return True, True
    methods = {"session-rename", "session-copy", "session-delete", "memory-add", "memory-update", "memory-settings", "assessment-run", "mcp-delete", "mcp-status", "task-dismiss", "schedule-toggle"}
    if method not in methods:
        return False, None
    if method == "mcp-status":
        return True, [dict(id=config["id"], connected=config["id"] in service.mcp.connections,
                           tools=len(service.mcp.connections.get(config["id"], {}).get("definitions", []))) for config in store.data["mcpServers"]]
    service.idle()
    if method.startswith("session-"):
        session = next((s for s in store.data["sessions"] if s["id"] == params.get("id")), None)
        if session is None:
            raise ValueError("Conversation no longer exists")
        if method == "session-rename":
            title = params.get("title", "")
            if not isinstance(title, str) or not title.strip() or len(title)>120:
                raise ValueError("Enter a conversation name below 120 characters")
            session["title"] = title.strip()
        elif method == "session-copy":
            return True, "\n\n".join(f"{m.get('role', '').title()}: {m.get('content', '')}" for m in session["messages"])
        else:
            # Explicit UI confirmation precedes this method; it never deletes project files.
            await service.tools.close(session["id"])
            store.data["sessions"].remove(session)
            store.data["tasks"] = [t for t in store.data["tasks"] if t.get("sessionId") != session["id"]]
            if store.data["activeSession"] == session["id"]:
                store.select_project(session.get("projectId"))
    elif method == "memory-settings":
        project = store.project()
        if not project:
            raise ValueError("Open a project to configure its memory")
        mode, size = params.get("mode", project.get("memoryMode", "project")), params.get("size", project.get("memorySize", 24000))
        if mode not in ("project", "global", "both", "off") or size not in (8000, 24000, 48000):
            raise ValueError("Choose a memory scope and budget")
        if sum(len(m["content"]) for m in store.memories()) > size:
            raise ValueError("This budget is smaller than your saved notes. Edit or remove notes first.")
        project.update(memoryMode=mode, memorySize=size)
    elif method in ("memory-add", "memory-update"):
        if not store.project():
            raise ValueError("Open a project to save project memory")
        if method == "memory-add":
            store.memory.save(params.get('content'),'project')
        else:
            memory = next((m for m in store.memories() if m["id"] == params.get("id")), None)
            text = params.get("content", "")
            if memory is None or not isinstance(text, str) or not text.strip() or len(text)>4000:
                raise ValueError("Choose a saved note and enter 1–4,000 characters")
            if store.project().get("memoryMode") in ("off", "global"):
                raise ValueError("Project memory is disabled")
            used = sum(len(m["content"]) for m in store.memories() if m["id"] != memory["id"])
            if used+len(text.strip())>store.project().get("memorySize", 24000):
                raise ValueError("Project memory budget is full")
            store.memory.save(text.strip(),'project',replace=memory['id'])
    elif method == "mcp-delete":
        await service.mcp.disconnect(params["id"])
        config=next((s for s in store.data["mcpServers"] if s["id"]==params["id"]),None)
        if config and config.get("oauth"):
            from .remote_mcp import Vault
            await Vault(store.directory,config["id"]).clear()
        store.data["mcpServers"] = [s for s in store.data["mcpServers"] if s["id"] != params["id"]]
        from .mcp_names import prefix
        removed=prefix(params["id"]);configured=[prefix(c["id"]) for c in store.data["mcpServers"]]
        valid = {t["function"]["name"] for t in service.tools.catalog()}
        store.data["enabledTools"] = [name for name in store.data["enabledTools"] if not name.startswith(removed) and (name in valid or any(name.startswith(p) for p in configured))]
        service.emit("catalog", service.tools.catalog())
    elif method == "schedule-toggle":
        schedule = next(s for s in store.data["schedules"] if s["id"]==params["id"])
        if not isinstance(params.get("enabled"), bool):raise ValueError("Choose enabled or paused")
        schedule["enabled"] = params["enabled"]
        if params["enabled"]:schedule["nextRun"] = now()+schedule["intervalSeconds"]*1000
    elif method == "task-dismiss":
        task = next(t for t in store.data["tasks"] if t["id"]==params["id"])
        if task["status"] not in ("queued", "failed", "interrupted", "cancelled", "paused"):
            raise ValueError("This task cannot be dismissed")
        task.update(status="dismissed", updated=now())
    elif method == "assessment-run":
        name = params.get("name")
        if name not in ("network_scan", "website_assess", "website_simulate"):
            raise ValueError("Unknown assessment")
        service.active = asyncio.create_task(run_assessment(service, name, params.get("arguments", {})))
        return True, await service.active
    store.save()
    return True, store.data


async def run_assessment(service, name, arguments):
    store = service.store
    session = store.session() or store.new_session()
    task = dict(id=identity(), sessionId=session["id"], projectId=session.get("projectId"),
                prompt=f"{name}: {arguments.get('target') or arguments.get('url') or 'local fixtures'}",
                source="Tool kit", status="running", created=now(), checkpoints=[])
    store.data["tasks"].append(task)
    store.save();service.emit("state", store.data)
    result = None
    service.emit("assessment-progress", dict(taskId=task["id"], name=name, state="running"))
    try:
        result = await service.tools.execute(name, arguments, session["id"])
        if name == "network_scan" and isinstance(result, dict) and result.get("session_id"):
            job = service.tools.jobs[result["session_id"]]
            while job["state"] == "running":
                service.emit("assessment-progress", dict(taskId=task["id"], name=name, output=job["output"][-24000:], state=job["state"]))
                await asyncio.sleep(.25)
            result = await service.tools.read_job(dict(session_id=job["id"], wait_ms=0, max_chars=100000), session["id"])
        if isinstance(result,str) and "declined" in result.lower():task["status"]="cancelled"
        else:task["status"]="completed"
        checkpoint = dict(tool=name, arguments=copy.deepcopy(arguments), status="finished", result=result)
        task["checkpoints"].append(checkpoint);task["result"]=result
        session["messages"].extend([dict(role="user", content=task["prompt"], created=now()),
                                     dict(role="tool", tool_name=name, content=json.dumps(result, ensure_ascii=False), created=now())])
        store.data.setdefault("assessmentResults", []).append(dict(id=task["id"], name=name, arguments=arguments, result=result, created=now(), sessionId=session["id"], projectId=session.get("projectId")))
        store.data["assessmentResults"] = store.data["assessmentResults"][-30:]
        return result
    except asyncio.CancelledError:
        task["status"]="cancelled"
        await service.tools.close(session["id"])
        raise
    except Exception as error:
        task.update(status="failed", error=str(error))
        raise
    finally:
        task["updated"]=now();store.save();service.emit("state",store.data)
        service.emit("assessment-progress",dict(taskId=task["id"],name=name,state=task["status"]))
