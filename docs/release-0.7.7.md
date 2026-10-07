# Wixal 0.7.7 — Memory, context and model switching

Project memory now has scope choices, editable notes and visible capacity. A short optional global preference profile makes chats more personal without uploading project history.

- Choose memory off, project-only (the default), global preferences only, or project + global when opening a new project. Relevant earlier active chats remain scoped to that project.
- Choose Light (8,000), Balanced (24,000) or Detailed (48,000) saved characters. The UI explains the tradeoffs and enforces capacity without silently deleting notes.
- Save a global profile of up to 1,200 characters. Guest profiles stay local; verified account users explicitly save through owner-only Firebase access. Signing in keeps guest and account profiles separate.
- See estimated context usage in the composer. Context defaults to 8k tokens with a model/RAM-aware ceiling of 32k and space reserved for replies. Older complete turns are summarized, long tool loops use bounded older evidence, and oversized new prompts receive an actionable error.
- Continue in a new chat with either a fresh start or an AI summary inserted as a visible first message. The source chat remains saved. Summary cancellation preserves the current chat; failures use labelled excerpts.
- Switch local models within a conversation. Wixal retains original history, identifies the generating model and converts older foreign tool exchanges into portable text evidence. Text-only models receive labels for earlier images.

This release also includes the local tool/workspace context, workspace-scoped Approved all, website assessments and local attack fixtures, Nmap profiles, folded tool activity, optional account presets, launch settings and app icon choices developed since 0.7.3.

## Install

Download the Apple Silicon DMG or ZIP and drag **Wixal.app** into **Applications**. Requires **macOS 14 or newer**. The local engine is included; no model weights are bundled. Download or import a model from the Models page.

This preview is ad hoc signed with bundle integrity checks. It is **not Developer ID signed or notarised**. If macOS blocks first launch, follow Apple's [instructions for opening an app from an unidentified developer](https://support.apple.com/en-au/guide/mac-help/mh40616/mac).

Model inference runs locally. Only explicitly saved account presets and the short global preference profile sync through Firebase. Companion sharing is separate and limited to selected projects. Project-only excludes the global profile. Review each action is the default; Approved all applies to enabled tools in the selected workspace. The bundled legal documents remain labelled drafts.

## Verification

Core tests cover scope isolation, capacity and migration, editable notes, context ceilings and output reserve, oversized-input rejection, long tool polling, model history conversion, handoff summary/fallback/cancellation, accounts, permissions, command sessions and local assessment fixtures. Electron checks exercise the actual renderer and IPC at desktop and compact sizes, including memory settings, persistence, new-project configuration, the context warning and summary cancellation.

Live Firebase checks verified owner save/read/clear, rejected anonymous and cross-account reads, verified the server's 1,200-character ceiling and removed all temporary test profiles/accounts. A real packaged GPT-OSS read returned file evidence; switching to Gemma in the same chat retained the exact marker, and Gemma generated a new-chat summary while the source remained saved. Packaged website and network tool flows were exercised against disposable loopback fixtures.

Token usage and memory fit are estimates, not exact tokenizer counts or a guarantee that a model fits alongside other apps. Project recall uses local keyword matching rather than embeddings. Summaries may omit details. Global profile refresh is explicit outside sign-in/restoration; there is no background multi-device merge. Save only information you want reused.

[Memory guide](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/memory.md) · [Feature guide](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/features.md) · [Local runtime and upstream credits](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/local-runtime.md)
