# Native app review and current verification

Updated 7 October 2026 after implementation, real integration checks and installation. The original audit is retained below as historical evidence. Its old source line numbers and missing-feature statements do not describe the current build.

## Feature completion update

The latest feature scope and binary-qualified checks are recorded in [IMPLEMENTATION_STATUS_2026-10-07.md](IMPLEMENTATION_STATUS_2026-10-07.md). Semantic recall, reviewed consolidation, optional local-model decision extraction, encrypted folder sync, remote HTTP MCP/OAuth plumbing, closed-app awake scheduling, interactive browser mode and account password/deletion endpoints are now built. They should not be listed as absent. Store/release work, cloud inference and the external ChatGPT companion are deferred by the user.

The sections below describe the earlier parity pass. Their reports remain evidence for those earlier binaries; the feature-completion status and current acceptance reports take precedence.

## Electron parity review and follow-up implementation

The latest source review found an important scope correction: Electron's provider picker (`ui/index.html:83`) and AI-provider connection section (`ui/index.html:105`) are hidden in the current UI. Their backend implementations exist, but describing them as current visible Electron parity was inaccurate. Native remains Ollama-only; OpenAI/custom/ChatGPT provider support is additional product work. The user authorised secure API-key creation, and the Platform picker was opened. No confirmed key name, organization/project or local destination has returned, so no secret was created and no API implementation is claimed.

| Area | Current follow-up result | Verification boundary |
| --- | --- | --- |
| Activity history and dock | Shared Foundation presentation model pairs calls/results using IDs with a pending-name fallback, groups command/scanner polling by session, merges output by recorded UTF-16 offsets, and assigns stable identities. Recorded errors, declines, interruption, pending/running and review states are represented. Both work history and dock use it. Dock exposes complete scrollable output, copy, project context, raw events and expandable approach updates, and restores focus after action selection. Replay is cancelled on conversation/view changes. | Production Swift projection compared with Electron `ui/activity.js` on four actual saved conversations: 15 actions and three command-output comparisons passed. One native JSON-error failure corrects an Electron false completed state. Fresh installed GPT-OSS inference read a real proof file and a requested missing file, persisted both results, and projected completed/failed correctly. Installed selection, raw events, focus and final dock command/output sizing were inspected. Full long-run/minimum-window/VoiceOver coverage remains pending. |
| Project opening | System folder chooser exposes locations, path navigation/search, hidden-folder shortcuts and New Folder. A native project-entry sheet adds explicit memory scope/budget. New-project settings are validated before adding; existing projects retain their saved choices. File-list results are cleared/guarded when changing projects, and file context follows the eight-attachment limit. | Real temporary-directory service checks passed for new settings, preserved existing settings and rejected invalid scope. Installed chooser exposed New Folder and path navigation; the new-memory sheet was inspected and cancelled without opening `/tmp` as a project. |
| Aggregate performance | New Usage & performance page reports current-chat input/output, saved output, saved request count, latest speed, first-output latency and recent requests. A durable 2,000-request ledger includes conversation steps and summaries; missing counters remain unavailable. Existing response usage is backfilled. Model benchmarks remain separately accessible. | Installed page displayed actual GPT-OSS counters for the fresh three-request conversation, including first output of 0.38 seconds. Source directory checks verified missing input counters were not invented. Historical backfill can only include usage still present in saved conversations. |
| Small interactions | Markdown link clicks copy the URL like Electron. Dock/work history can copy output. Composer's source-image guard now matches Electron's 12 MB guard. | Source/build verified; full clipboard/image edge cases remain pending. |
| Cloud providers | Pending secure credential target and local destination, followed by implementation and actual API requests. ChatGPT OAuth and custom endpoints are not implemented in native. | No key or cloud inference claim. |
| External companion | Existing local companion and prepared tunnel profile remain. External tunnel runtime key and ChatGPT connector are still pending. | Previous real packaged MCP checks remain valid; no new external tunnel end-to-end claim. |

Current follow-up code was built, packaged with explicit development signing, installed and reopened. Build transcript: `artifacts/native/build-current.log`. New evidence: `activity-acceptance.json`, `project-usage-acceptance.json`, and `dock-live-acceptance.json`. No fake inference or tool output was inserted. Application signing/notarisation and release/update distribution remain outstanding.

