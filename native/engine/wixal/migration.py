"""Validated, atomic import of the Electron workspace into native storage."""
import copy
import json
import hashlib
import re
from pathlib import Path
from .storage import now
from .conversation import attachments


def import_workspace(store, source, *, preview=False, preserve_preferences=False, expected_digest=None):
    source=Path(source).expanduser().resolve(strict=True)
    if source.stat().st_size>128*1024*1024: raise ValueError("Workspace exceeds the 128 MB import limit")
    with source.open("rb") as stream:raw=stream.read(128*1024*1024+1)
    if len(raw)>128*1024*1024:raise ValueError("Workspace exceeds the 128 MB import limit")
    digest=hashlib.sha256(raw).hexdigest()
    if expected_digest is not None and digest != expected_digest:
        raise ValueError("The source changed after preview. Choose it again to review the updated records.")
    legacy=json.loads(raw)
    if not isinstance(legacy,dict) or not all(isinstance(legacy.get(k),list) for k in ("projects","sessions","memories")):
        raise ValueError("This is not a Wixal workspace file")
    native_backup=legacy.get("wixalBackupVersion")==1
    if "wixalBackupVersion" in legacy and not native_backup:raise ValueError("Unsupported native backup version")
    candidate=copy.deepcopy(store.data)
    counts,warnings,skipped={},[],{}
    def warn(key,index,reason): warnings.append(f"{key} record {index+1}: {reason}")
    for key in ("projects","sessions","memories","agentProfiles","agentWorkflows","tasks","skills","schedules","workflowRuns","skillCandidates","agentJobs","mcpServers"):
        records=legacy.get(key,[])
        if not isinstance(records,list): raise ValueError(f"Invalid {key} collection")
        candidate.setdefault(key,[])
        seen={v["id"] for v in candidate[key]}
        counts[key]=0;skipped[key]=0
        for index,raw in enumerate(records):
            if not isinstance(raw,dict) or not isinstance(raw.get("id"),str) or not 1<=len(raw["id"])<=200:
                warn(key,index,"invalid identifier; skipped");continue
            if raw["id"] in seen:
                skipped[key]+=1;continue
            value=copy.deepcopy(raw)
            try:
                projects={p["id"] for p in candidate["projects"]}
                if key=="projects":
                    if not isinstance(value.get("root"),str) or not isinstance(value.get("name"),str): raise ValueError("missing project name or folder")
                    value={k:v for k,v in value.items() if k in ("id","name","root","created","memoryMode","memorySize","approvalMode")}
                    if value.get("memoryMode") not in ("project","global","both","off"):value["memoryMode"]="project"
                    if value.get("memorySize") not in (8000,24000,48000):value["memorySize"]=24000
                    value["approvalMode"]="review"
                else:
                    if value.get("projectId") is not None and value["projectId"] not in projects:raise ValueError("unknown project")
                if key=="sessions":
                    if not isinstance(value.get("messages"),list):raise ValueError("missing messages")
                    messages=[]
                    for message in value["messages"]:
                        if not isinstance(message,dict) or message.get("role") not in ("system","user","assistant","tool") or not isinstance(message.get("content",""),str):raise ValueError("invalid message")
                        message={k:v for k,v in message.items() if k in ("role","content","created","tool_calls","tool_name","usage","handoff") or native_backup and k in ("id","displayContent","memoryReferences")}
                        message.setdefault("content","")
                        original=value["messages"][len(messages)]
                        images=original.get("images",[])
                        if not isinstance(images,list):raise ValueError("invalid saved images")
                        prepared=[dict(type="image",name=(original.get("imageNames") or [])[i] if i<len(original.get("imageNames") or []) else f"Image {i+1}",base64=image) for i,image in enumerate(images)]
                        prepared+=original.get("attachments",[]) if isinstance(original.get("attachments",[]),list) else []
                        if prepared:
                            saved=attachments(prepared,None if preview else store)
                            message["attachments"]=saved
                            message["imageIds"]=[a["imageId"] for a in saved if a["type"]=="image" and "imageId" in a]
                        if "tool_calls" in message and (not isinstance(message["tool_calls"],list) or any(not isinstance(c,dict) or not isinstance(c.get("function"),dict) for c in message["tool_calls"])):raise ValueError("invalid tool history")
                        messages.append(message)
                    value=dict(id=value["id"],projectId=value.get("projectId"),title=str(value.get("title","Imported conversation"))[:120],created=value.get("created",now()),messages=messages,**({"archivedAt":value["archivedAt"]} if value.get("archivedAt") else {}))
                    if native_backup:
                        value["mode"]=raw.get("mode") if raw.get("mode") in ("chat","agent") else "agent"
                        value["memoryOwner"]=raw.get("memoryOwner","guest") if isinstance(raw.get("memoryOwner","guest"),str) else "guest"
                        value["memoryExcluded"]=raw.get("memoryExcluded") is True
                        for field in ("agentId","scheduledRun"):
                            if field in raw:value[field]=raw[field]
                        if isinstance(raw.get("summary"),dict) and isinstance(raw["summary"].get("content"),str):value["summary"]=copy.deepcopy(raw["summary"])
                elif key=="memories":
                    if not isinstance(value.get("content"),str):raise ValueError("missing note text")
                    value={k:v for k,v in value.items() if k in ("id","projectId","content","created")}
                elif key in ("agentProfiles","agentWorkflows","workflowRuns","skillCandidates","agentJobs"):
                    if not native_backup:raise ValueError("Agent records require a native backup")
                    from .agent_data import imported
                    value=imported(key,value,candidate,store)
                elif key=="tasks":
                    if not isinstance(value.get("prompt"),str):raise ValueError("missing task prompt")
                    value={k:v for k,v in value.items() if k in ("id","sessionId","projectId","prompt","created","updated","result","checkpoints","status") or native_backup and k in ("owner","agentId","agentSnapshot","source","workflowRunId","successCriteria","verification","attempts","turns","securityEvidence","securityFindings")}
                    from .agent_data import validate_transfer_snapshot
                    if native_backup:value=validate_transfer_snapshot(value)
                    value.setdefault("checkpoints",[])
                    if not isinstance(value["checkpoints"],list):raise ValueError("invalid action history")
                    if value.get("status") not in ("completed","failed","cancelled","interrupted","paused","queued","needs_attention"):value["status"]="interrupted"
                elif key=="skills":
                    if not isinstance(value.get("name"),str) or not isinstance(value.get("content"),str) or len(value["content"])>24000:raise ValueError("invalid skill")
                    value={k:v for k,v in value.items() if k in ("id","name","description","content","source") or native_backup and k in ("owner","versions","evaluationIds","created","updated")}
                elif key=="schedules" and native_backup and value.get("agentID"):
                    from .agent_data import imported
                    value=imported(key,value,candidate,store)
                elif key=="schedules":
                    if not isinstance(value.get("prompt"),str) or type(value.get("intervalSeconds")) is not int or not 60<=value["intervalSeconds"]<=31*86400:raise ValueError("invalid schedule")
                    value=dict(id=value["id"],prompt=value["prompt"],intervalSeconds=value["intervalSeconds"],nextRun=now()+value["intervalSeconds"]*1000,enabled=False,projectId=value.get("projectId"),importedPaused=True,model=str(value.get("model", ""))[:200],missedRunPolicy=value.get("missedRunPolicy") if value.get("missedRunPolicy") in ("latest","skip") else "latest",owner="guest")
                elif key=="mcpServers":
                    if not isinstance(value.get("command"),str) or not isinstance(value.get("args",[]),list) or any(not isinstance(a,str) for a in value.get("args",[])):raise ValueError("invalid server command")
                    # Do not turn a credential-bearing invocation into a different command.
                    invocation=" ".join([value["command"],*value.get("args",[])])
                    if re.search(r"(?i)(token|password|secret|api[-_]?key|authorization|bearer|://[^/\s]+:[^/\s]+@)",invocation):
                        raise ValueError("credential-bearing invocation excluded; add this server again")
                    value=dict(id=value["id"],name=str(value.get("name","Imported server")),command=value["command"],args=value.get("args",[]),credentialsExcluded=bool(raw.get("env") or raw.get("oauth") or raw.get("headers")))
                if key=="schedules":warn(key,index,"imported paused; review its model and enable it in Recurring tasks")
                if key=="mcpServers":warn(key,index,"imported disconnected; reconnect in Settings"+(" and add excluded credentials" if value["credentialsExcluded"] else ""))
                candidate[key].append(value);seen.add(value["id"]);counts[key]+=1
            except (ValueError,TypeError,KeyError) as error:warn(key,index,str(error)+"; skipped")
    if not preserve_preferences and candidate.get("migration",{}).get("settingsVersion",0)<3:
        if isinstance(legacy.get("autoSummary"),bool):candidate["autoSummary"]=legacy["autoSummary"]
        ui=legacy.get("ui",{})
        if isinstance(ui,dict):
            choices={"theme":("sakura","midnight","forest","paper"),"textSize":(11,13,15,17),"appIcon":("theme","sakura","midnight","pearl","copper")}
            for key,value in ui.items():
                if key in choices and value in choices[key] or key in ("reduceMotion","launchAnimation","launchSound","sidebarCollapsed") and isinstance(value,bool):candidate["ui"][key]=value
        candidate["appearanceVersion"]=2
    if not preserve_preferences and not candidate.get("migration"):
        for key,kind in (("model",str),("globalMemory",str),("globalMemoryEnabled",bool)):
            if isinstance(legacy.get(key),kind):candidate[key]=legacy[key]
        candidate["mode"]=legacy.get("mode") if legacy.get("mode") in ("chat","agent") else "agent"
        candidate["contextSize"]=legacy.get("contextSize") if legacy.get("contextSize") in (4096,8192,16384,32768) else 8192
        project=legacy.get("activeProject")
        if project is None or any(p["id"]==project for p in candidate["projects"]):
            candidate["activeProject"]=project
            session=next((s for s in candidate["sessions"] if s["id"]==legacy.get("activeSession") and s.get("projectId")==project),None)
            candidate["activeSession"]=session["id"] if session else None
        if isinstance(legacy.get("enabledTools"),list):
            from .tools import DEFINITIONS
            supported={t["function"]["name"] for t in DEFINITIONS}
            candidate["enabledTools"]=[name for name in legacy["enabledTools"] if isinstance(name,str) and name in supported]
    if candidate["projects"] or candidate["sessions"]:
        candidate["setup"].update(entryCompleted=True,completed=True)
    candidate["migration"]=dict(source=str(source),imported=now(),counts=counts,skippedExisting=skipped,warnings=warnings,settingsVersion=3)
    result=dict(source=str(source),digest=digest,counts=counts,skippedExisting=skipped,warnings=warnings,note="Original workspace retained. Credentials and pairing excluded. Schedules imported paused; MCP servers require explicit connection.")
    if preview:return result
    previous=store.data
    try:store.data=candidate;store.save()
    except BaseException:store.data=previous;raise
    return result
