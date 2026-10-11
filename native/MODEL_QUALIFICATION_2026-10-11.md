# Model qualification continuation — 11 October 2026

Issue [#6](https://github.com/TheJhyeFactor/Wixal/issues/6) remains open. Work uses isolated development apps and disposable owned-loopback workspaces. The public release and unfinished design files are unchanged.

## Reproduced defects and corrections

After an invalid discovery call narrowed selected schemas, the requested source-bound inspection could not restore `network_scan`. `Agent.request_body` now restores an unfinished requested continuation from eligible schemas before context fitting. The regression fails on the prior source and passes at 4K and 8K, including unavailable-tool, discovery-only and stopped-execution boundaries.

Reading retained cancelled or failed scan evidence previously counted as a failed action. A successful `network_read` of the exact requested terminal session now counts as a completed read while the original scan remains unsuccessful. An accurate explanation that a scan was halted also no longer triggers the completed-scan claim detector. Production-controller regressions verify correction without replaying scan actions.

Independent review found the model describing empty stdout/stderr as the zero hash. Explicit output-digest claims are now checked against retained SHA-256 metadata. Bounded feedback supplies the actual digests; exhausted correction preserves rejected model content and returns a factual controller summary.

Another exact-helper prerequisite run returned “network_discover is currently disabled” despite receiving its enabled schema. Verification now detects that wording as well as existing disabled-tool claims. Installation, readiness and review remain separate checks.

A cancelled-scan answer presented invocation ports under “Ports examined.” Requested coverage cannot establish which probes completed before cancellation. Verification now rejects that explicit table claim unless actual examined coverage is marked unknown. The supplemental grader also avoids falsely rejecting negated universal-port claims.

## Retained qualification attempts

Every changed helper receives a fresh qualification run. Prior failures are retained and never transferred to a newer helper.

| Candidate helper prefix | Measured result |
| --- | --- |
| `79a0720209d7` | 14/14 prerequisites; 16 completed core attempts passed before interruption to fix cancelled-evidence handling. No completed core qualification. |
| `9b3f9c76ac03` | Supplemental automated pass independently rejected for an unsupported zero-hash claim. Prerequisites interrupted; core not started. |
| `2579626ef98a` | Supplemental cancelled-evidence check passed; prerequisites 12/14. Two false disabled-tool claims failed. Core not started. |
| `297ad1ce141f` | Supplemental cancelled-evidence check failed. Independent review distinguishes an automated negation false positive from unsupported examined-port provenance. Core not started. |

The next candidate includes the examined-coverage correction. Final exact-helper counts and installed desktop results will be recorded after execution. **No evaluated-model status is granted yet.**

The latest completed full Python suite passed **368 tests**, before the final examined-coverage correction; that correction's 27 focused regressions pass and a fresh full suite is running. Production Swift interaction, activity and Markdown checks passed **24 / 29 / 5**. All installed candidates matched their 126 source-manifest entries and 542 staged files and passed strict signature verification.

The runner starts the core only after all mandatory gates pass, retains exactly 30 distinct attempts per core scenario, and runs an independent grader. Installed desktop history/model-switch acceptance remains a separate gate. Earlier desktop evidence belongs only to its recorded helper.

## Evidence boundary

Local reports are retained under `artifacts/native/priority-20261011/`, including frozen identities, raw attempts, independent reviews, regression logs and interrupted-run audits. Raw transcripts, workspace contents and preview private keys are excluded from publication.

The embedded TUF repository is a local single-operator preview repackaging an existing RustScan binary. This does not establish reproducible upstream builds, independent production key custody or public distribution readiness. The model remains `gpt-oss:20b`, digest `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`, at 8192 context. Qualifications must match the exact helper, source manifest, model, adapter, package and content identities.
