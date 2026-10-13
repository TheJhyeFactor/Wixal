# Wixal 0.7.10 Alpha 7 — Cyber toolkit and faster website publication

Apple Silicon, macOS 14 or newer. This is an ad-hoc signed, non-notarised prerelease. Download the ZIP and verify it against `SHA256SUMS.txt` before installing. Model weights, Nmap, Ghidra/Java and the optional Linux runtime are separate installations.

## Changes

The native Cyber toolkit brings evidence-bound finding drafts, CVE/component/identity metadata, dossier consistency checks, eight specialist roles and 18 assessment procedures into Wixal's existing controller and review system. Findings retain revisions and counterevidence; report completion and CVSS scoring do not confirm a vulnerability.

Technical and executive reports now export in Markdown, PDF and Word, with SARIF, an event timeline and a manifest-backed ZIP. Imported report packages are bounded and hash-verified without extracting files or restoring scope, approvals, credentials or verified findings. Original retained evidence stays separate from redacted export derivatives.

Local log monitoring adds selectable rules, per-batch incident grouping and source archiving. Collection is read-only, scoped, explicitly reviewed and bounded to ten minutes per start. Rotation/truncation pauses collection; a new source requires explicit enrollment. Archiving retains existing evidence references.

Optional installed Ghidra performs real static decompilation of a private file copy. The fixed export script is limited to 32 functions and the adapter limits input to 8 MB, two CPUs and 120 seconds. Network access is denied and writes are limited to disposable analysis storage. The sample is not executed.

The typed network adapter adds an RDP profile and preserves bounded scanner-script observations. Successful RDP negotiation reports protocol support, not required NLA, successful login or exploitability. Model-facing evidence presents normalized observations and limitations before duplicate raw XML. Parameter validation now gives exact action-field names. Evidence-only analysis handles reasoning-only replies without marking an empty answer complete.

Website publication now uses `website/release.json` for the published version and tag. A native development version no longer changes the public download automatically. Website-only changes no longer trigger the full macOS build/test workflow, which previously took about eleven minutes for a download-link update. Native changes still run the full checks. Publish verified release assets, then update the website manifest and copy.

## Evidence and limits

The implementation pass on the release source lineage recorded:

- 562 automated engine tests passed.
- Seven guided installed-model workflows and restart persistence passed with real Qwen3.5 9B inference.
- A separate two-model interpretation/denial/imported-instruction matrix passed 6/8. Gemma 4 E4B passed 4/4. Qwen passed denial and imported-instruction cases, but omitted explicit port-state wording in two completeness checks. These failures remain open.
- Real static Ghidra analysis recovered the comparison in a benign compiled Apple Silicon sample. Sandbox checks denied network and outside-directory writes.
- Eight monitors stopped automatically at their ten-minute limit. Explicit final collection accounted for 481,600 fixture records, including 240,800 matching records. This is bounded load evidence, not multi-day stability.
- A real disposable loopback listener changed from open to closed while a control port stayed open; the declared retest contract passed.
- Source and packaged Linux worker service scanning, outbound policy, cancellation and owned-resource cleanup passed in a dedicated validation VM.
- Native UI report export, reviewed static analysis, monitoring rule editing, source archiving and persistence were exercised.
- SARIF passed the pinned official schema and local Microsoft SARIF-tools consumption. PDF and Word output was rendered and inspected.
- Bounded private-lab services were observed through the installed adapter. Private addresses, hostnames and raw lab data are not published.

These dated implementation records describe their original Alpha 6 build identities. Alpha 7 packages the same cyber implementation with new version metadata; release verification, archive hashes and GitHub CI are recorded separately for this release. The release attachments identify the exact public bundle and source commit.

This release does not provide trained cyber weights, full Decepticon parity, broad model qualification, an authorised AD/cloud/C2 integration, persistent unrestricted shared shells, remote log collectors or automatic evidence retention expiry. External REA-provider interoperability, wider binary formats, other Mac/OS configurations, Developer ID signing and notarisation remain unqualified or unavailable.

See [implementation and remaining gaps](decepticon-cyber-completion-2026-10-13.md) and [native alpha guide](native-alpha.md). Compatible capabilities are original native Wixal adaptations, with attributed Decepticon CVSS arithmetic and retained licences. No upstream autonomous controller or payload corpus is bundled.
