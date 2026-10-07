# Wixal 0.7.9 — Feature completion and native preview

Wixal 0.7.9 is a feature-completion patch release for the Apple Silicon macOS app. It keeps local Ollama inference, project tools, browser workflows, memory, accounts, the terminal and Electron compatibility available while documenting the native SwiftUI/Python preview as a separate development target.

The native preview adds semantic retrieval with optional local embeddings, source-aware memory evidence, reviewed local-model extraction of durable decisions, exact-quote suggestions, explicit replacement or note combination, encrypted workspace-folder sync, remote Streamable HTTP MCP with OAuth plumbing, awake closed-app scheduling, interactive WebKit sessions, and improved account restore, composer and activity workflows. The packaged acceptance run passed semantic memory, actual Gemma3 1B review, remote MCP plus closed-app scheduling, encrypted sync, the broader Qwen3 4B model suite and packaged command/browser workflows. See [`native/IMPLEMENTATION_STATUS_2026-10-07.md`](../native/IMPLEMENTATION_STATUS_2026-10-07.md) for binary-qualified evidence.

The Electron download remains the supported release download. The native preview is development-signed and Apple Silicon-only. It is included in the source tree with build and acceptance instructions, but it is not presented as a notarised public replacement.

Known limitations remain: fresh-account creation and verification, password-change and deletion acceptance with a disposable live account, full four-theme/minimum-size/keyboard/VoiceOver acceptance, complete assessment-cancellation UI coverage, real migration collections, external OAuth provider sign-in, authenticated browser apps and download UI, two-device folder-provider delivery, sleeping-Mac wake, Windows/Linux/Intel packages, controlled Electron/native application performance comparisons, and public signing/notarisation/update delivery. Cloud inference and the external ChatGPT companion are deferred.

## Install

Download the Apple Silicon DMG or ZIP below, drag `Wixal.app` to Applications, and open it. Requires macOS 14 or newer. The application is not Developer ID signed or notarised, so macOS may require the usual Open action from Privacy & Security after the first launch.

SHA-256 hashes for the release downloads are in `SHA256SUMS.txt`.
