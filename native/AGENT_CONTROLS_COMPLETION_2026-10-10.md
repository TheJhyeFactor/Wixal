# Agent controls, editing and activity completion — 10 October 2026

This closes the three follow-up areas from the [application gap audit](APPLICATION_GAP_AUDIT_2026-10-10.md): agent controls/recovery, acknowledged editing/guidance, and activity/output. The native app and its own engine remain the execution boundary. Release qualification is excluded.

## Completed behavior

| Area | Result |
| --- | --- |
| Queue and cancel | Saved profiles are frozen at queue time. Queueing and cancelling pending work remain available during an active run. Rejected queue requests retain their task sheet, error and brief; acknowledged requests close it. Start agent is disabled while another run is active. Cancellation is persisted and the cancelled job never executes. |
| Resume context | Resume requires the original conversation, workspace owner and available local project. The original project/conversation are selected before any conversation metadata is changed. Personal tasks stay personal even when a project is selected later. The user's previous project, conversation, model and mode are restored after execution. |
| Targeted control | Stop and guidance check the actual executing task identity, not only a persisted status. Stale records marked running cannot control a newer run. Workflow cancellation checks the active parent workflow; child stop requests must use that parent. |
| Editor acknowledgements | Agent, workflow and routine editors wait for the engine's response, block duplicate saves/dismissal while waiting, show rejected saves without losing the draft, and close on acknowledgement. Existing routine edits preserve their saved project instead of inheriting the current selection. |
| Guidance | Failed submission retains the text and shows its error beside the input. Success clears only the submitted, unchanged draft and removes its obsolete warning. Text edited while waiting, including text edited and then reverted, survives the earlier acknowledgement. Guidance state belongs to the selected run. |
| Activity | Queued, paused, interrupted, stopped, waiting and attention-required states remain visible even when they include an error explanation or termination exit code. Empty/null error fields do not turn a successful result into a failure. Retained checkpoint states remain visible without a final tool message. |
| Command output | Existing regressions verify that one-unit Unicode pages advance over an emoji, offsets inside a surrogate pair fail clearly, public reads remain running until evidence finalization settles, and finalizer errors become visible failures. |

The new context regressions reproduced four failures before the changes: unrelated conversation tagging on resume, a selected project leaking into a personal resume, a selected project leaking into a queued personal task, and a stale running record cancelling current execution. The original failing log is retained locally.

## Validation

| Evidence | Result |
| --- | --- |
| Full Python regression suite | **300 passed** in 117.942 seconds, including **8 new controls/recovery tests**. |
| Production activity projector | **29 checks passed**, including explanatory errors, termination exits, retained checkpoint states and Unicode output merging. |
| Production submission/guidance state | **16 checks passed** in the new `InteractionAcceptance` executable. These exercise duplicate requests, obsolete acknowledgements, rejection/correction and edits during pending guidance. |
| Markdown | **5 production parser checks passed**. |
| Real saved workload | **30 replays**, five saved conversations, 159 exact tool-evidence checks; longest transcript 71,830 bytes. This measures the actual saved workload, not synthetic large-chat or scrolling/accessibility coverage. |
| Final installed UI | Rejected and corrected saves exercised separately for agent, workflow and routine editors. Rejected guidance and queue briefs retained their drafts; accepted corrections cleared/closed appropriately. Queue/cancel remained usable while a run was active; Start agent was disabled. Selected stop/resume preserved the exact task, conversation and project IDs. The resumed task included accepted guidance and completed after the controlled response was released. |
| Final installed real model | `gpt-oss:20b`, **3/3 passed**: frozen source review using actual documentation, a reviewed scratch JSON artifact with readback, and a frozen background source-review routine. |
| Final installed startup | **5/5 passed**: animated, animation off, reduced motion, held database lock and failed-database recovery. Splash still precedes engine start; workspace release waits for reveal and handshake/recovery. |
| Source/install identity | **124 source files** matched the embedded source manifest, including the new interaction library; **542 installed payload files** matched the retained package. Deep/strict ad-hoc signature verification passed. |

The installed UI tests use the actual installed Swift app and frozen engine with isolated storage and a held local fixture response. They establish controller/UI behavior rather than real-model reasoning reliability. The separate three-case model suite uses the real local model. Neither suite accepts new legal terms, copies conversations/credentials into the UI fixture, or registers a system LaunchAgent. Completed setup flags alone are copied from an already configured workspace.

## Reproduce

From the repository root:

```sh
PYTHONPATH=native/engine:native/tests native/.venv/bin/python -m unittest discover -s native/tests -v
swift build --package-path native --build-system native --product WixalNative
swift run --package-path native --build-system native ActivityAcceptance --self-test
swift run --package-path native --build-system native InteractionAcceptance
swift run --package-path native --build-system native MarkdownAcceptance
native/.venv/bin/python native/scripts/activity-workload.py --binary native/.build/debug/ActivityAcceptance
```

The Swift package uses acceptance executables rather than a Swift test target. GitHub's Native alpha checks run the full Python suite, native build, Markdown, activity and interaction acceptance executables.

For manual UI acceptance, quit the normal app first, choose a fresh output directory and run:

```sh
native/.venv/bin/python native/scripts/agent-interaction-ui-fixture.py \
  --app /Applications/Wixal.app \
  --output artifacts/native/agent-ui-new-run
```

Open the saved workflow and routine: try a 101-character workflow/agent name or an invalid routine timezone, confirm the error/draft stays visible, then correct and save. Give the fixture agent a task; its model response waits while you try rejected/accepted guidance, rejected/accepted queue submissions and queue cancellation. Stop/resume from the run detail. Creating `release-model` in that isolated output directory releases the controlled model response. Quit the test app to stop the fixture, then open Wixal normally to return to the user's workspace. The fixture's default setup source must already contain completed setup; it refuses to fabricate acceptance.

## Retained build and evidence

The final local development app is `/Applications/Wixal.app`; `release/native/Wixal.app` matches it. The immutable evidence copy is `release/native/agent-controls-installed-20261010/Wixal.app`. Previous installed apps remain in Wixal Release Backups. Version remains **0.7.10-alpha.2**; the published alpha download is unchanged.

```text
helper SHA-256:        94e476b1be1de7b8656481dda9c74e273b85ef5fe3c60c06658b71be951d42a6
native executable:    d835496e9ac134d30d1d31268b8df5f40c8c9f1bfc6cb972348aeb9138b917a1
source manifest:      713e4506bdced4a436fb2d92744fe19892140147cde22ff152ad841aef1ecab0
```

Local evidence is under `artifacts/native/agent-controls-completion-20261010/`, including `verification.json`, `python-tests.log`, `activity.log`, `interactions.log`, `installed-ui-final/observations.json`, the fixture's actual model requests, `installed-real-model/results.json`, and `installed-startup/report.json`. The preliminary UI run is retained separately; the final UI run additionally checks the corrected obsolete-warning behavior. Private raw evidence is not published as diagnostics. The final hosted CI result is recorded alongside this evidence and linked in the completion message.
