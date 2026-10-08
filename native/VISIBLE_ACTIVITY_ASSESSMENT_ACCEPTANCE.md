# Visible activity and assessment UI acceptance

Run date: 2026-10-07 (Australia/Sydney)

## Build and target identity

- Installed app: `/Users/jhye/Applications/Wixal Native.app`
- App executable SHA-256: `1182a0daa5eb359b32cd56c26095ad2f195ad3c897b5f75f017c93fbdb31db46`
- Packaged helper SHA-256: `ca4388bed45d01c4cc1ca0b746b20a82558e8a984853432fc4a731fc43522c4e`
- Reported UI version: `0.7.8`
- No source or installed-app code was changed in this workstream.

## What happened

The installed app was opened twice because the native app reads `WIXAL_NATIVE_DATA` only when its process starts. The second launch (PID 35080; helper PID 35082) correctly used `/Users/jhye/Library/Application Support/Wixal Workflow UI Records/engine.sock`, confirmed with `lsof`. That isolated store had 22 saved sessions and no tool messages.

The CUA binding by app path did **not** select that second process. It selected the already-running PID 34847 (helper PID 34884) instead. Its active project was the existing disposable `wixal-dock-live-nc8rbdsd` fixture under `/private/var/folders/.../T/wixal-dock-live-nc8rbdsd`. The project path and the resulting file error exposed the mismatch. No UI action was taken after that identity issue was recognized.

Before recognizing the mismatch, one read-only chat was submitted in that temporary fixture:

> Use a read-only file tool to read native/README.md in this project. Then list only its section headings in a concise answer.

The actual `gpt-oss:20b` response attempted `list_files(directory=native)`, `read_file(path=native/README.md)`, `list_files(directory=native)`, and `read_file(path=README.md)`. The final two reads failed because the temporary fixture has no `native/README.md` or top-level `README.md`. The transcript remains in temporary session `a1a80180-f4a0-499a-9a57-36cbbb8360e5` (eight messages); no file was written. The UI displayed the request as running with four milestones, then showed the failed read result and enabled “Replay run.” This is evidence of the visible failure state and replay availability only; replay itself was not run.

The composer initially displayed “Approved all.” It was changed to “Review each action.” After checking PID 34884’s exact socket and confirming its active project was still the disposable `wixal-dock-live` fixture, the project’s `approvalMode` was restored through that socket to `bypass` (“Approved all”). The final IPC hello confirmed the restored value. The accidentally launched isolated app/helper/supervisor (PIDs 35080/35082/35087) were terminated. The pre-existing app/helper (34847/34884) was left running.

## Acceptance result

**Not accepted.** The process ambiguity invalidated the intended installed-app run, and the read-only prompt exercised only a failure case in the other test process. This run did not verify scroll-up behavior during streaming, navigation away and back with a selected activity event, replay completion or replay Stop, review versus approval state, user Stop during a response, or the assessment Stop button during loopback requests/evidence save. No defect was fixed from this run, and no success is claimed for those flows.

The existing production IPC workload at `native/scripts/assessment-workload.py` covers persisted partial assessment results and real loopback requests, but explicitly excludes the desktop Stop button. It does not close this UI acceptance gap.

## Safe next attempt

Do not bind by bundle path while two `app.wixal.native.preview` processes are running. Use a uniquely identifiable acceptance app bundle/process, or coordinate a single-app UI run after the shared app is no longer needed. Before typing, verify the visible project name and query the same process-owned socket to confirm the active acceptance workspace. Use only a disposable data directory and read-only project content. Then record scroll position before and during a deliberately long real stream, selected milestone across conversation navigation, full Replay/Stop replay behavior, and Stop during a throttled loopback assessment and report-save phase. Retain any failed run record without replacing earlier evidence.

## Cleanup after report

The test transcript had landed in the default native SQLite store despite its project pointing at a disposable `wixal-dock-live` directory. To remove it from the active conversation list without permanently deleting evidence, I archived only session `a1a80180-f4a0-499a-9a57-36cbbb8360e5` using the normal reversible `session-archive` action. Its eight messages remain recoverable in Archived chats. The prior approval value is `bypass` (UI label “Approved all”). No files or other sessions were changed.

