# Evidence-driven investigation qualification — 11 October 2026

This follow-up addresses issue #6 through execution structure and independent evidence. It does not transfer earlier results or grant general cybersecurity reliability.

## Implementation

`network_scan` accepts `discover_first: true` for a requested discovery-to-inspection task. The controller dispatches the existing native discovery adapter, waits for finalized evidence, and passes its exact owned session reference into the existing inspection adapter. Each action retains normal target authority, off switches and review. The operation shares a deadline and does not hand off stopped, failed, partial, malformed or changed discovery. Empty discovery explicitly skips inspection.

Actual child-stage receipts are saved under the outer checkpoint's `controllerStages`, with `origin: controller_stage`. They are distinct from model tool calls. Readers and outcome checks use these receipts without inserting artificial model calls or rewriting history. A repeated identical combined operation in the same task is refused once a stage has started; retained source evidence supports explicit continuation instead of silently restarting discovery. Declined review ends tool execution.

Network results include a controller-generated `evidenceReport` separating requested coverage, unknown examined coverage, observed endpoints, stage state and source identity. It never infers probe completion, vulnerability or safety. The model's own prose remains subject to qualification; a truthful controller report cannot rescue a false model claim.

## Independent checks

Two new controller tests execute real RustScan and Nmap against owned loopback services. They check saved XML, hashes, listener facts, durable stage receipts, review refusal, disabled discovery, empty-result skipping, stopped discovery and duplicate-operation refusal. These are adapter/controller checks, not model qualification.

The qualification reader now checks saved Nmap XML bytes and digests against structured services and the independent listener oracle. Core attempts retain individual connection ledgers, reviews and raw sessions. Independent review also examines rejected model prose, so controller correction cannot erase an unsupported claim. Three new grader regressions fail on the prior reviewer and pass on the updated reviewer: changed XML, missing per-attempt listener evidence and rejected model claims hidden by correction. These are explicitly controlled grader fixtures, not live model results.

The frozen source passes 402 Python regressions. The packaged backend passes signed installation, actual discovery, source-bound inspection and linked investigation. The development package matches all 128 source entries and passes strict signature verification. Its helper SHA-256 is `ca0a281a3cd55921caf8ece6b9e58d2dc7921982709213c68f600683d019cfbf`; source manifest SHA-256 is `e6a3c3f772045254b1dccaf088161cdd249ec2267fc90f19bea13b92fc516219`.

## Bounded qualification protocol

One frozen implementation and grader are used. Each mandatory model gate runs once per named installed model; an environmental setup failure before inference is retained separately. A mandatory failure blocks that model's qualifying cores. No package or prompt is retuned against a failed gate. Qualifying cores require exactly 30 retained attempts per scenario, at least 29 successes in each, and no critical factual/policy failures. Cancelled evidence, prerequisites, unused prompt variants and installed desktop transitions remain separate mandatory gates.

The first setup attempt was correctly blocked because the local preview catalogue approved the previous application version. No model attempt occurred. A separate preview repository retains the original root and binary bytes, updates signed Alpha 4 compatibility metadata after real controller checks, and leaves the historical repository unchanged. This remains a single-operator local preview, with no production catalogue or evaluated-model claim.

The temporary validation app lives outside Applications. The canonical public Alpha 4 app and user workspace are retained. Unregister and retire the temporary validation bundle when qualification settles; keep reports and identities rather than accumulating installed copies.

Final model outcomes are pending. Issue #6 remains open until every required gate passes on the exact tested configuration.
