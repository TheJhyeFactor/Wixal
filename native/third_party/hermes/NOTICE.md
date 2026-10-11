# Hermes reuse review

Upstream: https://github.com/NousResearch/hermes-agent
Pinned commit: `0e21933114c911075782d5744cee5403996d38ae`
License: MIT, Copyright (c) 2025 Nous Research. Full license retained beside this notice and bundled in the app.

Reviewed `cron/jobs.py`, `tools/registry.py` and `agent/conversation_loop.py`. The full modules depend on Hermes profiles, gateway, provider resolution, environment backends and filesystem conventions; importing them would duplicate Wixal storage and execution.

Adapted only `parse_duration` from `cron/jobs.py` into `wixal/vendor/hermes_duration.py`, adding a positive bounded duration check. This implementation is used by the model-facing routine management tool. The profile, workflow, scheduling and UI integrations are Wixal implementations. Fresh run sessions, durable claims before execution, isolated configuration and evidence-based completion are architectural patterns, not copied modules.

No claim of full Hermes platform parity is made by this integration.

## Agent improvements reviewed 12 October 2026

Reference revision: `97a9ae8ee55d31bebce49f1fb6b5ef775323976a`.
Reviewed `tools/todo_tool.py`, `tools/skills_tool.py`, `tools/tool_search.py`,
`agent/delegation_context.py`, `agent/context_compressor_prellm.py` and
`agent/conversation_loop.py` for task progress, progressive skill disclosure,
bounded tool discovery, child-context isolation and long-task continuation.

The new `task_state.py`, `skill_resources.py`, tool search, whole-round context
compaction and delegation changes are original Wixal implementations of those
patterns. No additional Hermes source module or dependency was imported.
The existing adapted duration parser and its original pinned revision above
remain unchanged. Hermes's remote environments, messaging and media providers
are not included by these changes.