## Re-run against the rebuilt isolated app (2026-10-07)

Root rebuilt and installed the development package before this run. Installed app executable SHA-256: `c32cdc95229ac5401d7b2da7ac40119343d93ef6699b3bea9610bc28c41f32f5`; packaged engine helper SHA-256: `71b39c782f6f820e152e76c3767aad930df1d4991f0a7da38903345e74905324`. The app reported 0.7.8. One native PID (37083) and its engine PID (37086) were active; engine args named `/Users/jhye/Library/Application Support/Wixal Workflow UI Records`, whose `engine.sock` was owned by that engine. The CUA window showed project Wixal. No default native store was used. No source changes were made.

### Visible chat/activity checks

- Three real Gemma3:1b generations ran in the isolated workspace (software-change plan, cooking plan, plant-care routine; 688, 498, and 511 output tokens). The third stream was observed while scrolling up: earlier response content stayed in the viewport as the new answer streamed into the activity dock. The older-history position remained selected after the stream. **Scroll hold during streaming passed.**
- A selected Request 1 event was retained after opening a different saved conversation and returning. The dock restored Request 1 and its matching prompt/output. **Navigation and event selection restoration passed.**
- Replay run was invoked; its control changed to Stop replay and then back to Replay run after replaying the three milestones. **Replay completion and visible Stop replay state passed.** Clicking Stop replay was not exercised.
- Jump to latest was absent on the first scroll-up observation but appeared after the later activity assessment shifted the viewport. The affordance is therefore present; no claim about its exact timing/visibility transition is made.
- These generations used a conversation-only model. Approval/tool execution states and a model-generated failed tool were not exercised in this visible pass.

### Actual loopback assessment Stop

Started a local-only fixture at `http://127.0.0.1:8765/` with twelve linked pages and a 600ms response delay. Entered it in the installed Tools drawer, chose Website assessment, reviewed the request in the app’s Review website assessment sheet, and approved. The running UI displayed `Assessment progress`, `Running`, and an enabled `Stop assessment` button. Clicked that actual Stop assessment control while the 12-page request was in progress. The network run completed before the click took effect: the fixture logged `/` through `/11`; the app reported 12 GET requests, zero request errors, and generated the full assessment output. It then showed the evidence-save review sheet, which was declined. No report files were saved. Recent results displayed `Website Assess Completed`; **assessment Stop during active requests did not produce a cancelled/partial result, so this acceptance fails**. The tool run itself and output were persisted in the isolated workspace. The server was stopped; its shutdown produced only the expected asyncio cancellation traceback.

The UI's `Stop assessment` action was visible and clicked, but apparently did not interrupt this in-flight manual tool operation before it completed. Need inspect stop/cancellation propagation; underlying cancellation/persisted partial-result workload tests remain separate and do not prove this button works. Last app state was one Wixal Native window, one app PID 37083, helper PID 37086 with the isolated Workflow UI Records data path and its socket; store's active assessment result showed completed, not cancelled. App was left open because closing it while the evidence-save sheet was active was not safe to attempt within this run window; tell root to close that exact app process or continue only after reviewing this state.

### Outcome

Scroll-up hold, navigation restoration and complete replay are now accepted. Assessment Stop remains unresolved: action appeared to be accepted but did not cancel the run. Activity approval/running/stopped/failed differentiation, stopping Replay itself, a failed agent tool sequence, and proving evidence-preserving partial UI display remain unverified. The assessment produced a complete report in the review sheet but no saved project files.

## Slow-request Stop retest (2026-10-07)

Reopened the same installed app against the isolated `Wixal Workflow UI Records` store only. App SHA-256 remained `c32cdc95229ac5401d7b2da7ac40119343d93ef6699b3bea9610bc28c41f32f5`; sole native app PID 37873, helper PID 37876, helper args explicitly contained `--data /Users/jhye/Library/Application Support/Wixal Workflow UI Records`, and it owned that store's `engine.sock`. UI showed `wixal / Wixal`. No source edits.

