Wixal 0.7.10 Alpha 1 is the first public native Wixal release. The current app uses SwiftUI/AppKit and a persistent Python agent engine, with its Python runtime and local Ollama runner included.

Download **Wixal-0.7.10-alpha.1-macOS-arm64.zip**. It contains one **Wixal.app** for **Apple Silicon, macOS 14 or newer**. Model weights are downloaded or imported separately. No separate Python, Node or Electron installation is needed to use it.

## Included in this alpha

- Native Chat, project navigation, files, terminal, model library and usage views.
- Reusable agents with model-selected tools, task authority, success criteria and inspectable activity.
- Workflows with dependencies and bounded parallel execution, durable run history, queues and artifact verification.
- Calendar/interval routines with optional awake closed-app execution; work that needs review pauses.
- Reusable skills, explicit skill evaluation and candidate comparison/promotion.
- Editable memory, visible summaries, reviewed lasting-decision suggestions and optional encrypted folder sync.
- Local stdio and remote HTTP MCP connections, native WebKit tools and API access.
- A cybersecurity workspace for authorised scope, investigations, evidence and findings. Nmap is a separate local dependency.

## Install

Extract the ZIP and move Wixal.app to Applications. Open Models to download/import a tool-capable model or configure external Ollama, then open a project folder.

**This alpha is ad-hoc signed and is not Developer ID signed or notarised.** macOS may block first launch. After reviewing the source and these notes, use **System Settings → Privacy & Security → Open Anyway**. Updates are manual downloads from GitHub.

Existing native workspace data remains at `~/Library/Application Support/Wixal Native`. Earlier Electron records can be imported explicitly; source data is retained. Back up important work before testing.

## Verified for this release

- All 204 Python engine regression tests pass.
- The production Markdown acceptance executable passes all five groups.
- Five real-model acceptance outcomes pass against the frozen packaged helper using **gpt-oss:20b**: source inspection, reviewed artifact creation, calendar routine creation, verified skill creation and background tool execution.
- The production activity projection passes against five actual persisted conversations and nine paired tool actions, including stable identities and explicit error status.
- Installed native workspace startup, Agents navigation and the visible Alpha 1 version/update wording were checked.
- The extracted download bundle and installed app match in executable, engine, plist and source-manifest hashes. Deep strict ad-hoc signature verification passes; 105 source files match with no drift. The icon and required third-party notices are included; no preview workspace/endpoint overrides or model weights are bundled.
- Website page/link, syntax, consent analytics and aggregate report checks pass.

These checks cover the implemented local workflows. They do not establish equal reliability across models, every service integration or full Hermes parity.

## Still in progress

Remote/off-Mac execution, messaging/voice gateways, fully autonomous skill improvement/promotion, broader model/provider acceptance, production security evaluation, actual sleep/wake/reboot acceptance, full accessibility coverage, real two-Mac encrypted sync, service-specific OAuth/account lifecycle acceptance, Developer ID signing, notarisation and automatic updates.

Background execution requires an awake Mac. Desktop-only browser work requires the app open. Command tools run with your Mac account’s access. Inspect model output and security findings before relying on them.

[Native alpha guide](https://github.com/TheJhyeFactor/Wixal/blob/main/docs/native-alpha.md) · [Build and engine guide](https://github.com/TheJhyeFactor/Wixal/blob/main/native/README.md) · [Website](https://thejhyefactor.github.io/Wixal/) · [Report an issue](https://github.com/TheJhyeFactor/Wixal/issues)

The native engine includes an adapted Hermes duration parser with MIT attribution. Earlier Electron releases remain in release history; the current website and README link directly to this native alpha.

## SHA-256

`44800c10a8a9d392b96208fd0793404a66876fbfc1efd29f8ddeb687194fae4f  Wixal-0.7.10-alpha.1-macOS-arm64.zip`
