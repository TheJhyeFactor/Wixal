# Wixal agent capability review and Agents workspace proposal

14 October 2026. Design and audit only; no runtime or SwiftUI changes.

## User clarification: retain Wixal's style

The requested reference is information placement and setup organisation, especially Agents, Skills, Nodes and Cron Jobs. Preserve Wixal's existing native theme palettes, typography, buttons, spacing and visual identity. The OpenClaw/Hermes appearance replicas are reference studies, not the approved appearance for implementation.

Proposed organisation inside the existing Agents destination:

- Agents: saved specialists, selected-agent setup and task execution. Detail sections expose overview, instructions, model, tools, selected skills, memory and limits.
- Skills: a first-class procedure library with prerequisites, agent assignments and existing learning/evaluation/version controls.
- Nodes: execution devices/environments. Initially expose only the actual local Mac and existing bounded Linux worker, with their true availability and supported operations. This is not equivalent to OpenClaw's general paired-device node protocol; arbitrary remote nodes remain separate work.
- Cron Jobs / Schedules: one schedule view with linked agent, objective, timezone, next/last run, pause and run history. Naming remains a product choice; existing schedules should be reused.
- Runs and Workflows: retain direct access to execution evidence and multi-stage definitions.

## Proposed finite completion contract

Finish one supported native agent-workspace scope before adding more integrations. These are acceptance requirements, not claims that they currently pass:

1. A saved agent can discover/read project source, make a reviewed edit, run the appropriate tests and present independently checked results in one installed-app flow.
2. A selected skill can be discovered/loaded, its prerequisites explained, and its procedure used on a real task; reusable learning remains reviewed and versioned.
3. The coordinator can delegate a bounded assignment to a saved specialist, retain its evidence and correctly handle child failure/cancellation. Proposed changes use isolated branches and reviewed merge.
4. A scheduled task fires through the supported background lifecycle, produces one retained result, exposes next/last run and handles pause/missed runs according to its stated policy. Document any app/service uptime requirement.
5. Nodes reports actual local/worker readiness and supported capabilities. The bounded Linux worker must execute its supported operation and retain cancellation/cleanup results. Do not imply general remote-device support.
6. Guidance, declined actions, cancellation and restart recovery preserve evidence and never silently replay unknown effects.
7. Use a pinned build/runtime/model configuration and repeated real-model attempts with concrete outcome checks. Explain observed failures; if a behaviour cannot pass, fix it or explicitly exclude it from the supported scope rather than calling the whole workflow complete.

Track these as one deliverable with per-workflow acceptance, keeping optional expansion separate. This clarification does not authorise an engine replacement, hosted-model connection, installation or release.

## Verdict

Wixal already implements a substantial agent loop. The next useful step is to make capability readiness explicit, unify profile setup and task execution, and extend model-selected delegation to saved specialists. Adding more tools alone will not establish reliable autonomy.

This review inspected the current native source, Alpha 6/7 release notes, the 13 October cyber completion evidence, and current official Hermes documentation. It did not run Hermes or repeat Wixal installed-app/model qualification. Upstream documentation describes supported behaviour, not measured comparative performance. Recorded acceptance results retain their original build identities.

## Current implementation

