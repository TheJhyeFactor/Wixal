# Layout, activity and keyboard workflow tracker

Updated 2026-10-07. This section records implementation and evidence separately. Source changes are now packaged and installed; consult the main tracker for hash-specific evidence and open UI acceptance.

| Workflow | Implementation | Verification | Remaining acceptance |
| --- | --- | --- | --- |
| Compact drawer | Under 1200px, tools/memory use a dismissible overlay rather than narrowing chat beside the sidebar. Drawer retains readable width. Escape and explicit close remain available. | Swift frontend parse passed; diff check passed. | Installed minimum-window/four-theme/18pt check, drawer focus return and keyboard-only use. |
| Terminal and composer | Terminal height capped at 32% of window with a 120px minimum; visible labelled close. Composer text scrolls within 100px in compact layouts / 170px otherwise. | Swift frontend parse passed. | Installed terminal+drawer+dock+composer combinations; multiline editing. |
| Activity dock | Fold hides both chips and detail. Detail scrolling capped to 24% of chat height (90–220px). Running and waiting-for-approval labels distinct. Stopped/cancelled distinct from failed. Stop remains visible while busy. Replay has a Stop replay action and cannot start during work. | Swift frontend parse passed. | Full installed stream, scroll-up, approval, decline, error, Stop, replay sequence. |
| Activity navigation | Selected milestone and folded state stored per conversation (IDs/preferences only) and restored after switching chats/pages or reopening app. Existing scroll-up suppression and Jump to latest retained. | Swift frontend parse passed. | Installed navigate away/back with selected evidence; ensure scroll-up stays respected while streaming. |
| Assessment progress | Stop and progress moved above scrollable tool list. Partial result status, interruption explanation, completed cases and expandable exact evidence shown. | Swift frontend parse passed. Root owns backend persistence and cancellation verification. | Installed stop at each assessment stage; verify partial evidence can be saved. |
| Projection workload | Production projection precomputes turn count and checkpoint lookup, eliminating repeated full-transcript scans per tool. Cancelled checkpoints and structured assessment status recognised. | Final release binary: 7 actual saved tool conversations, 30 replays of longest actual transcript, 443 exact retained tool evidence checks. Max projection process time 0.016s. Report: artifacts/native/activity-workload.json. | Final release binary rerun passed; report updated. Available longest real transcript is 29 messages/96,284 bytes; this does not certify a 30,000-message chat. |
| Accessibility | Drawer Escape dismissal, terminal close label and message-copy labels added. Dock status accessible; semantic buttons retained. | Swift frontend parse passed. | Full spoken VoiceOver/focus order and sheet/menu return-focus acceptance remain unverified. |

Reproducible workload command after final build:

```
python3 native/scripts/activity-workload.py
```

This reads existing native SQLite read-only, emits no conversation content, preserves every recorded tool result exactly, and fails when no real transcripts are available. It writes failure details before propagating a failing assertion. It does not generate fake results or infer UI passes from source checks.
