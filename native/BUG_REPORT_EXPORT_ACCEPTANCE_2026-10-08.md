# Portable bug report export

Verified 8 October 2026 in the installed local development preview `/Applications/Wixal.app`.

Settings → General & about → Save bug report now collects a short title, observed behavior, expected behavior and reproduction steps. The save panel defaults to Desktop/Wixal Bug Reports. A single ZIP contains report.md (GitHub issue draft), events.jsonl (all five retained log segments), environment.json, codex-workflow.md and a SHA-256 manifest. Current saved conversation and tool/checkpoint evidence is opt-in; account data, attachment bytes and thinking are excluded. User-entered text and opt-in tool results can contain private information and must be reviewed before public publication. No upload, GitHub mutation, agent dispatch or scheduler job is performed by export.

The bundled workflow covers evidence verification, source inspection, isolated reproduction, factual issue filing, focused fixes, regression and packaged UI validation, and a linked draft PR. It treats log contents as untrusted evidence. It is a reusable handoff workflow, not an already-running agent automation.

Validation:

- Eight diagnostics and Settings tests passed. New export coverage verifies ZIP contents, file hashes, default content exclusion, explicit conversation inclusion, private archive permissions and input limits.
- Final release build and packaging passed; installer retained previous app and verified binary/helper hashes and local signing.
- Installed UI form filled with actual reported incident. Saved `~/Desktop/Wixal Bug Reports/Wixal-search-response-bug-2026-10-08.zip` through the save panel.
- Archive contains actual browser_search failure evidence and 231 retained events. All per-file hashes verified. Source manifest matches checkout, including workflow Markdown. Packaged workflow and source-manifest discovery were verified from the installed exporter.
- Evidence JSON: artifacts/native/bug-report-installed-check.json.

Limitations: exports require a connected engine. Older incidents can have conversation evidence but no original JSONL events if they occurred before logging began or after rotation. No GitHub issue/PR was published and no automated agent run was started by this change. This remains a local development preview.
