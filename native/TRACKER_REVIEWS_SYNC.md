# Memory reviews, recurring schedules and workspace sync

Updated 2026-10-07. Implemented source changes and engine checks below. Final Swift build, installed visual acceptance and packaged checks belong to the main everyday-workflow pass.

| Work | Implementation | Verification and remaining work |
| --- | --- | --- |
| Memory review clarity | Pending reviews appear before saved-note/settings controls; current and proposed notes are labelled; original conversation quote and source navigation are exposed; Replace, Combine and Save separately explain their effects. Recall and indexing settings are collapsible. | 20 memory quality/review tests passed using native/.venv. Added stale-correction refusal that retains pending evidence and Combine persistence with source IDs across restart. Final installed drawer visual/keyboard acceptance still required. |
| Schedule visibility | Each real persisted row shows project, saved model, cadence, next due date, enabled state, missed-interval policy, awake/background availability, last result/time and review/error reason. Open last run navigates through the task's project and session. Controls stack when space is limited. | Existing scheduling checks remain; final installed row/navigation acceptance still required. Sleeping-Mac wake is not implemented by this UI change. |
| Readable sync review | Conflicts expose actual local and incoming records, device IDs and saved timestamps when recorded. Note text, conversation messages and project memory settings render as readable content. Raw JSON is expandable. Buttons explain consequences and disable when local content changed since detection. | Six sync tests passed. Added immutable snapshots, stale refusal/refresh, restart persistence and 500-note encrypted roundtrip with 20 divergent resolutions. Actual delivery between two Macs is unverified. |
| Keep-local conflict lifecycle | Persist a reviewed incoming/local digest pair per device so an unchanged incoming version cannot immediately reopen a conflict after Keep local. A new local or incoming change still requires review. | Regression test repeats sync after Keep local and restart, then edits incoming content and verifies a new conflict. |
| Memory workload scale | Expanded benchmark measures full state save, changed save, index/retrieval, close/reopen and 768-dimensional production semantic scoring at 600, 6,000 and 30,000 passages. Assertions check source scope, changed-row count, persistence and stale-vector exclusion. | artifacts/native/memory-scale.json passed. At 30,000 passages / 20.9 MB persisted JSON: save 0.196 s, lexical recall 0.036 s, reopen 0.183 s; semantic scoring 3.785 s. Histories/vectors are generated workload fixtures in temporary storage, not real-model reliability evidence. Full embedding inference over 30,000 everyday passages remains unverified; packaged actual embedding acceptance is a separate main-pass check. |

Commands completed:

- `native/.venv/bin/python -m unittest discover -s native/tests -p test_sync.py` (6 tests).
- `native/.venv/bin/python -m unittest discover -s native/tests -p 'test_memory*.py'` (20 tests).
- `native/.venv/bin/python native/scripts/memory-scale.py` (all three sizes and correctness assertions).
- `git diff --check` (passed when run).

Environment detail: system Python had no cryptography dependency and the first sync test attempt failed before exercise. The project native/.venv has the required production dependencies and all sync cases were rerun successfully there. No dependency installation or user workspace data insertion was needed.

Open acceptance items: packaged visuals in compact layouts/themes/larger text, full keyboard/VoiceOver review controls, schedule last-run navigation in installed app, real two-Mac shared-folder transport, and full live semantic inference scale. No claim of these being complete is made by source or generated-workload checks.
