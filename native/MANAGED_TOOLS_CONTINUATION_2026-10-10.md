# Managed tools continuation

The user requested the remaining implementation work while excluding release qualification. They selected in-app contributor GitHub OAuth and requested that production catalogue promotion stay gated until independent signing custody exists.

## Implementation

- Application-owned managed profiles now cover RustScan, ffuf, Nuclei, Trivy and OSV-Scanner. The four Go candidates build from locked controlled fork commits with pinned module hashes and Go 1.27.2, vendored dependencies, retained corresponding source and notices, architecture/library checks and actual isolated CLI readiness.
- Shared registry operations and the Tools controls support each known profile's managed installation, provider selection, integrity verification, update/repair, retained approved rollback and lease-protected removal. Execution uses the exact immutable leased path and records executable/package/adapter identity. External installations remain separately selectable.
- Readiness probes use a temporary home and working directory; Nuclei's first-run configuration cannot modify an immutable installed package. Nuclei execution uses an explicit signed template, a bounded target-relative GET/HEAD HTTP profile, disabled redirects and callbacks, an immutable copy of the selected bytes, its recorded digest and disabled stdin processing.
- Socket reservations are coordinated through a shared SQLite database across engine processes. Reservation ownership transfers to the actual scan child. Cancellation releases reservations; stale process cleanup checks process birth identity. The tests exercise independent managers and actual child lifetimes.
- Requested discovery/inspection chains are checked against fresh task checkpoints. Empty inspection results retain source IDs. Current controller scan handles are retained separately in model context. Malformed tool-call JSON receives up to two inference corrections; an empty completed response receives one continuation request. Failed inference responses execute no actions, exhausted output remains a visible failure, and normal tool authority checks still apply.
- Contributor GitHub Device Flow, identity checks, cancellation/sign-out and exact-draft issue submission are implemented through manual IPC and the full-report review screen. Tokens stay in memory, the repository is fixed, confirmation starts unchecked, and uncertain submissions are not automatically retried. The registered public client ID is pending; see [setup](GITHUB_REPORTING_SETUP.md).
- The controlled source repository provides offline root/bootstrap signing, role signing, signed catalogue assembly, authenticated updates with increasing metadata versions and retained root history, root rotation checks, and candidate promotion verification. Promotion verifies the metadata chain, catalogue target hashes and exact acceptance tuple/evidence hashes. Its public trust and independent custody contract remains explicitly unconfigured; the workflow has read-only permissions and publishes nothing.
- The root splash precedes the engine launch and workspace construction. The updated installed app passed animated, animation-off, reduced-motion, slow real SQLite startup and failed database recovery cases.
- Tools Details now reads current library state instead of a stale selected row, displays installation failures and cancellation controls, and updates provider/readiness while open. The earlier diagnostics, sanitized local report preparation and response selection/collapse fixes are included.

## Measured evidence

Local evidence is retained in `artifacts/native/managed-tools-completion/`, outside source publication.

| Check | Result | File |
|---|---|---|
| Current engine regression | 269 passed | `regression-handles-final.log` |
| Native release UI and Python packaging | Passed; development signature verified | `package-handles-final.log` |
| Package/install/source agreement | 122 source files and 542 packaged files match | `install-final.json` |
| Packaged ffuf/Nuclei/Trivy/OSV installation and actual capability | Eight cases passed | `go-packaged-final/report.json` |
| Packaged IPv4/IPv6 host-specific handoff, empty result and cancellation | Three cases passed | `lifecycle-final/report.json` |
| Installed splash/startup ordering and recovery | Five cases passed | `startup-final/report.json` |
| Installed Tools/Recon | Managed Nuclei Details updated without reopening; reviewed single-port discovery and source-bound inspection completed | `installed-gui.json` |
| Source GPT-OSS 20B corrected linked inspection | 30/30 passed | `source-inspection-corrected/report.json` |
| Intermediate packaged GPT-OSS 20B, 8192 context | 30/30 discovery, 27/30 inspection; failed attempts retained | `packaged-final/report.json` |
| Final packaged model repeatability and prerequisite suite | Fresh run in progress; no evaluated badge granted | `packaged-handles-final/report.json` and subsequent prerequisite report |
| GitHub OAuth protocol/policy | Six controlled fixture tests passed; live authorization pending client ID | `native/tests/test_github_reporting.py` |
| Controlled source contracts and signing tests | Thirteen tests passed; public CI succeeded | `TheJhyeFactor/wixal-tools` |
| Four controlled Go source candidates | All local builds and all four public CI jobs passed | Go candidate workflow run `37931409877` |

Installed helper SHA-256: `dffae91912a8ddcf30fe23f80a859caae7effda1f232b7bff7edce0f12ed0b1a`.

The loopback catalogue is a local preview with private keys outside the served tree. It is not a public download service. The installed GUI scan used the owned catalogue server's TCP 18795 and retained its actual source-run reference and independent stdout/stderr hashes. Advisory acceptance used copies of Wixal's actual package and lock files. The Nuclei check used an official signed HTTP security-header template pinned to source commit `c8664a14c6078ae9da2d19dbb4c479981454cf65`.

The ffuf source tag is v2.3.0 but its executable reports 2.1.0-dev. The package descriptor uses the observed CLI semantic version and retains the full observed output and source provenance. A successful single build does not establish reproducibility. RustScan's two local package revisions contain the same real executable; they prove immutable revision lifecycle, not two upstream versions.

## Boundaries and remaining gates

- The registered GitHub OAuth public client ID has not been supplied. Contributor authorization and live issue creation are unproved. No issue has been posted during acceptance.
- Public catalogue promotion remains gated by the user's choice. No independent custodians are invented and no managed release is published. Production hosting, custody and promotion require their actual operational inputs.
- Nmap redistribution still needs its specific license/OEM review. Wireshark, testssl, mitmproxy, ZAP and Metasploit retain existing external/specialist integrations; their additional dependency/runtime managed profiles are not certified by these standalone builds.
- The complete 104-family contract remains retained. These results cover a measured subset. Unexecuted, deferred or failed families are not passing results. Wider model interpretation, switching and all GUI accessibility cases still require their own evidence before an evaluated model status can be granted.
- Developer ID signing, notarization, Gatekeeper distribution, wider OS/hardware and public release qualification are excluded from the current request. The installed app remains a development preview.
