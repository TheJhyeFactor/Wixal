# Managed tools implementation and acceptance status

Date: 9 October 2026.

**Continuation, 10 October 2026:** the installed primary native app now includes four additional managed standalone profiles, contributor OAuth reporting, cross-engine socket reservations, bounded inference recovery and current scan handles. The current source passed **277 engine tests**. The final installed helper passed eight real Go-package/capability cases, three discovery lifecycle cases and five splash/startup cases. Installed Tools and Recon interactions also succeeded. See [current implementation evidence and remaining configuration](MANAGED_TOOLS_CONTINUATION_2026-10-10.md). The historical results below describe the earlier RustScan preview; they do not supersede that continuation record.

Implemented as a native development preview. This document records implementation and measured evidence; it does not mark the entire 104-family release matrix passed.

## Implemented paths

- Dedicated SQLite package registry, cross-process mutation lock, content-addressed payload directories, durable publication/activation journals and restart reconciliation.
- Python TUF 7.0.1 with pinned cryptographic/network dependencies, embedded bootstrap trust, persisted trusted metadata, bounded download policy, exact target digest/length matching and catalogue schema isolation.
- Dependency-free RustScan package profile with bounded extraction, inventory, executable architecture, system-library audit and isolated application-owned version readiness. Unknown dependency/runtime profiles are explicitly unsupported.
- Install, update, repair, approved retained rollback, cancellation, provider selection and lease-protected removal. Activation outcomes survive receipt-write failure. Historical evidence and external programs remain retained.
- Execution leases on immutable managed artifacts, pre-run integrity checks and authenticated catalogue rechecks with visible last-known freshness/errors when refreshing fails.
- `network_discover`, selected-port and explicit all-TCP coverage, up to four resolved addresses, bounded presets, global per-engine socket budget, isolated RustScan config and direct argv. Selected coverage currently supports up to 1,024 ports; full TCP coverage is an explicit separate choice. Subnet discovery stays with direct Nmap.
- Separate retained stdout/stderr files and hashes, 16 MiB stream limits, structured partial/indeterminate results and a shared strict parser. Captured output instructions never grant authority.
- Chat source-session and investigation source-run Nmap handoff. Sources must retain matching ownership, target, completion and result hash; inspection derives per-host ports and batches at 256 ports under a shared deadline. Empty results skip inspection. Failed inspection retains evidence.
- Linked two-node discovery/inspection plans, dependency enforcement, project-scoped evidence, cancellation/restart semantics and preservation of prior service identification alongside later port-only observations.
- Tools library provider/readiness/model state controls, managed installation in Details on clean systems, receipt stages, recovery choices and Recon discovery/inspection controls. New models remain unevaluated.
- Actual-artifact regression/lifecycle tests, packaged-helper acceptance and repeated model utilisation harness. An evidence report validator checks mandatory cases, identity, evidence hashes and required attempt counts.

## Evidence

Evidence is retained under `artifacts/native/managed-tools/`. The local signed repository holds actual payloads and public metadata; private preview signing keys are outside the served directory. The two revisions contain the same real RustScan executable and different recorded package revisions. This demonstrates immutable package selection and recovery, not a comparison of two upstream scanner versions.

The Homebrew formula/package label is 2.4.1; its supplied executable reports `rustscan 2.3.0`. The descriptor uses the observed CLI version and records the supplied binary digest/receipt. Source-build reproducibility has not been proved.

The actual installed development app is `/Applications/Wixal Tools Preview.app`. Installation records independently verify app/helper/source-manifest/trust-manifest hashes against the packaged app. The existing primary Wixal application has a separate bundle path.

Validation results and exact helper hashes are written to the machine report and install receipt. `managed-tools-evidence.py` exports independently checked, hash-validated backend/model envelopes; the backend envelope passes and the two-core model envelope fails on the incomplete inspection attempt. The 104 mandatory families are also recorded in `tools-distribution/acceptance-suite.json`, with release status not qualified. Source tests, packaged helper execution, installed GUI checks and production distribution are separate evidence classes.

## Measured final preview results

