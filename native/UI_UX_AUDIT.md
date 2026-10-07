# Native versus Electron UI and UX audit

## Implementation update, 6 October 2026

The findings below are the original audit, retained as the comparison baseline. The current native package implements the following corrections. Implementation does not imply that every external service or visual state has been exercised live.

| Area | Current implementation | Verification |
| --- | --- | --- |
| Composer | Persistent conversation drafts, reviewed project excerpts, image preparation/previews/removal, vision capability check, enabled tool mentions, growing editor and compact overflow | Conversation tests; packaged Files → attachment → restored draft and tool insertion checked |
| Conversation | Bottom-sensitive streaming, jump to latest, grouped work history, action previews, context estimates/usage, summaries and continuation, richer Markdown and accessible tables | Engine/conversation tests; packaged work history and context controls inspected |
| Navigation | Rename/copy/archive/restore/delete, searchable archive dialog, task navigation, Settings shortcut, workspace menu keyboard focus and desktop shortcuts | Workspace tests; packaged Settings and Files shortcut checked |
| Terminal | Scene-owned terminal survives hiding; close on scene shutdown; clear output | Packaged hide/reopen retains terminal output |
| Models | Installed filters/sorting, fit/context advice, benchmark/cancel, delete/unload, runner/library status, curated catalog, persistent download queue and pause/resume/retry | Eight model tests with local HTTP fixture; packaged model page inspected |
| Memory | Edit/cancel notes, project/global/both/off modes, budgets, capacity, profile controls and summary clearing | Conversation/workspace tests |
| Tools | Search/categories, enable all, manual network/website forms, progress/results/report saving and eight-case loopback simulations | Eight website tests including sixteen vulnerable/hardened checks and cancellation |
| Account/setup/legal | Sign-in/create/verification/reset/profile/sign-out, Keychain-backed session, presets, global preferences, guest/setup flow and original draft legal text | Fake Firebase integration tests; packaged account dialog inspected; live authentication not attempted |
| Sharing/task inbox | Explicit scoped companion pairing, project/memory choices, commands/help, source/brief/start/dismiss/retry/result/open actions | Scoped companion integration and workspace task tests; real external tunnel not activated |
| Appearance | Original four palettes and wordmark, restrained card/row styling, popup focus, responsive parent dialogs, reduced-motion settings | Packaged Paper Settings/chat inspected; complete pixel and animation comparison remains unmeasured |

External sign-in/reset/Keychain recovery, real image-model inference, large real downloads and external companion tunnel operation still need user-driven live validation. These are connected implementations with fixture coverage, not claims of external service success. Developer ID/notarisation, other platforms, full browser form interactions and comparative performance benchmarks remain separate release work.

## Original audit baseline

Checked 6 October 2026 against the installed Electron Wixal 0.7.8, the current Electron UI source, and the newly packaged native preview. **The native preview is not yet a replacement with feature or interaction parity.** Its overall workspace layout and appearance controls have been ported, but several everyday workflows are incomplete.

## Evidence and scope

- Live original inspection: conversation, sidebar, Workspace popup, response statistics/context warnings and Settings dialog. Other original surfaces were reviewed in `ui/index.html` and `ui/renderer.js`; this is not a claim that every original control was exercised live.
- Live native inspection: packaged chat/terminal, Workspace popup, popup Escape dismissal, Settings opening/closing, Command-comma while the composer has focus, and installed Models, Tools and Memory. Additional native screens were inspected during the preceding design pass; remaining findings below are identified directly in current source.
- The packaged smoke uses an isolated workspace and a local model-shaped fixture. It checks streamed chat, a real file write and command, shared desktop/terminal IPC and native WebKit render/read/link/close with stale-reference rejection. It does not establish external service, account, scan, download or inference performance parity.
- Source references are `path:line` starting points. `Sources/` and `engine/` paths are relative to `native/`; `ui/` and `app/` paths are relative to the repository root. Findings describe visible controls and their actual connected actions, rather than counting backend methods as completed UI.

