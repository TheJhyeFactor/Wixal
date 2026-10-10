# Mixed agent controls and recovery — 11 October 2026

This completes the tested mixed-workload criteria in issue #9. Four reproduced defects were fixed: accepted late guidance was skipped on a final model answer; active queue jobs lacked a durable task link; unsent guidance disappeared when the run view was recreated; and selected-run Stop rejected tasks while outcome verification was still executing.

## Resulting behavior

- Guidance accepted during streaming or outcome verification receives a subsequent model turn before completion. The existing turn budget still bounds execution.
- Queued jobs and their actual tasks are linked before execution. A selected stop retains that identity and interruption history; an abrupt helper restart preserves the link without automatically retrying the job.
- Guidance drafts and outstanding acknowledgements belong to their owner/run, independently of view lifetime. Unsent text is atomically retained locally with user-only file permissions and restored on relaunch. Relaunch never automatically resubmits a request. Unreadable draft files are preserved and the error is visible.
- Runs stay active while controller verification waits on commands or evidence. Selected Stop and guidance continue to target the actual executing run. Final responses without independent criteria retain the existing “Finished · unverified” presentation.

## Completion criteria and evidence

| Issue #9 criterion | Measured result |
| --- | --- |
| Stop/guidance target the selected run; stale controls have no effect | Installed IPC rejected controls for an earlier task while another project ran. Actual pending action approvals became invalid after stop. Selected stop also interrupted a real verification command and retained its interrupted checkpoint. Production regressions separately cover guidance during verification. |
| Cancelled work stays cancelled after restart | Twelve cross-project cancellations remained cancelled through graceful and abrupt restart in the mixed suite. Twenty more remained cancelled in the separate real-model recovery workload. Desktop queue/cancel controls were also exercised while another run and an unsent draft remained active. |
| Resume restores original project/conversation and retained configuration | The mixed suite edited the saved profile, navigated to another project/conversation, restarted twice, and resumed the original task. The task retained its ID, source project, conversation and frozen instructions; the unrelated selected context was restored afterward. |
| Pending edits and finalised output survive tested workloads | The installed Swift UI retained an unsent guidance draft through Runs → Workflows → Runs and quit/relaunch. Resuming restored the draft; submission cleared it only after acknowledgement. Independent saved requests contain the restored guidance before the visible final output. |

The controlled installed-helper suite passed **8/8** cases:

1. Late guidance, concurrent queue cancellations and restored selection.
2. Active queued-job stop, durable task identity and stale controls against a different project.
3. Graceful/abrupt restart, retained cancellations and original frozen-context resume.
4. Stop during provider preparation, without inference or an unrelated task link.
5. Stop at pending action review, no write effect and rejected stale approval.
6. Stop after a real command committed its independently observed single effect; restart retained its checkpoints and ledger.
7. Selected stop during a real outcome verification command; restart retained the interrupted verification checkpoint.
8. Abrupt active queued-request restart, retained task linkage and no automatic replay.

The controlled server supplies decisions and timing only. Production IPC, SQLite, process execution, review, cancellation and recovery are exercised. These results establish controls, not model reasoning quality.

## Validation and frozen package

| Check | Result |
| --- | --- |
| Full Python regression suite | **363 passed**; four new controller regressions cover late guidance, queued-task identity, stop during verification and guidance during verification. |
| Production Swift interaction state | **24 checks passed**, including owner/run isolation, retained acknowledgements and text-only relaunch restoration. |
| Production activity projection / Markdown | **29 / 5 checks passed**. |
| Native build and development packaging | Passed. |
| Installed controlled mixed-workload suite | **8/8 passed** on the frozen helper below. |
| Installed real `gpt-oss:20b` recovery workload | **8/8 passed** on the same frozen helper: actual reads in two projects, exact-record graceful/abrupt restart, corrected-memory isolation, interrupted active inference without replay and SQLite integrity. |
| Installed desktop | Final frozen package passed navigation, unsent draft, quit/relaunch, original-task resume, acknowledged submission and visible completion checks. The earlier desktop pass additionally exercised queue/cancel during an active run. |
| Source/install identity | All **126 source-manifest entries** match; **539 installed files** counted; deep/strict development signature verification passed. |

```text
helper SHA-256:          ec96412c542d9f3d349dca735f388398a03fb88943983678c42c54ab0a31a3e7
native executable:      a9db1775b1c91ae45b5174d3ede2bfb6e8362b5738bef152afa0fc1d589e4591
source manifest:        186ffc8a7ef68d4619c207abd432422ff1f869bfe0e49df56b6ff3d19e73ee3f
mixed acceptance script: 2f614c37decfec019e6e9a7f7b2262b2fbf8f7009368eeb350ef16c35af95502
```

Local retained evidence is under `artifacts/native/mac-backlog-20261011/`: `python-final.log`, `interactions.log`, `activity.log`, `markdown.log`, `frozen-installed-identity.json`, `mixed-qualified/results.json`, `real-recovery-frozen/results.json`, and `desktop-frozen/observations.json`. Earlier attempts, including the rejected invalid acceptance input, remain at distinct paths. Raw workspace data and transcripts are not published.

Reproduce the installed suites with a development app and fresh disposable output directories:

```sh
native/.venv/bin/python native/scripts/mixed-controls-acceptance.py \
  --app /path/to/development/Wixal.app --output /path/to/fresh/mixed-evidence
native/.venv/bin/python native/scripts/recovery-workload-acceptance.py \
  --helper /path/to/development/Wixal.app/Contents/Resources/engine/wixal-engine \
  --model gpt-oss:20b --output /path/to/fresh/recovery-evidence
native/.venv/bin/python native/scripts/agent-interaction-ui-fixture.py \
  --app /path/to/development/Wixal.app --output /path/to/fresh/desktop-evidence
```

Quit the fixture app, then repeat the desktop command with `--resume` to reuse its isolated workspace without reseeding it. The fixture copies only already-completed setup flags, and opens the app bundle through Launch Services. It does not accept legal terms, copy credentials or register a background scheduler.

## Remaining backlog boundaries

Issue #7 still requires sustained desktop conversations, larger output/context pressure and broader service-disconnect acceptance. Issue #11 still requires full keyboard, spoken VoiceOver, layout/theme and long-session qualification. This batch does not close either issue.

Issue #6 remains unqualified. Inspection of its retained failed prerequisite confirms that requested source-bound inspection was omitted after discovery despite two controller feedback turns; truthful corrected output did not satisfy the missing action. No new repeated-run model qualification is claimed by this controls work.

The production release remains unchanged. This is a separate local development package, with no Developer ID/notarisation or wider device support claim. Resource-dependent issues and proposal-first expansion remain open.
