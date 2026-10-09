# Managed tools continuation

The user requested the remaining implementation work while excluding release qualification. They selected in-app contributor GitHub OAuth and requested that production catalogue promotion stay gated until independent signing custody exists.

## Implementation

- Application-owned managed profiles now cover RustScan, ffuf, Nuclei, Trivy and OSV-Scanner. The four Go candidates build from locked controlled fork commits with pinned module hashes and Go 1.27.2, vendored dependencies, retained corresponding source and notices, architecture/library checks and actual isolated CLI readiness.
- Shared registry operations and the Tools controls support each known profile's managed installation, provider selection, integrity verification, update/repair, retained approved rollback and lease-protected removal. Execution uses the exact immutable leased path and records executable/package/adapter identity. External installations remain separately selectable.
- Readiness probes use a temporary home and working directory; Nuclei's first-run configuration cannot modify an immutable installed package. Nuclei execution uses an explicit signed template, a bounded target-relative GET/HEAD HTTP profile, disabled redirects and callbacks, an immutable copy of the selected bytes, its recorded digest and disabled stdin processing.
- Socket reservations are coordinated through a shared SQLite database across engine processes. Reservation ownership transfers to the actual scan child. Cancellation releases reservations; stale process cleanup checks process birth identity. The tests exercise independent managers and actual child lifetimes.
- Requested discovery/inspection chains are checked against fresh task checkpoints. Empty inspection results retain source IDs. Current controller scan handles are retained separately in model context. Malformed tool-call JSON receives up to two inference corrections; an empty completed response receives one continuation request. Failed inference responses execute no actions, exhausted output remains a visible failure, and normal tool authority checks still apply.
- Progressive context fitting retains pending source-bound inspection and network read/stop schemas. Fresh natural scan/action requests omit earlier chats' transient instructions while preserving relevant saved notes and explicit historical recall. Source fields now explain that chat session IDs and investigation run IDs are different identifiers. These changes address failures retained in the first packaged evaluation; their fresh packaged run is recorded separately.
- Contributor GitHub Device Flow, identity checks, cancellation/sign-out and exact-draft issue submission are implemented through manual IPC and the full-report review screen. Tokens stay in memory, the repository is fixed, confirmation starts unchecked, and uncertain submissions are not automatically retried. The registered public client ID is pending; see [setup](GITHUB_REPORTING_SETUP.md).
- The controlled source repository provides offline root/bootstrap signing, role signing, signed catalogue assembly, authenticated updates with increasing metadata versions and retained root history, root rotation checks, and candidate promotion verification. Promotion verifies the metadata chain, catalogue target hashes and exact acceptance tuple/evidence hashes. Its public trust and independent custody contract remains explicitly unconfigured; the workflow has read-only permissions and publishes nothing.
- The root splash precedes the engine launch and workspace construction. The updated installed app passed animated, animation-off, reduced-motion, slow real SQLite startup and failed database recovery cases.
- Tools Details now reads current library state instead of a stale selected row, displays installation failures and cancellation controls, and updates provider/readiness while open. The earlier diagnostics, sanitized local report preparation and response selection/collapse fixes are included.
- The library footer follows its actual job to completion. Rollback controls require a locally retained recovery payload; unavailable recovery is explained. Historical receipts survive removal, but missing executable payloads are excluded from recovery choices. The remove/reinstall regression and actual installed UI both verify this distinction. Removal still reads historical receipts so a damaged payload with a missing executable is cleaned up and its active pointer cleared. A successful authenticated catalogue refresh clears the previous outage warning. These refinements were verified in the updated installed app.
- The acceptance inventory retains all 104 families, checks exact configuration and evidence hashes, and explicitly records missing, incomplete and user-deferred gates. Model repeatability requires both core scenarios, exactly 30 distinct attempts each, and at least 29 successes per scenario. Production promotion uses the same per-core requirement and remains gated. See [evidence workflow](MANAGED_TOOLS_EVIDENCE.md).

## Measured evidence

Local evidence is retained in `artifacts/native/managed-tools-completion/`, outside source publication.