## Current implementation status

| Original issue | Current implementation | Verification boundary |
| --- | --- | --- |
| Account / guest memory | Separate identity slots; the agent selects the active identity. Account writes never replace the guest slot. Unverified accounts cannot save account instructions. | Real verified sign-in, distinct temporary account instructions, unchanged guest slot, real model response following the account instruction, original instructions/conversation/mode restored, cloud preset create/apply/delete and native Keychain recovery passed. The temporary validation conversation was archived. Live sign-out and new-account/reset-email flows still need user participation. |
| Model capabilities | Model metadata controls the actual request. Conversation-only requests omit tools and convert historical tool exchanges to readable context. Images and requested tools have explicit capability checks. | Real Gemma 3 vision/chat inference and GPT-OSS tool execution passed. A requested read returned the actual file contents in a persisted tool result. |
| Helper recovery | Restart control, heartbeat, bounded request deadlines, connection-owned cancellation, generation isolation and cleanup of browser/host requests. A supervisor reaps the bundled runner when the helper dies. | Installed helper termination/restart preserved workspace state. Current packaged helper SIGKILL test confirmed supervisor and runner exit. No uncertain action is automatically replayed. |
| Browser controls | Rich snapshots, bounded wait_for, safe input fill, select options and permitted controls. Fresh references required. Public same-origin GET/HEAD fetch/XHR is mediated through a bounded, credential-free read transport. | Real WebKit Wikipedia search input and menu control plus Python documentation theme selection passed. Form submission was rejected. Authenticated interactions, cross-origin reads and workers/streaming widgets are outside this browser policy. |
| Mentions | Caret-relative suggestions, arrow selection, Tab/Enter acceptance and explicit requested-tool routing. | Caret and keyboard interaction checked; real requested-tool model execution passed. |
| Assessment controls | Website case/progress events reach the drawer; starting state exposes cancellation. Run controls check enabled tools, project, connection and input readiness. | Real Nmap scanned a disposable loopback listener and the user-authorised jhye.dev HTTPS port successfully. Current packaged website baseline covered three jhye.dev pages, emitted progress and saved evidence with zero request errors. Complete live UI cancellation coverage remains pending. |
| Nmap readiness | Dedicated readiness request; missing executable, disabled discovery and failed/disconnected request are separate states. Refresh supported. | Installed UI showed Nmap ready with discovery disabled and restored correctly when re-enabled. |
| First run | Entry/setup sheets cannot dismiss into an incomplete workspace; setup close is exposed only after completion. | Current packaged GUI launched with disposable storage: welcome shown, terms unchecked, Continue disabled, no Close control, Escape retained the sheet. No terms were accepted during the check. Existing migrated workspaces keep their completed entry state. |
| Migration | Validated, idempotent candidate import of projects, chats/images, notes, tasks, appearance, auto-summary, skills, paused schedules and safe MCP configuration. Credentials/pairing are excluded, with visible warnings. | Actual Electron workspace imported into disposable storage, imported twice and original file hashes retained. This workspace had no skills/schedules/MCP records, so those collection branches are not claimed as real-data verified. |
| Work history | Per-action selection/status and pending action details are rendered before results arrive. | Real tool results persisted; full presentation comparison across long histories remains pending. |
| Quiet timeline + live dock | Meaningful milestones use the shared stable action projection; the dock shows full command/output, accurate result status, raw events, copy and approach updates, and can fold or replay recorded history. | Installed build verified the timeline and dock against a real local-model response. Replay completed in the live UI. Tool-rich runs still need a separate long-run comparison. |
| Context meter | Uses the same prepared request as inference, including tools, images, summaries, skills and active memory scope; refreshes after responses and configuration changes. | Real summaries/continuation passed. Installed meter/details agreed and updated when tools changed. Counts remain labelled estimates, not tokenizer-exact usage. |
| Sidebar search | Project names and chat titles filter the groups. | Installed interaction checked during implementation. |
| Dialogs/accessibility | Sheets fit available window size, keyboard focus is restored, tool names and selected appearance values are exposed. Drawer scales with window width. | Composer focus restored after closing the context sheet. All four settings themes inspected. Full VoiceOver, minimum-size and every-page comparison remain pending. |
| Terminal | Retains separate shells per project folder while the app is open. Native accessibility wrapper exposes the actual visible buffer, project directory and focus action; SwiftTerm's current macOS service does not supply this itself. | Installed real zsh environment marker survived Wixal → Documents → Wixal; marker was removed afterward. Final installed accessibility tree contained actual shell command output. Shells do not persist across app exit. Full spoken VoiceOver interaction remains pending. |
| Markdown/visuals | Swift Markdown/swift-cmark 0.9.0 parses the document tree; native recursive rendering handles nested/multiline/task lists, quotes, resolved reference links, setext headings, fences and tables. Cells render emphasis/code and column alignment; raw HTML is inert text. Original palettes remain. | Production parser acceptance checks passed without mocked services. The rebuilt installed app was checked against a real 4,346-character local-model response: nested list and quote prefixes are no longer leaked into displayed text, the 45-row table is exposed through AppKit accessibility, and code blocks remain selectable. All four settings palettes were inspected. Full visual and animation/typography parity is not established. |

