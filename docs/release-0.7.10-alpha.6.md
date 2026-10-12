# Wixal 0.7.10 Alpha 6 — Models, agents and reviewed security workflows

12 October 2026

Alpha 6 combines the Hugging Face model library, agent run controls and scoped red-team workspace improvements in the native SwiftUI app and Python engine. This is an Apple Silicon macOS 14+ testing release, **ad-hoc signed and not Developer ID signed or notarised**. Model weights download separately. Updates are manual.

## Models and engine

- Browse Hugging Face GGUF models in a compact library. Search model types and providers using Hub metadata, with the leading filter choices shown first.
- Filter model sizes and inspect estimated memory requirements and recommendations before downloading. Memory estimates are guidance, not proof of acceptable inference speed.
- Manage installed models and downloads together, with download progress on model rows and model deletion controls.
- Models and Engine have a dedicated settings tab, including model imports and runtime controls.
- Downloads use Wixal's Hugging Face infrastructure. The managed local inference engine remains Ollama; a llama.cpp migration is deferred. Hugging Face downloads do not imply a change of inference backend.

## Agents

Durable task checklists, retained tool evidence and resource-aware skills from Alpha 5 remain available. This release adds clearer run budgets, wrap-up handling and recovery from stalled tool loops. A completed checklist remains separate from independent outcome verification. The controller preserves bounded tool authority and saved evidence through continuation.

## Reviewed security workflows

- Engagements carry authorised targets, capability scope and operation evidence. Local Linux-worker support is included; remote-worker and AD/cloud qualification remain pending.
- API investigations can use short-lived Keychain-backed bearer, cookie or OAuth access-token leases. Exact POST, PUT, PATCH and DELETE operations require action review, including when other actions are pre-approved. JSON mutation bodies are bounded; redirects and automatic cookie updates are disabled.
- OAuth supports same-origin public clients using authorization-code S256 PKCE and an ephemeral loopback callback. State and verifier stay in memory. This does not establish compatibility with arbitrary third-party identity providers or confidential-client flows.
- An API mutation-state validator compares an independent before/after observation with the retained mutation. Operators still need to perform and verify cleanup; a successful mutation is not proof of a broader compromise.
- Import an external controller's bounded JSON proposal as an inert draft, then separately review its execution under the current engagement scope. This is a file proposal bridge, not a general live controller connection.
- Import Suricata EVE or Zeek JSONL telemetry. Correlation requires a literal destination IP, port and declared operation time window. Format-fixture coverage does not establish live vendor-sensor qualification.
- Reviewed agent commands can use a persistent interactive PTY within an owned running job. This terminal state does not survive an engine restart.

See the [security workflow guide](security-workflows-alpha6.md) for scope and operational limits, and the [agent tools guide](agent-tools.md) for evidence and verification semantics. Hermes-inspired work remains adapted within Wixal's own architecture with [attribution and comparison](hermes-agent-improvements-2026-10-12.md).

## What was verified

The combined source passed **513 engine tests**, including regression coverage for real local HTTP cookie mutations, PKCE callback/state handling, independent mutation-state verification, reviewed controller proposals, vendor log matching and PTY interaction. The focused extension suite passed 29 tests. The native app was built and installed as Alpha 6. Release assets include fresh bundle/source verification and archive checksums.

Earlier six-model download and basic-generation checks do **not** establish reliable tool use, coding, long tasks or red-team analysis across all six. The previous agent-control qualification used Qwen3.5 9B and a different installed helper. Those results remain historical; they are not a fresh qualification of Alpha 6. The six-model capability matrix and installed-app end-to-end qualification of the new security workflows are **pending** in this release. Automated fixture tests are not a production penetration test.

## Remaining limits

Broader model qualification, capability-specific exploitation validators, external-controller protocol integrations, actual vendor deployments, third-party OAuth workflows and terminal recovery across restarts remain unfinished. Remote execution qualification and AD/cloud tests are deferred. Messaging gateways, voice/media integrations, full hardware/OS and accessibility coverage, real two-Mac sync acceptance, sleep/wake/reboot acceptance, automatic updates and notarisation remain open. Production managed-tool downloads require a qualified signed catalogue. This release does not claim full Hermes or Decepticon parity.

## Install or update

Download `Wixal-0.7.10-alpha.6-macOS-arm64.zip` from the [GitHub release](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.10-alpha.6), verify `SHA256SUMS.txt`, quit Wixal and replace the app in Applications. Existing workspace data and separately downloaded models are retained. Keep one active Wixal.app and use the [native alpha guide](native-alpha.md) for setup and macOS trust prompts.
