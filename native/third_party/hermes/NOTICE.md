# Hermes reuse review

Upstream: https://github.com/NousResearch/hermes-agent
Pinned commit: `0e21933114c911075782d5744cee5403996d38ae`
License: MIT, Copyright (c) 2025 Nous Research. Full license retained beside this notice and bundled in the app.

Reviewed `cron/jobs.py`, `tools/registry.py` and `agent/conversation_loop.py`. The full modules depend on Hermes profiles, gateway, provider resolution, environment backends and filesystem conventions; importing them would duplicate Wixal storage and execution.

Adapted only `parse_duration` from `cron/jobs.py` into `wixal/vendor/hermes_duration.py`, adding a positive bounded duration check. This implementation is used by the model-facing routine management tool. The profile, workflow, scheduling and UI integrations are Wixal implementations. Fresh run sessions, durable claims before execution, isolated configuration and evidence-based completion are architectural patterns, not copied modules.

No claim of full Hermes platform parity is made by this integration.
