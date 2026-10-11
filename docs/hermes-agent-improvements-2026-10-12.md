# Hermes-inspired native agent improvements

12 October 2026

Reference: [NousResearch/hermes-agent at 97a9ae8](https://github.com/NousResearch/hermes-agent/tree/97a9ae8ee55d31bebce49f1fb6b5ef775323976a). The upstream checkout was inspected as source; Hermes itself was not run, so its source patterns are not evidence that every upstream workflow works. Wixal retains its SwiftUI desktop, Python engine, JSON-line IPC, SQLite storage, local inference and action review.

| Area | Existing Wixal capability | Change in this implementation |
| --- | --- | --- |
| Task planning | Saved agent briefs and workflow stages | `todo_list` stores a revisioned checklist in each task, shows it in live runs, preserves it after context compaction and flags unfinished items at completion. Checklist progress is model-authored and does not prove verification. |
| Long single-task context | Whole user turns and bounded tool excerpts | Complete older tool rounds can be compacted while preserving the task brief, controller feedback and the latest two call/result chains. Full evidence stays in SQLite. |
| Evidence retrieval | Checkpoints visible to users | `tool_result_read` lists and pages through settled checkpoints from the current run, with exact saved text and its digest. It does not rerun the underlying action. |
| Skills | Imported Markdown and reviewed procedure learning | `SKILL.md` import snapshots bounded text from references, templates, examples, assets and scripts. `load_skill` pages through those snapshots. Scripts are read as text. Symlinks and credential paths are rejected. |
| Skill identity and versions | Workspace-owned learned skills | Skill loading and listing respect workspace identity. Resource snapshots are validated on transfer, included in evaluation digests and retained in rollback versions. |
| Delegation | Isolated, read-only project child | Child discovery is intersected with its explicit allowed tools; parent private instructions, notes and memory are not inherited. Optional bounded handoff context supplies relevant facts. Calls and wall time are bounded; recursive delegation stays unavailable. |
| Tool discovery | Exact name and category loading | `workspace_info(query=...)` searches enabled tool names/descriptions and loads at most eight matching schemas. Search does not grant authority. |
| Mixed read/fix/test requests | Named-file focus and progressive schema loading | Named-file focus retains edit and command schemas when the same request explicitly asks for changes or execution. A simple source read stays narrow. Calculation requests can access command tools. |
| Invalid tool calls | Provider syntax retry and per-tool schema validation | The entire returned call batch is parsed before any member executes. Malformed argument JSON receives bounded correction attempts. Nested schema objects are validated. |
| Source verification | JSON source comparison | `verify_json` supports independently summed numeric JSON arrays and CSV columns. Invalid sources are rejected before adding a durable criterion; later verification rereads the actual source bytes. Nonfinite, malformed and out-of-bound values are rejected. |
| Discovery recovery | Schema errors retained in checkpoints | A later successful call to the exact tool named in a failed discovery request resolves that discovery error. Explicit checks requiring discovery itself still fail until discovery succeeds. |
| Conversation summaries | Model summaries with excerpt fallback | Repeated summaries carry forward the previous summary and include labelled tool evidence instead of dropping older decisions or omitting tool results. |

The native implementation already includes reusable agents, schedules, queues, workflow dependencies, isolated workflow changes, memory retrieval, reviewed tool installation, browser controls and skill evaluation/promotion. These were reused rather than duplicated.

The work does not constitute complete Hermes platform parity. Hermes's messaging gateways, remote execution backends, cloud/provider matrix and media/voice tools require separate product integration and live acceptance. Voice remains outside the existing approved workspace design. No gateway credentials, messaging accounts or remote workers were configured. The implementation is included in the [Alpha 5 release](release-0.7.10-alpha.5.md). The development results below retain their original build identity; release-specific evidence is attached to the GitHub release. There is no notarization claim.

Validation reports are retained under `artifacts/native/hermes-agent-2026-10-12/`. Source regressions, live-model cases, packaged-helper checks and UI fixture observations must be read separately. Failed live-model cases remain evidence of limits; successful builds do not replace them.

## Verified result

The final build is installed at `/Applications/Wixal.app` on the existing 0.7.x alpha line. The previous installed bundle is retained by the installer. The final frozen helper is SHA-256 `5be4a6118fc085b03b0693db8ec2f3b5e6471e6b672eb297e5498a6362f6d9a0`.

- 417 engine tests passed, including 20 new regressions; the focused related suite passed 34 tests.
- The final installed helper passed five `gpt-oss:20b` acceptance cases: skill snapshot loading, durable plan and saved-evidence retrieval, isolated child execution, keyword discovery and independent CSV verification. The helper digest was captured before execution and remained unchanged afterwards.
- A fresh frozen-helper process recovered the same plan revision and checkpoint count without new actions.
- The installed native UI opened the retained run at 920 × 640, displayed the checklist and accessible content/status labels, and kept unchecked verification distinct from completed checklist items. This is controlled UI fixture evidence, separate from the real-model cases.
- The installed source manifest matched all 129 recorded source entries. Strict deep signature verification and installation inventory passed; no obsolete installed copies were found.

See `artifacts/native/hermes-agent-2026-10-12/validation.json` and `installed-capabilities-final/results.json`. Earlier failed live-model trials remain retained. An early staged test overlapped replacement of its app path; its identity warning excludes it from final acceptance. No general reliability claim across all models follows from the passing cases.
