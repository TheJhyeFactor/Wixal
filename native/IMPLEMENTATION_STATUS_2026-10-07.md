# Native completion status, 7 October 2026

Latest approved Working/Response pass: Answer first is implemented and installed, with compact live status, optional thinking/tool evidence, subtle animation and measured table rows. 116 supporting tests, 5 Markdown checks, packaged smoke, loopback UI and actual gpt-oss:20b response passed. Exact package and acceptance scope: ANSWER_FIRST_ACCEPTANCE_2026-10-08.md.

This records current implementation and acceptance separately. `PARITY_REVIEW_2026-10-07.md` is the before-change review; its listed differences are not all current defects.


## Approved UI implementation, 8 October 2026

The simplified UI is implemented and installed. Visible assessment Stop now passes with retained partial evidence; focused minimum-window/larger-text/four-theme and shortcut checks passed. The current full suite passes 114 tests and packaged smoke passed. See UI_UX_REDESIGN_ACCEPTANCE_2026-10-08.md for exact build hashes, project deletion semantics and remaining accessibility/external acceptance boundaries. Earlier test counts below describe preceding passes.

## Feature completion pass and current priority

The user asked to finish native capabilities first and deferred native store/release distribution. Cloud inference and the external ChatGPT companion remain deferred. The public v0.7.9 DMG and ZIP are Electron builds. The native capabilities described here are in the source tree and local development package; no public native release has been published.

| Area | Current implementation | Acceptance boundary |
| --- | --- | --- |
| Semantic memory | Optional local Ollama embeddings combined with lexical recall; vectors tied to content and actual weights; bounded incremental index with visible backlog/fallback; no second large chat model | Actual embeddinggemma and Gemma3 1B cases exercise paraphrase, unrelated exclusion, answer, correction and forgetting; supporting tests separately cover stale vectors and roles |
| Consolidation and conflicts | Existing-note review, lexical/semantic related candidates, possible superseded decisions, explicit replacement/merge, stale-review guards, retained sources and merged identifiers | Review is required; inferred relationship is not a verified conflict. The user can explicitly choose replacement or combination of notes |
| Broader memory suggestions | Opt-in selected-local-model review of ordinary human statements, bounded to four messages/4,000 characters; exact evidence selection, no silent saving, visible request usage; manual review also available | Actual Gemma3 1B source run passed ordinary decision extraction, changed decision replacement, temporary-progress exclusion and question exclusion. Final packaged acceptance is recorded separately in `memory-review/packaged.json`; classification still needs human review |
| Memory provenance | User/assistant/tool roles; current saved corrections take priority; deduplicated recall; past questions stay searchable but are excluded from factual context; unverified assistant text omitted when a relevant saved note answers the query | Small-model answers are measured separately from retrieval. Factual/tool requests use deterministic sampling; passing selected cases is not universal reliability |
| History indexing | Persisted per-session content digests and indexed row identifiers, update only changed recall rows, no full FTS scan for each change | Synthetic lexical benchmark at 30,000 passages: initial about 0.68 s, unchanged/one-session update about 37 ms; this excludes full state-save overhead and semantic scoring at that scale |
| Encrypted folder sync | Opt-in AES-GCM/Scrypt snapshots, Keychain secret, idle automatic sync, image integrity, identity boundary, explicit divergent-edit review, forgetting tombstones and local project remapping | Actual packaged helpers and Keychain passed with two local workspaces, real model history and image bytes. Cloud-folder delivery and a second Mac remain unverified. 64 MB per snapshot and 20 device snapshots are current limits |
| Remote MCP | Official pinned SDK Streamable HTTP, discovery/call/disconnect, loopback OAuth callback with SDK discovery/PKCE/registration and Keychain tokens | Actual public DeepWiki calls passed. OAuth discovery/registration/PKCE/bearer/reconnect passed using a local HTTP provider fixture; external provider sign-in is not certified |
| Closed-app scheduling | Opt-in per-workspace macOS LaunchAgent, saved model/identity, claim before work, latest/skip missed-run policy, paused reviews and interrupted ownership recovery | Actual closed-app Gemma inference passed and test LaunchAgent was removed. The Mac must be awake; waking a sleeping Mac is not implemented |
| Browser | Existing public-read mode plus reviewed ephemeral interactive WebKit mode; normal APIs, workers/streaming, manual authentication, submissions and destination-prompt downloads | Packaged streaming/Worker/actual form POST passed against a disposable site. External authenticated apps, popup authentication and download interactions still require their actual acceptance |
| Account lifecycle | Current-password reauthentication for password change and online deletion; refreshed Keychain; deletion of cloud presets/preferences before Firebase identity | Local service regression support only for new lifecycle endpoints. Fresh verification, user-completed password change and disposable live deletion remain outstanding; no real account was deleted |
| Image composer | Picker, multiple images, previews/removal, size bounds, saved drafts and incompatible-model guards; full model size tag and visible incompatibility prompt | Actual packaged CUA checks passed selection, preview, removal, navigation/relaunch, oversized rejection, incompatible send preservation and Gemma3 12B image inference. Selected dock/keyboard/theme checks do not certify the exhaustive layout/VoiceOver matrix |
| Other platforms | Current native app remains Apple Silicon macOS | Native Windows/Linux and verified Intel package are absent. Preserve Electron for that coverage |