| Capability | Source evidence | Assessment |
| --- | --- | --- |
| Iterative tool use | `native/engine/wixal/agent.py`, `tools.py`, `context_policy.py` | Model-selected discovery, schema validation, execution, retained results and subsequent model turns exist. |
| Planning and long tasks | `task_state.py`, `context_policy.py`, `agent.py` | Durable checklist, complete-round compaction and retained checkpoint retrieval exist. |
| Recovery and steering | `agent.py`, `run_control.py`, `recovery.py`, `agents.py` | Budgets, repeated-failure stopping, guidance, resume and uncertain-effect handling exist. Terminal continuity across engine restarts is still an acceptance gap recorded in the release notes. |
| Saved specialist profiles | `agents.py:save_profile`, `AgentBuilderView.swift` | Instructions, model, project binding, memory scope, skills, authority, success checks and budgets exist. |
| Memory | `memory.py`, `semantic.py` | SQLite FTS5 and optional local embeddings already exist. Agent-private notes exist; selectable memory scopes otherwise use project/global data rather than a full independently managed profile home. |
| Skills | `skill_resources.py`, `skill_learning.py`, `agents.py` | Text snapshots, resources, candidate learning, evaluation/promotion and rollback exist. Reading a scripts resource does not execute it. |
| Direct delegation | `service.py:delegate` | One generic project inspector, read-only, parent-model runtime, explicit handoff data, at most 8 turns/30 calls/180 seconds. It cannot select a saved specialist, write code or recursively delegate. |
| Workflow parallelism | `workflow_graph.py:execute` | Dependency graph branches run up to two ready stages concurrently. Writable stages use bounded project copies and reviewed merge with baseline checks. This is already parallel work, but it is a predefined workflow rather than general dynamic delegation. |
| Scheduling | `agents.py`, `scheduling.py`, `agent_jobs.py` | Recurrence, queues, missed-run handling and a background scheduler exist. Sleep/wake/reboot and durable process continuity need broader acceptance. |
| MCP | `mcp.py`, `remote_mcp.py` | Stdio and Streamable HTTP, optional OAuth and Keychain storage exist. The current remote client exposes tool listing/calls; broader deployed third-party OAuth qualification is pending. |
| Verification | `outcomes.py`, `tool_qualification.py` | Independent outcome checks and evidence/hash qualification exist. Verification is contract-specific, not proof of every possible task. |

## Remaining gaps, in priority order

### First: reliable defaults and visible readiness

The profile run preflight currently requires an installed model carrying the `tools` capability flag. That is an advertised capability, not a qualification result for this model, runtime and helper combination. Expose separate states: available, configured, tested for this task family, untested, and failed. Each state should link to evidence and its exact identity/date.

Create a compact setup check covering model/tool-call support, project, permissions, skill prerequisites, connections, verification criteria and execution environment. A saved profile can remain a draft; a missing dependency should be explained before an affected task starts. Always distinguish a tool's installation state from whether the selected model used it reliably.

Acceptance: same held-out workloads and repeated attempts for discovery, read/edit/test, browser work, MCP, skill use, delegation, long tasks, cancellation and recovery. Track incorrect arguments, false success, denied-action workarounds and fabricated evidence as well as completion rate. Newer 13 October evidence supersedes the Alpha 6 report's blanket installed-security-workflow gap: seven guided installed Qwen workflows and persistence passed. The separate two-model interpretation/denial/imported-instruction matrix passed 6/8, retaining two Qwen completeness failures. Broad qualification across all installed models remains unfinished. Alpha 7 notes distinguish these original Alpha 6 implementation identities from Alpha 7 package/release verification.

### Next: profiles as complete, understandable configurations

Add a validated capability policy to each agent profile: tool groups/connection bindings, prerequisite readiness, memory namespace/shared scopes, worker role and environment reference. Keep automatic tool choice inside this configured boundary. Current `available_names` generally starts from the workspace catalogue and narrows through read-only/delegate restrictions; profile persistence has no dedicated tool-group or MCP binding fields.

Effective authority must intersect workspace, profile, task, environment and connection restrictions. It must be enforced at dispatch as well as reflected in discovery. Existing authority and review logic remain authoritative.

Do not introduce a new engine, independent scheduler or unsynchronised storage. Extend the current `EngineClient` → JSON-line IPC → `Service` → SQLite/tool authority path. Freeze run configuration so changing a profile does not silently alter running work.

### Then: dynamic delegation to saved specialists

Adapt Hermes's bounded assignment pattern into the existing child execution machinery. Proposed model-facing API: list available specialists, delegate an assignment to a selected profile, inspect child status/evidence, and retrieve its structured result. Required inputs include objective, permitted resources, expected output, success checks and budgets.

Children must receive narrowed authority and explicit context. Preserve private-memory isolation. Reuse workflow branch copies/reviewed merge for changes rather than letting multiple workers write to the original tree. Add parent/child IDs, progress events and cancellation propagation to the live run display. Parallelism should be resource-aware; two async branches do not prove two local models can infer simultaneously at acceptable speed.

Acceptance: independent research, coder/reviewer handoff, blocked child, cancellation, budget exhaustion, parent restart and conflicting branch changes. No parent reports completion merely because a child says it succeeded.

### Skills: make useful procedures easy to find and run

Keep the existing reviewed learning path. Add prerequisite metadata, compatible platforms, required tool groups, connection setup and provenance/update checks. Show recommended compatible skills during profile setup. A future script runner needs an explicit execution contract and must use normal authority, review, process tracking and evidence retention. Importing a skill must never execute its scripts automatically.

