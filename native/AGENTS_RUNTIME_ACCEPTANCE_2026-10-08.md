# Wixal Agents runtime implementation and acceptance

> Completion follow-up: [AGENTS_COMPLETION_ACCEPTANCE_2026-10-08.md](AGENTS_COMPLETION_ACCEPTANCE_2026-10-08.md) supersedes the remaining-work snapshot below with outcome checks, scoped background work, durable jobs, isolated graph workflows, evaluated skills, transfer support and visible native acceptance. This document retains the original run evidence.


Implemented on 8 October 2026. This supersedes the earlier design-only Agents preview. Saved agents, workflows and routines now execute through Wixal's Swift UI and persistent Python engine.

## Delivered application

- Installed local development app: `/Users/jhye/Applications/Wixal Agents.app`.
- Matching package: `artifacts/native/agents-runtime/Wixal Agents.app`.
- Independent engine workspace: `artifacts/native/agents-runtime/verified-workspace`.
- Bundle identifier: `app.wixal.agents.verified`; executable: `WixalAgentsVerified`.
- Finder launches retain the independent workspace and loopback Ollama endpoint through development preview bundle configuration. The existing Wixal apps and their active workspace were not replaced.
- The preview selects the installed `gpt-oss:20b` model and provides four real agent profiles and six editable workflows. It does not silently activate routines.
- Development signing and strict signature verification passed. This is a local development build, not a notarised public release.
- `SOURCE_MANIFEST.json` records the Swift and engine source hashes used by the package. Source/package and installed/package hash checks are retained in `artifacts/native/agents-runtime/installed-verification.json`.

## Actual execution behaviour

Saved profiles have standing instructions, an installed tool-capable model, project scope, action review policy, memory scope and selected skills. The engine rejects unavailable models and missing skills before starting a task. Project binding survives profile registration and prevents running against a different project.

The model chooses tools from Wixal's catalogue, including connected MCP definitions. Tool errors provide their input schema so the model can correct invalid arguments. Task-relevant scheduling/skill schemas are exposed early; tool-heavy requests can trade excess thinking reserve for input room while preserving the latest input. Workspace context reports actual installed executable paths. Saved-agent execution does not depend on the legacy manual tool switches. Progressive tool discovery exposes descriptions and schemas; the loop executes chosen calls, returns real results and continues. Read-only profiles exclude changes and commands. Action review remains a control over effects. It is separate from tool selection.

Runs create real sessions and durable task records with the profile snapshot, project, model, source, prompt, checkpoints, errors and result. The original conversation, project and model selections restore after execution, failure or cancellation. Guidance is queued for the next model step. Interrupted effects are retained as uncertain; retries are instructed to inspect current state before acting.

Workflows freeze their stage definitions and profile configurations for a run. Stages pass bounded evidence to the next agent, can require review, retain failed child-task evidence and can resume without repeating completed stages. A configured automatic retry is limited to one attempt and only applies when no modifying tool was attempted. Workflows execute sequentially.

Routines support hourly, daily, weekday and Monday wall-clock schedules, named timezones and bounded intervals. Missed runs either coalesce into one latest run or skip. The due time is claimed durably before execution. Runs start fresh sessions. Background work cannot create more routines or bypass action review through a pre-approved profile. Actions needing review pause for the desktop. The Mac must be awake. The existing optional macOS background scheduler can be enabled in Schedules; the acceptance tests exercised its frozen helper entry point without registering a persistent LaunchAgent on the user's system.

Schedule updates are in-app records, with next/last run information and links to evidence. These controls do not promise OS push notifications or remote message delivery.

Agents can create, list and update reusable skills through a reviewed tool. Updates retain a bounded version history. This saves procedures, not model weights. Project and global preference memory use the existing bounded, editable memory engine. Project notes are shared within the selected project; this implementation does not claim separate private memory for each agent. Earlier local design drafts are registered only in the guest workspace, and imported preview routines remain paused.

## UI and cybersecurity

The Agents tab provides the roster, builder, task brief, workflows, real run records, schedules and an inspection-only tool catalogue. Simulated preview runs were removed. Navigation, profile sections and hover/press feedback respect reduced-motion preferences.

The shrinking editor was caused by measuring the key window repeatedly while it was the sheet being edited. Builder, task, workflow and routine sheets now capture their parent dimensions once and use that stable size. The release build compiles this fix. **Visible typing and layout regression checks remain pending:** computer-use inspection was blocked because the Mac was locked. No screenshot or successful visible UI regression is claimed for this runtime pass.

The Cybersecurity workspace can start a security agent from a brief containing authorised scope. Existing investigations, manual assessments and evidence views remain accessible. Security agents use the existing network and website tool implementations and their scope/action controls. The real-model security workload used disposable loopback fixtures. This establishes that an agent can select and execute the security simulation tool, retain evidence and report its results; it does not establish comprehensive detection quality against production targets.