## Fixes completed during this check

| Item | Result | Evidence |
| --- | --- | --- |
| Bottom-left Workspace menu | Replaced the generic system menu with the themed 220-point popup, grouped rows, counts, shortcuts, footer and refresh control. Anchored above the bottom-left button; Paper theme and Escape dismissal checked live. | `Sources/SidebarMenu.swift:15`; `Sources/WorkspaceView.swift:74` |
| Settings entry | Sidebar now consistently opens a dialog instead of toggling a full page. Added the macOS Settings menu action and Command-comma. Close returns to the conversation; shortcut checked with composer focus. | `Sources/WorkspaceView.swift:84`; `Sources/WixalApp.swift:23` |
| Popup appearance | Corrected SwiftUI environment placement so overlays inherit the selected theme instead of using default Sakura colours. | `Sources/WorkspaceView.swift:103` |

The Settings entry worked in the earlier installed preview during inspection. The reported failure was not reproduced as a crash or an inert button; the confirmed problems were different navigation behaviour and the absent standard Settings command. These corrections are packaged and installed locally.

## High-priority gaps and regressions

| Area | Original behaviour | Native gap or difference | Evidence |
| --- | --- | --- | --- |
| Project file context | Preview a file and add an excerpt to the next message. | The composer button says “Add project file” but only opens the read-only Files page. There is no add-to-message action. | `ui/renderer.js:853`, `ui/renderer.js:873`; `Sources/ChatView.swift:68`, `Sources/ManagementViews.swift:3` |
| Image attachments | Attach images, show/remove previews and apply model capability checks. | No attachment button, thumbnail strip, removal flow or vision composer. | `ui/renderer.js:879`; `Sources/ChatView.swift:54` |
| Tool mentions | `@ Tools` inserts a mention and offers tool selection in the composer. | `@ Tools` opens the tool permissions drawer; no mention insertion/autocomplete. The label promises a different action. | `ui/renderer.js:565`, `ui/renderer.js:1005`; `Sources/ChatView.swift:74` |
| Drafts | Save/restore text per conversation, including when navigating. | Prompt is view-local state with no draft persistence or per-session restore. Leaving Chat can discard it; switching sessions can leave text associated with the wrong conversation. | `ui/renderer.js:730`; `Sources/ChatView.swift:10`, `Sources/WorkspaceView.swift:39` |
| Streaming scroll | Follow output when near the bottom; permit reading older messages; offer jump-to-latest. | Every streamed update scrolls to the bottom. No jump-to-latest control. | `ui/renderer.js:303`, `ui/renderer.js:342`; `Sources/ChatView.swift:30` |
| Terminal lifecycle | Hiding the panel retains the existing shell session. | Removing the SwiftUI terminal view terminates its process, so hiding/reopening loses the interactive session. | `ui/renderer.js:817`, `app/main.cjs:447`; `Sources/Terminal.swift:19` |
| Chat versus Agent | Enabled tools can be requested in both modes. | Native only sends tool definitions in Agent mode. A user selecting Chat loses the original requested-tool workflow. | `ui/renderer.js:408`; `engine/wixal/agent.py:131` |
| Task navigation | Open the task conversation and view its work/results. | The button “Open conversation and resume” selects the session and starts work but does not switch the visible Tasks page to Chat. Completed tasks have no equivalent open-conversation action. | `ui/renderer.js:687`; `Sources/ManagementViews.swift:112` |
| Keyboard navigation | Project files have Command-Shift-F; Tools has Command-Shift-T. | Popup displays Command-Shift-F, but native has no corresponding binding. Drawer Escape/focus restoration and popup arrow-key traversal need parity work. | `ui/renderer.js:1148`; `Sources/WorkspaceView.swift:96`, `Sources/SidebarMenu.swift:27` |
| Model readiness feedback | Local runner/library status and errors inform connection UI. | `engine.connected` means the Python helper is ready; it does not establish that Ollama or the selected model is usable. Native “Wixal Local connected” can therefore overstate inference readiness. | `ui/renderer.js:585`; `Sources/EngineClient.swift:93`, `Sources/SidebarMenu.swift:32` |

