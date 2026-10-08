#!/usr/bin/env python3
"""End-to-end migration exercise over real native service APIs and persisted stores.

The Electron workspace inspected for this run has no skill/schedule/MCP creation
controls. This acceptance therefore creates the populated source with the native
service's production skill-add, schedule-add, and mcp-add APIs, serializes the
resulting saved state into the legacy workspace JSON shape, and imports it via
the production legacy-import API. It does not insert source collection rows.
"""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "native" / "engine"))
from wixal.service import Service
from wixal.mcp_names import prefix


def sha256(data):
    return hashlib.sha256(data).hexdigest()


async def main():
    report = {"status": "running", "started": time.time(), "sourceCreation": {}, "import": {}}
    fixture = ROOT / "native" / "tests" / "mcp_fixture.py"
    skill_paths = [ROOT / "README.md", ROOT / "native" / "README.md",
                   ROOT / "native" / "IMPLEMENTATION_STATUS_2026-10-07.md"]
    assert all(path.is_file() and path.stat().st_size < 24_000 for path in skill_paths)
    with tempfile.TemporaryDirectory(prefix="wixal-migration-live-") as temp:
        base = Path(temp)
        project = base / "migration-project"
        project.mkdir()
        source_dir, target_dir = base / "source", base / "target"
        source = Service(source_dir, ROOT / "runtime" / "ollama", lambda *_: None)
        target = None
        try:
            await source.dispatch("project-add", {"root": str(project)})
            # Skills are imported via the same bounded Markdown-file API used by the app.
            for path in skill_paths:
                await source.dispatch("skill-add", {"path": str(path)})
            await source.dispatch("settings", {"model": "migration-observed-local-model"})
            for minutes, policy, prompt in (
                (15, "latest", "Review the project README and summarize its setup steps."),
                (60, "skip", "Check the current implementation status and list open items."),
                (1440, "latest", "Review the native app documentation for stale workflow details."),
            ):
                await source.dispatch("schedule-add", {
                    "prompt": prompt, "intervalSeconds": minutes * 60, "missedRunPolicy": policy,
                })
            safe_mcp = []
            for name in ("Repository fixture echo", "Documentation fixture echo"):
                safe_mcp.append(await source.dispatch("mcp-add", {
                    "name": name, "command": sys.executable, "args": [str(fixture)],
                }))
            # A conspicuous fake marker verifies credential-bearing commands are excluded.
            await source.dispatch("mcp-add", {
                "name": "Excluded credential fixture", "command": sys.executable,
                "args": ["--secret", "MIGRATION_TEST_MARKER_ONLY"],
            })
            source_state = await source.dispatch("hello", {})
            state = copy.deepcopy(source_state["state"])
            # Serialize only legacy workspace fields. Every collection item above came
            # from production dispatch APIs and had already been committed by Store.save.
            legacy = {key: state[key] for key in (
                "projects", "sessions", "memories", "tasks", "skills", "schedules", "mcpServers"
            )}
            legacy.update({"ui": state["ui"], "model": state["model"], "mode": state["mode"],
                           "contextSize": state["contextSize"], "enabledTools": state["enabledTools"]})
            source_file = base / "legacy-workspace.json"
            source_file.write_text(json.dumps(legacy, ensure_ascii=False, indent=2))
            source_bytes = source_file.read_bytes()
            source_state_summary = {
                "creationApi": ["project-add", "skill-add", "schedule-add", "mcp-add"],
                "skills": len(legacy["skills"]), "schedules": len(legacy["schedules"]),
                "mcpServersIncludingExcludedFixture": len(legacy["mcpServers"]),
                "safeMcpServers": len(safe_mcp), "sourcePersistedBeforeExport": True,
                "sourceJsonBytes": len(source_bytes), "sourceJsonSha256": sha256(source_bytes),
            }
            report["sourceCreation"] = source_state_summary
        finally:
            await source.close()

        target = Service(target_dir, ROOT / "runtime" / "ollama", lambda *_: None)
        try:
            imported = await target.dispatch("legacy-import", {"path": str(source_file)})
            data = target.store.data
            assert imported["counts"]["skills"] == 3, imported
            assert imported["counts"]["schedules"] == 3, imported
            assert imported["counts"]["mcpServers"] == 2, imported
            assert imported["skippedExisting"]["skills"] == 0
            assert len(data["skills"]) == 3 and len(data["schedules"]) == 3 and len(data["mcpServers"]) == 2
            assert all(s["model"] == "migration-observed-local-model" for s in data["schedules"])
            assert [s["missedRunPolicy"] for s in data["schedules"]] == ["latest", "skip", "latest"]
            assert all(not s["enabled"] and s["importedPaused"] and s["owner"] == "guest" for s in data["schedules"])
            expected_schedules = [s for s in legacy["schedules"]]
            assert [(s["model"], s["missedRunPolicy"]) for s in data["schedules"]] == [
                (s["model"], s["missedRunPolicy"]) for s in expected_schedules
            ]
            assert all(m["credentialsExcluded"] is False for m in data["mcpServers"])
            assert [(s["command"], s["args"]) for s in data["mcpServers"]] == [
                (s["command"], s["args"]) for s in legacy["mcpServers"]
                if "command" in s and not any(word in " ".join([s["command"], *s.get("args", [])]).lower()
                                               for word in ("token", "password", "secret", "api-key", "api_key", "authorization", "bearer"))
            ]
            assert "MIGRATION_TEST_MARKER_ONLY" not in json.dumps(data)
            assert any("credential-bearing invocation excluded" in warning for warning in imported["warnings"])
            assert sum("imported paused" in warning for warning in imported["warnings"]) == 3
            assert sum("imported disconnected" in warning for warning in imported["warnings"]) == 2
            assert all(sid not in target.mcp.connections for sid in [s["id"] for s in data["mcpServers"]])
            imported_schedules = copy.deepcopy(data["schedules"])
            imported_mcp = copy.deepcopy(data["mcpServers"])

            # Prove reconnect is explicit, usable, and independent of imported credentials.
            first = data["mcpServers"][0]
            await target.dispatch("mcp-connect", {"id": first["id"]})
            definitions = target.mcp.definitions()
            echo = next(item for item in definitions if item["function"].get("original") == "echo")
            await target.dispatch("settings", {"enabledTools": [
                *target.store.data["enabledTools"], echo["function"]["name"],
            ]})
            await target.dispatch("settings", {"approvalMode": "bypass"})
            result = await target.dispatch("tool", {"name": echo["function"]["name"], "arguments": {"text": "migration reconnect round trip"}})
            assert "migration reconnect round trip" in str(result)
            assert first["id"] in target.mcp.connections
            await target.dispatch("mcp-disconnect", {"id": first["id"]})
            assert first["id"] not in target.mcp.connections
            assert source_file.read_bytes() == source_bytes

            # Add native records through production APIs, repeat the same import, and
            # verify original incoming IDs are skipped without overwriting local state.
            await target.dispatch("skill-add", {"path": str(skill_paths[0])})
            await target.dispatch("schedule-add", {
                "prompt": "Native-only schedule retained after import.", "intervalSeconds": 7200,
                "missedRunPolicy": "skip",
            })
            local_skill = target.store.data["skills"][-1]["id"]
            local_schedule = target.store.data["schedules"][-1]["id"]
            again = await target.dispatch("legacy-import", {"path": str(source_file)})
            assert all(count == 0 for count in again["counts"].values()), again
            assert again["skippedExisting"]["skills"] == 3
            assert again["skippedExisting"]["schedules"] == 3
            assert again["skippedExisting"]["mcpServers"] == 2
            assert any(s["id"] == local_skill for s in target.store.data["skills"])
            assert any(s["id"] == local_schedule for s in target.store.data["schedules"])
            assert source_file.read_bytes() == source_bytes

            expected = copy.deepcopy(target.store.data)
            await target.close()
            target = Service(target_dir, ROOT / "runtime" / "ollama", lambda *_: None)
            persisted = target.store.data
            assert persisted["skills"] == expected["skills"]
            assert persisted["schedules"] == expected["schedules"]
            assert persisted["mcpServers"] == expected["mcpServers"]
            assert not target.mcp.connections
            assert source_file.read_bytes() == source_bytes
            report["import"] = {
                "firstCounts": imported["counts"], "firstSkipped": imported["skippedExisting"],
                "secondCounts": again["counts"], "secondSkipped": again["skippedExisting"],
                "scheduleModels": [s["model"] for s in imported_schedules],
                "missedRunPolicies": [s["missedRunPolicy"] for s in imported_schedules],
                "schedulesPaused": all(not s["enabled"] for s in imported_schedules),
                "mcpCommandsPreserved": [s["command"] for s in imported_mcp],
                "mcpArgumentsPreserved": [s["args"] for s in imported_mcp],
                "mcpInitiallyDisconnected": True, "mcpExplicitReconnectToolCall": result,
                "mcpDisconnectedAfterTest": not target.mcp.connections,
                "credentialFixtureExcluded": "MIGRATION_TEST_MARKER_ONLY" not in json.dumps(persisted),
                "sourceUnchanged": True, "targetPersistsAfterRestart": True,
                "nativeEditsSurviveRepeatImport": True,
                "targetStateSha256": sha256(json.dumps(persisted, sort_keys=True, ensure_ascii=False).encode()),
            }
            report["status"] = "passed"
        finally:
            await target.close()
        report["finished"] = time.time()
        report["durationSeconds"] = round(report["finished"] - report["started"], 3)
        output = ROOT / "artifacts" / "native" / "migration-populated-acceptance.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