## Real acceptance evidence

Reports are under `artifacts/native/` at the repository root. None of the following results uses a fake Firebase account or inference response. The browser checks use live public pages; loopback Nmap uses a real scanner against a disposable listener.

- `acceptance-packaged.json`: actual legacy import, real model import, vision response, bundled-runner benchmark, Nmap, model-generated summary/continuation, cancellation and persisted GPT-OSS file-tool execution. Eight stages passed. This suite ran on the earlier package in this implementation pass; subsequent supervisor and final UI changes have separate checks below.
- `acceptance-source.json`: the same real source-engine acceptance stages; recovered from the completed stage journal after the old report filename was overwritten by the packaged run.
- `browser-acceptance.json`: installed WebKit public pages, input filling, checkbox interaction, option selection and blocked submission passed.
- `account-acceptance.json`: real signed-in account, distinct memory isolation/restoration, actual model response following the account instruction, temporary cloud preset lifecycle and Keychain recovery passed. No account identity or credentials are recorded in the report.
- `download-acceptance.json`: actual Qwen 3 4B registry download, 2,497,293,931 bytes, pause, abrupt helper interruption, interrupted-state recovery and completed resume. This test exposed an orphaned runner in the earlier build; the production supervisor fix was separately verified on the current build.
- `recovery-acceptance.json`: current packaged helper killed abruptly; its supervisor and runner exited within the bounded check.
- `install-current.json`: final installed executable/helper hashes and recoverable previous app path. The application remains an explicitly labelled development preview, not a notarised release.
- `first-entry-session.json`: current packaged first-run dismissal gate observed through the real GUI with disposable storage, without accepting terms.
- `markdown-acceptance.json` / `MarkdownAcceptance`: standalone executable invokes the exact production parser and fails on incorrect nested list, reference link, fence, table/alignment, raw-HTML or link-policy behavior. The command-line toolchain lacks XCTest; these checks do not claim visual UI coverage. The final installed legal document was separately inspected for heading/emphasis/paragraph rendering.
- `external-acceptance.json`, `external-nmap.json`, `external-website.json` and `external-website.md`: current packaged helper assessed jhye.dev following the user's explicit target authorisation. Nmap scope was TCP 443 only; website scope was three public pages using baseline reads. Twelve header/configuration observations across those pages are not an exploitation claim.

The final app was installed at `~/Applications/Wixal Native.app`; the user's verified account was restored through Keychain. Account instructions, original guest memory, original theme and enabled tools were restored after validation. No public release or upload occurred.

## Work still required

