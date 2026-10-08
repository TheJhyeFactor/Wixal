# Wixal 0.7.10 Alpha 1

The public download is a single native **Wixal.app** for Apple Silicon Macs running macOS 14 or newer. It uses SwiftUI/AppKit, a persistent Python engine and a bundled local Ollama runner. Python and Node do not need to be installed to use the app. Model weights are separate downloads.

## Installation and updates

Download `Wixal-0.7.10-alpha.1-macOS-arm64.zip` from the [GitHub alpha release](https://github.com/TheJhyeFactor/Wixal/releases/tag/v0.7.10-alpha.1), extract it and move Wixal.app into Applications. A SHA-256 checksum accompanies the release.

The alpha is ad-hoc signed and **not Developer ID signed or notarised**. macOS may block the first launch. After reviewing the source and release notes, use System Settings → Privacy & Security → Open Anyway. This alpha has no automatic updater; download and install newer releases manually.

Native data remains at `~/Library/Application Support/Wixal Native`. Replacing the app does not remove the workspace or model library. Back up important projects and workspace data before testing. Use Settings → Data to explicitly import earlier Electron records; credentials and account sessions are not imported.

## First use

Start as a guest or use the optional account features. Open Models to download or import a model, or configure external Ollama. A model needs tool support for agent tasks. Real agent acceptance for this release uses gpt-oss:20b; hardware fit and reliability vary by model.

Open a project folder with ⌘O. Chat works with project context. Agents holds reusable agents, workflows, run history, recurring work and skill evaluations. Cybersecurity holds authorised investigation scope and evidence records. ⌘L opens Models, ⌘J opens the terminal, and ⌘, opens Settings.

## Agents and workflows

Create an agent with a purpose, instructions and a selected model. Set its review policy, memory scope, task authority and success criteria. The model sees eligible tools and selects how to complete the task. The user does not need to toggle individual tools for each agent run.

Authority controls where the agent may act and which actions require review. File tools retain project-path and credential protections. Command sessions run with the access of your Mac account; they are not an operating-system sandbox. Connect trusted MCP servers explicitly before the agent can use their tools.

Run a small task first: inspect a real project document, write a summary within the project, and read it back. Inspect the run’s returned evidence, checkpoints and verification results. A completed run is scoped to its configured checks; it is not a guarantee that an arbitrary model answer is correct.

Workflows connect agent steps with dependencies and bounded parallel branches. Inspect step status and artifacts, fix failed conditions and retry recoverable work. Uncertain side effects are not automatically replayed after interruption.

Skills hold reusable procedures. Candidate skill changes can be evaluated against explicit cases and compared with the current version before promotion. Fully autonomous skill evaluation and promotion remains incomplete.

## Recurring tasks

Save interval or calendar routines, including timezone and missed-run policy. The foreground engine handles due work while Wixal is open. Enable Background schedules in Settings for macOS LaunchAgent execution while the app is closed and the Mac is awake.

A background task pauses if it requires interactive review or a desktop-only browser action. Check run history and notifications after reopening Wixal. The engine claims scheduled work before starting it to avoid duplicate replay. Actual sleep, wake and reboot behaviour still needs full acceptance; this alpha does not promise continuous operation on a sleeping Mac.

## Cybersecurity

Define authorised targets and scope before an investigation. The workspace supports bounded website checks, optional local Nmap, evidence records, findings and comparisons. Nmap is a separate local dependency. Evidence and model-generated interpretations need human validation. Local and loopback acceptance does not establish dependable production security investigation quality.

## Known limitations

- Remote/off-Mac agent execution and messaging/voice gateways are incomplete.
- Broader models and provider-specific services need acceptance; gpt-oss:20b results do not generalise to every tool-capable model.
- Background execution requires an awake Mac; desktop-only tools need the app open.
- Actual sleep/wake/reboot behaviour and full desktop accessibility coverage remain incomplete.
- Automatic skill improvement/promotion, public automatic updates, Developer ID signing and notarisation remain incomplete.
- Encrypted folder sync needs real two-Mac acceptance. Provider-specific OAuth and disposable account lifecycle checks need broader live verification.
- The native alpha is not full Hermes parity. It includes an adapted Hermes duration parser with its MIT notice; the main engine is Wixal’s implementation.

See [agent acceptance](../native/AGENTS_COMPLETION_ACCEPTANCE_2026-10-08.md) and [the native guide](../native/README.md). The dated reports describe earlier verified builds; the release notes record checks repeated on the public alpha bundle.
