"""Validate an explicitly signed-in real account without recording identity or secrets.

Saves the user's actual Wixal model/memory requirement, then restores the original instructions.
Creates, applies and removes only its own
temporary cloud preset; existing presets and guest instructions are retained.
"""
import asyncio
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


async def main():
    reader,writer=await asyncio.open_unix_connection(Path.home()/"Library/Application Support/Wixal Native/engine.sock",limit=16*1024*1024)
    counter=0
    async def call(method,params=None):
        nonlocal counter
        counter+=1;identifier=f"account-check-{counter}"
        writer.write((json.dumps(dict(id=identifier,method=method,params=params or {}))+"\n").encode());await writer.drain()
        while line:=await asyncio.wait_for(reader.readline(),90):
            row=json.loads(line)
            if row["event"]=="response" and row["data"]["id"]==identifier:
                data=row["data"]
                if data.get("error"):raise RuntimeError(data["error"])
                return data["result"]
        raise RuntimeError("Helper disconnected")
    report=dict(status="running",implementation="real account service and native Keychain")
    preset_id=None;memory_backup=None;workspace_backup=None;validation_session=None
    try:
        hello=await call("hello");state=hello["state"];account=state.get("account",{})
        if not account.get("signedIn"):
            account=await call("account-restore");state=(await call("hello"))["state"]
            report["existingKeychainCredentialRestored"]=bool(account.get("signedIn"))
        if not account.get("signedIn") or not (account.get("profile") or {}).get("verified"):
            raise RuntimeError("Sign in and verify the account in the app before running this check")
        guest=state.get("globalMemory","")
        refreshed=await call("global-memory-refresh")
        memory=refreshed["globalMemory"]
        marker="Wixal should make small lightweight open-source models efficient by using relevant project and global memory while retaining complete working features."
        memory_backup=memory
        await call("global-memory-save",dict(content=marker))
        saved=(await call("hello"))["state"]
        assert saved["globalMemory"]==guest and saved["account"]["globalMemory"]==marker and marker!=guest
        await call("global-memory-save",dict(content=memory));memory_backup=None
        report["memorySavePreservedGuest"]=True
        report["distinctAccountValueRestored"]=True
        workspace_backup=dict(projectId=state.get("activeProject"),sessionId=state.get("activeSession"),mode=state.get("mode","agent"))
        preference=marker
        memory_backup=memory
        await call("global-memory-save",dict(content=preference))
        await call("project-select",dict(id=None))
        await call("session-new")
        validation_session=(await call("hello"))["state"]["activeSession"]
        await call("settings",dict(mode="chat"))
        context=await call("context-info")
        assert context["memoryScope"]=="account" and context["globalMemoryIncluded"]
        result=await call("chat",dict(text="What is my saved preference for small lightweight open-source models and memory in Wixal? Answer from my global preferences. Do not use tools or invent preferences."))
        current=(await call("hello"))["state"]
        conversation=next(s for s in current["sessions"] if s["id"]==validation_session)
        response=next(m["content"] for m in reversed(conversation["messages"]) if m["role"]=="assistant" and m.get("content"))
        assert result["status"]=="completed" and "memory" in response.lower() and any(word in response.lower() for word in ("small","lightweight","efficient")),response
        report["realModelUsedAccountPreferences"]=True
        await call("global-memory-save",dict(content=memory));memory_backup=None
        await call("settings",dict(mode=workspace_backup["mode"]))
        await call("project-select",dict(id=workspace_backup["projectId"]))
        if workspace_backup["sessionId"]:await call("session-select",dict(id=workspace_backup["sessionId"]))
        await call("session-archive",dict(id=validation_session))
        validation_session=None;workspace_backup=None
        name="Wixal native current model and context acceptance"
        existing={p["id"] for p in saved["account"]["presets"]}
        created=await call("account-preset-save",dict(name=name))
        preset=next(p for p in created["presets"] if p["id"] not in existing and p["name"]==name)
        preset_id=preset["id"]
        await call("account-preset-apply",dict(id=preset_id))
        await call("account-preset-delete",dict(id=preset_id));preset_id=None
        report["cloudPresetCreateApplyDelete"]=True
        restored=await call("account-restore")
        assert restored["signedIn"] and restored["profile"]["verified"]
        current=(await call("hello"))["state"]
        assert current["globalMemory"]==guest and current["account"]["globalMemory"]==memory
        report["nativeKeychainRestore"]=True
        report["status"]="passed"
    except BaseException as error:
        report["status"]="failed";report["error"]=str(error);raise
    finally:
        if memory_backup is not None or workspace_backup is not None:
            try:await call("stop")
            except Exception:pass
        if memory_backup is not None:
            try:await call("global-memory-save",dict(content=memory_backup))
            except Exception:report["memoryRestorationPending"]=True
        if workspace_backup is not None:
            try:
                await call("settings",dict(mode=workspace_backup["mode"]))
                await call("project-select",dict(id=workspace_backup["projectId"]))
                if workspace_backup["sessionId"]:await call("session-select",dict(id=workspace_backup["sessionId"]))
                if validation_session:await call("session-archive",dict(id=validation_session))
            except Exception:report["workspaceRestorationPending"]=True
        if preset_id:
            try:await call("account-preset-delete",dict(id=preset_id))
            except Exception:report["cleanupPending"]=True
        (ROOT/"artifacts/native/account-acceptance.json").write_text(json.dumps(report,indent=2))
        writer.close();await writer.wait_closed()
    print(json.dumps(report))


if __name__=="__main__":asyncio.run(main())
