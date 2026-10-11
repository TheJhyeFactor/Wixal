# Specialist execution contracts

These are the current engine contracts in `wixal/addon_execution.py` and `wixal/addons.py`. Availability, an installed executable, passing execution, model interpretation and distribution qualification are separate observations.

| Capability | Current executable and inputs | Bounds and evidence | Qualification boundary |
| --- | --- | --- | --- |
| Saved packet analysis | TShark through `addon_run`, `id=wireshark`, project-relative `path` | Existing regular capture below 100 MB; fixed `-r … -q -z io,phs` argv; reviewed command session; poll `command_read`; retain capture hash, executable hash, exit status and raw protocol summary | Does not start live capture, set permissions, decrypt opaque payloads or establish Wireshark desktop acceptance. Fresh generated one-packet capture acceptance passed on the development helper. |
| TLS assessment | testssl.sh through `addon_run`, `id=testssl`, explicitly authorised single host/URL | Host validation through scan planning; fixed quiet/non-colour/batch argv; bounded command timeout; task target authority before review; retain actual endpoint, tool identity, output and exit status | CLI presence is not successful TLS coverage. Owned TLS fixture handshake and intentional cancellation passed on development helper `294bc44`, with actual protocol/cipher and terminal command evidence. A fresh completed owned-fixture assessment now passes with exact certificate fingerprint and independent TLS1.2/TLS1.3 handshakes. Absent-dependency and wider supported-runtime acceptance remain required. |
| HTTP interception | mitmproxy/mitmdump catalogue entry, `setup_required` | No `addon_run` execution profile. Requires explicit proxy/CA/browser configuration, allowed endpoint list and retained transaction evidence | No autonomous adapter or qualification is advertised. Installing the cask does not configure a proxy or authorize interception. |
| Web assessment automation | ZAP catalogue entry, `setup_required` | No `addon_run` execution profile. Requires configured runtime, authenticated context, reviewed automation plan, target scope and cancellation contract | Catalogue discovery does not establish a working ZAP session or agent capability. |
| Specialist module validation | Metasploit catalogue entry, `setup_required` | No `addon_run` execution profile. Requires independently scoped module/input policy, authenticated RPC and retained module/effect evidence | Catalogue presence grants no execution authority. Official installation and configured specialist operation remain separate. |

All implemented add-on profiles use structured argv rather than model-authored shell interpolation. File paths pass project/credential/symlink checks. Execution inside writable workflow branches is rejected. A restricted agent's network targets must match its task authority. A declined action must remain declined; command/session ownership and terminal outcomes remain inspectable. Temporary run homes and managed package leases are released on completion or failure.

The outer command timeout bounds supported runs. Each future specialist adapter still needs its own process-tree, cancellation, output-parsing and uncertain-effect recovery acceptance. Generic process machinery does not establish those tool-specific results.


## 11 October bounded installed follow-up

Frozen **Wixal Model Probe** helper `e274bc592a3602ae85cba4d6f113fdf19ef088c83a71e57c5b2c6e3fe5392341`, source manifest `919ecfd6871524aa33d2226059d2595ea3c210bf5e3a128edf32eca6162c5aa8`, matches127 source entries/542 files and passes strict signature verification. This source passed397 Python regressions. These backend observations do not grant the separately failed gpt-oss model qualification or change the public release.

The saved-capture adapter completed with exit0 and exact independently expected frame/eth/ip/udp counts of one42-byte packet each. The input capture hash stayed unchanged. The acceptance runner now checks numeric counts rather than protocol-name presence and retains helper/source/script identities.

One testssl assessment of a disposable owned loopback TLS endpoint completed with exit0 in63.8seconds. Its independent server recorded54 handshakes spanning TLS1.2 andTLS1.3. The retained output hash matches its saved file; the reported certificate SHA256 matches the generated certificate exactly. TLS1.0/1.1 are reported unavailable, TLS1.2/1.3 offered, HTTP200 observed and the certificate chain correctly identified as self-signed. Scanner vulnerability labels are retained tool observations, not independently validated vulnerabilities. The temporary private key was removed and is absent from reports.

The three unconfigured specialist entries, mitmproxy/ZAP/Metasploit, each report capabilityReady=false. Actual addon_run calls are rejected by the supported-profile schema before review; no installation or specialist command executes. This verifies refusal, not configured execution. The reusable runner records the exact installed tuple and all three rejections.

The TLS runner adds an explicit --complete mode with the existing600-second maximum and independent certificate/protocol checks. Default cancellation remains a separate mode; a fresh invocation recorded two real handshakes followed by terminal stopped/user_stop evidence and completedTLSAssessment=false. The completion report retains its executed script hash and source copy; subsequent stricter checks were also applied to that raw report independently, without relabelling its original execution.

Issue#17 remains open for absent-dependency/wider-runtime, process-tree recovery and any future configured specialist adapters. Installing catalogue entries does not satisfy those gates. Raw reports and fixture data remain local under artifacts/native/priority-20261011/.
