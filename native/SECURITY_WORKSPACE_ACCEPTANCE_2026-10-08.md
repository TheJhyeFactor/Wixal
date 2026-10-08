# Native cybersecurity workspace — 8 October 2026

This records the initial implementation. The subsequent investigation records, AI planning and chain studio update is documented in [the v2 acceptance report](SECURITY_INVESTIGATIONS_V2_ACCEPTANCE_2026-10-08.md).

Implemented and installed as a local development preview in Wixal Native. Open Cybersecurity → Investigations. The existing security agent view remains available in the adjacent Agents tab.

## Interaction and integration

- Project-scoped targets: Website / API, Network, Server, Network device and Software. Targets can have a parent for network/device grouping.
- Target sidebar, one main stage at a time, per-investigation model chooser, optional AI discussion and a collapsible execution dock.
- Recon → Research → Attacks → Results. Run details retain actual service observations, website findings, model analysis, technical evidence and errors.
- Prepare a named step with its actual capability, arguments, model and optional prerequisite. Chained steps require completed execution of their prerequisite; that status does not establish exploitation.
- Independent tool jobs execute concurrently with 1–4 slots. Pause affects future starts. Stop operates on the selected run's owned processes. Local model inference is serialized.
- Nmap profiles, bounded website observations/probes, disposable local website simulations, web search and local-model analysis use existing tools and project review settings.
- Software analysis reads a project-contained file or lists its directory through existing enabled tools.
- Targets, runs and evidence persist in native SQLite storage. Interrupted work is retained and is not automatically replayed at restart.
- Tools and imported skills are inspectable. New attack and privilege escalation skills remain future work.

## Verification

The native Python regression suite passed 141 tests in 35.088 seconds. The focused security tests cover review isolation, cancellation, dependent local simulation runs, pause, restart interruption, invalid targets, cross-project dependencies and evidence analysis. Fixtures are distinguished from real acceptance below.

Real packaged acceptance uses an actual loopback HTTP service, actual Nmap, retained HTTP evidence with a body checksum and a real Gemma 3 1B local model. The report is in artifacts/native/security-workspace/acceptance.json. The final installed-helper acceptance passed both parallelRecon and modelAnalysis; Gemma 3 1B generated 1163 tokens. Its helper SHA-256 matches the installed helper. It verifies overlapping tool runs and nonempty model output with token usage. Model prose quality and exploit validity are not established by this test.

Live installed-app checks created Server target 127.0.0.1, ran a Ports profile on TCP port 1, displayed the actual closed-port result, inspected the chain prerequisite picker, and reopened the app to verify target and evidence persistence. The native screen was visually inspected at the live window size, including the collapsed execution dock and the restored result. No external target was attacked.

The local fixture server originally exposed a timing-sensitive Nmap title assertion: a short connection timeout can yield tcpwrapped classification. The final acceptance checks the observed open port and the website's actual HTTP response/body checksum separately, rather than requiring Nmap to infer a page title.

Packaging uses the repository's native Swift build system. Development signing and strict bundle verification passed. The install compared the packaged and installed executable, helper and Info.plist hashes and retained a previous app backup.

## Installed bundle

- App: /Users/jhye/Applications/Wixal Native.app
- Previous app: /Users/jhye/Applications/Wixal Native previous 20261008-030923.app
- Contents/MacOS/WixalNative: 1496276dc2e6cad500f170d5e090502d7cd8ee70ceb3660da73d36a4d46c325e
- Contents/Resources/engine/wixal-engine: 506c7622ec593249acbd83d48989677e157579e7f101e2019caf8fcd238290b2
- Contents/Info.plist: 7521a4608187e554f3a9a1fb43fc22bb04f9400ff4c418dbe5741e8582af8afe

## Current limits

The workflow UI and execution queue are connected to the capabilities above. It is not a complete autonomous exploit engine. Custom exploits, privilege escalation, outcome-dependent exploit gates and a visual graph editor have not been implemented. Analysis proposes tests from observed evidence; it does not execute arbitrary commands. Research retains search result URLs and snippets; it does not validate every source or advisory. Multiple scanners can run concurrently, but inference is serialized. This is a locally installed development build, not a published release.
