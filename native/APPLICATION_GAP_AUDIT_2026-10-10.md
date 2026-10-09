# Native application gap audit — 10 October 2026

This work targets the native macOS application and its own Python engine. Findings are ordered by impact: incorrect evidence and effects first, recovery and agent controls next, then editing and presentation. Release qualification remains excluded. Public catalogue promotion remains gated pending independent signing custodians. Contributor GitHub sign-in still requires the registered Device Flow client ID promised by the owner.

## Prioritized findings and changes

| Priority | Gap and user impact | Implemented behavior | Verification |
| --- | --- | --- | --- |
| P1 | Chat's asynchronous Nmap results supplied paged XML without the service summary available in Cybersecurity. A preserved real-model trial incorrectly called two open ports closed. | Complete retained stdout is parsed once after collection. Every subsequent read includes structured services, port counts, coverage, executable identity and evidence hashes, independently of output pagination. | Real loopback listener and actual Nmap regression; packaged model follow-up recorded separately. |
| P1 | A successful process exit could hide malformed, timed-out or incomplete scanner evidence. | Shared parser requires complete Nmap XML and a successful completion record, rejects entity declarations and timed-out hosts, and enforces the evidence bound. Source-bound inspection uses the same parser. Cybersecurity retains parse failures as failed evidence rather than completed investigations. | Parser failure regressions and scanner/investigation suites. |
| P1 | Failed, queued or cancelled tool jobs could satisfy agent success checks if their response omitted an `error` field. | Explicit pending and unsuccessful states/statuses cannot count as successful tool outcomes. | State/status regression table covering both response forms. |
| P1 | Agent `tool_contains` checked the command-start acknowledgement instead of the resolved process result. Command metadata could also match the requested output without printing it. | Checks use completed output and structured evidence; command invocation text cannot substitute for actual stdout. | Actual subprocess positive and negative checks. |
| P1 | A provider failure or exhausted agent run could leave its asynchronous child commands running. | Failed, paused and attention-required runs stop and await their owned command collectors, retaining their captured evidence. Other conversations' commands are not stopped. | Real `sleep` subprocess with a controlled provider disconnect. |
| P1 | Timeout cleanup checked only the command leader. Background descendants could survive its exit, including after a command appeared completed. | Stop/timeout kills the owned process group even after the leader exits. Collector completion also terminates remaining group members. Persistent services should use tracked foreground jobs. | Reproduced a surviving `sleep` before the fix; actual timeout and redirected-background subprocess regressions now pass. |
| P1 | A command could launch in a changed project after action review. | Project identity/root and command capacity are checked again immediately after review. | Review callback changes the root; test asserts no process or artifact was created. |
| P2 | Polling could observe terminal process state before evidence postprocessing and cleanup finished. A finalizer exception was not a usable tool failure. | Public reads remain running until finalization settles; finalizer failures appear as failed results with an explicit error. | Real subprocess with a held finalizer; failing finalizer regression. |
| P2 | Agent resume could fall back to another active conversation if its retained conversation was missing. | Resume requires the original conversation and matching project before calling the model or changing execution context. | Missing retained conversation regression; existing resume/isolation suite. |
| P2 | Queueing and cancelling pending work were blocked by the global idle check while an agent was running. | Queue operations use frozen saved profiles and remain available during a run; cancellation publishes the new state immediately. | Active-run queue/cancel regression; existing durable priority/retry checks. |
| P2 | A stale run detail button could stop a different current run. | Agent/workflow stop requests carry the selected identity, reject terminal runs and route workflow children through their parent. | Stale identity cancellation regression; existing workflow cancellation checks. |
| P2 | Agent, workflow and schedule editors closed and displayed optimistic changes before the engine accepted a save. | Editors close only after acknowledged saves, remain open with visible errors on failure, and prevent duplicate saves. Archive and schedule state follow engine acknowledgements. | Installed agent editor: invalid scope rejected with draft retained; corrected save acknowledged; acceptance profile archived. Workflow/schedule rejection paths share the acknowledgement wrapper but were not separately exercised interactively. |
| P3 | Failed live guidance submissions cleared the user's text. | Guidance clears only after acknowledgement and only if the user has not changed it during submission. | Native build and source review; no forced GUI transport failure. |
| P3 | An operation event could clear the busy indicator while a workflow was still active. | Both state and operation events include active workflows when determining busy state. | Native build and workflow regression coverage. |
| P3 | A one-unit output page could split an emoji and return no text at the same offset indefinitely. | Pages advance over a complete Unicode character; offsets inside surrogate pairs fail clearly. | Actual emoji subprocess with one-unit pagination and invalid-offset regression. |
| P3 | Activity history could label queued, paused, interrupted or attention-required tool jobs as completed. | The production projection preserves pending and unsuccessful job status, including status-based running/stopped results. | Native activity regression mode checks job labels, interrupted actions, error exits, stable identities and overlapping Unicode output; added to GitHub CI. |

## Reproducing the checks

From the repository root:

```sh
PYTHONPATH=native/engine:native/tests native/.venv/bin/python -m unittest discover -s native/tests -v
cd native
swift build --build-system native --product WixalNative
swift run --build-system native ActivityAcceptance --self-test
swift run --build-system native MarkdownAcceptance
cd ..
native/.venv/bin/python native/scripts/activity-workload.py --binary native/.build/debug/ActivityAcceptance
```