Hermes's progressive skill loading, prerequisites and skill update lifecycle are useful reference patterns. Wixal already has resource loading, evaluation and rollback; these should be expanded rather than replaced.

### Execution environments and background continuity

Wixal has project copies, task authority, process controls, macOS sandbox execution for isolated workflow commands, bounded sandboxed Ghidra, and a dedicated Linux worker. The 13 October report records worker scanning, outbound policy, cancellation and owned-resource cleanup in a validation VM. These are implemented bounded environments, not a general selectable terminal/file backend for every agent. Extend them into a consistent per-profile environment abstraction when that scope is approved. All terminal/file/process operations in a run should target the same environment identity.

Before remote expansion, qualify disconnects, timeout/cancellation, terminal receipt recovery, app closure, sleep/wake and reboot. Retain unknown effects and require inspection before replay.

### Optional later breadth

Hermes also offers messaging gateways, additional execution backends, broad provider/model choices and media capabilities. These need separate integrations and live evidence. They are not prerequisites for a strong local Mac agent workspace. Voice, cloud inference and general remote-agent execution remain outside this redesign's implementation scope; the existing bounded Linux worker should be retained.

## Agents workspace redesign

Current source: `AgentsHubView.swift` presents agent/template card grids; global pages are Agents, Workflows, Runs, Schedules and Tools; a separate Live workspace menu exposes conversations/tasks. `AgentBuilderView.swift` uses Purpose, Model & tools, Memory & skills and Review steps. Agent detail has another set of Work/Configuration/Skills & tools/Memory/Schedules tabs. This makes the relationship between profile setup, current task and global tool state harder to follow.

Recommended direction: **Profile workspace**. Keep the app's stable navigation rail. Within Agents, use a compact agent list and one persistent selected-agent workspace. Tabs: Conversation, Runs and Setup. Setup categories: Identity, Model, Tools & connections, Skills, Memory, Permissions, Verification and Limits. Routines and Workflows remain accessible from the agent list, with a clearly labelled global view.

Every detail area must state its configuration scope. Tools & connections should distinguish profile bindings from global installation/authentication settings. Agent memory should distinguish private, project-shared and user preference data. Credentials remain in the existing secure storage and are never duplicated into exportable agent definitions.

The selected-agent header should show the active project, model and action policy. Runs should show objective, checklist, child assignments, tool activity, artifacts and independent verification, with guidance/resume/review controls close to the relevant state. Successful execution and verified outcome remain separate.

Alternative: **Run workspace**. Make the task inbox the main pane and place agent selection/configuration beside it. Better for many queued jobs, less direct for initial profile setup. Both concepts are included in the design preview; fixture names, states and results are illustrative.

## Delivery sequence

1. Approve the workspace direction and configuration scope. Build the native navigation against existing live state; preserve profile/run IDs and data.
2. Extend profile schema and add backend setup/readiness results. Update native setup, with availability and qualification shown separately.
3. Qualify task-family defaults against current installed helper/model identities. Surface the resulting evidence.
4. Extend delegation to saved specialists, with narrowed authority, structured results, branch review and parent/child lifecycle visibility.
5. Improve skill prerequisites and connection setup; qualify real services separately from fixtures.
6. Add background/environment expansion after process lifecycle acceptance.

Completion requires source regressions appropriate to each change, a packaged helper identity, installed native UI interaction, real-model task evidence, restart/cancellation behaviour and preserved workspace data. A redesigned tab alone cannot establish agent reliability.

## Official Hermes references checked

- [Profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles): independently scoped identity/configuration, and the distinction between profile, working directory and sandbox.
- [Web dashboard](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard): profile-scoped management, model/MCP/skill setup and explicit configuration target.
- [Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation): child context, configurable workers/models, concurrency, output contracts and monitoring.
- [Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills): progressive loading, prerequisites, platform filters and update provenance.
- [Tools and environments](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools): toolsets and consistent execution backends.
- [Model slots](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models): main and auxiliary tasks. Auxiliary routing is a later performance option, not a substitute for qualification.

Any future source adaptation must pin the reviewed upstream commit, check its licence and retain attribution. Existing Wixal Hermes attribution is under `native/third_party/hermes/`.