Current reports are under `artifacts/native/`: `memory-quality/`, `memory-review/`, `final-feature-verification.json`, `memory-scale.json`, `feature-acceptance/packaged.json`, `feature-acceptance/interactive-browser.json`, `feature-acceptance/composer-ui.json`, `folder-sync/packaged.json`, `final-ui/packaged.json`, `oauth-regressions.log`, `current-regressions.log`, `current-build.log` and `current-package.log`. Check each report's status and binary hash where available. The current supporting suite passed 89 tests. The source Qwen3 4B suite passed all 15 actual-inference stages, including mandatory-thinking summary/continuation, fresh filesystem errors, source-exact command evidence and streamed cancellation. A running/failed packaged broader-model report is unfinished acceptance, not a pass.

Acceptance found and fixed discovery-order-dependent MCP names, loss of enabled tools during disconnected-server settings changes, historical tool failures being recalled as evidence for a fresh explicit tool request, a stale account failure message after successful manual restore, and literal-repeat requests unnecessarily recalling old test commands. Literal-repeat requests now exclude recall while keeping history searchable; an early empty model response is distinguished from exhaustion of its output reserve. The account issue was found in the installed app: initial automatic restore timed out and the visible retry restored the real verified account. The success message now updates both visible and accessibility text. The startup restore bound was extended to 45 seconds to cover token refresh and cloud preferences; a subsequent installed-app launch restored the actual verified account automatically. Each acceptance record identifies its own binary; timeout/retry remains a visible supported outcome.

A repeated scheduling acceptance also exposed Gemma3 1B instruction-following limits: after recall was correctly excluded, it answered a literal-repeat request with “Okay.” That run is retained in `feature-acceptance/literal-model-noncompliance.json`, rather than relabelled as a content pass. Closed-app scheduling is subsequently checked with an ordinary recurring-task explanation and actual model counters. This does not establish reliable exact-format output for Gemma3 1B.

Still to certify: exhaustive minimum-size/four-theme/keyboard/spoken-VoiceOver layouts; long tool sessions with all dock/history/cancellation paths; assessment cancellation at each stage; real migration records for skills/schedules/MCP with visible warnings; live new account lifecycle; real two-device folder delivery; and external OAuth providers. Release/update distribution, comparative Electron/native application performance, sleeping-Mac wake and other native platforms have not been declared complete.

## Implemented in this working tree