| Check | Result | Evidence |
|---|---|---|
| Full native regression suite | 248 tests passed | Final source regression log |
| Focused managed tools | 18 tests passed | Actual artifact tests plus boundary fixtures |
| Swift/Python packaging and local signature | Passed | Final package build and codesign verification |
| Installed/source identity | 118 source files match; app/helper/trust hashes match package | `artifacts/native/managed-tools/install.json` |
| Installed helper install/discover/inspect/investigation | Four backend cases passed | `artifacts/native/managed-tools/packaged/report.json` |
| IPv4/IPv6 per-host handoff, empty results and Stop | Three real lifecycle cases passed | `artifacts/native/managed-tools/lifecycle/report.json` |
| GPT-OSS 20B, context 8192, fresh ports on each attempt | 5/5 discovery; 4/5 linked inspection | Ten attempts retained in packaged report; model qualification blocked |
| Installed GUI | Launch observed; first-use legal acceptance pending | No Tools/Recon GUI gate claimed |

Final installed helper SHA-256: `9fb7cda52f0bc86ea90f8a11625b5ba2e9b7d53c99c948bed1d5c5ed83871595`.

The final model failure completed fresh discovery but omitted the requested Nmap step. An earlier helper produced two unexecuted scan-completion claims; all those attempts remain in `intermediate-build-model-report.json`. The current system instruction requires fresh tool evidence for requested actions, and the final rerun uses new actual listener ports on every attempt. This improvement does not qualify the model: the linked task still failed one critical attempt and the complete model matrix has not run.

The preview artifact is tested only on this Mac: Apple Silicon, macOS 27.0.1 build 26A434. The declared minimum OS is not evidence of acceptance on older OS versions.

## Remaining gates and work

- The public controlled source/build repository is [TheJhyeFactor/wixal-tools](https://github.com/TheJhyeFactor/wixal-tools). All eleven existing tool repositories have controlled forks with inherited workflows disabled, full source pins and pinned license references. The repository holds a vendored RustScan build recipe and candidate workflow; immutable releases are enabled for future promotions. The public authenticated catalogue, production key custody, independent root quorum/recovery and release promotion remain unconfigured. No managed tool release has been published.
- This app and the local tool artifacts have no newly proved Developer ID/notarization/Gatekeeper distribution acceptance. Ad-hoc signature validation only establishes the local preview signature.
- The installed preview launches at its first-use Terms and Privacy screen. Completing that agreement requires the user's confirmation. Library/Recon UI interaction acceptance remains pending until the screen is completed.
- The 104-family matrix remains the required release suite. Current automated and real-task cases cover a subset; unexecuted families and other hardware/OS boundaries are not treated as passing.
- Repeated GPT-OSS tasks provide bounded utilisation evidence. The full held-out, denied-scope, injection, context-pressure, model-switch and interpretation suites, plus stable 30-attempt thresholds, remain uncompleted. No model is given an evaluated badge.
- Managed Nmap redistribution, additional runtime/dependency packages, downloaded assessment databases/templates, authenticated declarative content/workflow updates, independent cross-engine socket budgeting and a complete production build/promotion pipeline still require their own implementation and acceptance contracts. Existing external providers are usable through their existing adapters but are not managed-package certifications.
- Benchmark-derived pace tuning, wider private-subnet RustScan batching, additional OS/hardware support and production quarantine behaviour remain unqualified.

This is a functioning local RustScan pilot and package-manager foundation. It is not completion of every future-tool, production-operation and model-certification requirement in the technical plan.

## GitHub source publication

The tool library and managed pilot were prepared in an isolated checkout from the current public main branch. Separate in-progress diagnostics/reporting and unrelated UI edits were excluded. That scoped checkout passed **243 engine tests**, the native release Swift build and the five production Markdown parser checks on 9 October 2026. The earlier 248-test result above describes the broader local development checkout, including separate diagnostics tests; it is not the same source manifest as this publication.

The published CI builds its real RustScan fixture from the exact controlled source/build repository commit before running managed package and Nmap handoff tests. It does not rely on a pre-existing Homebrew RustScan installation, and missing real-artifact prerequisites fail rather than producing a qualified result. CI candidate construction does not replace installed-app, model or production-signing acceptance. Existing alpha download assets remain at their previously published build identity.