## Screen-by-screen missing controls

| Screen / workflow | Native state | Remaining UI and UX work | Evidence |
| --- | --- | --- | --- |
| Sidebar and conversation header | Grouped projects/chats, search, collapse and archive/restore exist. | Account row; rename from title/menu; conversation deletion/confirmation; dedicated searchable archived-chat dialog. Native Archives toggles archived items into the normal list. The options menu always offers both Archive and Restore. | `ui/renderer.js:122`, `ui/renderer.js:1087`; `Sources/WorkspaceView.swift:132`, `Sources/WorkspaceView.swift:152` |
| Composer | Text send/stop, model selection, mode/review choices and skills selector exist. | Attachments, file context, mentions, persistent drafts and content-driven editor height. Native editor has a fixed 58-point viewport. Compact mode hides Files, Tools and Skills rather than moving them to an overflow menu. | `ui/renderer.js:210`; `Sources/ChatView.swift:54` |
| Conversation work history | Native displays assistant text and individual expandable raw tool results. | Original grouped work history, step/tool counts, approach updates, activity dock, action selection/status and formatted scanner evidence. | `ui/renderer.js:235`, `ui/renderer.js:268`, `ui/renderer.js:271`; `Sources/ChatView.swift:94` |
| Context and continuation | Context size can be selected; recent complete turns are retained by the engine. | Estimated context meter, nearing-budget warning, continue-in-new-chat dialog, optional model summary/fallback excerpts, saved-summary view/clear and automatic summarization preference/pipeline. A stored `autoSummary` field does not implement the feature. | `ui/renderer.js:395`, `ui/renderer.js:814`, `ui/renderer.js:1350`; `engine/wixal/agent.py:82`, `Sources/SettingsView.swift:36` |
| Response usage/performance | Footer displays Ready/activity. | Tokens, tokens/second, generation duration, usage totals, saved benchmarks and performance dialog. | `ui/index.html:78`, `ui/renderer.js:552`; `Sources/ChatView.swift:79` |
| Markdown/readability | Paragraphs, inline formatting, simple headings, fenced code/copy and simple tables exist. | Full block lists/quotes, heading hierarchy and richer table parsing/layout. Tables use a grid rather than accessible table/header/cell semantics. Long table/code content needs narrow-window QA. | Original conversation AX exposed table/row/header/cell structure; `Sources/MarkdownMessage.swift:5`, `Sources/MarkdownMessage.swift:37` |
| Approval dialog | Real approval/decline controller remains connected. | Original action-specific titles/explanations and readable command/network/file previews. Native renders a generic JSON object for all actions. | `ui/renderer.js:1153`; `Sources/ChatView.swift:113` |
| Installed model library | Search, selection, capability/context information and import are present. | Capability/hardware-fit/size filters, sorting/reset, estimated RAM fit, benchmark/cancel/results, delete model, loaded-model memory, unload action, model-folder reveal and suggested context action. Native context choices lack the original model/hardware advice. | `ui/index.html:92`, `ui/renderer.js:448`, `ui/renderer.js:525`; `Sources/ManagementViews.swift:30` |
| Model downloads | Manual Ollama tag download exists. | Curated “Models for this Mac”, persistent queue, byte/percentage/speed feedback, cancel/pause/resume/retry and per-download management. Current native view only shows a waiting label/result. Import also requires a second manual selection step. | `ui/index.html:96`, `ui/renderer.js:597`; `Sources/ManagementViews.swift:81` |
| Project memory | Add/delete project notes; basic scope/global instructions in Settings. | Edit note/cancel edit, project/global/both/off mode parity, saved-note budget choices/capacity, retrieval explanation, global-profile enable/count/account refresh and saved conversation summaries. | `ui/renderer.js:1325`; `Sources/WorkspaceDrawer.swift:23`, `Sources/SettingsView.swift:43` |
| Tool kit | Flat tool toggles and descriptions work. | Search, categories, enable-all, manual network scan form and readiness state, website assessment controls, profiles/report path and recent structured results. The original eight-case website simulation suite is not ported. | `ui/renderer.js:406`; `Sources/WorkspaceDrawer.swift:14`; `README.md` port status |
| Files | Search/list/read-only preview exists as a page. | Original modal/return-to-composer flow, Add to message and specific loading/read-error/empty-list feedback. A page layout can be a valid native choice, but it must preserve the full workflow. | `ui/renderer.js:853`; `Sources/ManagementViews.swift:3` |
| Connections and sharing | Menu route currently opens Settings with local MCP controls. | Dedicated sharing screen, per-project companion access, shared-memory choice, companion enable/status, tunnel command and setup/help links. Local MCP clients are a different integration from the original companion. | `ui/index.html:104`, `ui/renderer.js:665`; `Sources/WorkspaceView.swift:181`, `Sources/SettingsView.swift:68` |
| Task inbox | Native agent runs/checkpoints/resume and app-open schedules exist. | Original companion-sourced task brief, source/project identity, explicit Start/Dismiss/Retry and completed-response/open-conversation presentation. New native scheduling does not replace these controls. | `ui/renderer.js:687`; `Sources/ManagementViews.swift:96` |
| Account | No native account UI. | Sidebar identity, sign-in/create/guest flow, verification/password-reset, sign-out/profile, cloud presets and account-linked global memory. | `ui/index.html:132`; native has no matching account view |
| First-run/setup and legal | Native launch intro and appearance controls exist. | Welcome/guest entry, setup steps/readiness, run-setup-again, Terms/Privacy dialogs and corresponding Settings links. | `ui/index.html:122`, `ui/index.html:132`; `Sources/SettingsView.swift:4` |
| Settings presentation | Now a working sheet; four themes, icon variants, text size, motion, launch options and compact sidebar exist. | Original account/setup/legal sections and auto-summary option; exact card/row spacing, checkbox/switch appearance and section order differ. Native adds Skills/MCP/import controls, making the dialog longer. | Live comparison; `Sources/SettingsView.swift:4` |
| Visual polish and motion | Original palettes, wordmark, broad geometry and intro vectors have been reused. | Exact icon shapes, typography/weight, message alignment/spacing, popup focus treatment, selected-state semantics and animation timing still require focused comparison. Fixed-size Settings/model sheets need small-window checks; the app currently has a 1000-by-680 minimum. Current work is not pixel-for-pixel parity. | Live Paper theme comparison; `Sources/Theme.swift`, `Sources/LaunchView.swift`, `Sources/ChatView.swift`, `Sources/WixalApp.swift:17` |

## Recommended completion order

1. Fix draft handling, terminal retention, streaming scroll, task navigation and truthful model status. Finish keyboard/focus behaviour for the menu, dialogs and drawers.
2. Restore the complete composer workflow: add file context, image attachments, tool mentions, expanding editor and compact overflow controls.
3. Restore conversation management, work history, context warnings/continuation and readable action reviews.
4. Bring model management up to parity, particularly download progress/cancellation, capability filters, hardware/context advice and benchmarks.
5. Complete Memory and Tools panels, including editing/budgets and the manual assessment workflows.
6. Port account, setup, legal and companion sharing as complete connected flows. Finish a visual/accessibility pass at regular and narrow window sizes in all four themes.

Acceptance should exercise a workflow from start to finish: for example, open a file, add it to a draft, switch away/back, send it, review an action, inspect its output and continue the conversation. A matching button or page heading alone is insufficient.

Cloud-provider fields hidden in the current Electron UI were not counted as visible shipped controls. This audit does not claim an exact parity percentage, runtime speed advantage or completed public release.
