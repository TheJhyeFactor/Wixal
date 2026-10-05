# Wixal 0.7.1 — Models, downloads and a clearer workspace

Manage local models from a dedicated **Models** page. Use **⌘L** for quick selection. The local provider is **Wixal Local**, with the engine included in the app.

## What changed

- Installed and Downloads tabs, clearer capability and memory-fit labels, search and filters, and a quieter model menu.
- In-app downloads from the catalog or a registry tag, with a persistent queue, pause/resume/cancel/retry, and verification before a model becomes available to select.
- Free disk space, loaded model memory, suggested context settings and explicit memory release. Real benchmarks remain available for this Mac.
- Cached model metadata, bounded metadata requests and throttled progress updates to reduce repeated work in the interface.
- Aligned Models, Settings and Workspace controls in both sidebar layouts, appearance preferences and an in-app project folder picker.

Interrupted downloads stay paused until you resume them. Model weights are downloaded separately; no weights are bundled. Memory fit is an estimate and depends on context size. Benchmark speed measures throughput on the tested Mac, rather than answer quality.

## Install

Download the Apple Silicon DMG or ZIP attached to this release and drag **Wixal.app** into **Applications**. Requires **macOS 14 or newer**. Node.js and a separate Ollama installation are not required.

This preview is ad hoc signed, not Developer ID signed or notarised. If macOS blocks launch, follow [Apple's instructions](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac). Compare the downloaded asset with `SHA256SUMS.txt`.

Existing conversations, project notes, connections and local model libraries stay saved. Open **Models → Downloads** to get a model, or expand **Local engine** to import an existing Ollama model. Imports preserve the original model files.

Wixal Local is built on pinned open-source Ollama 0.35.1 with its credits, licenses and provenance preserved. Optional external engines and cloud providers remain available. Downloads contact the registry; local inference stays on this Mac. [Runtime details](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/local-runtime.md).

## Verification

Unit checks cover queue ordering, pause/resume, retry, interrupted-state restoration, throttled updates, metadata caching, installation verification and cancellation. Electron checks cover the Models page, selector, responsive layout, aligned sidebar controls, settings, project selection, and existing tool and performance workflows.

A real Gemma 3 270M registry download was verified, selected, benchmarked and unloaded through the app in a disposable library. Managed-engine checks exercise imported-model inference, benchmarks, stop/start, persistence, external-server switching, deletion and quit cleanup. Protocol fixtures are used where live provider accounts are unnecessary. Download assets include the source commit and runtime provenance in `release-info.json`.
