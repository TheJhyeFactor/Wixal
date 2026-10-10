# Mac memory and workflow recovery completion — 11 October 2026

This follow-up to PR #33 addresses issues #8 and #20. The scope is the existing native Mac app, using isolated workspaces and the existing local `gpt-oss:20b` model. Expansion choices and the other backlog issues remain separate.

## Correctness fixes

Native backups now include global notes and the forgotten/superseded source markers. Restore retains project/global scope, ownership, provenance, correction revisions and merged note identities. Incoming exclusions are combined with local exclusions before restoring records, so an older backup cannot revive a locally forgotten note. Import remains transactional and does not import account credentials or grant tool authority.

An engine restart now marks active parent workflows and stages interrupted while retaining completed stages. Sequential stages save their task identity before execution. Graph branches save child/task identities and mirror checkpoints to the parent before tool effects or review. Retry history retains failed attempts. Recovery requests an explicit review for uncertain effects, including a command whose start call finished while its command handle remains running. Declining pauses recovery; stopping while review is pending targets the parent workflow.

A retry performs fresh prerequisite reads. Historical failed reads remain in the audit record rather than being supplied as current observations. Retained effect checkpoints remain in recovery context. JSON verification rejects self-comparison and invalid source paths before adding dynamic criteria, allowing a corrected independent verification to succeed while real source mismatches still fail.

## Installed identity

The development app is `/Applications/Wixal Recovery Final.app`, frozen from production source `f74a3a9`. Later test/document commits do not change packaged production source. All 542 installed file hashes match the staged app; all 125 source-manifest entries match that commit and the current production files. Strict recursive signature verification passed with an ad-hoc development signature.

- Helper SHA-256: `47c188c5a89533cbffb20452f44955e7b1aaae64174fb8f5453936714fcae5ad`.
- Source manifest SHA-256: `179ab89dfed7ebb7deffd93f3a4bcb2c285af88db34043d71f96757f91d73476`.
- Tool trust manifest SHA-256: `41161c9c2cf05df2e363862e779fa94fad520cf649cd0834e4767917022bf10b`.
- Model: existing `gpt-oss:20b`, digest `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`, context 8192.

## Acceptance methods and boundaries

`data-recovery-completion.py` exercises two projects, 24 initial notes and six actual model file reads across three restart cycles. It independently compares in-memory record arrays to SQLite, checks corrected/forgotten project notes and a global note, kills the installed helper while a separate SQLite lock blocks a write, then kills it after an acknowledged commit. A real SQLite abort trigger rejects a populated restore and checks both memory and disk rollback. Successful restore then checks exact content, revisions, exclusions, duplicate import, restart and unchanged backup hash.

Six additional controlled source faults terminate child processes inside the actual Store/import SQLite virtual machine, at callbacks 1, 5 and 10 for both save and import. These use production SQL and independent prior-record/integrity checks. They are source fault injection, not installed-helper or physical power-loss evidence.

`workflow-completion-acceptance.py` runs a six-stage graph with parallel branches, dependencies, an initially missing prerequisite and an isolated JSON writer. The missing prerequisite blocks downstream work; repairing it and resuming preserves the completed branch and the failed attempt. Declining final-stage review pauses the workflow, and a helper restart preserves those completed tasks. The writer must use an independently supplied, hash-checked oracle. Only the requested summary may change, and a separate reviewed merge applies it to the original project.

A second real-model workflow starts a command that appends and fsyncs an independent effect ledger. The harness kills the installed helper while that command is active. Recovery retains the interrupted task, decline causes no execution, and approved recovery must read the ledger without issuing another command or write. The ledger must contain exactly one effect, and the completed prerequisite task must remain unchanged.

Source regressions separately cover pre-effect checkpoint persistence during pending action review, stopping during recovery review, running command handles, interrupted parent/stage statuses, attempt retention, failed restore rollback, stale-backup forgetting, owner isolation and corrected independent JSON verification. Populated legacy migration uses production creation/import APIs against a declared fixture; generated history scale evidence remains the earlier PR #33 record.

These are bounded single-Mac scenarios. Six conversation turns do not establish endurance over days. Lexical recall is qualified; no embedding model is selected and semantic quality is not claimed. Process termination and SQLite faults do not simulate physical power loss. This is not clean-machine, OS/hardware matrix, Developer ID, notarisation, public release, general model-reliability or full desktop/VoiceOver qualification.

## Retained failures

Workflow runs 1 and 2 exposed stale failed-read context on recovery. Run 3 exposed invalid model verification behavior before the independent oracle was supplied. Run 4 passed on the earlier `48671c8` package. Run 5 on `713d2b7` exposed self-source verification permanently adding an impossible criterion; this led to the `f74a3a9` fix and its regression. All raw attempts remain separate and immutable. The final run, rather than an earlier success, determines the final package result.

Raw local evidence is retained under `artifacts/native/mac-completion/` in the primary checkout. A compact hash index is committed alongside this report; raw model transcripts and disposable workspace databases remain local.

## Final results and closure mapping

The final installed data run (`data-run-5`) passed all **13 cases**, including **six real model turns**. The final installed workflow run (`workflow-run-6`) passed all **five cases**. Both reports bind the exact helper and source-manifest hashes above. The fresh populated migration fixture passed separately. The final engine regression suite passed **359 tests**. An earlier full run caught an old test expecting a failed-result dictionary for invalid JSON source paths; that test now correctly checks the rejected-input contract. The corrected full suite passed; the prior failed log remains retained locally.

| Issue criterion | Measured evidence |
| --- | --- |
| #20: no lost, duplicated or cross-project data in supported scenarios | Exact record-array comparisons across repeated sessions/restarts and populated restore; duplicate-import idempotence; project/global scope and ownership regressions. |
| #20: failed/interrupted writes and migration recover safely | Installed kill before commit and after acknowledged commit; installed restore SQLite abort/rollback; six production-source SQLite interruption points; populated supported migration fixture. |
| #20: correction/forgetting and recall respect scope after restart | Restored revisions/provenance/exclusions, two-project correction/forgetting/recall, global note, stale-import exclusion and restart checks. Semantic embedding inference remains outside this lexical configuration. |
| #8: invalid prerequisites/artifacts block dependent steps | Actual missing prerequisite prevents dependent join/artifact; failed attempt retained; independent JSON oracle, exact changed-file list and reviewed merge. |
| #8: completed effects are not repeated; uncertain effects remain reviewable | Completed branch task IDs retained across retries/restart; installed helper killed during fsynced command effect; declined recovery performs no replay; approved recovery reads ledger and issues no effect command/write. Pending-review cancellation/checkpoint source regressions also pass. |
| #8: longer installed workflows retain branch/status/evidence | Six-stage real-model dependency graph, isolated writer and merge, retained failed child/task identities, paused review restart and interrupted effect recovery with complete attempt history. |

These observations satisfy #8 and #20 for the explicitly supported scenarios above. They do not close #6 (general model/tool qualification), #9 (mixed foreground/background controls), #11 (full accessibility/desktop qualification) or the release/platform issues. The other 24 backlog issues remain open.

Reproduction: run the two scripts with `--app '/Applications/Wixal Recovery Final.app' --output <new disposable directory>`. The output directory must not already exist. These use the existing local model endpoint and never overwrite a prior run. See [compact evidence index](MAC_RECOVERY_EVIDENCE_2026-10-11.json) for case names, immutable raw report hashes and acceptance script identities.
