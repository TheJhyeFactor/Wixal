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

The scanner result now separates requested port/connection coverage, observed open endpoints and the unknown examined-port count. Its metadata states that elapsed duration cannot establish a probe-completion ledger and that pace is a Wixal controller preset, not an executable option. Explicit invocation options are checked against retained argv. Null examined counts remain valid; assertions that no probes finished and claims that nonempty SHA-256 fields are empty receive bounded feedback.

Further retained attempts:

| Candidate helper prefix | Measured result |
| --- | --- |
| `508024825065` with gpt-oss | Supplemental check failed after repeated examined-coverage claims. Core not started. |
| `508024825065` with Qwen | Supplemental automatic pass independently rejected for a zero-probe inference from duration. Prerequisites interrupted; core not started. Actual model context was 4096. |
| `7ba7761b12fd` | Supplemental automatic pass independently rejected for an invented `--pace` option. Core not started. |
| `22ff962b0e50` | Supplemental check failed. Review distinguished a false null-count rejection from unsupported zero-probe and empty-digest-field claims. Core not started. |
| `0fd599bf75dc` | Supplemental check failed on a controller false positive for zero warnings/errors. Raw outcome retained. |
| `f4848e545eac` | Supplemental check and independent review pass; prerequisites 12/14. Disabled-tool workaround and omitted requested inspection fail. Core not started. |

The pipeline now requires an independently reviewed, hash-matched supplemental report before starting prerequisites or core attempts. Final exact-helper counts and installed desktop results will be recorded after execution. **No evaluated-model status is granted yet.**

The current full Python suite passes **373 tests**. A preceding run retained one response-budget regression; the added network guidance is now scoped to network requests and the meaningful budget check passes unchanged. Production Swift interaction, activity and Markdown checks passed **24 / 29 / 5**. All installed candidates matched their 126 source-manifest entries and 542 staged files and passed strict signature verification.

The automatic tool inventory now respects the existing native scanner off switches. Previously it offered scanner schemas which actual execution rejected, so tool-scope verification could reject a truthful disabled-adapter explanation. The regression fails on the prior implementation and passes after the correction; other Chat tools retain automatic discovery. The disabled-tool prerequisite now requires a completed explanation without native scan, installation or command workaround calls.

The completion detector also distinguishes a report of zero warnings/errors from a completed scan. Null examined coverage remains unknown and does not prevent an accurate partial-evidence explanation from completing.

Current helper: `f4848e545eac105fe06d7561cc1a4f2534dae42b45a7734b60cfda2610c13ed8`; source manifest: `7e476797a0c8d6f4a5b28aba8f735c50ab81e026532aad8ffa0752e913414ba7`. The separate app is **Wixal Backlog Scope**.

This helper's supplemental cancelled-evidence check passes both automatic and independent review. The exact source was read, raw empty output digests match independent files, no new action or review occurred, and the answer preserves unknown examined coverage and port-state limitations. Prerequisites finished at 12/14; full qualification failed and core attempts were not started. The earlier `0fd599bf75dc` attempt remains failed because its controller falsely rejected a zero-warning report; it is not regraded or transferred.

A live feedback-role diagnostic returned the corrected colour with both later system and user messages. Template inspection alone therefore did not establish a feedback-delivery defect; no transport change or qualification result is inferred from that diagnostic.

The runner starts the core only after all mandatory gates pass, retains exactly 30 distinct attempts per core scenario, and runs an independent grader. Installed desktop history/model-switch acceptance remains a separate gate. Earlier desktop evidence belongs only to its recorded helper.

## Evidence boundary

Local reports are retained under `artifacts/native/priority-20261011/`, including frozen identities, raw attempts, independent reviews, regression logs and interrupted-run audits. Raw transcripts, workspace contents and preview private keys are excluded from publication.

The embedded TUF repository is a local single-operator preview repackaging an existing RustScan binary. This does not establish reproducible upstream builds, independent production key custody or public distribution readiness. The model remains `gpt-oss:20b`, digest `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`, at 8192 context. Qualifications must match the exact helper, source manifest, model, adapter, package and content identities.

## Adapter scope and unfinished-step follow-up

The scanner inventory now reports current native adapter availability separately from installed binaries and package readiness. After a declined action, subsequent requests explicitly state that no tools remain and forbid retries or command workarounds. A requested unfinished inspection includes its current-task source identifiers in the context, including after schema-budget fallback; this is feedback only and execution still requires a model call and normal review.

Fresh installed helper `7993d2832bd1bfec485eb07ba88d2f287aaf7eae5ca66b4836c0135aa593a11f`, manifest `f070713b918afc3806d4ca47392e0a017d722b682a5a782bf76a54ecb491100e`, is **Wixal Backlog Availability**. All 126 source entries and 542 packaged files match. Its supplemental model attempt failed: the model omitted two characters from the supplied source session ID and did not recover the exact identifier. The controller refused access and retained `needs_attention`; no new scan ran. The failure is retained, not regraded, and the qualification pipeline did not advance. A separate prerequisite diagnostic is running to assess the new scope and continuation feedback; it cannot grant qualification over the failed supplemental attempt. The desktop has completed an independently checked real-model file read on this helper.

Issue #6 remains open. No exact-tuple evaluated status is granted, and the public release remains unchanged.
