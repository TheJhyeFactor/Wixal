# Wixal 0.7.10 Alpha 5 — Durable agent work

12 October 2026

Alpha 5 brings Hermes-inspired task progress, saved-evidence retrieval and richer skills into Wixal’s existing native SwiftUI app and Python engine. It is an Apple Silicon macOS 14+ alpha, ad-hoc signed and **not Developer ID signed or notarised**. Model weights download separately.

## What changed

- **Durable checklists:** revisioned task plans survive compaction and restarts, appear in live runs and prevent ordinary successful completion while steps remain unfinished. Completed checkboxes remain separate from independent verification.
- **Long-task continuation:** compact older complete tool rounds while retaining the task brief, controller feedback and recent call/result chains. Repeated summaries retain prior decisions and labelled tool evidence.
- **Saved evidence:** list and page through retained checkpoint results with `tool_result_read`, without repeating the original action.
- **Richer skills:** imported `SKILL.md` packages retain bounded supporting text snapshots. Paged loading, workspace identity, transfer checks and evaluation/rollback digests include those resources. Loading a script snapshot does not execute it.
- **Bounded delegation:** explicit child handoff context, restricted tools and limits on calls and execution time. Parent private instructions, notes and memory stay out of child context.
- **Keyword discovery:** search enabled tool names and descriptions and load up to eight matching schemas, within existing authority.
- **Recovery:** reject malformed call batches before any member executes and validate nested arguments. Successful use of an explicitly requested tool can resolve an earlier failed schema-discovery attempt.
- **Repair and source checks:** named-file repair requests retain eligible edit and command tools. `verify_json` independently sums numeric JSON arrays or CSV columns and rejects invalid sources before registering a check.

Read the [agent tools guide](agent-tools.md) for examples and the [pinned Hermes comparison](hermes-agent-improvements-2026-10-12.md) for implementation and attribution. Wixal keeps its storage, JSON-line IPC, local inference and action-review system.

## Validation and evidence identity

The implementation’s earlier installed development build passed 417 engine tests, 34 focused tests and five `gpt-oss:20b` cases. Its helper SHA-256 was `5be4a6118fc085b03b0693db8ec2f3b5e6471e6b672eb297e5498a6362f6d9a0`. A fresh helper recovered the same plan revision and checkpoint count without replay. A controlled native UI fixture at 920 × 640 showed checklist content/status labels and separate verification status. These dated observations retain that build identity.

Alpha 5 is packaged afresh with its own version and provenance. Release-specific results, package hashes, archive extraction and source-manifest verification are recorded in the attached `release-info.json` and `release-verification.json`. The release also includes `implementation-validation.json`, a sanitized copy of the earlier development summary. Earlier failed local trials remain retained; passing final cases do not establish reliability across all models.

Fresh Alpha 5 package checks:

| Check | Result |
| --- | --- |
| Full engine regression suite | 417 passed |
| Swift interaction / activity / Markdown | 24 / 29 / 5 passed |
| Native startup, including slow and failed database | 5/5 passed |
| Source manifest and strict deep signature | 129/129 source entries matched; signature passed |
| ZIP extraction and package identity | Passed; extracted hashes match the tested package |
| Fresh packaged `gpt-oss:20b` cases | 4/5 passed |
| Website | Build, link/consent checks and six desktop/mobile page cases passed |

The fresh model run passed skill snapshots, isolated delegation, keyword discovery and CSV source verification. In the durable-plan/evidence case, the model read the checklist checkpoint instead of the requested `read_file` checkpoint. Independent verification rejected the missing marker and retained `needs_attention`, even though the model checked off its plan. This is a retained qualification failure, not a passing evidence-retrieval acceptance. The earlier development 5/5 and this fresh package 4/5 are separate runs; neither establishes general model reliability.

## Known limits

This release does not establish full Hermes platform parity. Remote execution, messaging gateways, voice/media integration and broader model/provider qualification remain unfinished. Cybersecurity model qualification remains failed/incomplete; inspect retained evidence and use independent criteria for important tasks.

Production managed-tool downloads still require a qualified signed catalogue and independent signing custody. Contributor GitHub Device Flow needs a registered client ID. Actual sleep/wake/reboot, real two-Mac sync, broader hardware/OS and provider/account lifecycle coverage, full accessibility acceptance and automatic updates remain open. The macOS minimum is a deployment target, not a full OS-matrix pass.

## Install or update

Download `Wixal-0.7.10-alpha.5-macOS-arm64.zip`, verify it against `SHA256SUMS.txt`, extract it and replace Wixal.app in Applications after quitting the previous app. Existing workspace data and models are retained. Updates are manual. Retire obsolete preview/test app copies after verifying launch and data retention. See the [native alpha guide](native-alpha.md).
