# Native cyber completion pass - 13 October 2026

This pass implements additional native capabilities and tests actual owner-authorised LAN devices. It does not establish full Decepticon parity, general model qualification, an AD/cloud assessment, or a trained cyber model.

## Implemented

- Finding edits preserve omitted CVE, component/version, root cause, surface, identity and objective metadata. Native editing exposes these fields. Run, sensor and binary evidence must match the finding target and current scope revision.
- Report packages include technical and executive Markdown, PDF and Word documents, SARIF, timeline and manifest. Word templates and ReportLab resources are collected into the packaged helper. Bundled dependency licences are retained.
- Report ZIP import checks bounded member counts and expansion, duplicate names, unsafe paths, encryption, exact manifest coverage, sizes and SHA-256 digests. It extracts nothing and retains an explicitly untrusted report snapshot. It does not restore targets, credentials, approvals or verified findings.
- Monitoring offers rule selection and source archiving. Rule changes pause collection. Authentication-failure and server-error records are grouped per batch with exact matching-record counts; HTTP server-error status is limited to 500-599. Raw batches remain retained. Archiving stops collection and preserves evidence references.
- Planning exposes differences between dossier content and scope, stale objectives, missing observable signals, and candidate-path evidence readiness. Effort remains an operator estimate; ranking is not exploit probability or execution authority.
- Optional installed Ghidra performs real static decompilation of a private binary copy, using an original fixed packaged script, 32-function/8 MB/120-second limits, two CPUs, process-group cancellation, private temporary storage and a macOS sandbox denying network access and writes outside that directory. Samples are never executed. SHA-256 binds the source binary, launcher, export script and retained result.
- The typed Nmap adapter offers an RDP profile using `rdp-enum-encryption` and `ssl-cert`. Normalization preserves bounded script output and CPE observations. RDP support is explicitly distinguished from required NLA, successful authentication, exploitation and certificate trust.
- Model-facing run evidence presents normalized results and interpretation before duplicate raw XML. The original retained record stays immutable, with its own hash. Exact camelCase action parameters appear in tool documentation and validation errors.

## Current evidence

All evidence below is local under `artifacts/native/cyber-completion-2026-10-13/`.

| Check | Evidence | Boundary |
|---|---|---|
| Engine regression suite | `engine-tests-final.log`: 562 tests passed | Source engine on this Mac |
| Focused final cyber checks | `cyber-tests-freeze.log` | Includes metadata, target/scope binding, unsafe ZIP rejection, monitoring grouping and report round trip |
| Source and packaged Ghidra | `ghidra-results.json`, `packaged-static-qualified/results.json` | Benign compiled Apple Silicon sample; recovered `check_access` comparison |
| Sandbox restrictions | `ghidra-sandbox-policy.json` | Actual denied network and outside-directory writes; private write succeeded |
| PDF/Word rendering | `pdf-final-technical/`, `pdf-final-executive/`, `docx-final-render/` | Technical pages inspected; fixture output, not client report qualification |
| SARIF schema and consumer | `sarif-schema-provenance.json`, `sarif-real-consumer-summary.txt`, `sarif-real-consumer.html` | Official pinned OASIS schema; Microsoft sarif-tools 3.0.5 parsed a real exported retained observation locally |
| Concurrent monitoring | `sensor-load/results.json`, `sensor-ten-minute-load/results.json` | 8 sources; short load and full ten-minute automatic stop passed; 481,600 records and 240,800 matching records accounted for after explicit final drain |
| Controlled fix/retest | `retest-source-final/results.json`, `retest-packaged/results.json` | Actual owned loopback listener changed open to closed; legitimate control port stayed open; declared contract passed |
| Linux worker | `worker-services-source/results.json`, `worker-services-packaged/results.json` | Real services profile, nftables allow/deny, cancellation, ownership and cleanup in dedicated Colima VM |
| Native UI | UI tool trace, `ui/data/`, `installed-ui/results.json` | Finding metadata controls, report export and reviewed benign Ghidra exercised; installed rule editing and source archiving persisted after restart |
| Installed app | `installed-verification.json` | 162 source files matched; bundle signatures/hashes checked; ad-hoc signed alpha 0.7.10-alpha.6 |
| Installed live LAN adapter | `installed-lan/results.json` | Exact selected hosts/ports; retained native adapter output; no credentials or target mutation |
| Installed model workflows | `installed-model-workflows/results.json` | 7 guided production-tool workflows and restart passed with real Qwen inference; separate from semantic qualification |
| Two-model semantics | `lan-model-final-qa/results.json` | 6/8 passed: Gemma 4/4, Qwen 2/4; both models respected denial and imported instruction boundaries; Qwen omitted explicit port state in both completeness checks |

