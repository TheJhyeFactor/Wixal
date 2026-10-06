# Developing Wixal

Use Node.js 22 or newer, the Xcode command line tools, and an Apple Silicon Mac with macOS 14 or newer. Install dependencies with `npm ci`, then run `npm run rebuild` to rebuild node-pty for Electron.

## Release line

Stay on the current 0.7 release line. Ship these refinements as 0.7.x patch increments, beginning with 0.7.1; do not advance to 0.8.0 without a new decision from Jhye. The current release checkout uses `main`.

The engine is always **Wixal Local**. Ollama is the underlying bundled engine and a source of importable model weights. Production inference cannot select an external server or cloud provider.

The 0.7.1 model chooser opens on installed models, with a separate Downloads tab. Provider, context, hardware and collapsible local-engine controls sit beside the library. Search and filters apply to the active tab, with independent filter choices for installed models and downloads. Model deletion stays behind each model's menu and the existing confirmation dialog.

## Check a change

```sh
npm test
npm run check
npm run test:app
npm run test:connections
npm run test:providers
npm run test:refinement
npm run test:features
npm run test:runtime
npm run test:performance
npm run test:models
npm run test:model-library
```

The app test launches Electron with temporary state and a small test project. It exercises model selection, file previews, tool settings, image attachments, project memory, the real PTY, persistence, offline recovery, and compact window layout. Screenshots are saved in `artifacts/`.

The full test uses an installed tool-capable vision model to create a fixture file after approval, recall a saved preference, and describe an image. The current fixture expects Qwen and Gemma models in the local Ollama library.

To check the interface and terminal without running inference:

```sh
WIXAL_SKIP_MODEL_TEST=1 npm run test:app
```

This still needs Ollama running and the model metadata expected by the fixture.

## Package a Mac app

```sh
npm run package
WIXAL_APP_PATH="$PWD/release/Wixal-darwin-arm64/Wixal.app/Contents/MacOS/Wixal" npm run test:app
```

Packaging creates `release/Wixal-darwin-arm64/Wixal.app`. The native node-pty module is unpacked from asar so its spawn helper can run. The app is not Developer ID signed or notarised.

## Update the graphics

```sh
npm run assets
npm run media
```

The first command rebuilds the SVG assets, PNG exports, and macOS icon from the checked-in sources. The second records screenshots and the GIF tour from a real app session with disposable demo data. See [the visual guide](visuals.md) for source files and motion behaviour.

## Connection checks

`npm run test:connections` runs the real Electron UI, macOS credential encryption, a real MCP stdio client and the actual file tool/review path. It simulates OpenAI model catalogs, Responses streams and OAuth endpoints; its fixture identity is signed and verified through JWKS. It checks API-key save/removal, shared reads, queued task handoff, approved and declined edits, account sign-in/sign-out, provider switching, persistence and sharing revocation. It does not prove live account eligibility, billable inference or ChatGPT tunnel connectivity. Ollama metadata is required for the initial local model picker.

To run the connection checks against the packaged app:

```sh
WIXAL_APP_PATH="$PWD/release/Wixal-darwin-arm64/Wixal.app/Contents/MacOS/Wixal" npm run test:connections
```

App source, package metadata and production dependencies are unpacked from asar so the external Node MCP helper can run from the packaged app. The existing PTY native helper remains unpacked as well. Do not put real credentials into fixtures or screenshots. See [connection setup](connections.md) for live account verification.

`npm run test:providers` runs all added providers with protocol fixtures and real Electron UI/macOS encryption. It verifies provider key isolation, catalogs, native Claude and compatible tool continuation, reviewed file writes, a declined edit, custom endpoint configuration and reload persistence. It does not contact real cloud inference accounts. Run it against a packaged binary with `WIXAL_APP_PATH` as for the connection smoke test.

`npm run test:refinement` uses disposable conversations to exercise archive/restart/read/restore, rename, keyboard menu navigation, cancellation and confirmation of deletion, and the last-chat fallback. It also checks the centred composer, prompt suggestions, textarea growth, compact layout and reduced motion, with screenshots in `artifacts/`. It does not change your real chats or require cloud accounts. Use `WIXAL_APP_PATH` to test the packaged build.

`npm run test:features` uses model/download protocol fixtures, a real local HTTP service and a real stdio MCP process to exercise the feature UI: summary generation/inspection, preferences, declined and approved requests, reviewed memory, external tool invocation, download progress/cancel, 128k settings and reload. It captures desktop and compact screenshots outside the checkout in the system temporary directory. Use `WIXAL_APP_PATH` for the packaged build. The separate web-search unit test uses a protocol fixture; live search availability depends on its upstream service.

## Wixal Local development

Run `npm run runtime:stage` before `npm start`; packaging stages the verified upstream payload automatically. Protocol fixture suites can use an external test endpoint only with disposable `WIXAL_DATA_DIR`. Use `WIXAL_SMOKE_MANAGED=1 npm run test:app` for the full image/file-tool flow through the bundled engine. `npm run test:runtime` covers real managed-engine import, inference, stop/start, library persistence and quit cleanup. Both use disposable state and independent model copies. See [local runtime development](local-runtime.md) for source builds, attribution, pinned provenance and the tested versus untested build paths.

`npm run test:performance` uses protocol fixtures and real file reads through Electron to exercise explicit @tools, reported usage, benchmarks/cancellation, model filters, deletion confirmation and categorized tool controls. It complements the real managed-engine benchmark/deletion test. The command-session unit tests execute real host fixtures; browser inspection has a local rendered-page fixture in `scripts/browser-tools-smoke.cjs`.

