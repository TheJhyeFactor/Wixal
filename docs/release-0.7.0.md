# Wixal 0.7.0 — Wixal Local

Wixal now includes its local inference engine. Open the app, download or import a model, and work with your files without installing a separate Ollama app.

## New in this release

- **Wixal Local:** a bundled, pinned Ollama 0.35.1 engine with app-controlled startup, loopback serving, restart and shutdown.
- **A model library owned by Wixal:** downloads live with the app's data. Existing Ollama models can be imported through the picker with independent copies and SHA-256 verification.
- **Engine controls:** inspect state, start/stop the engine, open the model folder, or switch back to a separately installed Ollama server.
- **Usage and performance:** inspect reported input/output tokens, generation speed, request counts and first-output timing, including summaries and tool steps.
- **Real benchmarks:** run two bounded generation samples, cancel them, keep results locally, and filter installed models by measured performance or estimated memory fit.
- **Model management:** discover downloads by capability and size, download/import models, and delete a selected local model after confirming its active library.
- **A redesigned tool kit:** searchable categorized controls, enabled built-in tools, an Enable all action, and explicit `@tool_name` selection from the composer. Requested tools are enforced with bounded retries and honest failure reporting.
- **Browser and command sessions:** inspect rendered websites after review, run longer commands, read output, send reviewed stdin, stop jobs and save reviewed execution evidence in the project.
- **Transparent foundations:** “Built on Ollama” credit in the app, preserved upstream notices, pinned source/archive provenance, and staging/source-build scripts for continued development.
- **Project workflows continue:** memory, summaries, reviewed file/command/network tools, image inputs, MCP connections, cloud providers and the real terminal all remain available.

## Install

Download the Apple Silicon DMG or ZIP attached to this release. Drag **Wixal.app** into **Applications**. Requires **macOS 14 or newer**, matching the bundled runner's minimum version. Node.js and a separate Ollama installation are not required to use the download.

This preview is ad hoc signed, not Developer ID signed or notarised. If macOS blocks launch, follow [Apple's instructions for opening an app from an unidentified developer](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac). Download only from this repository and compare the asset's SHA-256 with `SHA256SUMS.txt`.

## First launch and upgrade

Choose **Wixal Local** in **⌘L**. Its library starts empty. Download a model by tag or use **Bring an installed model into Wixal → Find installed models → Import**. Existing conversations, memories and connections stay saved. Import preserves the original Ollama model files; licenses still apply. A larger model/context can require more RAM than your Mac has.

Local inference stays on this Mac. Model downloads contact the model registry after your click. The bundled runner disables Ollama cloud inference. Optional cloud providers and reviewed web/API tools retain their existing consent controls.

## Foundation and build status

This release uses the official Ollama 0.35.1 Darwin payload, verified against the pinned archive SHA-256. Its engine remains open-source Ollama, with its original notices preserved. Wixal owns the surrounding lifecycle, model import experience, UI and project/tool workflows. Models are supplied by their original publishers; no model weights are bundled in these downloads.

A source build workflow is included, but compilation of the native engine was not exercised on the release machine because Go, CMake and full Xcode are absent. See [the local runtime guide](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/local-runtime.md) for prerequisites, provenance, attribution and fork development.

## Verification

The core suite covers runtime integrity, lifecycle, import isolation, benchmark accounting, explicit-tool enforcement, command sessions and existing agent/tool/provider behavior. Real managed-engine Electron checks exercise imported-model inference, actual benchmarking, scoped deletion, image/file tools, persistence, PTY, stop/start, external-server compatibility and quit cleanup. The performance UI suite checks token reporting, benchmark cancellation, hardware/size/result filters, deletion cancel/confirm, @ selection and tool-kit persistence with protocol fixtures and actual project reads. Provider and new-feature suites use protocol fixtures where live accounts or network services are not needed. Each download includes release metadata recording the source commit and runtime provenance. See [usage and benchmark details](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/performance.md).
