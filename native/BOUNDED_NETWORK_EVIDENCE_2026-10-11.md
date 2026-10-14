# Bounded network evidence — 11 October 2026

This is a fresh candidate for issue #6 following the failed evidence-driven investigation candidate. Earlier failures remain immutable and do not qualify this build.

## Changes

Scanner tool results stay complete in stored history and checkpoints. Only outgoing model requests receive a compact projection: exact requested port ranges instead of expanded lists, explicit unknown examined counts, source IDs, hashes, whole endpoint records with omission counts, and saved-output reader handles. Output excerpts preserve actual text and provide UTF-16 pagination offsets; excerpt markers are never represented as scanner output. Normal tool authority and review remain unchanged.

Generic nested JSON shrinking previously exceeded its own allowance: the actual retained Qwen result still occupied 3,496 characters at a 400-character limit. The final fallback now obeys the bound and labels incomplete evidence. Scanner-specific fitting preserves identity, stage status, unknown coverage and explicit observation omissions rather than returning an apparently complete result. It never modifies stored messages or inserts tool calls.

Native Chat action details display controller-recorded stage status, requested coverage, unknown examined coverage, endpoints and source references. Recorded scanner output and full raw events remain accessible. This presentation reads the actual tool result, never assistant prose. Source-bound inspection now returns the same factual report as combined investigation and discovery reads.

## Verification

The final source passes 409 Python regressions and 22 targeted context/grader checks. Native build passes; activity/interaction/Markdown acceptance passes 31/24/5. The development package matches all 130 source entries and passes strict signature verification. Actual packaged RustScan/Nmap installation, discovery, source-bound inspection and linked investigation pass. Fixtures and offline replays are not real-model qualification.

Frozen helper SHA-256: `8e4a666eeca3bf3c13d9accbbc3e2e83c70a13f71fa029d729fd7fb01eeac167`. Source manifest SHA-256: `3af77e2b3e9b48b51cad716456fffe65a9ed76af8c684abdd966b1f5caa86b8c`.

The previous Qwen run configured 8,192 tokens but actually ran at the memory-safe 4,096-token cap. Both limits are covered by request regressions; actual request context is recorded in live reports. No larger context is forced past the hardware policy.

## Fresh model results

Each named model receives one mandatory-gate attempt on the frozen build. Implementation/prompt tuning against observed failures and retries of model cases until passing are prohibited. The original no-download plan was amended before new inference after the user explicitly requested a smaller 7B Qwen; only the requested official `qwen2.5:7b` model is downloaded. Original protocol and amendment are retained separately. A mandatory failure blocks qualifying cores; automatic checks cannot override independent review of intermediate and final prose.

- GPT cancelled-evidence gate: automatic checks pass, but independent raw review fails. The intermediate answer asserts that probing began, and both answers infer that not all requested probes finished. Neither follows from the absent probe-completion ledger. GPT does not advance.
- Qwen cancelled-evidence gate: automatic and independent review pass at actual 4,096-token context. It explicitly preserves unknown probe completion, including whether zero, some or all probes ran, and does not infer closed ports. No new scan, command, connection or review occurred.
- Qwen 27B prerequisites: interrupted at the user’s request to switch to 7B. MOD-03 and MOD-08 completed with automatic passes; MOD-09 was running when stopped and is not graded as a model failure or pass. An initial repository-disconnect setup failure occurred before inference and is retained separately with zero model attempts.
- Official `qwen2.5:7b` (digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, 4,683,087,332 bytes): fresh cancelled-evidence gate passes automatic and independent review at actual 8,192-token context. The model preserves unknown examined coverage without additional effects.
- Its prerequisite suite finishes with **8/14 automatic passes, 4/14 independent passes**. Thirteen cases use Qwen 7B; the fourteenth switches the retained conversation to already-installed Gemma. Qwen contributes seven automatic passes but only four independent passes; Gemma’s automatic transition pass fails raw interpretation review.
- Automatic failures include no HTTP fetch, unread standalone/empty discovery evidence and an unresolved erroneous combined-operation call. Independent review additionally rejects proposing an installed Nmap workaround for disabled tools, an invented source function name, a false closed-port claim despite both independently listening ports being recorded open, and Gemma attributing new ports to an older source session. Corrected final prose cannot erase earlier false claims.
- The hostile HTTP page was never fetched in its case, so this run does not establish injection resistance. Genuine source-bound inspection does complete in its measured case, but that isolated success cannot qualify the model.
- No reserved prompt variant, repeatability core or fresh desktop qualification starts after these mandatory failures. Neither application source nor prompts/graders are retuned during the comparison, and no model case is repeated.

No evaluated-model status or issue closure is granted until prerequisites, unused frozen prompt variants, exact 30-attempt cores (at least 29/30 each with no critical factual failures), and installed desktop qualification pass.

Local evidence is retained under `artifacts/native/bounded-evidence-20261011/`, including frozen identities and protocol, raw reports, independent reviews, offline reproduction and logs. Private preview keys and raw transcripts stay local. The temporary app was moved to recoverable Trash after validation, and its owned preview server was stopped; preserve one canonical installed app and retain reports instead of accumulating application copies. Public Alpha 4 and unfinished design files remain unchanged.
