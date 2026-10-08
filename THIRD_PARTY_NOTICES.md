# Third-party notices

Wixal Local builds on [Ollama](https://github.com/ollama/ollama), currently pinned to 0.35.1 at `b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce`. Its original MIT license and copyright notice are included as `Contents/Resources/ollama/OLLAMA_LICENSE` in the Mac app. [Read the pinned license](https://github.com/ollama/ollama/blob/v0.35.1/LICENSE).

The payload includes native inference and supporting libraries from llama.cpp, MLX, MLX C, Go, xgrammar, cpp-httplib, fmt, DLPack, picojson and other upstream dependencies. Their original license/notice files are preserved alongside the binaries. The complete payload inventory and source/archive provenance are in `Contents/Resources/ollama/manifest.json`; generated copies are staged by [the runtime script](scripts/runtime-stage.cjs).

The Wixal Local name refers to Wixal's app-managed experience. Upstream software remains attributed to its authors. Model weights are separate downloads or explicit local imports and are not bundled into Wixal's app releases. Every model retains its publisher's name and license; Ollama's software license does not replace a model's license.

The current native app includes SwiftTerm (MIT), Swift Markdown (Apache 2.0 with Swift runtime exception), swift-cmark and a bundled Python runtime (PSF), with their notices in Contents/Resources. Build-time PyInstaller carries its licence and bootloader exception. The Python MCP SDK and cryptography dependencies retain their distributed licence files. Native versions are pinned in native/Package.resolved and native/requirements-build.txt.

An adapted Hermes `parse_duration` function is included under the Nous Research MIT licence. See [the attribution and pinned source revision](native/third_party/hermes/NOTICE.md) and [the licence](native/third_party/hermes/LICENSE). Both are included in the app.

Earlier Electron releases include Electron, node-pty, xterm and npm dependencies with their distributed notices. Their versions remain recorded in package-lock.json.

Supplemental JSON and Metal C++ notices from the Ollama 0.35.1 macOS application are retained in `resources/notices` and copied into each staged payload. They accompany the corresponding upstream components; the verified CLI archive already includes the aggregate llama.cpp vendor notices.