Started a loopback-only HTTP fixture on `127.0.0.1:8765`, with 2-second response delay per page and a 12-page chain. Started the installed website assessment, reviewed its exact loopback URL and 12-page limit, and approved. While it was running, the Tools drawer exposed enabled `Stop assessment`. Clicked that button while fixture logging showed `/5` in flight (five earlier pages had completed; click came roughly 1.4 seconds into its 2-second wait). The callback did not cancel the request: fixture next logged `/5` completed and then `/6` through `/11`; total assessment duration was 26.24 seconds, 12 GETs, zero request errors. The app showed the second `Review save website evidence` sheet and its generated 12-page report. I declined saving, so no report was written.

Recent results displayed `Website Assess Completed`, not `Partial result · Cancelled`; the result included the full report rather than preserved partial cases, and evidence-save review was offered. **This rules out a simple click-too-late explanation. The installed UI Stop path does not cancel the active website assessment.** The visible click was made during an in-flight slow request, but cancellation was not propagated to the running assessment. No completed-check partial result was shown. Fixture was stopped; expected asyncio server shutdown traceback only. The exact isolated app PID 37873 was terminated after capturing state; its helper and socket exited.

## Cancellation fix and current installed retest status (2026-10-07)

The source path had a fragile ownership check: `assessment-cancel` cancelled the assessment only when its dedicated task was still identical to the engine's shared `active` operation pointer. The UI also fired cancellation as an unobserved one-way action, so it gave no immediate “stopping” feedback or visible error if the engine did not acknowledge it.

The fix now targets the dedicated assessment task directly and leaves unrelated work untouched. The engine reports whether an assessment was actually cancelled. The UI changes the button to `Stopping…`, disables repeated clicks while it waits for acknowledgement, and displays an actionable error if the engine cannot confirm cancellation. After cancellation the existing Recent results card shows the preserved partial/cancelled result and completed cases.

A new IPC-level workload (`native/tests/test_assessment_cancel_ipc.py`) sends the same production `assessment-cancel` method while the assessment is inside a 1.5-second loopback response. It verifies that the active HTTP request closes, no later pages are fetched, completed cases persist as a cancelled partial result, no report file is delivered, and unrelated engine work is not cancelled. It passed alongside all existing cancellation tests.

The fix was built and installed. New installed executable SHA-256: `34996b6c3f3a2c5f62fe70453c549c63b505da5b567c7914952f8e46e267343c`; helper SHA-256: `7755a37f0a79718c818bec052010862cac3b11cc78cbfbf4382ff426ba438fb2`. Full Python regressions passed 108/108; the native Swift release build succeeded using SwiftPM's native build system.

The final visible retest is **blocked**, not passed: the exact new app and helper hashes launched with the isolated `Wixal Workflow UI Records` data path and the engine socket existed, but macOS was locked and CUA could not inspect or operate the UI. The exact isolated app PID and helper were terminated. No assessment was started and no data changed. The two previous UI failures remain valid evidence against the older `c32cdc…` binary. Re-run the focused slow loopback Stop test after the desktop is unlocked before claiming visible Stop acceptance.


## Updated installed UI: visible Stop passed, 8 October 2026

The approved redesign was installed and visibly tested while unlocked. Exact executable `5acfd34cbf6da94825ded2a121d44bc5462c8ace045b4c4c74210f57432c58ec` and helper `dc60972e41fec230e0483cf7b824135e6ebd5ea55664e4211b44bf02e14749a9` passed the final 12-page slow loopback Stop workflow. The UI returned to idle, displayed Partial result · Cancelled with 12 completed checks, and retained that evidence after quit/reopen. Final request log contains only `/` and `/1`; no later requests or report delivery occurred. Earlier redesigned installed builds also passed Stop during a held response. This supersedes the pending visible retest, while preserving preceding failure and locked-desktop records as historical evidence. See UI_UX_REDESIGN_ACCEPTANCE_2026-10-08.md and artifacts/native/redesign/acceptance.json for exact scope and screenshots.