- Eligible, progressively selected tool schemas rather than every enabled schema in each request. Project tools are unavailable in personal chats. Discovery can load another tool category without enabling disabled permissions.
- Per-request model/hardware context ceiling, bounded memory and evidence, output reserve and complete-turn pruning. Required user input that cannot fit produces a visible error rather than silent truncation. Request estimates and recalled source IDs are recorded for acceptance.
- Three identical caught tool failures stop further actions. Full tool-returned evidence persists; model excerpts remain bounded. Command reads support larger explicit pages, retain UTF-8 correctly and use Swift-compatible UTF-16 offsets.
- Relevant project/global saved notes and indexed earlier real conversations. Identity and project scope determine eligibility. Conversation-only models receive selected memory without needing tool support. Models can explicitly recall/save/correct/forget; durable user statements can also produce reviewable suggestions. Provenance, correction, deletion and exclusion of derived forgotten history are tracked. Preferences for referencing history and suggesting memories are independent.
- Native memory UI exposes global saved notes, suggestions, source lookup and source conversation navigation. New memory editors have accessibility labels. Disabled global scope explains how to enable it, and failed saves retain the entered note.
- Previously selected account sign-in restores from Keychain at startup before account memory is selected. Guest launches skip Keychain; failed restoration is visible and offers recovery.
- Minimum window matches 920 × 640, splash version derives from bundle metadata and skip/disappearance stops its sound.
- Credential-bearing MCP migration test now matches intentional importer rejection. Supporting regression tests remain separate from genuine acceptance.
- Real search parses returned source links from DuckDuckGo Lite with a bounded Bing RSS fallback and truthful provider/error metadata. This fixes a bot-challenge failure found against the real service.

## Real acceptance work

`native/scripts/real-acceptance.py` runs actual downloaded small models against source-backed Wixal requirements and actual project files through the production engine. It checks request budgets, reviewed project memory, changed answers in new conversations, restart persistence, cross-project exclusion, disabled memory, corrections/forgetting, global memory with a conversation-only model, file tools, real directory errors, full command evidence and actual file draft persistence.

`native/scripts/real-services-acceptance.py` uses the packaged helper for real public HTTPS and search, source-exact command pagination, packaged companion MCP reads and revocation, and an explicitly supplied mailbox's real reset request. Neither suite supplies fabricated model replies, substitute endpoints or injected chat history. Isolated durable workspaces retain real evidence without changing the user's project records. Existing fixture tests are regression support, not end-to-end evidence.

The reports in `artifacts/native/real-acceptance/packaged.json` and `artifacts/native/real-services/packaged.json` are authoritative for each run's status. A failed or running report is not acceptance. Reset request acknowledgement alone does not prove email delivery or completion of a password reset. All-screen keyboard/VoiceOver, full first-run account creation/verification and distribution acceptance still require their actual paths to pass.

## ChatGPT companion explicitly deferred by the user

The packaged local companion supports scoped MCP project reads and explicit sharing/revocation. A tunnel-client v0.0.16 local stdio profile was prepared at `artifacts/native/tunnel-client-v0.0.16/profile/local-stdio.yaml`. No OpenAI Platform control-plane credential was available, no new credential was created, and no external ChatGPT connection was established. The user requested documenting this state and moving on because it is a low-priority feature at present.

When resumed, supply the credential through secure setup, start the prepared tunnel, connect the client, then verify real scope, queued task submission/review, result retrieval and revocation externally. Local MCP acceptance cannot stand in for that external connection. This deferred integration is not a blocker for the current native memory/model/service work.

## Distribution boundary

An earlier local check did not find a valid Developer ID identity. The user subsequently confirmed that a signing identity and another Mac are available, then explicitly prioritised feature work and deferred release/store work. Installed/package development signing is not notarised distribution. Public download/update, another-machine Gatekeeper acceptance and release signing remain deferred. Keep the existing Electron app available for unverified native workflows and other-platform coverage.

## Earlier installed-engine acceptance, before the feature completion pass

The earlier packaged helper matched the earlier model-suite and real-service report hashes. These records remain evidence for that build. The latest installation is identified separately by `artifacts/native/install-current.json`; an older report does not certify a newer binary.