## Hermes reuse

Reviewed Hermes at `0e21933114c911075782d5744cee5403996d38ae`, specifically `cron/jobs.py`, `tools/registry.py` and `agent/conversation_loop.py`, alongside the upstream feature description. Hermes' full modules depend on its gateway, provider resolution, profile layout and environment backends. Importing them would introduce a second execution/storage stack inside Wixal.

Adapted the small `parse_duration` implementation into `native/engine/wixal/vendor/hermes_duration.py`, with additional positive duration bounds. Model-created interval routines use this code. The original MIT copyright/license, pinned source and adaptation boundary are retained in `native/third_party/hermes/` and bundled notices.

Profile isolation, tool discovery, fresh scheduled sessions, durable execution claims and skills retained from verified work informed the integration. The runtime and Swift interfaces are Wixal implementations using its existing engine. Full Hermes platform parity is not claimed.

## Verification and reproducible workloads

**Python regression suite: 155 tests passed**, including 27 agent runtime/calendar tests. These controlled model-decision tests execute actual Wixal tools and SQLite storage, with real command output and filesystem effects. They cover automatic discovery with legacy switches empty, read-only rejection, cancellation, guidance, restoration, stage handoff/review, failed-stage retention, bounded retry, resume, restart interruption, background review, no duplicate due runs, routine creation, skills/versioning, project binding and Sydney DST/missed-run behaviour.

```sh
PYTHONPATH=native/engine native/.venv/bin/python -m unittest discover -s native/tests -v
```

**Real local model: six workload checks passed with `gpt-oss:20b`.** These independently verify saved artifacts and recorded tool outcomes rather than accepting the model's final claim.

| Workload | Independent outcome |
| --- | --- |
| Read-only file inspection | Exact source marker/count retrieved, source unchanged |
| CSV analysis and JSON artifact | Numeric total equals 21; actual write tool recorded |
| Reproduce, fix and test code | Corrected program passes an independently invoked unittest; model's command evidence retained |
| Two-agent workflow handoff | Both stages finish; saved report preserves exact source identifiers |
| Due scheduled agent | Real file tool executes in a fresh scheduled session and completes |
| Local cybersecurity simulation | Model calls `website_simulate`, inspects saved report; 16/16 expected HTTP controls, zero unexpected results |

```sh
native/.venv/bin/python native/scripts/agents-real-model-acceptance.py \
  --output artifacts/native/agents-runtime/real-model-verified3
```

Evidence: `artifacts/native/agents-runtime/real-model-verified3/results.json`, raw `events.json`, generated project artifacts and SQLite state. Earlier trials retain identifier-preservation, management-discovery, command-environment, tool-argument and schema-budget failures. Corrections include exact source identifiers, task-relevant management schemas, executable discovery, explicit validation/schema feedback, calendar alias normalization and adaptive thinking reserve. Failed trials were not erased; the final six-workload pass is recorded separately.

**Frozen installed engine: five checks passed** through Swift's JSON IPC protocol: actual repository-source inspection, a reviewed artifact write/read-back, model-created weekday routines with verified wall time/timezone, verified reusable skill creation, and a real background scheduled tool run. Exact results are retained in `artifacts/native/agents-runtime/installed-verified3/results.json`.

```sh
PYTHONPATH=native/engine native/.venv/bin/python native/scripts/agents-packaged-acceptance.py \
  --app '/Users/jhye/Applications/Wixal Agents.app' \
  --output artifacts/native/agents-runtime/installed-verified3 --management
```

Build and test logs: `artifacts/native/agents-runtime/python-tests.log`, `package-build.log`, `real-model.log`. Signature checks, installation hashes and source manifest passed. `git diff --check` passed.

## Remaining Hermes-level platform work

The requested local agent execution path is implemented and tested within the workloads above. Further Hermes-level platform capabilities remain distinct work:

- Broad unattended multi-agent orchestration with isolated parallel write environments and explicit merge/conflict handling. Current workflows serialize stages; existing delegation remains bounded.
- Automatic skill evaluation, promotion and rollback based on repeated real task performance. Reviewed skill creation/versioning is implemented; a closed autonomous improvement loop is not.
- Remote execution backends such as Docker, SSH and hosted sandboxes, plus remote wake/delivery. Current delivery is the local macOS engine.
- Messaging/voice gateways and cross-channel conversation continuity. These were not imported.
- A wider repeated evaluation matrix across supported models, MCP services, network targets and longer running jobs. The current evidence covers one installed real model and local fixtures/source files; it is not a universal guarantee of task success.
- The pending visible editor/layout/animation check, macOS background registration exercise and public distribution signing/notarisation.

Engine status `completed` means the run reached its final response. Tool evidence is recorded, and the acceptance suite independently verifies its specified outputs. Arbitrary task correctness still requires assessment of that evidence; the UI does not label every completed response as independently proven.