1. Finish exhaustive four-theme/minimum-window/larger-text/keyboard/spoken-VoiceOver acceptance and the complete long-running activity sequence. Actual composer selection, image inference, removal, oversized/incompatible rejection and draft navigation/relaunch checks have passed.
2. Complete live fresh-account verification, password change and disposable online deletion with user participation. Existing-account restore and actual reset-email receipt passed; the new lifecycle endpoints have supporting regressions.
3. Validate real migration collections for skills, schedules and MCP, including visible malformed/credential-bearing warnings. Real project/chat migration already passed.
4. Verify external authenticated browser/download workflows, an actual external OAuth provider, and encrypted folder delivery on two Macs. Current local protocol, actual public remote MCP, packaged WebKit and two-workspace encrypted-sync checks are scoped evidence.
5. Keep external ChatGPT companion and cloud inference deferred. Local companion sharing/revocation passed; external client acceptance has not.
6. Keep store/release/signing/update delivery deferred under the user's latest instruction. A signing identity and another Mac are available. Comparative application performance, sleeping-Mac wake and other native platforms remain separate outstanding coverage.

Remote HTTP MCP and closed-app scheduling are implemented in the feature completion pass. Scheduling runs while this Mac is awake and the session is logged in. Apple Silicon macOS remains the packaged native target; retain Electron for other platforms and unverified native workflows.

## Historical audit before these fixes

Reviewed 7 October 2026 against current native source, the installed native app and the Electron source. This is a review, not a new implementation pass. It supersedes the broad completion wording in the previous handoff.

## Confirmed functional gaps

| Priority | Finding | Impact and evidence |
| --- | --- | --- |
| High | Account and guest global preferences share one local slot | The agent reads `store.data.globalMemory`. Signing in loads a separate account snapshot but does not switch the agent to that profile; saving account preferences also overwrites the guest slot, and signing out leaves those preferences active. Reproduced with temporary storage and fake Firebase: after sign-in the agent still had `guest profile`; after account save and sign-out it still had `account-specific profile`. Electron selects the profile by account identity instead. `engine/wixal/account.py:157–180,206–212`, `engine/wixal/agent.py:85–87`, original `app/main.cjs:37–38`. |
| High | Non-tool models lack the original capability-aware request path | Except for the image check, native sends enabled tool definitions regardless of the selected model's Tools capability. A conversation-only model can receive a request it cannot handle. Electron checks capabilities and offers ordinary Chat without tools. Native composer also leaves tool actions discoverable without this advice. Source finding: `engine/wixal/agent.py:189–195`; original `app/agent.cjs:126–132`. |
| High | Helper failure has no restart/reconnect workflow | Python termination marks the connection stopped and fails pending calls, but leaves the `process` reference populated; `start()` then returns early. There is no Retry/restart-helper control, and calls have no timeout/disconnected guard. A user must relaunch the app; a helper that stays alive but stops replying can leave an action waiting. Source finding: `Sources/EngineClient.swift:43–44,64–70,107–114`. |
| Medium | Browser automation is substantially narrower | Native returns rendered text and links and supports same-origin link clicks. It lacks input fill, option selection, permitted button/control interactions, the original richer controls/forms/scripts/console snapshot, and `wait_for`. The catalog admits these limits. `Sources/Browser.swift:54–80`, `engine/wixal/resources/tools.json`; original `app/browser-tools.cjs`. |
| Medium | Tool mentions are only a partial autocomplete port | Suggestions use the final token of the whole prompt rather than the caret position. The prompt editor handles Return only; it has no Up/Down/Tab/Enter suggestion-selection path. The picker exposes the first 12 matches, and the backend does not have the original explicit requested-tool parsing/guidance. Typing a name into the prompt is still possible. `Sources/ChatView.swift:22,136–139`, `Sources/PromptEditor.swift:4–9`; original `ui/renderer.js:565–578`, `app/mentions.cjs`. |
| Medium | Assessment progress/cancel UI is incomplete | Website/simulation emits `assessment-case`, but the Swift client only consumes `assessment-progress`. Tool kit shows its Stop button only after progress exists, so website/local simulation lacks that inline progress/cancel path. Network polling has a progress path; general agent Stop is a separate control. `engine/wixal/website.py:208`, `Sources/EngineClient.swift:156`, `Sources/ToolsDrawer.swift:34–35`. |
| Medium | Nmap readiness conflates disabled discovery with missing installation | The drawer obtains readiness by invoking the enabled `security_tools` tool and converts every error to `false`. If discovery is disabled or otherwise fails, it says Nmap is missing even when installed. It checks only when the drawer appears. `Sources/ToolsDrawer.swift:38,45`. |
| Medium | First-run entry can be bypassed by closing setup | The backend requires explicit entry completion before setup completion, but the first-run sheet always has a Close button and can dismiss into the workspace before entry choice/acceptance. Existing migrated workspaces are intentionally treated differently; the issue is the new first-run path. `Sources/WorkspaceView.swift:99`, `Sources/SetupView.swift:17–26`. |
| Medium | Migration leaves several settings and records behind | Import copies projects, sessions, memories and tasks and a small preference list. It does not migrate appearance settings, auto-summary preference, skills, schedules or MCP configurations. Credential/pairing exclusion is intentional and should remain explicit. `engine/wixal/storage.py:120–140`. |

