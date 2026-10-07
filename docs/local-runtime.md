# Wixal Local

Wixal Local is the app-managed local inference experience. It includes a pinned Ollama runner, starts it when local models are requested, and stops its process group when Wixal quits. Users do not need a separate Ollama installation. The engine remains credited to Ollama; model names, authors and licenses remain those of their publishers.

## Use it

Open **⌘L**. All models run through **Wixal Local**. Download a model by its Ollama registry tag, or click **Import & use** on a model already installed in Ollama. The expanded engine panel also provides a manual import workflow. Downloads contact the registry after your click. Inference uses the installed weights on your Mac. The bundled engine disables Ollama cloud inference.

Imported models come from the default `~/.ollama/models` library. Wixal supports the registry's GGUF blob manifests; other formats or custom stores may need a fresh download. Each blob is checked against its SHA-256 digest before the manifest is published. APFS uses independent copy-on-write clones when supported; other filesystems copy the data normally. Large models can take time to verify and consume additional space. Wixal does not delete or modify the source library.

The picker shows engine state and provides **Start engine**, **Stop engine**, and **Model folder** controls. Refreshing local models starts a stopped engine. The picker has no external engine or cloud inference choice. Models from Ollama are imported as weights into the bundled engine. Existing chats, project notes, and provider settings carry forward; the managed library starts empty until you import or download a model.

Models live in `~/Library/Application Support/Wixal/local-runtime/models` (or below `WIXAL_DATA_DIR` for development). The managed server binds to a fresh loopback port, separate from external Ollama. It loads at most one model with one parallel request, uses a two-minute keep-alive and a quantized KV cache, and receives no provider keys or inherited `OLLAMA_*` configuration. The default context is 8192 tokens. The first local-only migration caps older larger settings at 8192 once; subsequent explicit settings persist. Selecting another model caps context at its reported limit and 16384 tokens. The context control still supports larger explicit settings where the model permits them. Thinking metadata selects `false` only when supported, otherwise a supported level such as `low` for GPT-OSS. Thinking records are retained across tool steps. Requests automatically include the current workspace, enabled tools and approval policy. Review each action and Approved all apply to both Chat and Agent. Loopback restricts network exposure; it is not a security boundary against other processes running as your Mac user.

## Upstream and attribution

The checked-in pin is [resources/runtime.json](../resources/runtime.json): **Ollama 0.35.1**, commit `b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce`. The runtime is MIT licensed. Wixal retains the upstream executable name, original copyright text, and bundled notices for llama.cpp, MLX, Go, and other dependencies. See [third-party notices](../THIRD_PARTY_NOTICES.md) and the license files in the packaged `Contents/Resources/ollama` folder.

Wixal's lifecycle manager, import workflow, interface, project memory, tool controller, and release pipeline are developed in this repository. The current release uses the verified upstream engine binary. It does not claim that the inference engine or pretrained models were created by Wixal. A source build path is included for developing changes on top of the pinned foundation.

## Stage the verified engine

On Apple Silicon macOS 14 or newer:

```sh
npm ci
npm run rebuild
npm run runtime:stage
npm start
```

Staging downloads the exact official archive and checks its published SHA-256 (`3137dbf28948ee844e0fb3e584d9b5de6879d73d9f0cb7eff3ad64930601d307`). It preserves included notices, adds the pinned Ollama license, and writes a file inventory. Runtime startup verifies that inventory before executing the bundled runner. Generated binaries, archives and source clones stay in the ignored `runtime/` directory. Packaging stages the verified archive automatically and places the payload outside ASAR.

## Build the engine from source

Install **Go**, **CMake 3.24 or newer**, a C/C++ compiler, and **full Xcode with its Metal toolchain**. Command Line Tools alone are insufficient for the default MLX/Metal build. Follow [Ollama's pinned development instructions](https://github.com/ollama/ollama/blob/v0.35.1/docs/development.md) to prepare the toolchain.

```sh
npm run runtime:build
npm run test:runtime
# Preserve the source-built payload by skipping prepackage's verified archive staging:
npm exec electron-packager -- . Wixal --platform=darwin --arch=arm64 \
  --asar.unpackDir='{app,node_modules}' --asar.unpack=package.json \
  --extra-resource=runtime/ollama --extend-info=resources/Info.plist \
  --out=release --overwrite --icon=assets/Wixal.icns \
  --app-bundle-id=app.wixal.desktop \
  --app-category-type=public.app-category.developer-tools \
  --ignore='^/(runtime|release|test|scripts|artifacts|docs|\.git)($|/)'
node scripts/runtime-package.cjs
```

The build script checks out the pinned commit in `runtime/source`, rejects uncommitted edits, calls upstream's arm64 native build targets, stages the native libraries and executable, and records `built-from-pinned-source` provenance. It is a documented build workflow, not a claim of bit-for-bit reproducibility. The 0.7.0 release was tested with the checksum-verified official payload; native source compilation was not exercised on the release machine, which lacks Go, CMake and full Xcode.

To maintain an engine fork, develop it in a separate checkout and review its diff against the recorded upstream commit. Then intentionally update the pin/build workflow, retain notices, and run the runtime and app suites before releasing. Do not silently replace a verified binary or relabel publisher models as Wixal-trained models.

## Validation

`npm test` checks startup coalescing, protected environment, integrity failures, stop/restart, cancellation during startup, independent imports, malformed/symlinked blobs, and partial import rejection.

`npm run test:runtime` runs the real bundled engine through Electron: default startup, importing `gemma3:12b`, actual inference, stop/start, rejecting external engine selection, saved library/chat after restart, actual benchmarking, model deletion and owned-process cleanup. Set `WIXAL_RUNTIME_TEST_MODEL` to another supported installed chat model if needed. It uses disposable app state and does not change your original model library.

`WIXAL_SMOKE_MANAGED=1 npm run test:app` imports the existing Gemma and Qwen fixtures and runs the complete app path with Wixal Local, including image input, a reviewed model-driven file write, project memory, PTY, persistence and offline recovery. Use `WIXAL_APP_PATH` to run either suite against the packaged executable.