`test_runtime_gaps.py` owns the new regressions. Its Nmap integration check needs Nmap on `PATH`; otherwise that one case is explicitly skipped. The existing GitHub workflow installs Nmap before running the full suite. This Swift package uses acceptance executables rather than a Swift test target.

Without `--self-test`, the activity acceptance executable reads a JSON transcript from stdin. The workload script supplies actual saved transcripts and checks stable IDs and exact evidence preservation without emitting transcript content. Empty stdin is not a valid check.

To repeat the bounded model/network check, choose a fresh output directory:

```sh
native/.venv/bin/python native/scripts/network-chat-acceptance.py --app /Applications/Wixal.app --output artifacts/native/network-chat-new-run
```

This creates two ephemeral owned loopback listeners, approves only their exact Nmap ports/profile, records real model decisions and scan results through production JSON IPC, and retains every attempt. Review final prose as well as automated assertions. The default three attempts provide regression evidence rather than a broad model success-rate claim.

The packaged and installed checks, exact counts, immutable bundle identity and hosted CI result are recorded below after validation. A regression with scripted model decisions verifies controller behavior; it does not establish real-model reliability. Earlier failed model evaluations remain retained under their original helper identities in the [managed tools continuation record](MANAGED_TOOLS_CONTINUATION_2026-10-10.md).

## Scope boundaries

The audit covers chat request/tool execution and context recovery, agent outcome verification, durable queues, frozen-profile resume, sequential and graph workflows, Cybersecurity investigation ownership and evidence, native editor state, and startup/package recovery. It does not claim an exhaustive absence of bugs.

Specialist Metasploit, ZAP and mitmproxy installations still need their own bounded execution contracts and service configuration; catalogue installation alone does not enable arbitrary autonomous use. Remote always-on hosting, messaging gateways and broad service/model certification are separate product decisions. The implemented local queues, workflows, adapters and verification are exercised within the available local runtime.

## Validation record

The final local native build is installed at `/Applications/Wixal.app`, with an immutable copy at `release/native/gap-audit-installed-20261010/Wixal.app`. The canonical `release/native/Wixal.app` matches it. The previous installed bundle is retained in the Wixal Release Backups folder.

| Evidence class | Actual result |
| --- | --- |
| Full Python suite | **292 passed** in 115.556 seconds, including **15 new runtime regression tests**. |
| Native build/package | SwiftPM native production build and frozen helper package completed; ad-hoc signature verified with deep/strict checking. |
| Activity projection | **15 checks passed** using the production projector, plus **30 replays** of the longest real saved transcript across five saved conversations; tool evidence preserved exactly. |
| Markdown | **5 production parser checks passed**. |
| Installed startup | **5/5 passed**: animated 2.253 s, animation off 0.424 s, reduced motion 0.431 s, held database lock 3.524 s, failed database recovery 2.218 s. Splash precedes engine start and workspace release waits for reveal/handshake or recovery. |
| Installed real-model network check | `gpt-oss:20b`: **3/3 passed**, two owned ephemeral listeners, actual Nmap, production JSON IPC. Both ports appeared open in independent listener/scanner evidence and in every final model answer. All three final answers reviewed for contradictions. |
| Installed real-model agent checks | **3/3 passed**: frozen read-only source review, reviewed scratch JSON artifact with readback, and a frozen background source-review routine. Isolated storage; no system LaunchAgent registered by this suite. |
| Installed native UI | Rejected agent save retained its editor/error/draft; correcting it saved successfully and closed the editor. Acceptance profile archived. Five managed tools remained Ready; Nmap 7.991 verified through the installed Tools view. |
| Source/install identity | **123 source files matched** the embedded manifest; **542 installed payload files matched** the immutable package. |

Final installed identity:

```text
helper SHA-256:          e86ff0a47098e4b3252d65cf85753e4429ce20ce63a74262d94b107e4e497f4c
native executable:      7c847624d0cdac36a9d021b89d813291f0f7199975a55d6ca7ff97aec2c54a96
source manifest:        9cccf17db96141ea9bd7a3bc38ba38c4e07ddb943179de62fa624a93deeb26f5
```

Local raw evidence is under `artifacts/native/gap-audit-20261010/`: `verification.json`, `python-tests-final.log`, `package-final.log`, `installed-startup/report.json`, `installed-network-real-model/report.json`, `installed-agents-real-model/results.json` and their complete transcripts. These raw local records are not uploaded as public diagnostics.

Failed trials are retained. The earlier general-chat run on helper `f71895f1371776c0d8d1a28487954b3fc05bc79a41f277be886217892e214ff2` passed **3/4**: its independent verification generated a comparison against the wrong JSON field. The actual report artifact was correct; the generated verification command failed and the controller correctly reported `needs_attention`. This is a remaining model-reliability limit, not a passing general-chat benchmark. That earlier helper's three Nmap attempts passed too; the three installed attempts above are separate, bound to the final helper. The pre-fix descendant leak and subsequent macOS duplicate-cleanup failure are also retained alongside the final passing suite.

GitHub's Native alpha checks now run the full Python suite, native build, Markdown acceptance and the new activity regression mode. The final hosted run is linked in the completion message; local checks do not substitute for that hosted result. Release qualification, notarization, broad model certification and public catalogue promotion are not implied by this audit.