## UI and interaction work still incomplete

- Work history groups tool results, but has no equivalent of the original per-action selection/status dock. Assistant `tool_calls` with empty text do not render their action details until a result appears. `Sources/ChatComponents.swift:47–55`.
- The context counter can reuse a saved `contextInfo` estimate generated before the latest response; its fallback also omits full tool/image/summary overhead. It is an approximation, but should remain current and agree with the details view. `Sources/ChatView.swift:132`, `engine/wixal/agent.py:177–185`.
- Disabled manual assessment tools leave an enabled-looking Run button; clicking it produces an error asking the user to enable the tool. Electron disables these controls according to tool/model readiness. `Sources/ToolsDrawer.swift:45–55`, original `ui/renderer.js:408–412`.
- Sidebar search matches conversation titles, but does not actually filter project groups by project name despite saying “Find a project or chat”. `Sources/WorkspaceView.swift:151–152`.
- Some secondary sheets still use fixed sizes, including account/legal sheets inside setup and image preview. Long content, keyboard focus restoration, VoiceOver and the minimum-size window with both terminal and drawer need a dedicated pass. `Sources/SetupView.swift:44–45`, `Sources/ChatComponents.swift:45`.
- Terminal retention within the same project works. Switching project replaces/terminates that terminal when shown again; there is no per-project shell restoration. This is a remaining workflow limitation rather than a claim that every original version kept separate project shells. `Sources/Terminal.swift:8–15`.
- Exact typography, icon shapes, card spacing, selected states, Markdown edge cases and motion timing still differ or have not been compared across every screen in all four themes. The app has a 1000 × 680 minimum. Matching palettes does not establish complete visual parity.

## Implemented but still needing live validation

These should not be described as missing implementations:

- Firebase sign-in/create/reset/verification, Keychain restore and cloud preset operations with an actual account.
- Companion operation through a real external tunnel and ChatGPT connection; local scoped transport/queue tests already exist.
- Real image-model inference and large-file/image behaviour through the packaged composer.
- Large real model download pause/resume/retry, interrupted-launch recovery and benchmarks against the bundled runner.
- Real Nmap assessment and external website/search workflows on an authorised target.
- Long real conversations exercising summary generation, continuation and scroll behaviour, and large Markdown/code/table rendering.

The previous 48-test suite and packaged smoke remain useful evidence, but do not cover all these paths. During this review, installed Workspace keyboard navigation successfully opened Task inbox, and Tool kit opened with compact composer controls and live readiness. A temporary fixture reproduction confirmed the account-memory problem. No user account, credentials, public service or project content was changed.

## Separate product/release work

Cloud inference providers, remote MCP HTTP/OAuth, closed-app scheduling, self-service online account deletion, Developer ID/notarisation, release/update distribution and non-Apple-Silicon/non-macOS packaging remain outside the completed local preview. Cloud-provider fields were hidden in the current original UI, and some items are new capabilities rather than regressions from visible Electron behaviour. A SwiftUI/AppKit frontend also does not itself provide Windows/Linux UI.

No controlled Electron-versus-native startup, memory, UI responsiveness or inference benchmark has been completed. Model benchmark controls do not answer the application-level performance comparison.

## Recommended next order

1. Correct account/guest memory separation and model capability handling.
2. Add helper recovery and finish assessment progress/cancellation/readiness.
3. Finish first-run gating, caret/keyboard mentions and migration coverage.
4. Decide the intended browser-control parity, then implement and verify that scope.
5. Run the visual/accessibility and live integration passes before calling the native app a complete replacement.
