# Model qualification continuation — 11 October 2026

Issue [#6](https://github.com/TheJhyeFactor/Wixal/issues/6) remains open while fresh exact-helper qualification runs. This work is in a separate **Wixal Priority** development app. The public release and unfinished design files are unchanged.

## Reproduced defect and correction

An invalid discovery call can narrow the selected tool schemas to those retained in that request. After discovery completes, the requested inspection check correctly identifies unfinished work. Previously, context fitting intersected the required continuation schemas with the already narrowed selection, so it could not restore `network_scan`. The retained 10 October failure includes the model concluding that no ports-profile tool was available.

`Agent.request_body` now restores an explicitly requested, unfinished source-bound inspection from schemas eligible in the current task before context fitting. It keeps lifecycle schemas available at supported context limits. Execution still requires a model tool call, source ownership checks and controller review. Discovery-only requests, unavailable tools and stopped execution retain their boundaries.

The regression failed before the correction and passes at 4K and 8K context, including stop and disabled-tool checks. The full Python regression suite passed **364 tests**. Production Swift interaction, activity and Markdown checks passed **24 / 29 / 5**. Native development packaging and strict signature verification passed.

## Frozen development identity

```text
helper SHA-256:     79a0720209d75ca0cbe9bee2ff57932df6bcdb6d6a423ded217f1cab536a8a7e
source manifest:    4fc050755205a68a38c144788da68d00e8a53dcfa18327239cb4b957b2eb85bc
model:              gpt-oss:20b
model digest:       17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7
context:            8192
```

All **126 source-manifest entries** and **542 installed files** match the staged package. The embedded TUF repository is a local, single-operator preview using an explicitly repackaged existing RustScan binary; it does not establish source reproducibility, independent production custody or public distribution readiness.

## Qualification status

The fresh prerequisite suite has passed the previously failing `MOD-14-c` source-bound inspection case. The suite and core attempts are still running; no final prerequisite count, core threshold pass or evaluated-model status is claimed here.

The sequential runner starts the core only if all 14 prerequisites pass. It retains exactly 30 distinct attempts for each of natural discovery and source-bound inspection, then runs the independent grader. Failed attempts are never retried or regraded as passes. Mandatory desktop model-switch acceptance remains separate.

Local reports are under `artifacts/native/priority-20261011/`: `python-regression.log`, `interactions.log`, `activity.log`, `markdown.log`, `installed-identity.json`, `qualification-identity.json`, `prerequisites/report.json`, and, if prerequisite gates pass, `core/report.json` and `core/independent-review.json`. Invalid local activity-check invocations are retained separately and do not count as passing component checks. Raw transcripts, workspace contents and preview private keys are excluded from publication.
