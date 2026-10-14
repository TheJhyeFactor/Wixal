# Native Agents workspace implementation

14 October 2026. Implemented and installed locally at `/Applications/Wixal.app`. This is a local update on the existing alpha line, not a new public release.

## Delivered

- Agents mode uses Wixal's existing sidebar for Agents, Skills, Nodes, Schedules, Runs, Workflows and Tools. When the main sidebar is collapsed, the workspace retains responsive local navigation. Theme palettes, fonts, button styles and the core app rail are unchanged.
- Saved agents use compact rows and open an Overview containing configuration, setup inspection, instructions and task actions. Existing editors, history, workflow execution and schedule controls remain connected to the engine.
- Skills is a dedicated library. Import Markdown/SKILL.md, inspect snapshots/resources, assign procedures to agents, review candidate evaluations, promote verified procedures and inspect/restore versions.
- Nodes displays the actual native engine/model state and the existing optional Linux worker's last inspection. Inspection does not install a runtime, start a VM or dispatch a scan. The node surface is not a general remote-device pairing system.
- Optional per-agent tool groups are persisted and enforced both during discovery and execution. Existing profiles retain automatic access to available groups unless restricted. Planning, checkpoint retrieval and skill text loading remain foundational capabilities; authority and read-only policy can narrow access further.
- Setup inspection reports missing models/skills, project availability, action policy and verification defaults. Tool capability advertisement remains distinct from measured model qualification.
- `workspace_info` exposes eligible saved specialists. `delegate_task(agent_id=...)` uses the specialist's instructions, model and selected skills in an isolated read-only child. Parent and specialist restrictions intersect, budgets narrow, private notes/history are excluded, and recursion/external services/writes remain unavailable. Writable specialists continue to use existing isolated workflow branches and reviewed merge.
- Parent-linked child assignment state, errors, results and checkpoints are retained and visible in live runs. Cancellation is retained; unfinished assignments become interrupted on restart.
- A real-model failure exposed that a skill task phrased as “reading evidence.txt” did not reliably receive the file reader in its initial schema set. File routing now recognises that phrasing and common named project files, while existing execution permissions remain enforced.

## Validation

Evidence root: `artifacts/native/agent-workspace-2026-10-14/`.

- Final source engine suite: **577 tests passed** (`engine-tests-final.log`).
- Focused workspace, agent-runtime and Hermes-adaptation suite: **55 tests passed** (`focused-final.log`).
- Production Swift interaction checks: **32 passed** (`swift-interactions.log`).
- Native release build, source manifest, deep/strict signature and installed identity checks passed. Reports: `package-verification-final.json`, `installed-verification-final.json`, `install-final.json`.
- Six real-model checks passed against the staged helper, then the same six passed again against the installed helper, with matching helper identity. Model: `hf/unsloth/qwen3.5-9b-q4_k_m:03b74727a860`. Reports: `real-model-final/results.json`, `real-model-installed-repeat/results.json`.
- Checks: configuration readiness, actual skill loading/source reading, assignment to a saved specialist with child file-read evidence, reviewed source edit plus the actual test command and independent verification, actual worker inspection, and a due routine executed by the background helper with desktop closed.
- Native installed UI exercised all seven destinations, worker inspection/unavailable state, Markdown import, the agent editor's skill assignment and tool-group restrictions, acknowledged save, setup inspection and collapsed-sidebar fallback. `ui-persisted.json` confirms saved groups/skill assignment and that the fixture schedule stayed paused. UI tests used isolated Application Support storage and a controlled model endpoint; they do not count as real-model checks.
- At installation, hashes for the normal workspace's sessions, projects, agent profiles, tasks, schedules, skills, selected model, active project/session, appearance and setup were unchanged (`workspace-preservation.json`). The normal workspace was reopened afterward and the new navigation was inspected there.
- Install inventory: one canonical installed app and zero obsolete installations (`install-inventory.json`). The installer retained compressed rollback copies outside Applications.

The earlier `real-model/` attempt is retained as failed/interrupted development evidence. It is not part of the final passing results. Final reports identify the tested helper; no historical result is relabelled as current.

## Remaining boundaries

These repeated bounded tasks establish the tested Qwen/helper path, not reliability of every installed model or arbitrary tasks. No new hosted provider, unrestricted child execution, general remote-node protocol, messaging gateway, VM installation, notarisation, public release or model training was performed. Worker inspection reported the optional runtime unavailable; no new Linux scan is claimed. The background test invokes the production helper directly after making a disposable routine due; it does not qualify sleep/wake, reboot or LaunchAgent timing.

The design preview remains separate from native evidence. No preview's fixture agent, task or status was inserted into the normal user workspace.