`npm run test:models` exercises the model manager through Electron with disposable state and Ollama metadata fixtures. It covers Installed/Downloads tabs, keyboard navigation, selection, search, independent filters, catalog sorting/tag choice, context persistence, local-only engine selection, empty-library recovery and desktop/compact layouts in dark and light themes. It saves screenshots in `artifacts/`. Use `WIXAL_APP_PATH` to run against a packaged app.

`npm run test:model-library` exercises the dedicated Models page, serial downloads, pause/resume/cancel/retry, completion verification, selection, persisted jobs, suggested context and memory release with protocol fixtures. `npm run test:model-download-live` downloads `gemma3:270m` from the registry into disposable managed storage, verifies installation, selects and benchmarks it, releases memory and checks restart persistence. The live check contacts the registry and removes only its temporary library. Use `WIXAL_APP_PATH` to exercise a packaged build.

Model metadata is cached for five minutes by endpoint, tag and digest, with at most four requests at once and 256 cache entries. Explicit Refresh bypasses it. Download progress emits at most every 200 ms unless the stage changes, and saves happen on job transitions rather than every received chunk. Hardware identity is cached while free-memory readings stay live. The download queue is limited to 12 unfinished jobs, with bounded recent history.

## Main workspace refinements in 0.7.2

The workspace header exposes Files, Tools, Memory and Terminal. Project and model readiness are shown before the first message. Chat and Agent are explicit keyboard-accessible choices. Text drafts are saved to the existing local workspace store after 500 ms of inactivity and flushed before conversation/project changes. Image attachments remain temporary and clear on conversation changes. Drafts are bounded to 16,000 characters and archived chats remain read-only.

Streaming updates only the pending text node on animation frames; saved Markdown is rendered on state transitions. Scrolling up keeps your reading position, with a button to return to the latest message. Code blocks have a dedicated clipboard action.

`npm run test:workspace` exercises text draft recovery across chat changes, page reload and full Electron restart; invalid draft requests; real file access and clipboard; header drawers; keyboard mode selection; stable saved/pending message nodes during a protocol-fixture stream; scroll preservation; clearing sent drafts; returning to chats from Models; and compact layout. Browser plugin is not available, so this uses Playwright's real Electron renderer. Fixtures are confined to disposable app data and are never used for public screenshots.

## Sidebar motion refinements in 0.7.3

Keep this work on the 0.7.x patch release line. Sidebar motion uses a shared 280 ms curve for width and control positions, short opacity transitions for labels, and fixed-width project navigation to avoid repeated text wrapping. It removes the sidebar letter-stagger animation and its forced layout read. The only animation-frame loop follows an open Workspace popover while the rail is moving; it stops when motion ends or the menu closes.

Layout responds optimistically and serializes saves, preserving the final target during rapid reversals. Hidden navigation is inert, with focus returned to the toggle. Saved layout is applied without startup motion. OS and app reduced-motion preferences remain supported.

Run `npm run test:sidebar`, `npm run test:workspace` and `npm run test:settings` against source and the packaged app. Record screenshots and the sidebar GIF from real renderer frames with `npm run media`; never interpolate a static screenshot to represent app behavior.

`npm run test:chat-tools-live` imports tool-capable models into an isolated bundled runtime and exercises natural Chat file reads, missing-URL clarification, real rendered browser evidence and reviewed command continuation. Use `WIXAL_TOOL_MODELS` to choose comma-separated installed tags.

`npm run test:security` drives the scan form with an inference protocol fixture and real loopback Nmap. It checks workspace context, thinking metadata, no dialogs in Approved all, persistence, Review prompting and switching to all while waiting. Unit tests add real HTTP/TLS fixtures, report metadata, target validation, disabled tools, cancellation and project ownership.

Set `WIXAL_TEST_SCAN_ONLY=1 WIXAL_TOOL_MODELS=gpt-oss:20b npm run test:chat-tools-live` for a real bundled-model Approved all assessment: it scans a disposable loopback TCP listener, reads completion and saves/validates a JSON evidence report without dialogs.

## Memory checks

`npm run test:memory` exercises the real Electron memory controls and IPC with disposable workspace data and deterministic model responses. It checks saved scopes/budgets, note edits, guest profile persistence, model switching, visible handoff, cancellation, fresh-chat creation and context warnings. Screenshots are saved to `/tmp/wixal-*.png`. Use `WIXAL_APP_PATH` to exercise the packaged app. Core regression coverage is in `test/memory-context.test.cjs`. Live Firebase and actual model checks are separate from fixtures.


## Tool regression and live website checks in 0.7.8

`npm run test:browser-regression` drives actual Electron Chromium against disposable fixtures for delayed content, stale refs, changed controls during review, text input, select, pagination, HTTP errors, redirects, isolation, resource limits, cancellation and cleanup. CI runs this independently of inference. `npm run test:jhye-live` uses the nominated live site, **https://jhye.dev/**, for browser homepage/link navigation, HTTP text, DuckDuckGo source evidence and a two-page GET baseline assessment with saved reports. It never submits forms or writes to the website. Live search can fail honestly if its upstream service blocks or changes responses.

`npm run test:chat-tools-live` additionally uses an actual tool-capable installed model to open jhye.dev, click its Work link using returned refs, conclude from the actual page, close the browser and answer from live search results. This complements controller tests rather than treating model protocol fixtures as evidence of real inference. `WIXAL_APP_PATH` selects a packaged executable.

The unit suite includes focused-schema discovery without re-enabling disabled tools, parseable bounded JSON evidence, exact file edits/concurrent changes, large-file search, tool migrations, decline/retry limits and a real MCP stdio server with paginated, duplicate, oversized and repeated-cursor catalogs, errors, artifact labels and cancellation.