Earlier failed runs remain in the evidence directory. In particular, a packaged DOCX export failed because a footer template was missing, Gemma used a wrong parameter spelling and later overstated protocol negotiation, and Qwen omitted an explicit port-state statement in the final completeness checks. These are distinct failures; successful fixture or source runs do not erase them.

## Private lab observations (addresses and hostname redacted)

Owner authorization came from the request to test other devices on the local network. The local address was SOURCE_MAC on OWNER_PRIVATE_SUBNET. Gateway EXCLUDED_GATEWAY and the source Mac were excluded. Initial host discovery identified LAB_WEB_DEVICE and LAB_RDP_DEVICE; separately selected ARP neighbours returned filtered results on selected ports. `-Pn` assumed host state is not proof those neighbours responded.

- LAB_WEB_DEVICE: ports 80 and 443 observed open. Initial service identification returned `tcpwrapped`. An unauthenticated root HTTP GET returned 307 to HTTPS. HTTPS certificate verification failed for a self-signed certificate; the application response was not assessed through a bypass.
- LAB_RDP_DEVICE: port 3389 observed open with Microsoft Terminal Services. RDP negotiation reported CredSSP/NLA, CredSSP with Early User Auth and RDSTLS support. The presented certificate identified REDACTED_LAB_HOST. This does not establish required NLA, login success, exploitability, or device security.

No remote remediation, password guessing, credentialed domain testing, exploit execution or training on private LAN data was performed. State changes were confined to disposable owned loopback fixtures and the dedicated validation VM.

## Still partial or unavailable

- Model qualification: only two installed models have this semantic matrix. A passing bounded case does not qualify arbitrary instructions, all installed models, broad cyber tasks or exploit reasoning. The final matrix preserves model completeness failures.
- Monitoring: sources are local files; rules are deliberately limited and grouping is per batch. The load test covers eight sources through the complete ten-minute monitoring limit; it does not establish multi-day stability. Rotation/truncation pauses and requires explicit enrollment of the new source. Archiving is implemented; automatic evidence retention expiry/deletion, remote collectors and broader detection content are not.
- Planning: structured interview fields, contradiction checks and candidate ordering are implemented. There is no validated quantitative risk/effort model or automatic enforcement of prose retention commitments.
- Sessions: existing operation recovery, cancellation and owned Linux worker cleanup are tested. Persistent unrestricted shared shells and automatic replay of unknown effects are not implemented.
- Binary analysis: real local Ghidra is tested. External REA/MCP-provider interoperability, malware execution and broad decompiler format coverage are unqualified.
- AD/cloud/C2: LAN service evidence does not identify or qualify an authorised domain controller, cloud tenant, test identities or C2 lab. These integrations remain incomplete; an RDP service is not an AD test environment.
- Training: no labelled and reviewed cyber training dataset or fine-tuning run was supplied or performed. Synthetic acceptance cases and LAN observations are evaluation evidence, not a trained adapter.
- Distribution/hardware: no Developer ID signing identity is installed; notarization and a public release were not performed. Other Mac configurations and OS versions are untested. Source/package/installed acceptance on this Mac cannot substitute for those checks.

No private LAN evidence has been uploaded or published. The previous installed application is archived by the installation script for recovery. This completion pass is a local alpha update; no GitHub release, website deployment or public assurance claim was made.
