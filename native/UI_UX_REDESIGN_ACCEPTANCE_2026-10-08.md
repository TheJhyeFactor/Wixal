# Native UI and UX acceptance, 8 October 2026

User approved implementation of the simplified design. This is an installed local development preview, not a public native release. The Electron distribution remains separate.

## Implemented design

- Quiet sidebar with Chat, Agents and Cybersecurity, independently collapsible Projects and Recents, project labels on recent chats, and Settings at the bottom.
- Separate Chat and Agent routes with per-conversation mode persistence. Agent tasks and schedules use Agent mode. No mode switch below the chat composer.
- Inviting empty chat with four starter questions that populate the draft without sending. Model selection stays in the composer.
- Project overview contains Files and Terminal. Project settings contains saved context. No top-level Memory, Pinned Memory or catch-all More destination.
- Settings groups General, Models & tools, Context and Connections; account/setup remains discoverable.
- Dedicated Cybersecurity assessment/evidence workspace. Review keeps its target above scrolling parameters, supports Escape decline and readable before/after file previews.
- Project deletion confirmation explains scope: associated chats including archived chats, saved project context, pending suggestions, tasks, assessment evidence, usage and recall index are removed locally; the actual folder and files remain. Unrelated projects and global context are preserved. Local deletion exclusions prevent older encrypted snapshots restoring the deleted project in the same workspace; this does not certify cross-device project deletion delivery.
- Larger-text scaling covers navigation, forms, composer and terminal; compact composer layout and accessibility selected states are improved. JSON-quoted declined results now project as Declined while retaining raw evidence.

## Final package and supporting verification

Installed: `/Users/jhye/Applications/Wixal Native.app`.

- Executable SHA-256: `e2fd0b229b403618455b51023e0f67fd70ff33999498ca511c626b34411fb4b4`.
- Engine SHA-256: `359dd14fe3674cae5091f9b041236e3b48478dda80726b51cd098eefa004fcb2`.
- Previous install retained at `/Users/jhye/Applications/Wixal Native previous 20261008-000733.app`.
- Full Python regression suite: **114 passed**. Native Swift release build, development packaging, hash-verified installation and packaged smoke passed (`PACKAGED_NATIVE_SMOKE_OK`).
- Meaningful project deletion regressions include inactive/active projects, archived chats, recall cleanup, save/reopen persistence and exclusion of stale encrypted snapshot records. Mode routing and startup phase reporting are covered.
- SQLite startup diagnostics now report database path, phase and helper PID before open through local OSLog. The original OS file-open hang has not been reproduced or diagnosed; watchdog/lock timeouts remain mitigations.

## Visible installed acceptance

All UI actions used a disposable workspace `/tmp/wixal-redesign-acceptance/state`; no real project was deleted or user conversation sent.

On the immediately preceding executable `5acfd34…` / helper `dc60972…`, a 12-page loopback website with four-second responses was started through the review UI. Clicking Stop while the assessment was running returned the UI to idle. Evidence visibly showed **Partial result · Cancelled, 12 checks recorded**. Only `/` and `/1` were requested in this final run, no further requests or report files were produced, and the result survived app quit/reopen. Earlier installed passes also cancelled during an in-flight response, retaining 12 or 18 checks. Earlier failures and locked-desktop blockage remain recorded in VISIBLE_ACTIVITY_ASSESSMENT_ACCEPTANCE.md.

Focused minimum-window checks used the production UI with acceptance sizing at **920 × 640 content points**, **17-point Extra large text**, and Sakura, Midnight, Forest and Paper themes. The four-theme matrix ran on executable `3336b414515486fab45d4e73c7b4b83d852d43e8616a493cd37ec80219a1d5f1`; final changes after that matrix affected backend deletion persistence and generated build metadata. Final Chat and assessment/evidence views were checked again on that same package. The final package changes only the saved-account startup deadline and generated build metadata. Manual CUA drag resizing failed and is not counted as a pass.

Observed: starter question fills a draft without sending; independent sidebar collapse; Chat/Agent session switching; project Files/Terminal; grouped Settings; assessment review; cancellation evidence; deletion confirmation opening and Escape cancellation. Keyboard checks passed Command-K command search, Command-comma settings, Command-N new Chat, Command-J terminal, Escape decline and Escape cancel deletion. Sidebar selected-state labels are exposed in accessibility.

Artifacts: `artifacts/native/redesign/acceptance.json`, regression/package/smoke logs, loopback request log, persisted state summary, and screenshots `chat-final.png`, `stop-final.png`, `review-final.png`, `settings-final.png`, `delete-confirmation.png` and the four `*-large.png` theme views.

## Additional normal-workspace startup correction

Reopening the real workspace exposed a separate deadline mismatch: saved sign-in restoration allowed 45 seconds but the native startup watchdog allows 30. The account restore deadline is now 10 seconds, preserving a route to local guest preferences when the remote service is unavailable. A meaningful cancellation regression passes. The final installed normal workspace visibly loaded its projects and recent chats, restored Agents and connected gpt-oss:20b after the bounded restoration wait. This is distinct from the original SQLite file-open incident.

## Remaining acceptance boundaries

Spoken VoiceOver and exhaustive keyboard focus/all-dialog/all-theme checks remain unverified. Focused checks above do not certify every screen. Original SQLite file-open cause remains unknown. Disposable online account lifecycle, actual two-Mac sync delivery, privileged sleeping-Mac wake, Intel hardware and paused Windows/Linux coverage retain their existing blockers. No public release, online account deletion or privileged service installation occurred.
