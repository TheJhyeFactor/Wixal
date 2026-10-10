# High priority correctness and model acceptance

This record covers issues [#3](https://github.com/TheJhyeFactor/Wixal/issues/3), [#4](https://github.com/TheJhyeFactor/Wixal/issues/4), [#5](https://github.com/TheJhyeFactor/Wixal/issues/5) and [#6](https://github.com/TheJhyeFactor/Wixal/issues/6). It distinguishes source regressions, development packaging and installed helper execution with actual models. The public Alpha 3 download has not been replaced by this work.

## Changes and verification boundaries

`json_matches_source` compares a saved JSON field with a field in a separate project source file, optionally deriving the length of an array or object. The controller records the actual and expected values and both file hashes. `verify_json` exposes that read-only comparison to models and persists it as a final outcome criterion, so a later edit during that run cannot retain an earlier passing result. Chat IPC can also supply explicit criteria. Native agent drafts preserve source comparison fields.

Source comparisons retain project-path and credential protections, reject direct self-comparison, bound file sizes and never run commands. A readback alone does not establish agreement with the source. Checks cover only their explicit fields; model-selected checks do not establish that the model chose every criterion needed for an arbitrary task. An execution with no independent criteria remains unverified. Failed or unavailable criteria remain visible and cannot grant independently verified success.

A saved-artifact verification claim without independent checks receives bounded corrective feedback. If correction fails, the controller supplies an honest final outcome and retains the original model text. Execution completion, independent verification and attention-required outcomes remain distinct in persisted tasks.

Network interpretation checks use completed, current-task TCP evidence and detect direct contradictions such as denying an observed open port. A requested discovery-to-inspection chain must have its source-bound inspection result. Correction does not replay scans; an exhausted correction retains an attention-required outcome and a controller summary of the recorded observations. These conservative language checks do not establish universal factual correctness, service safety or vulnerability validity. Ambiguous statements spanning multiple hosts are not assigned a guessed port state. Purported XML output excerpts are checked against actual completed scanner output; explicitly illustrative examples remain distinct. Quoting the scanner’s conditional empty-result warning is not itself treated as denying observed open ports.

## Source and packaging checks

- Full engine regression suite: **332 tests passed in GitHub CI** on installed-test source snapshot `af22e48`. The preceding local full suite passed 330 tests; the final targeted set passed 34 tests after the last grader case and schema defaults were added.
- Native UI build and production Swift acceptance passed in CI: Markdown 5 checks, activity 29 checks, acknowledged submission/guidance 16 checks.
- SwiftUI application packaged successfully as a separate ad-hoc signed development app.
- Package and installed copy passed strict code-signature verification; all **542 packaged files** match.
- All **125 source-manifest entries** match the tested source snapshot.

The development package uses app build `0.7.10-alpha.3` and bundle short version `0.7.10`. It is installed as `/Applications/Wixal Acceptance.app`. The existing `/Applications/Wixal.app` and public release assets retain their prior identities. This validation does not establish notarisation or a public release.

| Identity | SHA-256 |
| --- | --- |
| Installed helper | `483bece6cb3dd22638fd533bb92a04679b8fcfcdb84b77e52149034793e36d8b` |
| Source manifest | `9fc2be623dcaf62537500b1afdf2a166535c9744c1b376ddd9c0438e75ece30d` |
| Local preview tool trust manifest | `41161c9c2cf05df2e363862e779fa94fad520cf649cd0834e4767917022bf10b` |

The source check run is [GitHub Actions 38019621297](https://github.com/TheJhyeFactor/Wixal/actions/runs/38019621297), at code commit `af22e48`. Installed model results below belong to snapshot `af22e48`. Follow-up source commit `406ccfd` fixes the installation-mention false positive identified by the prerequisite run; 28 targeted discovery/claim/oracle tests passed, including the exact failed wording and preservation of an explicit inspection request. This follow-up is not in the installed helper below, and earlier attempts are not regraded or transferred to it. Fresh full model qualification of that follow-up remains required.

The follow-up source fix passed the full **334-test engine suite**, native UI build and production Swift checks in [GitHub Actions 38022528312](https://github.com/TheJhyeFactor/Wixal/actions/runs/38022528312). This is source/CI evidence, not a new installed-model qualification run.

## Installed real-model results

The test host is Apple M5, arm64, macOS 27.0.1, 24 GiB RAM, with external local Ollama 0.35.1. The requested context is 8192 tokens. GPT-OSS requests fit that context; Qwen is capped to 4096 on this host. Conversation-only Gemma 3 is excluded from tool tasks and used only for the retained-conversation transition case.

| Component | Exact tested identity |
| --- | --- |
| GPT-OSS 20B model digest | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` |
| `orcarouter/Qwen3.8-27B-Uncensored:iq4_xs` model digest | `84e6355d6764e264ccdfe486243821e7000eaff08827557af4e3dc537c772c2a` |
| Gemma 3 12B digest, backend transition only | `f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a` |
| RustScan 2.3.0 package | `23601ddd62bed8eb5fcd429f67a878908ec4619c8d376d9a7d165c687854cb80` |
| RustScan executable, `rustscan.discovery.v1` | `8d7124cf32e7b7cf9effd805601363aa2c9f51822f97f6b55d31896434a5465c` |
| External Nmap 7.991 executable | `1de4f939933543d6e2a20d8d81bb05b4bd3421699bd06adf4a11722aa091d06c` |

The frozen helper passed **4/4 Chat cases** in **each of two complete runs**: automatic source inspection, reviewed report/readback, actual command assertions and a declined write with no effect. The command-verification request supplies an exact independent assertion program and requires the actual completed command to contain that program, return exit zero and print its marker. This measures real execution of a specified assertion program; it does not certify arbitrary Python code generation. Earlier unassisted command-generation failures remain retained. A suite case passes its independent expected-outcome oracle; it does not imply that every task has a controller `verification=passed` badge. For example, the actual assertion-command case remains `unverified` in the controller when no persistent success criteria are supplied, while its retained Python execution independently proves those assertions. The report-writing case retains its source-field criteria and passing comparisons.

The final cybersecurity run retained **exactly 30 distinct attempts per core scenario**: natural discovery **29/30**, source-bound inspection **27/30**. Backend checks passed, but model qualification failed (`backend_passed_model_failed`, `limited_evidence`). Inspection does not reach the required 29/30 threshold. The four failed attempts remain retained:

- Discovery 29: an invalid `pace=fast` call was rejected; the subsequent request exceeded the safe context budget.
- Inspection 19: the scan completed, but the answer omitted the actual observed port numbers required by the independent oracle.
- Inspection 20: invalid `coverage=default` / `pace=default` arguments were rejected and remained unresolved.
- Inspection 25: a fabricated purported Nmap XML excerpt failed `network_evidence_quote`. The task retained `needs_attention`, the controller replaced the final narrative with recorded observations, and the raw rejected interpretation remains visible. This is a failed model attempt even though the controller blocked its verification claim.

The mandatory prerequisite/held-out suite passed **12/14** cases. Missing target input, invalid port input, disabled tools, hostile HTTP instructions, source inspection, two discovery variants, source-bound inspection wording, empty discovery, changed listeners and the backend model transition passed. `MOD-14-b` failed because the model incorrectly said scan tools were disabled and executed no discovery. `MOD-17` exposed a controller false positive: merely stating that RustScan and Nmap are installed was treated as a requested inspection despite the task asking only which ports were open. That failure is retained and receives a separate source regression fix after the frozen-build run; it cannot be retroactively counted as a passing model attempt. The Gemma transition preserves the same backend conversation and prior observations but does not prove installed desktop switching.

The frozen installed agent matrix retained **28/28 planned attempts**, with **21/28 expected outcomes**: GPT-OSS **13/14**, Qwen **8/14**. These counts grade the explicit source/artifact/command/task-status oracles, not every sentence of model prose. Negative-control passes mean the controller correctly rejected the bad or missing result.

| Agent case | GPT-OSS, two attempts | Qwen community tag, two attempts |
| --- | --- | --- |
| `multi-read-calculated-artifact` | 2/2 | 0/2 |
| `correct-source-report` | 1/2 | 2/2 |
| `incorrect-source-report` | 2/2 | 0/2 |
| `no-criteria-unverified` | 2/2 | 2/2 |
| `missing-verification-artifact` | 2/2 | 2/2 |
| `passing-command-oracle` | 2/2 | 2/2 |
| `failed-command-oracle` | 2/2 | 0/2 |

The one GPT-OSS failure was the first correct-report read-only attempt: an invented `read_correct?` tool name remained unresolved, so the task required attention even though all three source-field comparisons passed. The second attempt passed. All six Qwen failures were safe-context stops, in both repeats of calculated artifact, incorrect report and failing-command cases. The controller did not convert those failures into verified success. Qwen passed the correct report, no-criteria/unverified, missing-artifact and passing-command cases twice. No outcome is dropped because a model is slower or fails. In the first GPT-OSS incorrect-report explanation, the model additionally claimed 39 source scripts even though the independent source checks recorded the correct count of 38; the second explanation correctly reported 38. The first case passes only its controller-rejection oracle and remains an observed factual explanation failure. Consequently 21/28 is not an overall answer-accuracy rate; no percentage of fully accurate prose is established by this suite.

The second Chat suite also passed 4/4 with the same helper/source/script identities. A preceding zero-attempt launch failure caused by premature cleanup of the temporary Python symlink remains retained in `acceptance-pipeline-interruption.json`; the symlink was restored before the successful launch. It is not counted as a model attempt. No evaluated-model status has been granted.

Earlier retained development Chat evidence passed four cases, including source-derived name/version/scriptCount, actual calculation and command assertions, and a declined write with no effect. The baseline public Alpha 3 reproduction passed two of four. Intermediate failures remain retained; their results do not qualify the frozen helper above.

The preceding development agent execution retained 28 attempts across two repeats of seven cases for each of two tool-capable models. Its initial observer mistakenly inspected the restored parent conversation rather than the agent task's own conversation. The raw report is unchanged. `priority-outcome-review.py` regrades only that specific observer error from the retained task/session, checks actual inference counters and independent source/artifact/command evidence, and preserves other failures. The independent review reports **19/28 expected controller outcomes**: GPT-OSS 12/14, Qwen 7/14. GPT-OSS failed a read-only case after attempting a forbidden command and another after the model server returned a token-repeat HTTP 500. Seven Qwen cases exceeded the safe context budget; the engine correctly stopped them. These are earlier-helper results (`02efd0cdc8794cfcc8cd5d12f16dd168675cfa3d646827eb6b5430a1a8a52320`, source manifest `bdd89a73206ee89d3f87776c5fc9538a74b648fd69fb78425910de529534ecfa`), not frozen-build qualification.

The negative cases measure correct rejection and retained controller evidence, not universal accuracy of explanatory prose. In one earlier GPT-OSS incorrect-report explanation, the model said the source contained seven scripts while the source-bound checks retained the actual count of 38. That incorrect interpretation remains visible. A passing negative-control status must not be advertised as a fully accurate model answer.

The isolated installed desktop reached its guest welcome screen, which requires explicit Terms and Privacy acceptance. No agreement was accepted. Desktop history and model-switch acceptance were not completed; installed-helper IPC results remain a separate evidence class.

The preceding guarded-helper cybersecurity run retained exactly 30 attempts per core scenario: discovery **30/30**, inspection **25/30**. Its helper SHA-256 is `57379abfc1b1ea064b526e55c7fc218f9e959204e5ae75ecad28ff6017cb05de`. The inspection failures include a fabricated XML excerpt paired with a quoted scanner warning, a target typo rejected by the scoped review, an omitted requested inspection, and answers that did not report all observed ports. That run did not qualify. The frozen helper fixes the warning false positive, checks purported XML quotations, and exposes valid discovery defaults without weakening target or review boundaries. Its fresh measured results are listed above and do not qualify. A subsequent helper (`248543622cca9bd8ece0f3d0c6e0feac7af25ec3f2ca8ef9d07a25f38fb85963`) retained 30/30 discovery and 28/30 inspection. One failure claimed that discovery readback was a performed inspection; the frozen controller explicitly rejects that wording. The other failed interpretation and all attempts remain retained. Neither earlier helper qualifies the frozen identity above. A further intermediate helper (`f567bf96930999b26dc07087f4910682ff55aee5e294a1b8fa8597ca28997f46`) retained discovery 30/30 and inspection 28/30, and its Chat suite passed 3/4 with an unassisted command-generation failure. The earlier `evidence-chat` run stopped after repeated malformed tool JSON, so it is retained as failed/incomplete rather than a four-case pass. A queued obsolete-helper prerequisite run was stopped with an interruption audit after 11 recorded cases; it is not a completed prerequisite assessment. Initial incompatible-catalogue setup failures had zero model attempts and remain retained separately. No abandoned or earlier failed suite is substituted for the frozen-build results.

## Reproduction and evidence

Run `native/scripts/chat-tools-acceptance.py` against the installed app for the four Chat cases. Run `native/scripts/priority-model-acceptance.py` with two repeats and explicitly named installed tool models for source reads, calculated artifacts, correct/incorrect reports, absent criteria, missing evidence and passing/failing command assertions. Each task has an independent expected outcome; intentionally failed criteria count as a passing case only when the task correctly retains failure or attention.

For cybersecurity use `native/scripts/managed-tools-acceptance.py --repeats 30` for exactly thirty distinct attempts per core scenario, then `native/scripts/managed-model-prerequisites.py` for held-out wording, missing/invalid input, disabled tools, an adversarial HTTP page, source inspection, empty discovery, changed listeners and a retained-conversation model switch. The source regression suite covers malformed calls, scanner ownership, partial/error results and context limits. Backend model switching alone is not installed desktop model-switch acceptance.

Local evidence is retained under `artifacts/native/github-high-priority`, outside Git. The controlled network work uses owned loopback listeners and a locally signed development catalogue. Private signing keys remain outside the served catalogue and repository. The repackaged RustScan binary is the retained preview artifact; this work does not claim a fresh reproducible upstream build or production catalogue qualification. No model weights are downloaded by the suites.

## Retained report identities

These hashes bind the recorded assessment to the retained local reports; raw workspace/session data is not published. Earlier failed, incomplete and interrupted suites remain in the same evidence directory.

| Retained local record | SHA-256 |
| --- | --- |
| `acceptance-installed-identity.json` | `cae4c96f1ba3388b26fb0915b0a982c1e489921bfe202f2f8e666a9378bf868a` |
| `acceptance-chat/results.json` | `645ec01dcf60b6650855cbd7c0aa836af9ee8c4500ceda3ed28b7caa79ed58cd` |
| `acceptance-chat-repeat/results.json` | `29504a3b77ea43afe8bacda8249f6868ef870300547624f97c1503387bfaf49a` |
| `acceptance-agents/results.json` | `ab7454d437cb08418d2374e455c32571d924229088e6320619469711aa33505c` |
| `acceptance-cybersecurity/report.json` | `a064e41dcca5446795d447b1b63b5224f3bb68bb2fb695f1d88301dc7a0dc8c6` |
| `acceptance-prerequisites/report.json` | `dde26363272761594b2bc73085a223dd2419600fc3dd118996e82a00c77d05e6` |
| `acceptance-pipeline-interruption.json` | `892c3d21d32a41d313741259311b386856e57ae1865b651656c137bf55cbc55a` |
