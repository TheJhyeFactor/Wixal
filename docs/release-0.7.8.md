# Wixal 0.7.8 — Browser sessions and tool reliability

Browser tools now keep an isolated page session, follow reviewed links, use ordinary controls and return readable evidence to the conversation. This release also reduces tool schema overhead and improves error handling, search, HTTP and project file tools.

- Open, read, interact with and close isolated Chromium sessions. Use fresh refs for reviewed clicks, text input and option selection; wait for delayed content and page long text. Stale or changed controls, submissions and credential fields are rejected. Four-session ceiling, fifteen-minute idle expiry, Stop and quit cleanup.
- Read real source titles, links and snippets from search. Empty searches, challenges and rate limits have distinct outcomes. HTTP GET results include chunk offsets and byte-limit metadata; HEAD requests are supported. Redirects still require a reviewed destination.
- Load tool schemas for the current task, with workspace_info discovery for another enabled category. The tool kit remains authoritative. A declined action or three identical failures ends tool execution for that turn and requests a visible conclusion.
- Make exact unique file edits and create project directories after review. File search now includes supported text files up to 1 MB and pages later matches. Concurrent edits and protected paths remain enforced.
- View readable browser/search/HTTP evidence and status in chat activity. Full original tool results remain saved, while model context receives valid JSON excerpts with session and pagination metadata.
- Validate advertised tool arguments before execution and strengthen MCP catalog, cancellation and error regression coverage.

Read [tool workflows and limits](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/tool-workflows.md) for the supported browser actions and limits. This is an isolated reading/control tool; authenticated sessions, arbitrary browser JavaScript, downloads and form submissions are unsupported. Search depends on its external service. Local model decisions still vary.

Project memory scopes, the optional 1,200-character account profile, context estimates, new-chat handoff and model switching from 0.7.7 remain available.

## Install

Download the Apple Silicon DMG or ZIP and drag **Wixal.app** into **Applications**. Requires **macOS 14 or newer**. The local engine is included; download or import model weights from Models.

This preview is ad hoc signed with bundle integrity checks. It is **not Developer ID signed or notarised**. See [Apple's instructions for opening an app from an unidentified developer](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac) if macOS blocks first launch. Verify downloads with the accompanying SHA256SUMS.txt.
