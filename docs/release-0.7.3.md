# Wixal 0.7.3 — Smoother sidebar navigation

A 0.7.x patch release refining the redesigned workspace from 0.7.2.

- The sidebar narrows and expands with coordinated brand, toggle and icon movement. Navigation keeps its width, with labels fading before the rail closes.
- Motion starts immediately and reverses from its current position. Layout saves run in order so rapid toggles preserve the final choice.
- Collapsed navigation leaves the keyboard tab order. Focus returns to the toggle when it would otherwise be hidden.
- Repeated Workspace-button clicks correctly close its menu. The bottom-left Models, Settings and Workspace controls stay aligned, and the Workspace menu follows its anchor during motion.
- Saved layout applies immediately on launch. Both macOS Reduce Motion and Wixal's own preference disable the animation.

The main workspace, saved drafts, Chat/Agent selector, model downloader, library and Wixal Local branding from 0.7.2 are included.

## Install

Download the Apple Silicon DMG or ZIP and drag **Wixal.app** into **Applications**. Requires **macOS 14 or newer**. Wixal Local is included; a separate Ollama installation and Node.js are optional.

This preview is ad hoc signed, with bundle integrity checked. It is **not Developer ID signed or notarised**. If macOS blocks first launch, use Apple's [instructions for opening an app from an unidentified developer](https://support.apple.com/en-au/guide/mac-help/mh40616/mac).

No model weights are included. Downloads contact the model registry. Cloud providers receive the conversation and context you allow; local chats and notes remain on your Mac. Review model-requested edits and commands before execution.

## Verification

64 core tests and actual Electron checks cover the sidebar, workspace and settings. Sidebar checks exercise intermediate geometry, interrupted motion, delayed saves, persistence after reload, keyboard focus, reduced motion and menu placement at 1360×880 and 920×640. Workspace checks cover full-process draft recovery, file reads, clipboard copying and streamed scroll behavior. Public screenshots and animation are recorded from the packaged app using disposable data and actual local models.

This is an interface-motion change; no inference-speed improvement is claimed. Download checksums and source/runtime provenance are included with the assets. Wixal Local uses pinned open-source Ollama with original credits preserved. See [the local runtime guide](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/local-runtime.md).
