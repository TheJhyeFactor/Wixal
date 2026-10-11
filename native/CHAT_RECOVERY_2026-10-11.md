# Chat history and uncertain-effect recovery — 11 October 2026

Issue #7's bounded installed recovery scenarios passed after fixing a reproduced first-retry defect. A Chat task with no attempt counter could resume its original execution request without recovery guidance. An installed real-model attempt proposed repeating a command after its durable effect had occurred and the helper was killed. Ordinary review prevented that initial replay; that protection could not be assumed under bypass or pre-approved policies.

The fix supplies bounded retained checkpoint evidence on the first retry, preserves each checkpoint's original project and conversation owner, and blocks replay of uncertain actions before review or execution. Command aliases and changed timeouts cannot bypass the recorded command identity. New actions outside the read-only tool set require a recovery review independently of ordinary pre-approval or global bypass. Background command and scanner handles remain uncertain until matching successful terminal evidence settles them. Arbitrary semantic equivalence between different commands is not inferred; changed actions still require recovery review.

## Exact installed identity

The final development app was **Wixal Recovery Verified**, built from source commit `003bf57`. Its installed helper and source manifest were frozen before acceptance:

| Identity | Value |
| --- | --- |
| Helper SHA-256 | `37e845ca1b70b275a86b9e0bf23d3ef8890e4411c4db48a3bb3ae32cf0256ed9` |
| Source manifest SHA-256 | `b94db7a4b4978c83979493c5d7eb1f76cea8b28f2918fe3acaf8440f1ef27fb0` |
| Source entries matching the checkout | 127 |
| Installed files matching the staged package | 542 |
| Strict package signature verification | Passed |
| Actual model | `gpt-oss:20b` |
| Model digest | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` |
| Requested context | 8,192 tokens |

The owned loopback fault proxy forwarded actual Ollama inference and cut actual unfinished streams. It did not invent model output or stop the shared model service. Proxy source SHA-256: `4516a79b77ec7d75943560c386316f7b02073db4ddb247da9fe290aa7ba85235`.

## Validation

| Check | Result |
| --- | --- |
| Full final-source Python regression suite | 379 passed |
| Focused recovery boundaries | 6 passed |
| Prior-source comparison for the first four boundaries | 3 failed, 1 passed; failures retained |
| Installed helper real-model recovery suite | 8/8 passed |
| Installed desktop recovery scenarios below | 6/6 passed |
| Source-head GitHub CI | [Passed](https://github.com/TheJhyeFactor/Wixal/actions/runs/38109908380) |

The eight helper checks include actual reads from two projects, corrected and forgotten memory retention, queued cancellation, graceful and abrupt exact-record restart, interrupted active inference without automatic replay, project isolation and independent SQLite integrity. They are helper IPC evidence; the six desktop checks independently exercise the native application.

1. **Summary stream disconnect:** an actual summary stream was cut before completion. The controller recorded the excerpt fallback reason, then actual inference read a fresh source file and returned independently matching HEAD/TAIL markers. The next-message draft survived generation. The original 52-message and 13-task prefixes remained exact.
2. **Main response disconnect:** after an actual successful summary, the main model stream was cut. The task failed with “Model response ended before completion,” no tool checkpoints or effects, no automatic retry, and the request returned to the composer.
3. **Native quit/relaunch:** exact messages and task records reopened, with next-message draft text and attachments unchanged. The draft save timestamp refreshed normally.
4. **Explicit failed-task retry:** the native task inbox showed the failure. “Inspect and continue” reused its task identity, opened a recovery conversation and completed fresh actual inference. The original long conversation and its draft remained intact.
5. **Durable effect and helper crash:** after an approved disposable Python command fsynced exactly one ledger marker, only the owned helper was killed. Its child process was reaped. The native disconnected state and Restart engine control recovered the same interrupted task and unfinished checkpoint without replay. The inbox displayed the interrupted work and retained evidence. Explicit inspection preserved original checkpoint ownership; a new script-inspection command required recovery review and ordinary command review. Two model proposals to rerun the original command with different timeouts were blocked before review or execution. Fresh reads showed one ledger marker. The original effect remained uncertain and the task visibly needed attention.
6. **Post-recovery navigation and relaunch:** the retained long conversation scrolled to earlier actual-model reads, navigation retained its draft, and native quit/relaunch preserved all messages, tasks, checkpoints, draft contents and the single ledger marker. The application reopened connected and usable.

The sustained conversation was imported from the genuine earlier #35 workload: 12 consecutive backend file-reading turns, 196,560 retained tool-output characters, model-generated summaries and a thirteenth installed-desktop turn. Those original turns remain evidence for their original helper, not freshly repeated turns on this helper. The final candidate independently tested exact retention plus the additional actual inference, disconnect and recovery cases above.

## Evidence limits and retained failures

The recovery model incorrectly inferred in its final prose that the killed command was still sleeping. Independent process evidence showed it had been reaped, no command completion was established, both replay proposals were blocked, and the task remained **Needs Attention**. This is a retained model interpretation failure, not a qualified model result. Issue #6 remains open; no evaluated-model status was added.

An earlier frozen helper reproduced the missing first-retry warning and proposed a duplicate effect; its ordinary approval was declined. Intermediate package identities and failed attempts remain retained and are not promoted by the final candidate's results. A transient CUA native-menu observation failure required restarting only the disposable native test app; the command palette subsequently opened the task inbox successfully. This is recorded separately from acceptance results.

Local raw records include `recovery-verified-desktop-results.json`, `recovery-verified-backend/results.json`, before/after SQLite snapshots, the fsynced ledger, interruption identity and proxy events. They contain disposable local paths and transcripts and remain private. No sleep/reboot, second physical Mac, spoken VoiceOver, remote account or production release qualification is claimed. The public release and unfinished design files are unchanged.