| Check | Result | File |
|---|---|---|
| Current engine regression | 277 passed | `regression-recovery-complete.log` |
| Native release UI and Python packaging | Passed; development signature verified | `package-recovery-complete.log` |
| Package/install/source agreement | 122 source files and 542 packaged files match | `install-recovery-complete.json` |
| Current packaged signed install/discovery/source-bound inspection/linked investigation | Four backend cases passed; model skipped on this recovery-only build | `packaged-recovery-complete-backend/report.json` |
| Packaged ffuf/Nuclei/Trivy/OSV installation and actual capability | Eight cases passed | `go-recovery-complete/report.json` |
| Packaged IPv4/IPv6 host-specific handoff, empty result and cancellation | Three cases passed | `lifecycle-recovery-complete/report.json` |
| Installed splash/startup ordering and recovery | All five cases passed on the current installed helper | `startup-recovery-complete/report.json` |
| Installed Tools/Recon | Managed Nuclei Details updated without reopening; reviewed single-port discovery and source-bound inspection completed | `installed-gui.json` |
| Updated installed library and retained evidence | Ready footer, unavailable rollback explanation, evidence reopened after restart, reviewed current r2 discovery completed | `installed-library-gui.json` |
| Earlier source GPT-OSS 20B linked inspection | 30/30 passed | `source-inspection-corrected/report.json` |
| Intermediate packaged GPT-OSS 20B, 8192 context | 30/30 discovery, 27/30 inspection; failed attempts retained | `packaged-final/report.json` |
| First final packaged model repeatability | 30/30 discovery, 20/30 inspection; below policy, failed attempts retained | `packaged-handles-final/report.json` |
| First packaged prerequisites | 12/14 checks passed; held-out variant and comparable-tool selection failed; backend model switch passed | `model-prerequisites-final/report.json` |
| Interrupted context evaluation | 30/30 discovery and 2/2 inspection completed before process interruption; attempt 3 retained as interrupted | `packaged-context-final/report.json` |
| Resumed context model evaluation | 30/30 discovery, 28/30 inspection; below 29/30 inspection policy. Attempt 3 omitted inspection and made an unsupported inspection claim; attempt 17 exhausted malformed/invalid tool-call recovery. No evaluated badge granted | `packaged-context-resumed/report.json` and `context-model-critical-review.json` |
| Resumed packaged prerequisites | 10/14 passed. MOD-02, MOD-14-b, MOD-17 and MOD-07 failed. Backend alternate-model transition passed. MOD-17 contradicted actual open-port XML and listener evidence; qualification remains blocked | `model-prerequisites-context-resumed/report.json` and `context-model-critical-review.json` |
| Current installed recovery | Update, approved retained rollback, restored latest package and complete inventories verified; removed payload not offered | `installed-recovery-complete-gui.json`; removed-payload UI check on the preceding recovery helper in `installed-removed-recovery.json` |
| Current installed Recon | Reviewed selected TCP 18795 discovery and source-bound Ports inspection completed; four raw evidence files independently hash-verified; original source and raw hashes reopened after quit/relaunch | `installed-recon-complete-gui.json` |
| Installed managed provider inventory | All five supported tools selected as managed; full active inventories hash-verified | `installed-five-complete.json` |
| GitHub OAuth protocol/policy | Six controlled fixture tests passed; live authorization pending client ID | `native/tests/test_github_reporting.py` |
| Controlled source contracts and signing tests | Fourteen tests passed; public CI succeeded at `c3cb66b` | `TheJhyeFactor/wixal-tools` |
| Four controlled Go source candidates | All local builds and all four public CI jobs passed | Go candidate workflow run `37931409877` |

Installed helper SHA-256: `21726e3619794600d34b9ce5971827dfa4c34653e43dde4e0804944b8ee166b8`.

The first 60-attempt model run and prerequisite checks used the preserved prior helper `dffae91912a8ddcf30fe23f80a859caae7effda1f232b7bff7edce0f12ed0b1a`. The intermediate installed UI refinements used `164c99848a82ae098883f3e116e2ab80cecc883539fd4fe3fb1d15285374332d`. The context-corrected model evaluation uses preserved helper `70dc9c1d52c6d57be0dcb295fd52c7ff47e929763ee8994bf45b1c5601374b26`. The latest installed helper adds the removed-recovery filtering correction and damaged-payload removal cleanup and has its own backend and installed UI evidence. Earlier results do not grant evaluated status to a later helper. Every build remains a development preview.

The loopback catalogue is a local preview with private keys outside the served tree. It is not a public download service. The installed GUI scan used the owned catalogue server's TCP 18795 and retained its actual source-run reference and independent stdout/stderr hashes. Advisory acceptance used copies of Wixal's actual package and lock files. The Nuclei check used an official signed HTTP security-header template pinned to source commit `c8664a14c6078ae9da2d19dbb4c479981454cf65`.

The ffuf source tag is v2.3.0 but its executable reports 2.1.0-dev. The package descriptor uses the observed CLI semantic version and retains the full observed output and source provenance. A successful single build does not establish reproducibility. RustScan's two local package revisions contain the same real executable; they prove immutable revision lifecycle, not two upstream versions.

The final regenerated Python build and staging directories were moved to recoverable Trash. The canonical app, installed app, immutable acceptance builds, evidence, private signing keys and Swift dependency cache remain retained. See `build-cleanup-complete.json`.

The current recovery build has a separate acceptance inventory in `normalized-recovery-complete/matrix.json`: seven complete families, two partial families, 80 unexecuted families and 15 release families deferred by request. These counts record evidence coverage, not an aggregate regression count or a qualified model. The preserved context model build is evaluated in `normalized-context-resumed/matrix.json`, with the independently reviewed failed MOD-13 claim in a separate hash-bound envelope. Its global critical-model failure blocks qualification; zero families are qualification-passing in that combined model envelope, 70 are missing, 19 are incomplete/failed and 15 release families are deferred. The underlying backend outcomes remain retained in their original reports. These identities are not merged with the newer recovery build.

## Boundaries and remaining gates

- The registered GitHub OAuth public client ID has not been supplied. Contributor authorization and live issue creation are unproved. No issue has been posted during acceptance.
- Public catalogue promotion remains gated by the user's choice. No independent custodians are invented and no managed release is published. Production hosting, custody and promotion require their actual operational inputs.
- Nmap redistribution still needs its specific license/OEM review. Wireshark, testssl, mitmproxy, ZAP and Metasploit retain existing external/specialist integrations; their additional dependency/runtime managed profiles are not certified by these standalone builds.
- The complete 104-family contract remains retained. These results cover a measured subset. Unexecuted, deferred or failed families are not passing results. Wider model interpretation, switching and all GUI accessibility cases still require their own evidence before an evaluated model status can be granted.
- Developer ID signing, notarization, Gatekeeper distribution, wider OS/hardware and public release qualification are excluded from the current request. The installed app remains a development preview.
