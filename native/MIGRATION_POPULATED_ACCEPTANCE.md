# Populated migration acceptance

Date: 2026-10-07 (Australia/Sydney)

## Result

The native importer passed a populated skills, schedules, and MCP end-to-end workload using Wixal's production service APIs. The source collections were created through `project-add`, `skill-add`, `schedule-add`, and `mcp-add`, persisted by the actual native `Store`, serialized to a temporary legacy workspace JSON file, and imported through the normal `legacy-import` service dispatch. No source collection rows were inserted directly.

The test imported **3 skills, 3 schedules, and 2 usable MCP stdio servers**. A third MCP record carrying a conspicuous fake credential marker was correctly skipped with a warning, and the marker did not reach target state. The test then explicitly connected one imported server and called its real `echo` tool (`migration reconnect round trip`), disconnected it, restarted the target Store, and checked persistence. An unchanged second import added zero records; all three source skills, all three source schedules, and both imported servers were counted as duplicates. A native skill and schedule added after the first import survived the repeat import.

Imported schedules preserved their selected local model name and both `latest` and `skip` missed-run policies. They were disabled, marked `importedPaused`, and assigned guest ownership so import does not silently start recurring work. Imported MCP servers retained their executable and argument arrays, remained disconnected until explicitly reconnected, and contained no credentials.

## Evidence

The reproducible acceptance command is:

```sh
python3 native/scripts/migration-populated-acceptance.py
```

The latest run completed in **0.068 seconds**. The source workspace JSON was 56,228 bytes with SHA-256 `228d23e349c147a41815614d81ac87d14f0636c012d35d9be61343a6eb0b872e`. The reopened target state had SHA-256 `06bfd57192e17219620732d8445c4a8df1d391340abee06f0b5a63eaac8098b0`. The source file's bytes and hash remained unchanged through both imports. Machine-readable counts, policies, warnings, and hashes are in [migration-populated-acceptance.json](../artifacts/native/migration-populated-acceptance.json).

Focused importer regressions also passed:

```sh
cd native/tests
../.venv/bin/python -m unittest \
  test_integration_workloads.MigrationWorkloads \
  test_parity_fixes.ParityFixes.test_migration_settings_records_idempotency_and_no_secrets -v
```

Result: **3 tests passed**, including 100-record-per-collection persistence/repeat-import workload and malformed collection/record handling. The acceptance script also passed `python3 -m py_compile native/scripts/migration-populated-acceptance.py`.

Implementation paths exercised: [migration.py](engine/wixal/migration.py), [service.py](engine/wixal/service.py), [storage.py](engine/wixal/storage.py), and [mcp.py](engine/wixal/mcp.py). The added executable workload is [migration-populated-acceptance.py](scripts/migration-populated-acceptance.py).

## Evidence boundary and remaining gap

### Actual Electron source export

I also launched the Electron 0.7.9 UI in a disposable user-data directory and saved an MCP server through **Tool kit → Connect external tools → Save server**. The actual Electron `workspace.json` was copied byte-for-byte to [electron-mcp-source-workspace.json](../artifacts/native/electron-mcp-source-workspace.json) and imported with the production native `Store.import_legacy` method into a fresh isolated target. The run passed: one server imported with the exact executable and arguments, one “imported disconnected” warning appeared, the source remained byte-for-byte unchanged, and the target contained no credentials. The saved server was deliberately left disconnected; explicit reconnect and a successful tool call are covered by the preceding native service workload.

Exact source export SHA-256: `cf3e88daa96b1a01dae1177aa54de84d9f7a9ab839ef97d14e7ef0d5e278f912` (2,126 bytes). Exact normalized imported native state SHA-256: `23a6f9af814e7ee9702f81e17faddfe9c5561c6f27fad63b0099e455494378b1`. The full source-side report is [migration-electron-source-acceptance.json](../artifacts/native/migration-electron-source-acceptance.json). The reproducible UI run is:

```sh
node native/scripts/migration-electron-source-acceptance.cjs
```

### Skills and schedules in Electron history

The real Electron export contained **0 skills and 0 schedules**. I checked `app/store.cjs`, `app/main.cjs`, `app/preload.cjs`, and `ui/renderer.js` at the current Wixal 0.7.9 source, and searched their full Git history. The Electron app has no `skill-add` or `schedule-add` API and no UI flow that writes either collection; its store initializes `mcpServers`, but not `skills` or `schedules`. The earliest Electron MCP UI/API was introduced in commit `414f5b4` (0.6.0); the history searches for skill/schedule creation methods return no matches. Existing JSON acceptance and backup records in the repository contain empty legacy collections or are native workload data, not historical Electron exports populated with these entries. No genuine older export containing populated skills/schedules was found.

So the populated native API migration workload above verifies the importer's collection rules, persistence, pause/reconnect behavior, and repeat-import safety. A populated **Electron-origin** skills/schedules export cannot be accepted from this repository's app history because Electron did not create those records. This gap is limited to historical source provenance; the actual Electron-origin MCP import has now passed.

The local MCP test covers legacy stdio command/argument migration and explicit reconnect. Electron's current MCP implementation is stdio-based; an HTTP endpoint is not a valid legacy MCP record for this importer and must be configured again in native Settings. No account credential, actual API token, remote endpoint, or live user workspace was accessed. Test data and the disposable workspaces were removed after the run; the JSON evidence report retains only counts, non-secret command metadata, and hashes.
