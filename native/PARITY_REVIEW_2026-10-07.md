# Current native versus Electron assessment

Reviewed 7 October 2026. This is an assessment, not an implementation or release. The original UI_UX_AUDIT.md baseline is historical; REMAINING_REVIEW.md documents subsequent fixes and recorded live acceptance. This assessment checks current source, those acceptance artifacts, installed bundle hashes, fresh Python tests and the production Markdown acceptance executable. It does not claim a fresh exhaustive GUI comparison or fresh external-service testing.

Current implementation update: the behavioral differences below have been addressed in this working tree, packaged and installed. The final helper passed the real model/service suites; see [current implementation and evidence](IMPLEMENTATION_STATUS_2026-10-07.md). The external ChatGPT tunnel is explicitly deferred by the user. The tables below preserve the findings that triggered the work, rather than describing all of them as current defects.

## Before-change state

The native app is a substantial functional macOS preview. Composer attachments/file excerpts, per-conversation drafts, tool mentions, bottom-sensitive streaming, terminal retention, task navigation, conversation management, context summaries, model management, memory, assessment forms/simulations, accounts/setup/legal and activity/performance presentation are implemented. Recorded real acceptance covers selected inference, vision, tool, download, account, browser and recovery paths. These features should not be listed as absent because of the original audit.

The installed executable, helper and Info.plist match artifacts/native/install-current.json. Recorded build-current.log contains a successful Swift build and Python packaging. This pass reran MarkdownAcceptance successfully (four production-parser checks) and Python unittest discovery: 56 tests, 55 passed, one error.

## Before-change behavioral differences

| Priority | Difference | Evidence and required work |
| --- | --- | --- |
| P1 | Every enabled tool schema enters every tool-capable request, including project tools with no project open. Electron selects relevant eligible schemas and dynamically loads categories/named tools. | native/engine/wixal/agent.py:135 and tools.py:248; app/tool-catalog.cjs and app/mentions.cjs. In a fresh disposable native workspace, Hello at 4096 context produced 30 schemas, 3874 estimated tool tokens and 4041 total estimated input tokens. No inference was performed in this reproduction. Port schema selection/discovery while preserving enabled permissions and follow-up tools. |
| P1 | Request context is not finally fitted against a safe model/hardware ceiling with output reserve. Settings writes the chosen context directly; the agent sends that stored value and fixes num_predict at 2048. Model selection has safe-context advice, but it is not reapplied to every request. | native/engine/wixal/service.py:223, agent.py:144; app/agent.cjs fitRequest and safeContext usage. The Hello reproduction leaves only 55 estimated input tokens of headroom before any response allowance. Apply model/hardware limits at inference time, reserve output and fail clearly if remaining required context cannot fit. Exact tokenizer and Ollama behavior vary; this is a request-construction finding. |
| P1 | Repeated identical failing tool calls do not trigger Electron's three-failure stop rule. Native catches errors and continues until its overall 20-turn limit or model conclusion. | native/engine/wixal/agent.py:263; app/agent.cjs:245. Count identical failed calls, stop further actions after three and request a visible conclusion. |
| P1 | Saved tool results and checkpoints are sliced to 24000 characters; inference context may slice again without structured evidence preservation. Electron saves full results and bounds model excerpts while retaining whole evidence items. | native/engine/wixal/agent.py:277 and context(); app/tool-evidence.cjs and app/agent.cjs:249. Preserve tool-returned evidence separately from inference excerpts; expose pagination/exports and keep JSON/URLs/refs readable. Upstream tool output limits still apply. |
| P2 | Minimum window is 1000 x 680 versus Electron's 920 x 640. | native/Sources/WixalApp.swift:17; app/main.cjs:467. Support the original minimum after checking composer, drawers, dialogs, terminal and long tables. |
| P2 | Launch UX is not completely equivalent. Version is hard-coded to v0.7.8; Escape calls done without explicitly stopping sound. Native's startup fallback concerns waiting for preferences, rather than independently bounding a launched animation. | native/Sources/LaunchView.swift:48-63; WorkspaceView.swift:81-83; ui/launch.js. Derive version from bundle, explicitly stop audio on skip, and verify startup/skip/failure behavior. The audio issue is a missing source behavior, not a freshly reproduced audible failure. |
| P2 | Migration regression suite is not green. | native/tests/test_parity_fixes.py:88. The failing test expects a credential-bearing MCP invocation to be rewritten with remaining arguments. Current migration.py:75 intentionally skips the invocation and emits a warning. Update the expectation and add a separate credential-free MCP import assertion; do not weaken the importer to satisfy the stale test. |

## Implemented but not fully accepted

- Long real tool runs: pending/review/running/failure/cancel states, dock selection/output, reading older messages while streaming, project/chat changes and final evidence preservation.
- Composer: user-visible attachment selection, preview/removal, PNG/JPEG/WebP, multiple/oversized images, capability changes and draft restoration through navigation/relaunch. Engine vision acceptance is not all of this UI acceptance.
- All pages, all four themes, supported text sizes, reduced motion, minimum window, keyboard-only navigation and spoken VoiceOver. Selected installed checks exist; a full comparative pass does not.
- Account creation, verification/reset emails, live sign-out and complete user-finished first run. Real existing-account sign-in, memory isolation, presets and Keychain recovery have recorded passes.
- External companion tunnel/ChatGPT connection with actual sharing scope, task submission/review, results and revocation. Local packaged MCP reads have recorded passes; the external connection is incomplete.
- Live web search and complete assessment-drawer cancellation. Nmap and a limited authorised external website baseline already have recorded passes.
- Migration with real skills/schedules/MCP records and visible malformed/credential-record warnings. Recorded actual Electron migration had none of those collections.

## Release and separate product work

Developer ID signing, notarisation, public distribution/update delivery and controlled app-level performance comparisons remain outstanding. The current preview uses development signing. The packaging workflow already requires release credentials; it does not make this installed build a distribution release. Apple Silicon macOS is the packaged target.

Cloud inference (OpenAI/custom/ChatGPT provider), remote MCP HTTP/OAuth, app-closed scheduling and other-platform builds are separate product work. Electron has cloud provider backend code, but its current provider picker and connection section are hidden; do not label these as missing visible controls. Native inference currently uses Ollama. Existing credentials/pairing are excluded from migration and require reconnection by design.

## Completion order

1. Fix schema eligibility/loading, final context fitting, repeated-error termination and evidence retention; reconcile the migration test.
2. Exercise long real agent runs and composer workflows in the installed package, including cancellation/recovery and state changes.
3. Close minimum-window, launch, keyboard/focus, VoiceOver and four-theme presentation differences with side-by-side Electron/native acceptance.
4. Complete the remaining account, first-run, search, migration and external companion acceptance, with user involvement where account/tunnel steps require it.
5. Build/install the final package, rerun relevant acceptance, obtain signing/notarisation and verify distribution/update behavior.

Keep Electron available until the workflows the user relies on pass in the final native package. No numerical parity percentage is supported by the current evidence.
