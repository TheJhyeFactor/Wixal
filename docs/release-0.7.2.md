# Wixal 0.7.2 — A clearer main workspace

A 0.7.x patch release with a redesigned main interface and improvements to everyday conversation handling.

- Project and model readiness beside the starting composer, with practical prompts for planning, exploring files and troubleshooting.
- Files, Tools, Memory and Terminal directly in the workspace header; aligned project navigation and sidebar controls.
- Explicit Chat and Agent choices with descriptions and keyboard navigation.
- Text drafts saved on this Mac and restored when changing chats or reopening Wixal. Temporary image attachments clear when changing conversations.
- Individual code-block copying and a button to return to the latest message in long chats.
- Streaming updates the pending reply without rebuilding the saved conversation on every frame, and respects your position when reading earlier messages.
- Returning to a chat from the Models page opens the conversation immediately. Wixal Local branding, in-app downloads, library controls and performance measurements carry forward from 0.7.1.

## Install

Download the Apple Silicon DMG or ZIP and drag **Wixal.app** into **Applications**. Requires **macOS 14 or newer**. Wixal Local is included; a separate Ollama installation and Node.js are optional.

This preview is ad hoc signed, with bundle integrity checked. It is **not Developer ID signed or notarised**. If macOS blocks first launch, use Apple's [instructions for opening an app from an unidentified developer](https://support.apple.com/en-au/guide/mac-help/mh40616/mac).

No model weights are included. Downloads contact the model registry. Cloud providers receive only the conversation and context you allow; local chats and notes remain on your Mac. Review model-requested edits and commands before execution.

## Verification

64 core tests and actual Electron checks cover the workspace, models, sidebar, archive/history, preferences and downloader. The new workspace check exercises draft recovery across a full process restart, keyboard mode selection, file reads, clipboard copying, scroll preservation and stable conversation nodes while streaming. Managed-runtime checks exercise real local inference, image/file tools and terminal behavior. Public screenshots and the tour are captured from the packaged app with a disposable project and actual local models.

Renderer changes reduce repeated DOM and Markdown work; no inference-speed improvement is claimed. Download checksums and source/runtime provenance are included with the assets. Wixal Local uses pinned open-source Ollama with original credits preserved. See [the local runtime guide](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/local-runtime.md).
