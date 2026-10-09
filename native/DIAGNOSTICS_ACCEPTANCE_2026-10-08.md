# Native local diagnostics and selection fixes

Verified 8 October 2026, Australia/Sydney. Installed local development preview: `/Applications/Wixal.app`. Electron was not edited.

## Findings from actual saved conversation

The Sabrina Carpenter conversation retained 18 messages. `browser_search` failed because the tool name was unavailable. The first `web_search` supplied unsupported `recency_days` and `top_k` arguments; supported fields were `query` and `limit`. A corrected `web_search` succeeded. Three 547-character assistant conclusions remained saved. The task finished `needs_attention`, with `browser_search` still listed as unresolved. Controller verification could therefore request another conclusion. The previous UI projected only the last conclusion per user turn.

## Implemented

- Preserve all saved assistant conclusions in the visible chat when another response or user turn arrives.
- Historical action selection uses stable action IDs and toggles off when clicked again. Collapsing Details clears the selection.
- Current action disclosure uses explicit optional selection and supports closing the selected action and the overall Details group.
- Native Markdown table selection clears on a second ordinary click of the same row or Escape; text selection and table accessibility remain available.
- Always-on local metadata log: `~/Library/Application Support/Wixal Native/logs/engine.jsonl`. Rotates at 2 MiB with four backups. Files are private (`0600`), folder is private (`0700`).
- Event records include boot/sequence IDs, request start/end and elapsed time, model requests, saved-response counts, tool attempts/results with action/task/session IDs, classified failures/fingerprints, verification status/unresolved IDs, and Details selection events.
- Chat text, model thinking, tool input values, full tool result contents, credentials and page text are excluded. Full tool errors remain in the saved conversation action details. Logs are local and are not part of cloud workspace sync or saved-work backups.
- Settings → General & about → View local logs shows the latest 200 records, with Refresh, Copy events and Show logs in Finder.
- Swift UI interaction and table selection events also emit OSLog records in ChatActivity and ResponseTable categories.

## Verification

- Swift debug build and final release/package build passed.
- 59 relevant Python regression tests passed across diagnostics, Settings, thinking streams, Chat tools, agent outcomes and IPC. After final logger changes, 9 diagnostics/Settings/stream tests were rerun and passed. These are automated regression evidence, separate from real model and UI evidence.
- Packaged isolated UI preview used a copy of the actual saved conversation, without copying account credentials. Verified failed-action select/deselect, history collapse, current-action expand/collapse and the local log viewer. Recorded UI events were confirmed in both the JSONL file and OSLog.
- Final installed app: WCF row changed from selected to unselected on a second click; Escape cleared selection and emitted the corresponding OSLog event.
- Final installed helper with actual `gpt-oss:20b`, in a separate workspace, read the actual diagnostics.py source. Confirmed all required model/tool/verification events and task correlation. An actual invalid-argument tool call and a later successful workspace-info call remained separately recorded. See `artifacts/native/diagnostics-final-model/result.json`.
- Installed source manifest matched every current source hash. Installed binary/helper hashes matched the packaged app; local bundle signature verification passed. See `artifacts/native/install-current.json`.
- Saved-work digest matched before and after installation: 15 sessions, 1 project, 0 memories, 13 tasks. See `artifacts/native/diagnostics-installed-check.json`.
- Previous installed app was retained by the installer; its archive path is in `artifacts/native/install-current.json`.

## Limits

This adds observability and corrects visible response/selection handling. It does not alter the controller's outcome recovery policy; unresolved tool failures can still lead to additional conclusions. Metadata failure categories are diagnostic hints, not a replacement for the full saved action error. Existing answers were not fact checked. Logs begin with this build and cannot reconstruct earlier unsaved transient UI state. This remains a locally signed development preview, without notarization verification.