| Actual check | Recorded result |
| --- | --- |
| Packaged small-model suite | 15 stages passed with actual Qwen3 1.7B and Gemma3 1B weights; prompts, answers, measured runner counters, source hashes and request budgets retained |
| Account services | Actual verified account, Keychain restoration, original guest/account preference separation, actual-model preference use and cloud preset lifecycle passed |
| App quit/reopen | Verified account restored automatically; `account-relaunch.json` |
| External services | Public HTTPS and relevant source-link search, real authorised TCP 443 and three-page public website baseline with saved evidence, source-exact command pagination and packaged scoped MCP/revocation passed |
| Reset delivery | Received in supplied Gmail inbox at 2026-10-07 04:29:57 UTC; receipt metadata only retained, no reset secret |
| Desktop browser | Installed production WebKit checks passed against actual Wikipedia/Python documentation pages |
| Abrupt termination | Actual packaged helper killed; supervisor cleaned up its managed runner |
| Supporting regressions | 56 tests passed; these include fixtures and are not counted as real acceptance |
| Production Markdown | Four parser acceptance checks passed |

The brief project greeting used 3 schemas and 1235 estimated input tokens in a 4,096-token context, reserving 819 for output. This is a request-budget observation, not a controlled application performance benchmark. The full-evidence case saved 48,141 actual source characters (50,518 JSON characters) while limiting the inference excerpt.

The baseline directory-error stage allowed the model to stop voluntarily before three failures. `native/scripts/real-failure-guard.py` separately requests a bounded three-attempt diagnostic on the real directory and requires three actual tool errors, the controller stop marker, and a conclusion generated without tool schemas. Its report passed with three actual failures and a conclusion without tool schemas on the same final helper.

Remaining acceptance includes complete fresh account creation/verification and the user-completed password change, an exhaustive four-theme/minimum-window/keyboard/spoken-VoiceOver/composer pass, and signed/notarised distribution plus another-machine/update delivery. Existing focused successes do not prove all of those paths. The external ChatGPT tunnel remains explicitly deferred.


## Everyday workflow completion pass (7 October, evening)

See [the workflow tracker](WORKFLOW_TRACKER_2026-10-07.md) for final changes, build hashes, retained failures and open acceptance. Three section agents implemented compact activity/layout, memory/schedule/sync review, and browser/account/migration workflows. The combined supporting suite passed 107 tests; actual source and packaged local-model suites passed, and final installed WebKit download completion/cancellation/failure/repeated-transfer cases passed. Assessment cancellation persists partial evidence and stops actual scanner children. Memory workload now measures state saving/reopening and 30,000-passage semantic scoring, with generated workload data explicitly distinguished from live embeddings. Follow-up acceptance also passed populated native skills/schedules/MCP migration and actual Electron-origin MCP migration; see [the populated migration report](MIGRATION_POPULATED_ACCEPTANCE.md).

Disposable-account and two-Mac checks are blocked at the user's request. Windows and Linux native support are paused. The full minimum-window/four-theme/larger-text/keyboard/spoken-VoiceOver matrix remains unverified. Long Unix socket paths are now fixed with a real engine/client test. SQLite lock waits are bounded and the app has a 30-second engine-startup watchdog, but the original `posixOpen` stall was not reproduced and its file path/provider was absent from the sample; therefore its underlying filesystem cause remains unresolved. Assessment Stop now targets a dedicated cancellable task, reports “Stopping…” while awaiting acknowledgement, and preserves partial results; the production IPC regression passes, but the visible retest on the newest package is blocked until the Mac is unlocked. Streaming scroll hold, navigation restore and replay completion are visibly accepted on the prior package. Sleeping-hardware wake remains blocked because Apple's scheduled power API requires root and this ad-hoc-signed local preview has no valid signing identity for a privileged helper. This is an installed local native development preview; published v0.7.9 downloads remain Electron.
