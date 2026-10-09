# Optional community reporting

Implemented local preparation:

- Per-report opt-in, unchecked by default. No automatic uploads, future-report consent or agent execution.
- Local AI sees sanitized user descriptions, at most 160 current-conversation diagnostic events, and optional sanitized tool error strings. It receives no raw conversation, tool argument values, images, browser contents, account data or saved memory. No model tools are provided.
- Deterministic detection removes known account identities and workspace/home paths, credential patterns, private keys, provider tokens, JWTs, UUIDs, email addresses, URLs, local file paths, IPv4 addresses and common phone formats. Original cross-event identifiers are replaced with per-report aliases. Generated output is sanitized again.
- Review shows title, full body, embedded evidence, local model identity and detected-redaction counts. Draft can be copied or saved. Incomplete/failed model output produces an explicitly labelled evidence-template report, rather than an invented AI result. The screen explicitly says nothing has been uploaded.
- Automatic detection cannot recognize all personal facts in free text. Do not claim exhaustive removal. Public review remains necessary; unrecognized medical, financial or identifying statements may survive pattern detection.

Verified:

- Ten regression tests passed across privacy, consent, existing diagnostic export and Settings.
- Native debug build passed using the repository's native SwiftPM build system. Default build system requires unavailable Metal compiler and was not used for final verification.
- Actual gpt-oss:20b drafted from the saved incident's six tool-result events, including the failed browser_search and corrected web_search. A test email and credential value were removed. No upload was performed. See artifacts/native/community-report-real-result.json.

Implementation continuation, 10 October 2026:

Contributor GitHub OAuth Device Flow and in-app issue submission are now wired through manual IPC and the full-report review screen. The contributor signs in through their own GitHub account. The implementation checks the exact reviewed draft digest, requires a fresh public-submission confirmation, uses the fixed issue destination, and prevents duplicate or automatic retry after an uncertain outcome. Tokens remain in memory. Six protocol/policy tests passed; these are controlled fixtures, not live GitHub authorization evidence. The registered public client ID is still awaiting the owner, so the installed build reports sign-in as unconfigured. See [reporting setup](GITHUB_REPORTING_SETUP.md).

A bug issue is the intake record. The investigation agent can later produce a linked fix PR after reproduction and validation. Selecting reporting opt-in must not silently grant local code-editing, repository-write, issue-triggered execution or merge authority.

Installed-app verification caught an incomplete model stream, which is now covered by a regression test and a labelled fallback. Original local-AI success and installed UI behavior are separate evidence classes.
